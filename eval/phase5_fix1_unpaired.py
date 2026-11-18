# ruff: noqa: E501
"""Why the Gemma 4 E4B deadline answers that are shown after fix 1 do not pair with a label item.

    uv run python -m eval.phase5_fix1_unpaired    # writes eval/reports/phase5_fix1_unpaired_deadlines.md

Reads the saved trace (no model, no network), replays it through the current llm.py exactly as
eval.phase5_fix1_replay does, pairs the answer items with the label items as
eval.silver.compare.item_pairs does (greedy, agree.item_same), and classifies every answer item
left unpaired. Nothing is changed or scored differently. Dev only. The report holds item ids
(doc prefix, cited sentence ids, kind) and counts, no document text.
"""

import json
import sys
from pathlib import Path

from shiori_core.extract import llm

from eval.documents import load_sentences
from eval.phase5_fix1_replay import after_outputs
from eval.run import label_dirs, read_labels
from eval.silver import run as silver_run
from eval.silver.agree import ACTIVE, item_same, overlap

OUT = Path("eval/reports/phase5_fix1_unpaired_deadlines.md")
MARKS = ("必着", "消印", "郵送", "電子", "開札", "質問", "到着", "説明会")
CAUSES = [
    (
        "duplicate",
        "same item as an answer item that already paired (the label item is used up)",
    ),
    ("kind", "only the kind differs from a label item on a shared sentence"),
    ("flags", "only the flags differ"),
    ("date", "only the datetime differs"),
    ("several", "two or more of kind, datetime, flags differ"),
    ("no_label_on_sentence", "no label item cites any sentence this answer cites"),
]


SUMMARY = """"""


def ident(doc: str, it: dict) -> str:
    return f"{doc[:8]}:{'+'.join(it['citations'])}:{it['kind']}"


def label_date_in_sentence(g: dict, by_id: dict) -> bool | None:
    """Does the label's own datetime appear (date, and time when it has one) in the sentences
    it cites? None when it has no datetime."""
    when = g.get("datetime")
    if not when:
        return None
    for i in g.get("citations", []):
        s = by_id.get(i)
        if s is None:
            continue
        for sp in llm.spans_of(s.text_norm):
            if sp.date == when[:10] and (len(when) == 10 or when[11:16] in sp.times):
                return True
    return False


def main() -> int:
    dirs = label_dirs("dev")
    trace = json.loads(Path("data/cache/hybrid/trace_cmp_gemma4_e4b.json").read_text())
    calls = {(d, s["field"]): s for d, s in trace}
    docs = {d for d, _ in trace}
    rows = [r for r in silver_run.select("dev", doc_ids=None) if r.doc_id[:12] in docs]
    sents = {
        r.doc_id: [s for s in load_sentences(r) if s.language == "ja"] for r in rows
    }
    outs, _, _ = after_outputs(calls, rows, sents)

    unpaired: list[dict] = []
    total = paired_n = 0
    for r in rows:
        gold = (read_labels(r.doc_id, dirs) or {}).get("deadlines")
        if gold is None:
            continue
        mine = (outs.get(r.doc_id, {}).get("deadlines").normalized or {}).get("items", []) if outs.get(r.doc_id, {}).get("deadlines") else []  # fmt: skip
        labels = (gold.get("normalized") or {}).get("items", [])
        by_id = {s.id: s for s in sents[r.doc_id]}
        free = list(labels)
        taken: list[tuple[dict, dict]] = []  # (answer, label) pairs
        for it in mine:
            total += 1
            hit = next((g for g in free if item_same("deadlines", it, g, ACTIVE)), None)
            if hit is not None:
                free.remove(hit)
                taken.append((it, hit))
                paired_n += 1
                continue
            row = {"id": ident(r.doc_id, it), "doc": r.doc_id[:8], "it": it}
            used_same = next(
                (t for t in taken if item_same("deadlines", it, t[1], ACTIVE)), None
            )
            near = [
                g for g in labels if overlap(it["citations"], g.get("citations", []))
            ]
            if used_same:
                row["cause"], row["detail"] = "duplicate", ident(r.doc_id, used_same[0])
            elif not near:
                row["cause"], row["detail"] = "no_label_on_sentence", ""
            else:
                # best partner: most of kind, datetime, flags equal; prefer a label still free
                def diff(g: dict, it: dict = it) -> list[str]:
                    d = [k for k in ("kind", "datetime") if it.get(k) != g.get(k)]
                    return d + (["flags"] if set(it.get("flags", [])) != set(g.get("flags", [])) else [])  # fmt: skip

                g = min(near, key=lambda g: (len(diff(g)), g not in free))
                d = diff(g)
                row["cause"] = (
                    {"datetime": "date"}.get(d[0], d[0]) if len(d) == 1 else "several"
                )
                row["detail"] = (
                    f"{'+'.join(d) or 'none'}; answer {it['kind']} / label {g['kind']}"
                )
                if "datetime" in d:
                    a, b = it.get("datetime") or "", g.get("datetime") or ""
                    row["detail"] += f"; {'time only' if a[:10] == b[:10] else 'date'}"
                row["label_date_ok"] = label_date_in_sentence(g, by_id)
                row["label_used"] = g not in free
                row["label_flags"] = sorted(g.get("flags", []))
                row["answer_flags"] = sorted(it.get("flags", []))
            cited = [by_id[i] for i in it["citations"]]
            text = "".join(c.text_norm for c in cited)
            order = [x.id for x in sents[r.doc_id]]
            nxt = [by_id[order[order.index(i) + 1]].text_norm for i in it["citations"] if order.index(i) + 1 < len(order)]  # fmt: skip
            row["marks"] = [m for m in MARKS if m in text]
            row["marks_next"] = [m for m in MARKS if any(m in n for n in nxt)]
            row["same_datetime_label"] = sorted({"+".join(g.get("citations", [])) + ":" + g["kind"] for g in labels if g.get("datetime") and g["datetime"][:10] == (it.get("datetime") or "")[:10]})  # fmt: skip
            when = it.get("datetime") or ""
            own = [sp for c in cited for sp in llm.spans_of(c.text_norm) if sp.date == when[:10] and (len(when) == 10 or when[11:16] in sp.times)]  # fmt: skip
            row["own_marks"] = sorted({m for sp in own for m in MARKS if m in sp.text})
            row["tail_marks"] = [m for m in ("必着", "消印") if any(m in c.text_norm[max((sp.end for sp in llm.spans_of(c.text_norm)), default=0) :] for c in cited)]  # fmt: skip
            if row["cause"] in ("kind", "flags", "several"):
                lab = [
                    by_id[i]
                    for gg in near
                    for i in gg.get("citations", [])
                    if i in by_id
                ]
                row["label_marks"] = sorted(
                    {m for c in lab for m in MARKS if m in c.text_norm}
                )
                row["label_only_ids"] = sorted({i for gg in near for i in gg.get("citations", [])} - set(it["citations"]))  # fmt: skip
            unpaired.append(row)

    counts = {c: [x for x in unpaired if x["cause"] == c] for c, _ in CAUSES}
    L = [
        "# Phase 5 fix 1: why 21 Gemma 4 E4B deadline answers do not pair", "",
        "Saved trace `data/cache/hybrid/trace_cmp_gemma4_e4b.json` replayed through the current `llm.py` (no model, no network, nothing changed), paired with the dev labels exactly as `eval.silver.compare.item_pairs` does (greedy, `agree.item_same`: kind, datetime, relative_text, flags and a shared cited sentence all equal). Dev only, 14 documents, model-reviewed silver labels (D-41), so \"the label looks wrong\" is only what code can see, not a Japanese reading. Item ids are `doc8:cited sentence ids:kind`; no document text.", "",
        f"Answer items {total}, paired {paired_n}, unpaired {len(unpaired)}.", "",
        "## Counts per cause (first match in this order)", "", "| cause | meaning | items |", "| --- | --- | --- |",
    ]  # fmt: skip
    for c, m in CAUSES:
        L.append(f"| {c} | {m} | {len(counts[c])} |")
    L += ["", "## Items", ""]
    for c, _ in CAUSES:
        if counts[c]:
            L += [f"### {c} ({len(counts[c])})", ""]
            L += [f"- `{x['id']}` {x['detail']}; wording markers in the cited sentence {x['marks']}, in the next sentence {x['marks_next']}; labels with the same date (cited ids:kind) {x['same_datetime_label']}; markers inside the answer's own date span {x['own_marks']}, 必着/消印 after the last date span {x['tail_marks']}" + ("" if "label_marks" not in x else f"; markers in the label's cited sentences {x['label_marks']}, sentences only the label cites {x['label_only_ids']}") + ("" if "label_used" not in x else f"; label already paired by another answer: {'yes' if x['label_used'] else 'no'}; label datetime found in its own cited sentence: {x['label_date_ok']}; answer flags {x['answer_flags']}, label flags {x['label_flags']}") for x in counts[c]]  # fmt: skip
            L.append("")
    L += SUMMARY
    OUT.write_text("\n".join(L))
    print(
        f"wrote {OUT}: {total} answer items, {paired_n} paired, {len(unpaired)} unpaired"
    )
    for c, _ in CAUSES:
        print(c, len(counts[c]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
