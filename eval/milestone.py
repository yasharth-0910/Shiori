# ruff: noqa: E501
"""v0.1 milestone run (D-109): the shipped pipeline (rules + local Qwen3.5-9B, eval.hybrid)
on the labeled test documents, once.

    uv run python -m eval.milestone [--name v0_1]

Writes eval/reports/test_milestone_<name>.md and refuses to overwrite it. Kept apart from
eval.run on purpose: tests/test_eval_run.py keeps that module free of test-split paths.
Dev-time only, no cloud call, and the report holds ids, counts and seconds, never document
text. Scores are against model-reviewed silver labels (D-41).
"""

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from shiori_core.fields import SCHEMA_VERSION
from shiori_core.models import EXTRACTOR_VERSION

from eval import hybrid, run
from eval.documents import load_sentences
from eval.silver import run as silver_run
from eval.silver.model import Candidate
from eval.silver.prompt import applicable_fields

DIRS = [Path("data/eval/test/labels"), Path("data/eval_private/test/labels")]
SETTLED = "settled by rule"
PARTIAL = Path("data/cache/milestone/partial.json")  # gitignored; ids and booleans only
WATCHED = ("core", "eval")  # hashed before and after the run


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def tree_digest() -> str:
    """One SHA-256 over every .py file under core/ and eval/ and every test label file."""
    h = hashlib.sha256()
    files = [p for d in WATCHED for p in sorted(Path(d).rglob("*.py")) if "__pycache__" not in p.parts]  # fmt: skip
    files += [p for d in DIRS if d.exists() for p in sorted(d.glob("*.jsonl"))]
    for p in files:
        h.update(str(p).encode() + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def settled_items() -> set[tuple[str, str]]:
    out = set()
    for d in DIRS:
        for p in d.glob("*.jsonl") if d.exists() else []:
            for ln in map(json.loads, filter(str.strip, p.read_text().splitlines())):
                if SETTLED in (ln["provenance"].get("review_note") or ""):
                    out.add((ln["doc_id"][:12], ln["field"]))
    return out


def cause(r: dict) -> str:
    """Mechanical cause category of a wrong Verified answer; no text."""
    if r["gold"] == "absent":
        return "label says absent, answer shown"
    if r["value_in"] is False:
        return "value not in the cited sentences"
    if not r["value_ok"]:
        return "value differs from the label"
    return "right value, no cited sentence in common with the label"


def score(recs: list[dict]) -> dict[str, tuple[int, int]]:
    t = run.tally(recs)
    shown = [r for r in recs if r["pred"] == "present"]
    gp = sum(r["gold_cites"] for r in recs if r["gold"] == "present")
    pp = sum(r["pred_cites"] for r in shown)
    t["citation_precision"] = (sum(r["pred_in_gold"] for r in shown), pp)
    t["citation_recall"] = (sum(r["gold_hit"] for r in recs if r["gold"] == "present"), gp)
    return t


def run_all(rows, started: float) -> tuple[list[dict], dict[str, dict]]:
    recs, timing = [], {}
    for row in rows:
        gold = run.read_labels(row.doc_id, DIRS)
        assert gold is not None
        t0 = time.perf_counter()
        sents = load_sentences(row)
        t1 = time.perf_counter()
        by_id = {s.id: s for s in sents}
        out = hybrid.extract(row, [s for s in sents if s.language == "ja"])
        t2 = time.perf_counter()
        d = row.doc_id[:12]
        timing[d] = {"type": row.doc_type, "load": t1 - t0, "extract": t2 - t1,
                     "model": hybrid.State.doc_seconds.get(d, 0.0)}  # fmt: skip
        for f in applicable_fields(row.doc_type):
            if f not in gold:
                continue
            p = out.get(f) or Candidate(f)
            r = run.record(row, f, p, gold[f], by_id)
            pc, gc = set(p.citations) if p.status == "present" else set(), set(gold[f].get("citations", []))  # fmt: skip
            r.update(pred_cites=len(pc), pred_in_gold=len(pc & gc), gold_cites=len(gc), gold_hit=len(pc & gc))  # fmt: skip
            recs.append(r)
        PARTIAL.parent.mkdir(parents=True, exist_ok=True)
        PARTIAL.write_text(json.dumps({"done": list(timing), "records": len(recs)}))
        print(f"{d} {row.doc_type}: {t2 - t0:.0f} s ({len(recs)} records so far)", flush=True)
    return recs, timing


def pair(n: int, m: int) -> str:
    return f"{n} of {m} ({100 * n / m:.0f}%)" if m else "0 of 0"


def table(rows: list[tuple[str, list[dict]]], keys: list[tuple[str, str]], skip: set) -> list[str]:
    """label | for each key: all items | without the settled five."""
    out = ["| | " + " | ".join(f"{t} (all)| {t} (w/o 5)" for t, _ in keys) + " |", "|---|" + "---|---|" * len(keys)]  # fmt: skip
    for label, rs in rows:
        rs2 = [r for r in rs if (r["doc"], r["field"]) not in skip]
        a, b = score(rs), score(rs2)
        out.append(f"| {label} | " + " | ".join(f"{pair(*a[k])} | {pair(*b[k])}" for _, k in keys) + " |")  # fmt: skip
    return out


def report(name: str, recs, timing, skip, ctx: dict) -> str:
    rs2 = [r for r in recs if (r["doc"], r["field"]) not in skip]
    A, B = score(recs), score(rs2)
    metrics = [
        ("Verified field accuracy (headline)", "verified_accuracy"),
        ("Value accuracy (citations ignored)", "value_accuracy"),
        ("Citation precision (predicted cites in the label's cites)", "citation_precision"),
        ("Citation recall (label cites that were predicted)", "citation_recall"),
        ("Not found (answer absent)", "not_found"),
        ("Wrong value shown (shown but wrong, or label absent)", "wrong_shown"),
        ("Hallucination (shown, value not in cited sentences)", "hallucination"),
        ("Over-abstention (label present, not found)", "over_abstention"),
    ]
    docs = sorted(timing)
    fields = sorted({r["field"] for r in recs})
    types = sorted({t["type"] for t in timing.values()})
    ndocs = len(docs)
    tot = [t["load"] + t["extract"] for t in timing.values()]
    L = [
        f"# v0.1 milestone report, test split ({name})", "",
        f"Run {ctx['start']} to {ctx['end']} UTC, extractor {EXTRACTOR_VERSION}, schema {SCHEMA_VERSION}, commit {ctx['commit']}, pipeline: rules + local `{hybrid.MODEL.name}` through llama-server on 127.0.0.1 (`eval.hybrid`, the same code the app ships). {ndocs} labeled test documents, one run, no cloud call. Frozen by D-109.", "",
        "Scores are against model-reviewed silver labels (D-41), not human-verified ones, and Qwen3.5-9B was one of the two labelers (D-50), so it leans optimistic. Every number is given twice: all items, and without the 5 label lines whose note says \"settled by rule, native check pending\" (D-105 to D-107). No document text in this report.", "",
        "## Freeze evidence", "",
        "`git status --short core/ eval/ docs/` before the model started (empty means clean). Lines here are the run's own new files, nothing under `core/`:", "",
        "```", ctx["status_before"] or "(empty)", "```", "",
        "Same command after the model stopped:", "", "```", ctx["status_after"] or "(empty)", "```", "",
        f"SHA-256 over every .py file in core/ and eval/ and the test label files: before `{ctx['digest_before'][:16]}`, after `{ctx['digest_after'][:16]}`, {'identical' if ctx['digest_before'] == ctx['digest_after'] else 'DIFFERENT, the run is void'}.", "",
        f"`git diff --stat HEAD -- core/` before the run: {ctx['core_diff'] or 'empty (core/ matches the last commit)'}.", "",
        f"Settled-by-rule label lines found: {len(skip)} ({', '.join(f'{d} {f}' for d, f in sorted(skip))}).", "",
        "## Headline", "", "| rate | all items | without the 5 settled |", "|---|---|---|",
    ]  # fmt: skip
    L += [f"| {t} | {pair(*A[k])} | {pair(*B[k])} |" for t, k in metrics]
    keys = [("verified", "verified_accuracy"), ("not found", "not_found")]
    L += ["", "## By field", ""] + table([(f, [r for r in recs if r["field"] == f]) for f in fields], keys, skip)  # fmt: skip
    L += ["", "## Not found by document type", "", "Not found counts every asked field whose answer was absent, including fields whose label is absent too.", ""]  # fmt: skip
    L += table([(f"{t} ({sum(v['type'] == t for v in timing.values())} docs)", [r for r in recs if timing[r["doc"]]["type"] == t]) for t in types], keys, skip)  # fmt: skip
    L += ["", "## By document", "", "| document | type | verified (all) | seconds, whole document | seconds, model calls only | seconds, loading sentences |", "|---|---|---|---|---|---|"]  # fmt: skip
    for d in docs:
        rd = [r for r in recs if r["doc"] == d]
        t = timing[d]
        L.append(f"| {d} | {t['type']} | {pair(*score(rd)['verified_accuracy'])} | {t['load'] + t['extract']:.0f} | {t['model']:.0f} | {t['load']:.0f} |")  # fmt: skip
    L += ["", f"Time per document: mean {sum(tot) / ndocs:.0f} s, median {sorted(tot)[ndocs // 2]:.0f} s, max {max(tot):.0f} s; total {sum(tot):.0f} s. Seconds are from one MacBook Air M4, not the Windows 16 GB machine.",  # fmt: skip
          f"Peak memory (getrusage, bytes to MiB): this process {ctx['rss_self']:.0f} MiB; llama-server (largest waited-for child) {ctx['rss_child']:.0f} MiB. Memory of the model is mapped, so treat these as rough.", "",
          "## Wrong Verified answers", "",
          "A Verified answer is a field shown as present. Listed: shown and not Verified-correct (wrong value, label absent, or right value with no cited sentence in common with the label). Cause is a mechanical category, not a diagnosis.", "",
          "| document | field | cause category | one of the 5 settled |", "|---|---|---|---|"]  # fmt: skip
    wrong = [r for r in recs if r["pred"] == "present" and not r["verified_ok"]]
    L += [f"| {r['doc']} | {r['field']} | {cause(r)} | {'yes' if (r['doc'], r['field']) in skip else 'no'} |" for r in wrong] or ["| none | | | |"]  # fmt: skip
    L += ["", f"Count: {len(wrong)} of {A['wrong_shown'][1]} asked fields ({len([r for r in wrong if (r['doc'], r['field']) not in skip])} without the 5 settled).", "",
          "## What this does not tell you", "",
          "- Silver labels, 10 documents, one run, one machine. Small n: a single field moves a rate by several points.",
          "- The 5 settled items wait for a native reader; the second column shows what they change.",
          "- Item-level precision and recall for the three list fields are in the dev reports only; here a list field counts as one field (every item must pair).", ""]  # fmt: skip
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval.milestone", description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--name", default="v0_1")
    a = ap.parse_args(argv)
    out = Path("eval/reports") / f"test_milestone_{a.name}.md"
    if out.exists():
        print(f"{out} exists; reports are never overwritten and the test split is run once (D-109)")
        return 1
    rows = [r for r in silver_run.select("test") if run.read_labels(r.doc_id, DIRS) is not None]
    skip = settled_items()
    ctx = {"start": datetime.now(UTC).strftime("%Y-%m-%d %H:%M"), "commit": sh(["git", "rev-parse", "HEAD"]),
           "status_before": sh(["git", "status", "--short", "core/", "eval/", "docs/"]),
           "core_diff": sh(["git", "diff", "--stat", "HEAD", "--", "core/"]), "digest_before": tree_digest()}  # fmt: skip
    print(f"git status before:\n{ctx['status_before'] or '(empty)'}\ndigest {ctx['digest_before'][:16]}; {len(rows)} labeled test documents, {len(skip)} settled items", flush=True)  # fmt: skip
    try:
        recs, timing = run_all(rows, time.time())
    finally:
        hybrid.stop()
    ctx |= {"end": datetime.now(UTC).strftime("%Y-%m-%d %H:%M"), "digest_after": tree_digest(),
            "status_after": sh(["git", "status", "--short", "core/", "eval/", "docs/"]),
            "rss_self": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20,
            "rss_child": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 2**20}  # fmt: skip
    out.write_text(report(a.name, recs, timing, skip, ctx))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
