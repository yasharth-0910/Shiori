# ruff: noqa: E501
"""Phase 4 eval harness: run an extractor on the dev split and score it against the
reviewed labels (eval_protocol.md, Metrics).

    uv run python -m eval.run --split dev --extractor stub

Dev-time only, never imported by the app. Field comparison is eval.silver.compare.score
(the consensus agreement rule), citation checks are eval.silver.checks; nothing here
rewrites them. Labels are model-reviewed silver labels (D-41): every number is a score
against silver labels, not against human-verified ones.

The test split is closed to this module. `require_dev` refuses any other split, and the
label directories are built only from a split that passed it, so no path of the test
split is ever formed (tests/test_eval_run.py).
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from shiori_core.fields import BY_ID, SCHEMA_VERSION
from shiori_core.models import EXTRACTOR_VERSION, Sentence

from collector.manifest import ManifestRow
from eval.silver import compare
from eval.silver.checks import citations_exist, value_in_citation
from eval.silver.config import TIER1
from eval.silver.model import Candidate
from eval.silver.prompt import applicable_fields

REPORTS = Path("eval/reports")
Extractor = Callable[[ManifestRow, list[Sentence]], dict[str, Candidate]]


def stub_extractor(row: ManifestRow, sentences: list[Sentence]) -> dict[str, Candidate]:
    """The floor: not found for every field."""
    return {f: Candidate(f, status="absent") for f in applicable_fields(row.doc_type)}


def rules_extractor(
    row: ManifestRow, sentences: list[Sentence]
) -> dict[str, Candidate]:
    """core/shiori_core/extract/rules.py: deterministic rules; a field it cannot answer
    is left out, which the harness scores as not found."""
    from shiori_core.extract.rules import extract

    return {
        f: Candidate(f, x.status, x.value_ja, None, x.normalized or None, x.citations)
        for f, x in extract(row.doc_type, sentences).items()
    }


def hybrid_extractor(
    row: ManifestRow, sentences: list[Sentence]
) -> dict[str, Candidate]:
    """eval/hybrid.py: rules, plus the local model for eligibility, deadlines and
    required_documents (core/shiori_core/extract/llm.py)."""
    from eval import hybrid

    return hybrid.extract(row, sentences)


EXTRACTORS: dict[str, Extractor] = {"stub": stub_extractor, "rules": rules_extractor, "hybrid": hybrid_extractor}  # fmt: skip


def require_dev(split: str) -> str:
    # ponytail: test is refused outright; a milestone mode comes with its own decision
    # entry (eval_protocol.md: test runs only at milestones).
    if split != "dev":
        raise ValueError(f"eval.run reads the dev split only, not {split!r}")
    return split


def label_dirs(split: str) -> list[Path]:
    """Open documents' labels, then restricted and unknown ones (D-24)."""
    s = require_dev(split)
    return [Path("data/eval") / s / "labels", Path("data/eval_private") / s / "labels"]


def read_labels(doc_id: str, dirs: list[Path]) -> dict[str, dict] | None:
    """field -> label line, or None when the document has no label file. A file made
    for another extractor or schema version is refused (sentence ids would not match)."""
    for d in dirs:
        p = d / f"{doc_id}.jsonl"
        if p.exists():
            lines = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
            for ln in lines:
                if (ln["extractor_version"], ln["schema_version"]) != (EXTRACTOR_VERSION, SCHEMA_VERSION):  # fmt: skip
                    raise ValueError(f"{doc_id[:12]}: labels are for extractor {ln['extractor_version']} / schema {ln['schema_version']}")  # fmt: skip
            return {ln["field"]: ln for ln in lines}
    return None


def record(row: ManifestRow, field: str, pred: Candidate, gold: dict, by_id: dict[str, Sentence]) -> dict:  # fmt: skip
    """One asked field: value correct (compare.score's rule), citation overlap with the
    label, and the citation checks. Verified = correct and, when the label has a value,
    a cited sentence in common (the headline metric)."""
    value_ok = dict(compare.score(row, {field: pred}, {field: gold}))[field]
    overlap = bool(set(pred.citations) & set(gold.get("citations", [])))
    shown = pred.status == "present"
    value_in = value_in_citation(pred, by_id) if shown else None
    return {
        "doc": row.doc_id[:12], "field": field, "kind": BY_ID[field].kind,
        "tier1": field in TIER1, "gold": gold["status"], "pred": pred.status,
        "value_ok": value_ok,
        "verified_ok": value_ok and (gold["status"] == "absent" or overlap),
        "cite_exists": citations_exist(pred, by_id) if shown else None,
        "value_in": value_in,
        "halluc": shown and value_in is False,  # shown, value not in the cited sentences
        "wrong_shown": shown and not value_ok,  # protocol: wrong value or absent gold
        "over_abstain": gold["status"] == "present" and pred.status == "absent",
    }  # fmt: skip


def evaluate(rows: list[ManifestRow], dirs: list[Path], extractor: Extractor,
             sentences_of: Callable[[ManifestRow], list[Sentence]]) -> tuple[list[dict], list[str]]:  # fmt: skip
    """(records, skipped doc ids). A document with no label file is skipped."""
    recs, skipped = [], []
    for row in rows:
        gold = read_labels(row.doc_id, dirs)
        if gold is None:
            skipped.append(row.doc_id)
            continue
        sents = sentences_of(row)
        by_id = {s.id: s for s in sents}
        out = extractor(row, [s for s in sents if s.language == "ja"])
        for f in applicable_fields(row.doc_type):
            if f in gold:
                recs.append(record(row, f, out.get(f) or Candidate(f), gold[f], by_id))
    return recs, skipped


def cell(n: int, m: int) -> str:
    return f"{n} of {m} ({100 * n / m:.0f}%)" if m else "- (0 of 0)"


def tally(recs: list[dict]) -> dict[str, tuple[int, int]]:
    """(count, out of) for every rate in the report."""
    shown = [r for r in recs if r["pred"] == "present"]
    gold_present = [r for r in recs if r["gold"] == "present"]
    return {
        "verified_accuracy": (sum(r["verified_ok"] for r in recs), len(recs)),
        "value_accuracy": (sum(r["value_ok"] for r in recs), len(recs)),
        "citation_exists": (sum(r["cite_exists"] is True for r in shown), len(shown)),
        "value_in_citation": (sum(r["value_in"] is True for r in shown), len(shown)),
        "not_found": (sum(r["pred"] == "absent" for r in recs), len(recs)),
        "hallucination": (sum(r["halluc"] for r in shown), len(shown)),
        "wrong_shown": (sum(r["wrong_shown"] for r in recs), len(recs)),
        "over_abstention": (sum(r["over_abstain"] for r in gold_present), len(gold_present)),
    }  # fmt: skip


def groups(recs: list[dict], key: str) -> dict[str, dict]:
    keys = sorted({r[key] for r in recs}, key=str)
    return {k: tally([r for r in recs if r[key] == k]) for k in keys}


def build(recs: list[dict], skipped: list[str], rows: list[ManifestRow], name: str,
          split: str, extractor: str, reviewed_lines: tuple[int, int]) -> dict:  # fmt: skip
    return {
        "name": name, "split": split, "extractor": extractor,
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": git_commit(), "extractor_version": EXTRACTOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "documents": sorted({r["doc"] for r in recs}), "skipped": [d[:12] for d in skipped],
        "documents_in_split": len(rows),
        "label_lines_reviewed_by_a_model": reviewed_lines,
        "overall": tally(recs), "tier1": tally([r for r in recs if r["tier1"]]),
        "by_kind": groups(recs, "kind"), "by_field": groups(recs, "field"),
        "records": recs,
    }  # fmt: skip


def git_commit() -> str | None:
    """Read only (`git rev-parse`); this never creates a commit."""
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()  # fmt: skip
    except (OSError, subprocess.CalledProcessError):
        return None


def markdown(rep: dict) -> str:
    o = rep["overall"]
    rates = [
        (
            "Verified field accuracy (correct and a cited sentence matches the label)",
            "verified_accuracy",
            "all asked fields with a label",
        ),  # fmt: skip
        (
            "Value accuracy (citations ignored)",
            "value_accuracy",
            "all asked fields with a label",
        ),
        ("Citation exists rate", "citation_exists", "fields shown as present"),
        ("Value-in-citation rate", "value_in_citation", "fields shown as present"),
        ("Not-found rate", "not_found", "all asked fields with a label"),
        (
            "Hallucination rate (shown, value not in the cited sentences)",
            "hallucination",
            "fields shown as present",
        ),  # fmt: skip
        (
            "Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent)",
            "wrong_shown",
            "all asked fields with a label",
        ),  # fmt: skip
        (
            "Over-abstention rate (label present, not found)",
            "over_abstention",
            "fields whose label is present",
        ),  # fmt: skip
    ]
    out = [
        f"# Eval run {rep['name']}", "",
        f"Split `{rep['split']}`, extractor `{rep['extractor']}`, extractor version {rep['extractor_version']}, schema {rep['schema_version']}, commit {rep['git_commit'] or '-'}, {rep['date']}.",  # fmt: skip
        "",
        "Scores are against model-reviewed silver labels, not human-verified ones (D-41). "
        "Only fields asked of the document's type are scored. No cloud call and no document text in this report.",  # fmt: skip
        "",
        f"Documents scored: {len(rep['documents'])} of {rep['documents_in_split']} in the {rep['split']} label set. "  # fmt: skip
        f"Label lines reviewed by a model: {cell(*rep['label_lines_reviewed_by_a_model'])}.",
        "", "| rate | count | out of |", "| --- | --- | --- |",
    ]  # fmt: skip
    out += [f"| {t} ({d}) | {cell(*o[k])} | |" for t, k, d in rates]
    out += ["", "## Tier 1 fields", "", "| rate | count |", "| --- | --- |"]
    out += [f"| {t} | {cell(*rep['tier1'][k])} |" for t, k, _ in rates]
    for title, key in (("By field type", "by_kind"), ("By field", "by_field")):
        out += ["", f"## {title}", "", "| | verified accuracy | value accuracy | not found | hallucination |", "| --- | --- | --- | --- | --- |"]  # fmt: skip
        for k, t in rep[key].items():
            out.append(f"| {k} | {cell(*t['verified_accuracy'])} | {cell(*t['value_accuracy'])} | {cell(*t['not_found'])} | {cell(*t['hallucination'])} |")  # fmt: skip
    out += ["", f"## Skipped ({len(rep['skipped'])}): no label file", ""]
    out += [f"- {d}" for d in rep["skipped"]] or ["- none"]
    return "\n".join(out) + "\n"


def write(rep: dict) -> tuple[Path, Path]:
    """Reports are never overwritten: a taken name gets _2, _3, ..."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    base, n = rep["name"], 1
    while (REPORTS / f"run_{base}.json").exists():
        n += 1
        base = f"{rep['name']}_{n}"
    rep["name"] = base
    j, m = REPORTS / f"run_{base}.json", REPORTS / f"run_{base}.md"
    j.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n")
    m.write_text(markdown(rep))
    return j, m


def reviewed_count(rows: list[ManifestRow], dirs: list[Path]) -> tuple[int, int]:
    lines = [
        ln for r in rows if (g := read_labels(r.doc_id, dirs)) for ln in g.values()
    ]
    return sum(bool(ln["provenance"].get("reviewed_by")) for ln in lines), len(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="eval.run", description=(__doc__ or "").split("\n")[0]
    )
    ap.add_argument("--split", default="dev", choices=["dev"])
    ap.add_argument("--extractor", default="stub", choices=sorted(EXTRACTORS))
    ap.add_argument("--name", help="report name (default <split>_<extractor>)")
    ap.add_argument("--docs", nargs="*", help="only documents whose id starts with one of these")  # fmt: skip
    ap.add_argument("--model", type=Path, help="GGUF for --extractor hybrid (default: hybrid.MODEL)")  # fmt: skip
    a = ap.parse_args(argv)
    if a.model:
        from eval import hybrid

        hybrid.MODEL = a.model
    from eval.documents import load_sentences
    from eval.silver import run

    dirs = label_dirs(a.split)
    rows = run.select(a.split, doc_ids=a.docs)
    try:
        recs, skipped = evaluate(rows, dirs, EXTRACTORS[a.extractor], load_sentences)
    finally:
        if a.extractor == "hybrid":
            from eval import hybrid

            hybrid.stop()
    scored = [r for r in rows if r.doc_id not in skipped]
    rep = build(recs, skipped, rows, a.name or f"{a.split}_{a.extractor}", a.split,
                a.extractor, reviewed_count(scored, dirs))  # fmt: skip
    j, m = write(rep)
    print(f"{len(scored)} documents scored, {len(skipped)} skipped (no label file)")
    for k, v in rep["overall"].items():
        print(f"  {k}: {cell(*v)}")
    print(f"tier 1 verified accuracy: {cell(*rep['tier1']['verified_accuracy'])}")
    print(f"wrote {j} and {m}")
    if a.extractor == "hybrid":
        from eval import hybrid

        print(f"wrote {hybrid.write_report(rep, scored, dirs)}")
        hybrid.show(scored, load_sentences)
    return 0


if __name__ == "__main__":
    sys.exit(main())
