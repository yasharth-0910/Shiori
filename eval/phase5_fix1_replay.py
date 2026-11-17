# ruff: noqa: E501
"""Replay of the saved list-field traces through the current llm.py checks (Phase 5, fix 1).

    uv run python -m eval.phase5_fix1_replay    # writes eval/reports/phase5_fix1_changelog.md

No model is started and nothing is sent anywhere. Input: `data/cache/hybrid/trace_cmp_<name>.json`
(the items each model proposed, with its verdicts, from the saved comparison run). "Before" is the
items the old code kept; "after" feeds every proposed item back through `llm.extract_lists` with
a fake model that returns them, so the new date recovery and polarity rule run on the same answers.
The scorer is eval.run / eval.silver.compare, unchanged. Dev only. The report holds counts and ids,
no document text.
"""

import json
import sys
from pathlib import Path

from shiori_core.extract import llm
from shiori_core.extract.rules import Extracted
from shiori_core.fields import validate_normalized

from eval import hybrid
from eval.documents import load_sentences
from eval.run import evaluate, label_dirs
from eval.silver import run as silver_run
from eval.silver.model import Candidate

MODELS = {"qwen35_9b": "Qwen3.5-9B", "gemma4_e4b": "Gemma 4 E4B"}
OUT = Path("eval/reports/phase5_fix1_changelog.md")


def before_outputs(calls: dict[tuple[str, str], dict], rows: list, sents: dict) -> dict:
    """The old code's answer: the items it kept, built the way extract_lists builds them."""
    out: dict[str, dict[str, Candidate]] = {}
    for r in rows:
        by_id = {s.id: s for s in sents[r.doc_id]}
        for f in llm.LIST_FIELDS:
            c = calls.get((r.doc_id[:12], f))
            items = [it for it, v in (c["trace"] if c else []) if v == "kept"]
            if not items:
                continue
            validate_normalized(f, {"items": items})
            ids = list(dict.fromkeys(i for it in items for i in it["citations"]))
            x = Extracted(field=f, value_ja=llm._value_ja(f, items, by_id), normalized={"items": items}, citations=ids)  # fmt: skip
            out.setdefault(r.doc_id, {})[f] = Candidate(f, x.status, x.value_ja, None, x.normalized, x.citations)  # fmt: skip
    return out


def after_outputs(
    calls: dict, rows: list, sents: dict
) -> tuple[dict, list[tuple[str, llm.CallStat]], int]:
    """The new code's answer on the same proposals; also the number of calls whose retrieved ids
    differ from the saved ones (the proposals would then not match the window)."""
    out: dict[str, dict[str, Candidate]] = {}
    stats: list[tuple[str, llm.CallStat]] = []
    moved = 0
    for r in rows:

        def complete(
            system: str, user: str, schema: dict, max_out: int, doc: str = r.doc_id[:12]
        ) -> str:
            f = user.split("Field: ")[1].split("\n")[0]
            items = [it for it, _ in calls[(doc, f)]["trace"]]
            return json.dumps({"items": items}, ensure_ascii=False)

        st: list[llm.CallStat] = []
        found = llm.extract_lists(r.doc_type, sents[r.doc_id], complete, st)
        for s in st:
            c = calls.get((r.doc_id[:12], s.field))
            if c and c["retrieved"] != s.retrieved:
                moved += 1
        stats += [(r.doc_id[:8], s) for s in st if (r.doc_id[:12], s.field) in calls]
        out[r.doc_id] = {f: Candidate(f, x.status, x.value_ja, None, x.normalized, x.citations) for f, x in found.items()}  # fmt: skip
    return out, stats, moved


def score(rows: list, dirs: list[Path], outs: dict, sents: dict) -> dict:
    recs, _ = evaluate(rows, dirs, lambda row, ss: outs.get(row.doc_id, {}), lambda row: sents[row.doc_id])  # fmt: skip
    recs = [x for x in recs if x["field"] in llm.LIST_FIELDS]
    items = hybrid.item_totals(rows, dirs, outs)
    return {
        "rows": len(recs),
        "right": sum(x["value_ok"] for x in recs),
        "wrong": sum(x["pred"] == "present" and not x["value_ok"] for x in recs),
        "notfound": sum(x["pred"] == "absent" and not x["value_ok"] for x in recs),
        "items": {f: items[f] for f in llm.LIST_FIELDS},
        "by_field": {
            f: [
                sum(x["value_ok"] for x in recs if x["field"] == f),
                sum(x["field"] == f for x in recs),
            ]
            for f in llm.LIST_FIELDS
        },  # fmt: skip
        "keys": {(x["doc"], x["field"]): x["value_ok"] for x in recs},
    }


def main() -> int:
    dirs = label_dirs("dev")
    allrows = silver_run.select("dev", doc_ids=None)
    L = [
        "# Phase 5 fix 1: deadline date recovery and eligibility polarity",
        "",
        "Replay of the saved Qwen3.5-9B and Gemma 4 E4B traces (`data/cache/hybrid/trace_cmp_*.json`) through the current `core/shiori_core/extract/llm.py`. No model was started, no cloud call, no label, scorer, prompt, retrieval or `EXTRACTOR_VERSION` change; dev only (14 documents, model-reviewed silver labels, D-41). The proposals are the models' saved answers, so this shows what the two code changes do to the same answers, not what a new run would give. Both models were tuned or labeled on these documents, so every number is a fit.",
        "",
        "- Fix A (`_recover_date`, `_recovered`): a deadline with `kind` and `citations` but no `datetime` and no `relative_text` gets its date from the cited sentences (`spans_of`, i.e. `value_normalize.find_dates`/`find_times`) when they give exactly one distinct date for that kind (mail spans for `mail_arrival`, the others for any other kind). The result still goes through the old `_check` (date and time must be in the cited sentence). Two dates or none: dropped as `schema`, as before.",
        "- Fix B (`_polarity`): an eligibility item whose `text_ja` keeps its negation (…ないこと, …でないこと, …ない者であること) is a requirement (docs/labeling_guide.md). The other half of the guide rule (negation stripped means disqualification) is not applied: a text without a negation is often a plain requirement, so the model's polarity stays.",
        "",
    ]
    for name, label in MODELS.items():
        trace = json.loads(Path(f"data/cache/hybrid/trace_cmp_{name}.json").read_text())
        calls = {(d, s["field"]): s for d, s in trace}
        docs = {d for d, _ in trace}
        rows = [r for r in allrows if r.doc_id[:12] in docs]
        sents = {
            r.doc_id: [s for s in load_sentences(r) if s.language == "ja"] for r in rows
        }
        saved = json.loads(Path(f"eval/reports/run_cmp_{name}.json").read_text())[
            "records"
        ]
        b = score(rows, dirs, before_outputs(calls, rows, sents), sents)
        aout, stats, moved = after_outputs(calls, rows, sents)
        a = score(rows, dirs, aout, sents)
        ref = [x for x in saved if x["field"] in llm.LIST_FIELDS]
        ref_ok = (len(ref), sum(x["value_ok"] for x in ref)) == (b["rows"], b["right"])
        flipped = [k for k, v in a["keys"].items() if v != b["keys"][k]]
        rec = [(d, s) for d, s in stats if s.recovered]
        pol = [(d, s) for d, s in stats if s.polarity_set]
        L += [
            f"## {label}",
            "",
            f"Before-replay matches the saved run (`run_cmp_{name}.json`): {'yes' if ref_ok else 'NO'} ({b['rows']} rows, {b['right']} right). Calls whose retrieved ids differ from the trace: {moved}.",
            "",
            "| list-field count | before | after |",
            "| --- | --- | --- |",
            f"| rows scored | {b['rows']} | {a['rows']} |",
            f"| rows right (value correct) | {b['right']} | {a['right']} |",
            f"| rows wrong value shown | {b['wrong']} | {a['wrong']} |",
            f"| rows not found | {b['notfound']} | {a['notfound']} |",
        ]
        for f in llm.LIST_FIELDS:
            (p0, g0, n0), (p1, g1, n1) = b["items"][f], a["items"][f]
            L.append(f"| {f}: answer items paired / label items / answer items | {p0} / {g0} / {n0} | {p1} / {g1} / {n1} |")  # fmt: skip
        for f in llm.LIST_FIELDS:
            L.append(f"| {f}: rows right of {b['by_field'][f][1]} | {b['by_field'][f][0]} | {a['by_field'][f][0]} |")  # fmt: skip
        L += [
            "",
            f"Items recovered by fix A: {sum(s.recovered for _, s in stats)} (in {len(rec)} calls, documents {', '.join(sorted({d for d, _ in rec})) or 'none'}). Eligibility polarity set by fix B: {sum(s.polarity_set for _, s in stats)} items (in {len(pol)} calls, documents {', '.join(sorted({d for d, _ in pol})) or 'none'}). Rows whose right/wrong state changed: {len(flipped)}{' (' + ', '.join(f'{d}/{f}' for d, f in flipped) + ')' if flipped else ''}.",
            "",
        ]
    L += ["## What I saw", "", "Counts above come from this run of `uv run python -m eval.phase5_fix1_replay`. Anything not shown (for example why a recovered item still does not pair with its label item) was not looked into.", ""]  # fmt: skip
    OUT.write_text("\n".join(L))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
