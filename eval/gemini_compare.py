# ruff: noqa: E501
"""Compare the rules extractor with Gemini's silver answers on 50 documents (no model, no network).

    uv run python -m eval.gemini_compare

Reads data/cache/gemini_ref/gemini_fields.csv and the document list in data/cache/gemini_batches/index.md,
finds each PDF in data/manifests/documents.jsonl by its 12-character doc id prefix, and runs the sidecar's
path (read_pages, doc type from the first page, segment, rules.extract). Writes, under data/cache/gemini_compare/
(gitignored): report.md (counts and doc id prefixes only) and disagreements.tsv (Japanese text; one line per
both_found_differ). Gemini is a silver reference, not ground truth: its quotes are not verbatim. Documents whose
issuer is in the test split are refused, not read.
"""

import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from shiori_core.doctype import detect_doc_type, first_page_lines
from shiori_core.extract import rules
from shiori_core.extract.rules import Extracted
from shiori_core.fields import BY_ID
from shiori_core.ingest import read_pages
from shiori_core.normalize import normalize
from shiori_core.segment import segment
from shiori_core.value_normalize import find_dates

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data/cache/gemini_ref/gemini_fields.csv"
INDEX = ROOT / "data/cache/gemini_batches/index.md"
OUT = ROOT / "data/cache/gemini_compare"
FIELDS = (
    "title",
    "issuer_org",
    "contracting_officer",
    "notice_date",
    "performance_period",
)
CLASSES = (
    "both_found_agree",
    "both_found_differ",
    "we_found_gemini_not_stated",
    "gemini_found_we_not_found",
    "both_not_found",
)
_NOT_FOUND = re.compile(
    r"(?i)\s*(not stated|not explicitly|not required|in another document)"
)
_CJK = re.compile(r"[぀-ヿ一-鿿々]+")
_TITLEISH = re.compile(r"[官長知事殿庁省局部課県市府町村]|参事|担当")


def flat(s: str) -> str:
    """NFKC, no whitespace: the form two Japanese strings are compared in."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def contains_either(a: str, b: str) -> bool:
    a, b = flat(a), flat(b)
    return bool(a and b) and (a in b or b in a)


def gemini_found(answer: str) -> bool:
    return bool(answer.strip()) and not _NOT_FOUND.match(answer)


def iso_dates(text: str) -> list[str]:
    """ISO dates in a Japanese string, by the project's own normalizer and date finder."""
    return [
        d.value.isoformat()
        for d in find_dates(normalize(text)[0])
        if d.value is not None
    ]


def officer_tokens(answer_en: str) -> list[str]:
    """Person-name tokens in Gemini's answer: Japanese runs that are not a post (長, 官, 知事...)."""
    return [t for t in _CJK.findall(answer_en) if not _TITLEISH.search(t)]


def compare(
    field: str, ours: Extracted | None, answer_en: str, quote_ja: str
) -> tuple[str, bool]:
    """(class, gemini_value_unparsed). Gemini's side is read with code only, never a model."""
    we = ours is not None and ours.status == "present"
    g = gemini_found(answer_en)
    unparsed = False
    if field == "issuer_org":
        runs = _CJK.findall(answer_en)
        g = g and bool(runs)
    elif field == "contracting_officer":
        runs = officer_tokens(answer_en)
        g = g and bool(runs)  # a post with "individual name not stated" is not a name
    elif field == "notice_date":
        gd = iso_dates(quote_ja)
        unparsed = g and not gd
    elif field == "performance_period":
        gd = iso_dates(quote_ja)
        unparsed = g and not gd
    if not (we or g):
        return "both_not_found", False
    if not g:
        return "we_found_gemini_not_stated", False
    if not we:
        return "gemini_found_we_not_found", unparsed
    assert ours is not None
    n = ours.normalized
    if field == "title":
        same = contains_either(ours.value_ja, quote_ja)
    elif field == "issuer_org":
        same = any(contains_either(ours.value_ja, r) for r in runs)
    elif field == "contracting_officer":
        mine = flat(str(n.get("name", "")))
        same = bool(mine) and any(contains_either(mine, r) for r in runs)
    elif field == "notice_date":
        same = bool(gd) and gd[0] == n.get("date")
    else:  # performance_period: (start, end); one Gemini date is the end
        gs, ge = (
            (None, gd[0]) if len(gd) == 1 else (gd[0], gd[-1]) if gd else (None, None)
        )
        same = bool(gd) and (n.get("start"), n.get("end")) == (gs, ge)
    return ("both_found_agree" if same else "both_found_differ"), unparsed


def read_index() -> list[tuple[str, str]]:
    """(12-char doc id prefix, issuer) per row of the batches index."""
    rows = []
    for line in INDEX.read_text().splitlines():
        c = [x.strip() for x in line.strip("|").split("|")]
        if len(c) >= 6 and re.fullmatch(r"[0-9a-f]{12}", c[2]):
            rows.append((c[2], c[3]))
    return rows


def run_one(path: Path) -> tuple[str, dict[str, Extracted], dict[str, int]]:
    """The sidecar's path for one file: (doc_type, answers, field -> page of its first citation)."""
    doc = read_pages(path)
    doc_type = (
        detect_doc_type(first_page_lines(doc.pages[0])) if doc.pages else "notice"
    )
    sents = segment(doc.pages)
    found = rules.extract(doc_type, sents)
    page = {s.id: s.page for s in sents}
    return (
        doc_type,
        found,
        {f: page.get(x.citations[0], 0) for f, x in found.items() if x.citations},
    )


def one_line(s: str) -> str:
    return re.sub(r"[\t\r\n]+", " / ", s)


def main() -> None:
    splits = json.loads((ROOT / "data/eval/splits.json").read_text())
    manifest = [
        json.loads(x)
        for x in (ROOT / "data/manifests/documents.jsonl").read_text().splitlines()
    ]
    gem: dict[tuple[str, str], dict[str, str]] = {}
    for r in csv.DictReader(CSV.open(encoding="utf-8")):
        if r["field"] in FIELDS:
            gem.setdefault((r["doc_prefix"], r["field"]), r)
    by_field = {f: Counter() for f in FIELDS}
    by_issuer: dict[str, Counter] = {}
    na: Counter = (
        Counter()
    )  # gaps on a field that does not apply to the detected doc type
    unparsed: Counter = Counter()
    failures: dict[str, list[str]] = {}
    types: Counter = Counter()
    tsv = ["doc\tfield\tour_value_ja\tour_page\tgemini_answer_en\tgemini_quote_ja"]
    done = 0
    for prefix, issuer in read_index():
        rows = [m for m in manifest if m["doc_id"].startswith(prefix)]
        if len(rows) != 1:
            failures["manifest_match_" + str(len(rows))] = failures.get(
                "manifest_match_" + str(len(rows)), []
            ) + [prefix]
            continue
        m = rows[0]
        if splits.get(m["issuer_org"]) == "test":
            failures.setdefault("test_split_refused", []).append(prefix)
            continue
        try:
            doc_type, found, pages = run_one(ROOT / m["path"])
        except Exception as e:  # counted by type, listed by prefix; never the message
            failures.setdefault(type(e).__name__, []).append(prefix)
            continue
        done += 1
        types[doc_type] += 1
        for f in FIELDS:
            g = gem.get((prefix[:8], f), {"answer_en": "", "quote_ja": ""})
            cls, bad = compare(f, found.get(f), g["answer_en"], g["quote_ja"])
            by_field[f][cls] += 1
            by_issuer.setdefault(issuer, Counter())[cls] += 1
            unparsed[f] += bad
            if (
                cls == "gemini_found_we_not_found"
                and doc_type not in BY_ID[f].applies_to
            ):
                na[f] += 1
            if cls == "both_found_differ":
                x = found[f]
                tsv.append("\t".join([prefix[:8], f, one_line(x.value_ja), str(pages.get(f, "")), one_line(g["answer_en"]), one_line(g["quote_ja"])]))  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "disagreements.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    head = (
        "| field | "
        + " | ".join(CLASSES)
        + " | gap on non-applicable doc type | gemini date unparsed |"
    )
    sep = "|---|" + "---|" * (len(CLASSES) + 2)
    md = ["# Gemini vs rules extractor", "", f"Documents processed: {done} of {len(read_index())}. Doc types detected: {dict(types)}.", "",
          "Gemini is a silver reference. Counts and doc id prefixes only; text is in disagreements.tsv.", "", "## Per field", "", head, sep]  # fmt: skip
    md += [
        f"| {f} | "
        + " | ".join(str(by_field[f][c]) for c in CLASSES)
        + f" | {na[f]} | {unparsed[f]} |"
        for f in FIELDS
    ]
    md += [
        "",
        "## Per issuer (all five fields summed)",
        "",
        "| issuer | " + " | ".join(CLASSES) + " |",
        "|---|" + "---|" * len(CLASSES),
    ]
    md += [
        f"| {i} | " + " | ".join(str(c[k]) for k in CLASSES) + " |"
        for i, c in sorted(by_issuer.items())
    ]
    md += ["", "## Failures by type", ""] + (
        [f"- {k}: {len(v)} ({', '.join(v)})" for k, v in failures.items()] or ["- none"]
    )
    (OUT / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(
        f"documents processed: {done}; failures: { {k: len(v) for k, v in failures.items()} }"
    )
    print(head.replace("| field", "| field", 1))
    for f in FIELDS:
        print(
            f"| {f} | "
            + " | ".join(str(by_field[f][c]) for c in CLASSES)
            + f" | {na[f]} | {unparsed[f]} |"
        )
    print(f"disagreements: {len(tsv) - 1}", file=sys.stderr)


if __name__ == "__main__":
    main()
