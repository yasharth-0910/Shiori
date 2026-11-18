# ruff: noqa: E501
"""eval/reports/phase5_fix4_deadline_dupes.md: deadline rows before and after the same-sentence
copy drop (D-72), replayed on the saved traces in data/cache/hybrid/. No model, no cloud call,
no scorer. Reads the kept items of each deadlines call and the cached sentences of its document.
The report holds ids, kinds, datetimes and counts only, no document text.

    uv run python -m eval.deadline_dupes_report
"""

import json
from pathlib import Path

from shiori_core.extract import llm
from shiori_core.models import Sentence

TRACES = Path("data/cache/hybrid")
OUT = Path("eval/reports/phase5_fix4_deadline_dupes.md")
SETS = [
    "cmp_*",
    "cmp5d_*",
]  # the 8-model dev comparison, then the 3-model run on 5d75d4a67c71


def sentences_of(doc: str) -> dict[str, Sentence]:
    (f,) = Path("data/processed").glob(f"{doc}*/sentences.json")
    return {s["id"]: Sentence.model_validate(s) for s in json.loads(f.read_text())["sentences"]}  # fmt: skip


def replay(trace: Path) -> tuple[int, int, list[str]]:
    before = after = 0
    gone: list[str] = []
    for doc, s in json.loads(trace.read_text()):
        if s["field"] != "deadlines":
            continue
        stat = llm.CallStat("deadlines", trace=[(t[0], t[1]) for t in s["trace"]])
        kept = [it for it, v in stat.trace if v == "kept"]
        left = llm._drop_same_sentence_copies(kept, sentences_of(doc), stat)
        before, after = before + len(kept), after + len(left)
        gone += [f"{doc[:12]} {'+'.join(it['citations'])} {it['kind']} {it['datetime']}" for it in kept if it not in left]  # fmt: skip
    return before, after, gone


def main() -> None:
    L = ["# Fix 4: same-datetime, same-sentence deadline copies (D-72)", "",
         "Replay of `llm._drop_same_sentence_copies` on the kept deadline items of each saved trace in `data/cache/hybrid/`. No model run, no scorer, so these are item counts, not verified-accuracy scores. Rows are deadline items kept by the old code (before) and by the old code plus the new drop (after). `cmp` is the dev comparison (13 documents with deadline calls per model), `cmp5d` is the 3-model run on `5d75d4a67c71` only. The traces predate the change, so the new code is applied to their kept items; everything else in them is unchanged.", "",
         "| trace | model | deadline rows before | after | dropped |", "| --- | --- | --- | --- | --- |"]  # fmt: skip
    detail: list[str] = []
    for pat in SETS:
        for t in sorted(TRACES.glob(f"trace_{pat}.json")):
            b, a, gone = replay(t)
            name = t.stem.removeprefix("trace_")
            L.append(
                f"| {name.split('_')[0]} | {name.split('_', 1)[1]} | {b} | {a} | {b - a} |"
            )
            detail += [f"- {name}: {g}" for g in gone]
    L += [
        "",
        "## Dropped rows (doc prefix, sentence ids, kind, datetime)",
        "",
        *(detail or ["none"]),
        "",
    ]
    OUT.write_text("\n".join(L))
    print("\n".join(L[:20]))


if __name__ == "__main__":
    main()
