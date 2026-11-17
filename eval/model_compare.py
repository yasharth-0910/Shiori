# ruff: noqa: E501
"""Model comparison on the three list fields: reads finished `eval.run --extractor hybrid`
runs (run_cmp_<name>.json, data/cache/hybrid/trace_cmp_<name>.json, the diagnostic) and
writes eval/reports/model_compare_list_fields.md. No model, no network, no document text.

    uv run python -m eval.model_compare            # every model in MODELS that has a run
"""

import json
import re
from pathlib import Path

from shiori_core.extract.llm import LIST_FIELDS

from eval.run import REPORTS, cell, tally

TIMES = Path("data/cache/compare")  # <name>.time = wall seconds, <name>.log = run log
TRACES = Path("data/cache/hybrid")
MODELS = [  # (run name, gguf file)
    ("qwen35_9b", "Qwen3.5-9B-Q4_K_M.gguf"),
    ("qwen3_swallow_8b", "Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf"),
    ("nemotron_nano_9b_jp", "NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf"),
    ("lfm25_8b_a1b", "LFM2.5-8B-A1B-Q4_K_M.gguf"),
    ("qwen35_4b_ollama", "qwen3.5-4b-ollama.gguf"),
    ("gemma4_e4b_ollama", "gemma4-e4b-ollama.gguf"),
    ("sarashina22_3b", "sarashina2.2-3b-instruct-v0.1-Q4_K_M.gguf"),
    ("lfm25_12b_jp", "LFM2.5-1.2B-JP-202606-Q4_K_M.gguf"),
    ("qwen35_4b", "Qwen3.5-4B-Q4_K_M.gguf"),  # unsloth builds, D-70
    ("gemma4_e4b", "gemma-4-E4B-it-Q4_K_M.gguf"),
]
KEYS = ["verified_accuracy", "value_accuracy", "not_found", "wrong_shown", "hallucination", "citation_exists", "value_in_citation"]  # fmt: skip


def diag_counts(name: str) -> list[str]:
    """The `all` row of the diagnostic: label items, hit, a, b, c, d, extra answer items."""
    t = (REPORTS / f"hybrid_diagnostic_cmp_{name}.md").read_text()
    m = re.search(r"^\| all \| (.+) \|$", t, re.M)
    return [x.strip() for x in m.group(1).split("|")] if m else ["?"] * 7


def row(name: str, gguf: str) -> str:
    j = REPORTS / f"run_cmp_{name}.json"
    if not j.exists():
        return f"| `{gguf}` | no result (see failures below) |" + " |" * 12
    rep = json.loads(j.read_text())
    recs = [r for r in rep["records"] if r["field"] in LIST_FIELDS]
    t = tally(recs)
    stats = [s for _, s in json.loads((TRACES / f"trace_cmp_{name}.json").read_text())]
    calls = [s for s in stats if s["sentences_sent"]]
    failed = sum(bool(s["call_failed"]) for s in calls)
    docs = max(len(rep["documents"]), 1)
    secs = sum(s["seconds"] for s in stats) / docs
    wall = (TIMES / f"{name}.time").read_text().strip() if (TIMES / f"{name}.time").exists() else "?"
    d = diag_counts(name)
    cells = [cell(*t[k]) for k in KEYS]
    return f"| `{gguf}` | {len(recs)} | " + " | ".join(cells) + f" | {secs:.0f} | not recorded | {failed} of {len(calls)} | {d[1]} / {d[2]} / {d[3]} / {d[4]} / {d[5]} | {wall} |"  # fmt: skip


def main() -> int:
    head = ["model", "list fields scored", "verified accuracy", "value accuracy", "not found", "wrong value shown", "hallucination", "citation exists", "value in citation", "model s/doc", "tok/s", "calls failed after retry", "diagnostic hit / a / b / c / d", "run wall s"]  # fmt: skip
    L = [
        "# Local models on the three list fields (dev split)", "",
        "Same hybrid extractor for every model: same retrieval, prompts, thresholds and schema, `EXTRACTOR_VERSION` 0.3.0, temperature 0, one llama-server on 127.0.0.1:8792 at a time. Only the GGUF changes (`eval.run --model`). Every number below is from a run executed for this table (`eval/reports/run_cmp_*.json`, `hybrid_cmp_*.md`, `hybrid_diagnostic_cmp_*.md`). The earlier Qwen3.5-9B v3 numbers were not reused: `rules.py` and `eval/hybrid.py` differ from the v3 freeze, so that model was rerun.", "",
        "**Read with care.** Scores are against model-reviewed dev silver labels (D-41), 14 documents, notices only (specs have no list fields). Small n: a few fields move a rate by several points. Qwen3.5-9B was one of the labelers behind those labels and the prompts were tuned on these documents with it, so it is favored. This is a fit on dev, not a forecast.", "",
        "Scored fields: eligibility, deadlines, required_documents, one row per (document, field) with a label. Rates as `eval.run.tally`; `wrong value shown` = shown but wrong, or label absent. tok/s is not recorded by the harness (CallStat has seconds only). `model s/doc` = sum of model-call seconds over documents. Diagnostic columns count label items (hit, a not in window, b not produced, c dropped by a check, d wrong value or kind), summed over the three fields.", "",
        "| " + " | ".join(head) + " |", "|" + " --- |" * len(head),
    ]  # fmt: skip
    L += [row(n, g) for n, g in MODELS if (REPORTS / f"run_cmp_{n}.json").exists() or (TIMES / f"{n}.time").exists()]  # fmt: skip
    fails = [f"- `{g}`: no result. llama-server exited while loading (RuntimeError in the run, exit 1, 1 to 2 s, no request sent). The same load failure is in `model_loadcheck.md`: for the qwen3.5-4b file the loader rejects `qwen35.rope.dimension_sections` (wrong array length), for the gemma4 file it says `failed to load model` with no further detail in that report. Not retried, not swapped." for n, g in MODELS if n.endswith("_ollama") and (TIMES / f"{n}.time").exists() and not (REPORTS / f"run_cmp_{n}.json").exists()]  # fmt: skip
    for n, g in MODELS:  # models that ran but whose calls failed: error types only, no text
        tf = TRACES / f"trace_cmp_{n}.json"
        if tf.exists():
            kinds: dict[str, int] = {}
            for _, st in json.loads(tf.read_text()):
                if st["call_failed"]:
                    kinds[st["call_failed"]] = kinds.get(st["call_failed"], 0) + 1
            if kinds:
                fails.append(f"- `{g}` ran, calls failed after the retry (error type: count): " + ", ".join(f"{k} {v}" for k, v in kinds.items()) + ". Not found is the recorded result for those fields. Cause not investigated.")
    L += ["", "## Failures", ""] + (fails or ["- none."]) + [""]
    (REPORTS / "model_compare_list_fields.md").write_text("\n".join(L))
    print(f"wrote {REPORTS / 'model_compare_list_fields.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
