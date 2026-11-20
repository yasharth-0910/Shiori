# ruff: noqa: E501
"""Found rate per field of the rules extractor over the non-test corpus (no model, no cloud call).

    uv run python -m eval.coverage_report

Reads every PDF in data/manifests/documents.jsonl whose issuer is not in the test split of
data/eval/splits.json (the unit the splits are made in, D-40; nothing from the test split is opened),
runs the sidecar's path (read_pages, segment, rules.extract) and writes data/manifests/coverage_report.md.
Counts, issuer names from the manifest and doc id prefixes only; no document text. A field counts only for
documents whose manifest doc_type is in the field's `applies_to`; "found" is any answer the rules gave
(present or see_other_document). Meant as a "before" baseline: the header has the date and git commit.
"""

import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from shiori_core.extract import rules
from shiori_core.fields import BY_ID, FIELD_IDS
from shiori_core.ingest import read_pages
from shiori_core.segment import segment

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "manifests" / "coverage_report.md"
WORST_FIELDS = ("title", "issuer_org", "notice_date")
WORST_N = 10


def applicable(doc_type: str) -> list[str]:
    return [f for f in FIELD_IDS if doc_type in BY_ID[f].applies_to]


def run_one(path: Path, doc_type: str) -> set[str]:
    """The sidecar's path for one file: ingest, segment, then the rules (stage retrieve)."""
    doc = read_pages(path)
    return set(rules.extract(doc_type, segment(doc.pages)))


def table(rows: list[tuple[str, Counter, Counter, int]], first: str) -> list[str]:
    """One row per group; a cell is found/applicable, empty when the field never applies."""
    out = [f"| {first} | docs | " + " | ".join(FIELD_IDS) + " |", "|---|---|" + "---|" * len(FIELD_IDS)]  # fmt: skip
    for name, found, appl, n in rows:
        cells = [f"{found[f]}/{appl[f]}" if appl[f] else "-" for f in FIELD_IDS]
        out.append(f"| {name} | {n} | " + " | ".join(cells) + " |")
    return out


def pct(found: int, appl: int) -> str:
    return f"{100 * found / appl:.0f}%" if appl else "-"


def main() -> None:
    splits = json.loads((ROOT / "data/eval/splits.json").read_text())
    skipped: Counter = Counter()
    found_all: Counter = Counter()
    by_issuer: dict[str, tuple[Counter, Counter, list[int]]] = {}
    by_type: dict[str, tuple[Counter, Counter, list[int]]] = {}
    misses: dict[tuple[str, str], list[str]] = {}  # (issuer, field) -> doc id prefixes
    failures: dict[str, list[str]] = {}
    all_appl: Counter = Counter()
    done = 0
    rows = [json.loads(x) for x in (ROOT / "data/manifests/documents.jsonl").read_text().splitlines()]  # fmt: skip
    todo = []
    for r in rows:
        if splits.get(r["issuer_org"]) == "test":
            skipped["issuer in test split"] += 1
        elif r.get("format") != "pdf" or not (ROOT / r["path"]).exists():
            skipped["not a PDF on disk"] += 1
        else:
            todo.append(r)
    for i, r in enumerate(todo, 1):
        pre = r["doc_id"][:8]
        try:
            got = run_one(ROOT / r["path"], r["doc_type"])
        except Exception as e:  # counted by type, listed by prefix; never the message
            failures.setdefault(type(e).__name__, []).append(pre)
            continue
        done += 1
        print(f"{i}/{len(todo)}", file=sys.stderr, end="\r")
        for groups, key in ((by_issuer, r["issuer_org"]), (by_type, r["doc_type"])):
            f, a, n = groups.setdefault(key, (Counter(), Counter(), [0]))
            n[0] += 1
            for fid in applicable(r["doc_type"]):
                a[fid] += 1
                f[fid] += fid in got
        for fid in applicable(r["doc_type"]):
            all_appl[fid] += 1
            found_all[fid] += fid in got
            if fid not in got:
                misses.setdefault((r["issuer_org"], fid), []).append(pre)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # fmt: skip
    out = [
        "# Coverage of the rules extractor (no model)", "",
        f"- date: {date.today().isoformat()}",
        f"- git commit: {commit}",
        f"- documents processed: {done} of {len(todo)} PDFs read",
        f"- skipped: {dict(skipped) or 'none'}",
        f"- failures: {sum(map(len, failures.values()))}", "",
        "Test-split issuers are not opened. Counts only; no document text. A cell is found/applicable: a field "
        "counts only for documents whose manifest doc_type it applies to, and found means the rules gave a "
        "verified answer. `-` means the field never applies to that group.", "",
        "## Overall", "",
        "| field | found | applicable | rate |", "|---|---|---|---|",
    ]  # fmt: skip
    out += [f"| {f} | {found_all[f]} | {all_appl[f]} | {pct(found_all[f], all_appl[f])} |" for f in FIELD_IDS]  # fmt: skip
    out += ["", "## Per document type (manifest)", ""]
    out += table([(k, *v[:2], v[2][0]) for k, v in sorted(by_type.items())], "doc type")
    out += ["", "## Per issuer", ""]
    out += table([(k, *v[:2], v[2][0]) for k, v in sorted(by_issuer.items())], "issuer")
    for fid in WORST_FIELDS:
        ranked = sorted(
            ((k, v[0][fid], v[1][fid]) for k, v in by_issuer.items() if v[1][fid]),
            key=lambda t: (t[1] / t[2], -t[2]),
        )[:WORST_N]
        out += ["", f"## {WORST_N} issuers with the lowest found rate: {fid}", "",
                "| issuer | found | applicable | rate | not found (doc id prefixes, first 10) |", "|---|---|---|---|---|"]  # fmt: skip
        for k, f, a in ranked:
            ids = ", ".join(misses.get((k, fid), [])[:10])
            out.append(f"| {k} | {f} | {a} | {pct(f, a)} | {ids} |")
    out += ["", "## Failures (documents that could not be read)", ""]
    if failures:
        out += [f"- {t}: {len(ids)} ({', '.join(ids)})" for t, ids in sorted(failures.items())]  # fmt: skip
    else:
        out.append("none")
    OUT.write_text("\n".join(out) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {done} processed, {sum(map(len, failures.values()))} failed")  # fmt: skip


if __name__ == "__main__":
    main()
