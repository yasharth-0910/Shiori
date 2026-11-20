# ruff: noqa: E501
"""Measure the first-page document type rule (shiori_core.doctype, D-92) against the manifest doc_type.

    uv run python -m eval.doctype_report

Every PDF in data/manifests/documents.jsonl whose issuer is NOT in the test split of data/eval/splits.json
(the unit the splits are made in, D-40) is read; nothing from the test split is opened. Writes
eval/reports/doctype_confusion.md: counts only, doc id prefixes and license class, never document text.
Accuracy is over the three types the rule can name (notice, bid_instructions, spec); the other manifest
types (forms, qa, ...) are listed with what the rule said, since the app only meets them by mistake.
"""

import json
from collections import Counter
from pathlib import Path

from shiori_core.doctype import DETECTED, detect_doc_type, first_page_lines
from shiori_core.ingest import read_pages

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "reports" / "doctype_confusion.md"
NO_TEXT = "(no text)"


def main() -> None:
    splits = json.loads((ROOT / "data/eval/splits.json").read_text())
    conf: dict[str, Counter] = {}
    errors: list[tuple[str, str, str, str]] = []
    skipped = Counter()
    for line in (ROOT / "data/manifests/documents.jsonl").read_text().splitlines():
        r = json.loads(line)
        if splits.get(r["issuer_org"]) == "test":
            skipped["test split"] += 1
            continue
        if r.get("format") != "pdf" or not (ROOT / r["path"]).exists():
            skipped["not a PDF on disk"] += 1
            continue
        doc = read_pages(
            ROOT / r["path"], ocr=False
        )  # the text layer only: a scanned page counts as "no text"
        lines = first_page_lines(doc.pages[0]) if doc.pages else []
        got = detect_doc_type(lines) if lines else NO_TEXT
        conf.setdefault(r["doc_type"], Counter())[got] += 1
        if r["doc_type"] in DETECTED and got != r["doc_type"]:
            errors.append((r["doc_id"][:8], r["doc_type"], got, r["license_class"]))
    cols = [*DETECTED, NO_TEXT]
    rows = [*DETECTED, *sorted(t for t in conf if t not in DETECTED)]
    ok = sum(conf.get(t, Counter())[t] for t in DETECTED)
    n = sum(sum(conf.get(t, Counter()).values()) for t in DETECTED)
    no_text = sum(conf.get(t, Counter())[NO_TEXT] for t in DETECTED)
    out = ["# Document type rule against the manifest (D-92)", "",
           "Documents with issuers in the test split are not read. Rows are the manifest doc_type, columns what the rule said. "
           "No text from any document is in this file.", "",
           "| manifest \\ rule | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]  # fmt: skip
    for t in rows:
        out.append(
            f"| {t} | "
            + " | ".join(str(conf.get(t, Counter())[c]) for c in cols)
            + " |"
        )
    out += ["", f"Accuracy on the three named types: {ok} of {n} ({100 * ok / n:.1f}%), of which {no_text} had no text layer on page 1 "
            f"(the rule answers notice there, so it counts as wrong unless the document is a notice).",
            f"Skipped: {dict(skipped)}.", "", "## Wrong on the three named types (doc id prefix, manifest, rule, license)", ""]  # fmt: skip
    out += [
        f"- {a} {b} -> {c} ({d})"
        for a, b, c, d in sorted(errors, key=lambda e: (e[1], e[0]))
    ]
    OUT.write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
