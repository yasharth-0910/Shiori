# ruff: noqa: E501
"""Replay of the saved list-field traces for fix 3 (eligibility proviso merge, 第73条 kind other, D-71).

    uv run python -m eval.phase5_fix3_replay    # writes eval/reports/phase5_fix3_eligibility_proviso.md

No model is started and nothing is sent anywhere. Input: `data/cache/hybrid/trace_cmp_<name>.json`.
Both sides feed the saved proposals through the current `llm.extract_lists` with a fake model;
"before" turns the two fix-3 functions off (`_merge_provisos`, `_kind`), "after" leaves them on, so
only fix 3 differs (fixes 1 and 2 are on in both). Scorer unchanged (eval.run). Dev only. The
report holds counts and ids, no document text.
"""

import json
import sys
from pathlib import Path

from shiori_core.extract import llm

from eval.documents import load_sentences
from eval.phase5_fix1_replay import after_outputs, before_outputs, score
from eval.run import label_dirs
from eval.silver import run as silver_run

OUT = Path("eval/reports/phase5_fix3_eligibility_proviso.md")
NAMES = ["qwen35_9b", "qwen35_4b", "gemma4_e4b", "qwen3_swallow_8b", "lfm25_12b_jp", "lfm25_8b_a1b", "nemotron_nano_9b_jp", "sarashina22_3b"]  # fmt: skip


def eligibility_items(outs: dict) -> set[str]:
    """doc8:cited ids:kind, one per answer item."""
    return {
        f"{doc[:8]}:{'+'.join(it['citations'])}:{it['kind']}"
        for doc, fields in outs.items()
        if "eligibility" in fields
        for it in fields["eligibility"].normalized["items"]
    }


def main() -> int:
    dirs = label_dirs("dev")
    allrows = silver_run.select("dev", doc_ids=None)
    L = [
        "# Phase 5 fix 3: eligibility proviso merge and 第73条 kind",
        "",
        'Replay of the saved list-field traces (`data/cache/hybrid/trace_cmp_<model>.json`, one per model) through the current `core/shiori_core/extract/llm.py`. No model was started, no cloud call, no label, scorer, prompt, retrieval, deadlines code or `EXTRACTOR_VERSION` change; dev only (model-reviewed silver labels, D-41). Both columns replay the same saved proposals with fixes 1 and 2 on; "before" switches off only the two fix-3 functions, so the difference is fix 3 alone. The models\' proposals are old saved answers, so this shows what the code change does to them, not what a new run would give. Every number is a fit to documents the prompts were tuned on.',
        "",
        "- Change 1 (`_merge_provisos`): a sentence that starts with なお or ただし right after an eligibility item's last cited sentence is added to that item (text_ja joined with a line break, id added to citations). An item that cites only such a sentence is dropped (trace verdict `merged`). With no item before it the sentence stays as it was.",
        "- Change 2 (`_kind`, D-71): an item whose text_ja starts with 予算決算及び会計令第73条 and holds 支出負担行為担当官が定める資格 gets kind other.",
        "",
        "Rows: the saved traces cover 13 of the 14 labeled dev documents (5d75d4a67c71 was labeled after those runs). For Qwen3.5-9B, Gemma 4 E4B and Qwen3-Swallow-8B, 5d75d4a67c71 was run live twice (temperature 0, fix 3 off and on), so those three have 42 rows. The other five models have no usable GGUF in `models/`, so they stay at 39 rows (13 documents).",
        "",
        "Item ids below are `doc8:cited ids:kind`; no document text.",
        "",
    ]
    for name in NAMES:
        tp = Path(f"data/cache/hybrid/trace_cmp_{name}.json")
        if not tp.exists():
            L += [f"## {name}", "", "No saved trace.", ""]
            continue
        trace = json.loads(tp.read_text())
        calls = {(d, s["field"]): s for d, s in trace}
        docs = {d for d, _ in trace}
        rows = [r for r in allrows if r.doc_id[:12] in docs]
        sents = {r.doc_id: [s for s in load_sentences(r) if s.language == "ja"] for r in rows}  # fmt: skip
        keep_merge, keep_kind = llm._merge_provisos, llm._kind
        llm._merge_provisos = lambda kept, by_id, stat: kept  # type: ignore[assignment]
        llm._kind = lambda it: it["kind"]  # type: ignore[assignment]
        try:
            bout, _, _ = after_outputs(calls, rows, sents)
        finally:
            llm._merge_provisos, llm._kind = keep_merge, keep_kind
        aout, stats, _ = after_outputs(calls, rows, sents)
        extra = ""
        t5 = {
            k: Path(f"data/cache/hybrid/trace_cmp5d{k}_{name}.json")
            for k in ("before", "")
        }
        if all(t.exists() for t in t5.values()):
            # 14th document: a real run each way (fix 3 off, fix 3 on); its kept items are the answers
            r14 = [r for r in allrows if r.doc_id.startswith("5d75d4a6")]
            s14 = {
                r.doc_id: [x for x in load_sentences(r) if x.language == "ja"]
                for r in r14
            }
            tr = {k: json.loads(t.read_text()) for k, t in t5.items()}
            cl = {k: {(d, x["field"]): x for d, x in v} for k, v in tr.items()}
            bout |= before_outputs(cl["before"], r14, s14)
            aout |= before_outputs(cl[""], r14, s14)
            rows, sents = rows + r14, sents | s14
            e = [x for _, x in tr[""] if x["field"] == "eligibility"]
            extra = f" Includes 5d75d4a6 from a real run each way (`trace_cmp5dbefore_{name}.json`, `trace_cmp5d_{name}.json`): provisos merged {sum(x.get('merged', 0) for x in e)}, kind other set {sum(x.get('kind_set', 0) for x in e)}."

        b, a = score(rows, dirs, bout, sents), score(rows, dirs, aout, sents)
        flipped = [k for k, v in a["keys"].items() if v != b["keys"][k]]
        bi, ai = eligibility_items(bout), eligibility_items(aout)
        el = [(d, s) for d, s in stats if s.field == "eligibility"]
        (p0, g0, n0), (p1, g1, n1) = (
            b["items"]["eligibility"],
            a["items"]["eligibility"],
        )
        L += [
            f"## {name}",
            "",
            f"Documents: {len(rows)}; list-field rows scored: {b['rows']} (eligibility {b['by_field']['eligibility'][1]}).{extra}",
            "",
            "| count | before | after |",
            "| --- | --- | --- |",
            f"| all list-field rows right | {b['right']} of {b['rows']} | {a['right']} of {a['rows']} |",
            f"| all list-field rows wrong value shown | {b['wrong']} | {a['wrong']} |",
            f"| all list-field rows not found | {b['notfound']} | {a['notfound']} |",
            f"| eligibility rows right | {b['by_field']['eligibility'][0]} of {b['by_field']['eligibility'][1]} | {a['by_field']['eligibility'][0]} of {a['by_field']['eligibility'][1]} |",
            f"| eligibility items: paired / label items / answer items | {p0} / {g0} / {n0} | {p1} / {g1} / {n1} |",
            "",
            f"Provisos merged: {sum(s.merged for _, s in el)} (documents {', '.join(sorted({d for d, s in el if s.merged})) or 'none'}). Items set to kind other by the 第73条 rule: {sum(s.kind_set for _, s in el)} (documents {', '.join(sorted({d for d, s in el if s.kind_set})) or 'none'}). Rows whose right/wrong state changed: {len(flipped)}{' (' + ', '.join(f'{d[:8]}/{f}' for d, f in flipped) + ')' if flipped else ''}.",
            "",
            "Eligibility answer items that changed:",
            "",
            "| before only | after only |",
            "| --- | --- |",
            f"| {'<br>'.join(sorted(bi - ai)) or 'none'} | {'<br>'.join(sorted(ai - bi)) or 'none'} |",
            "",
        ]
    L += ["## What I saw", "", "Counts above come from this run of `uv run python -m eval.phase5_fix3_replay`. Why a changed item does or does not pair with its label item was not looked into beyond the counts.", ""]  # fmt: skip
    OUT.write_text("\n".join(L))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
