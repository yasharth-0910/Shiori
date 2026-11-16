"""Run the deterministic pipeline (ingest to segment) over every PDF in the manifest,
run the value converters on every sentence, and write
data/manifests/segmentation_report.md, plus sentences.txt and debug renders for a
review sample.

    uv run python -m eval.segmentation_report

Dev-time only. The report quotes matched date and amount strings only from `open`
documents (D-22); for restricted and unknown documents it gives the doc_id and
sentence ID instead.
"""

import random
import statistics
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from shiori_core.debug_render import PROCESSED_DIR, write_debug
from shiori_core.html_ingest import load_html_document
from shiori_core.ingest import PasswordProtectedError, load_document
from shiori_core.models import EXTRACTOR_VERSION, Document, Line, Page, Sentence
from shiori_core.value_normalize import (
    Found,
    find_amounts,
    find_dates,
    find_deadline_flags,
    find_fiscal_years,
    find_tax_basis,
    find_times,
)

from collector.manifest import ManifestRow, read_rows

REPORT_PATH = Path("data/manifests/segmentation_report.md")
SEED = 20261002
SAMPLE_QUOTA = {"notice": 3, "spec": 3}  # plus other doc types up to SAMPLE_SIZE
SAMPLE_SIZE = 10
TWO_COLUMN_ROWS = 5  # rows with two side-by-side text lines before a page is flagged


def _table(header: list[str], rows: list[list[object]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out


def _html_rows(
    rows: list[ManifestRow], docs: dict[str, Document]
) -> list[list[object]]:
    by: dict[str, list[Document]] = defaultdict(list)
    for r in rows:
        by[r.source].append(docs[r.doc_id])
    out: list[list[object]] = []
    for src, ds in sorted(by.items()):
        sents: list[Sentence] = [s for d in ds for s in d.sentences]
        out.append(
            [
                src,
                len(ds),
                len(sents),
                f"{sum(bool(s.section_path) for s in sents) / max(len(sents), 1):.0%}",
                sum(not d.sentences for d in ds),
            ]
        )
    return out


def _pick_sample(
    rows: list[ManifestRow], docs: dict[str, Document]
) -> list[ManifestRow]:
    """SAMPLE_SIZE documents with sentences: the doc_type quotas first, then other
    doc types, each time from a source not used yet where possible, open documents
    first (they can be shown to an outside reviewer, D-22)."""
    rng = random.Random(SEED)
    pool = [r for r in rows if r.doc_id in docs and len(docs[r.doc_id].sentences) >= 20]
    rng.shuffle(pool)
    pool.sort(key=lambda r: r.license_class != "open")  # stable: random within class
    sample: list[ManifestRow] = []

    def take(ok: Callable[[ManifestRow], bool]) -> None:
        used = {r.source for r in sample}
        for fresh in (True, False):
            for r in pool:
                if r not in sample and ok(r) and (r.source not in used or not fresh):
                    sample.append(r)
                    return

    for doc_type, n in SAMPLE_QUOTA.items():
        for _ in range(n):
            take(lambda r, t=doc_type: r.doc_type == t)
    while len(sample) < SAMPLE_SIZE:
        types = {r.doc_type for r in sample}
        before = len(sample)
        take(lambda r, ts=types: r.doc_type not in ts)
        if len(sample) == before:
            take(lambda r: True)
    return sample


def _body_lines(page: Page) -> list[Line]:
    return [
        line
        for line in page.lines
        if line.cell is None
        and not line.furniture
        and not line.vertical
        and len(line.text.strip()) >= 6
    ]


def _two_column(page: Page) -> tuple[int, int]:
    """(rows with a text line on each side of the page middle, times reading
    order jumps between the halves). Many of both means the columns interleave."""
    mid = page.width / 2
    lines = _body_lines(page)
    left = [ln for ln in lines if ln.bbox[2] < mid]
    right = [ln for ln in lines if ln.bbox[0] > mid]
    rows = sum(
        any(
            min(a.bbox[3], b.bbox[3]) - max(a.bbox[1], b.bbox[1])
            > 0.5 * (a.bbox[3] - a.bbox[1])
            for b in right
        )
        for a in left
    )
    side = [0 if ln.bbox[2] < mid else 1 for ln in lines if ln in left or ln in right]
    jumps = sum(a != b for a, b in zip(side, side[1:], strict=False))
    return rows, jumps


class _Tally:
    """Found / converted counts and failure reasons for one kind of value."""

    def __init__(self) -> None:
        self.found = 0
        self.converted = 0
        self.reasons: Counter[str] = Counter()
        self.examples: dict[str, list[str]] = defaultdict(list)
        self.warned = 0  # converted, with a weekday warning (DATE-5)
        self.warned_examples: list[str] = []

    def add(self, items: Sequence[Found[Any]], where: str, row: ManifestRow) -> None:
        for f in items:
            self.found += 1
            if f.value is not None:
                self.converted += 1
                w = f.warning
                if w is not None:
                    self.warned += 1
                    if len(self.warned_examples) < 5:
                        self.warned_examples.append(
                            f"`{f.text}` (actual {w.actual_weekday}, written "
                            f"{w.written_weekday}; {row.doc_id[:12]} {where})"
                            if row.license_class == "open"
                            else f"restricted: {row.doc_id[:12]} {where}"
                        )
                continue
            reason = f.reason or "?"
            self.reasons[reason] += 1
            ex = self.examples[reason]
            if len(ex) < 3:
                if row.license_class == "open":
                    ex.append(f"`{f.text}` ({row.doc_id[:12]} {where})")
                elif not any(e.startswith("restricted") for e in ex):
                    ex.append(f"restricted: {row.doc_id[:12]} {where}")


def main() -> None:
    all_rows = read_rows()
    rows = [r for r in all_rows if r.format == "pdf"]
    html_rows = [r for r in all_rows if r.format == "html"]
    docs: dict[str, Document] = {}
    failures: list[tuple[ManifestRow, str]] = []
    start = time.perf_counter()
    for r in rows:
        try:
            docs[r.doc_id] = load_document(Path(r.path))
        except PasswordProtectedError:
            failures.append((r, "password protected"))
        except Exception as e:  # report every failure by type, keep going
            failures.append((r, type(e).__name__))
    seconds = time.perf_counter() - start
    start = time.perf_counter()
    hdocs = {r.doc_id: load_html_document(Path(r.path)) for r in html_rows}
    html_seconds = time.perf_counter() - start
    by_id = {r.doc_id: r for r in rows} | {r.doc_id: r for r in html_rows}

    sentences = [(by_id[d.id], s) for d in docs.values() for s in d.sentences]
    html_sentences = [(by_id[d.id], s) for d in hdocs.values() for s in d.sentences]
    english = [(r, s) for r, s in sentences + html_sentences if s.language == "en"]
    ocr_sentences = [(r, s) for r, s in sentences if s.source == "ocr"]
    html_with_path = sum(bool(s.section_path) for _, s in html_sentences)
    text_pages = [
        (d, p) for d in docs.values() for p in d.pages if p.kind in ("text", "mixed")
    ]
    per_page = Counter((d.id, s.page) for d in docs.values() for s in d.sentences)
    counts = [per_page[(d.id, p.number)] for d, p in text_pages]
    with_path = sum(bool(s.section_path) for _, s in sentences)
    no_path = [
        by_id[d.id]
        for d in docs.values()
        if d.sentences and not any(s.section_path for s in d.sentences)
    ]
    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r, s in sentences:
        by_type[r.doc_type][0] += 1
        by_type[r.doc_type][1] += bool(s.section_path)
    multi_page = sum(len({b.page for b in s.boxes}) > 1 for _, s in sentences)
    in_table = sum(s.in_table for _, s in sentences)
    excluded = Counter(
        line.furniture
        for d in docs.values()
        for p in d.pages
        for line in p.lines
        if line.furniture
    )
    lengths = [len(s.text_orig) for _, s in sentences]

    tallies = {
        "dates": _Tally(),
        "fiscal years": _Tally(),
        "times": _Tally(),
        "amounts": _Tally(),
    }
    flags = Counter[str]()
    tax = Counter[str]()
    for r, s in sentences + html_sentences:
        if s.language == "en":
            continue  # English text is not read as Japanese (D-37)
        t = s.text_norm
        tallies["dates"].add(find_dates(t), s.id, r)
        tallies["fiscal years"].add(find_fiscal_years(t), s.id, r)
        tallies["times"].add(find_times(t), s.id, r)
        tallies["amounts"].add(find_amounts(t), s.id, r)
        flags.update(str(f.value) for f in find_deadline_flags(t))
        tax.update(str(f.value) for f in find_tax_basis(t))
    all_reasons: Counter[tuple[str, str]] = Counter()
    for kind, tl in tallies.items():
        for reason, n in tl.reasons.items():
            all_reasons[(kind, reason)] = n

    two_col = []
    for d, p in text_pages:
        rows_side, jumps = _two_column(p)
        if rows_side >= TWO_COLUMN_ROWS:
            two_col.append((by_id[d.id], p.number, rows_side, jumps))

    sample = _pick_sample(rows, docs)
    for r in sample:
        write_debug(Path(r.path), docs[r.doc_id], PROCESSED_DIR / r.doc_id)

    md: list[str] = [
        "# Segmentation report",
        "",
        f"Generated {date.today().isoformat()} by "
        f"`uv run python -m eval.segmentation_report`, extractor version "
        f"{EXTRACTOR_VERSION}. Phase 2 part B: header/footer exclusion (D-30), "
        "normalization, sentences, section paths, value converters. Part C: scanned "
        "and "
        "outlined pages are read by OCR (D-36) and have sentences with source `ocr`; "
        "HTML notices are included (D-37).",
        "",
        f"PDFs: {len(rows)}. Processed: {len(docs)}. Failed: {len(failures)}"
        + (
            " (" + ", ".join(f"{r.doc_id[:12]} {why}" for r, why in failures) + ")"
            if failures
            else ""
        )
        + f". Time: {seconds:.0f} s for {sum(len(d.pages) for d in docs.values())} "
        "pages, ingest to sentences.",
        "",
        "## Sentences",
        "",
        f"{len(sentences)} sentences. Per text or mixed page: mean "
        f"{statistics.mean(counts):.1f}, median {statistics.median(counts):.0f}, "
        f"max {max(counts)}; {counts.count(0)} text pages have none. Length in "
        f"characters: median {statistics.median(lengths):.0f}, 99th percentile "
        f"{sorted(lengths)[int(0.99 * len(lengths))]}, max {max(lengths)}.",
        "",
        f"In a table cell: {in_table} ({in_table / len(sentences):.0%}). Running "
        f"across a page break: {multi_page}. Lines left out as page numbers: "
        f"{excluded['page_number']}; as repeated headers or footers (D-30): "
        f"{excluded['header_footer']}.",
        "",
        "## Section paths",
        "",
        f"Sentences with a non-empty section path: {with_path} "
        f"({with_path / len(sentences):.0%}). By doc_type:",
        "",
        *_table(
            ["doc_type", "sentences", "with path"],
            [
                [t, n, f"{k / n:.0%}"]
                for t, (n, k) in sorted(by_type.items(), key=lambda kv: -kv[1][0])
            ],
        ),
        "",
        f"Documents where section parsing found nothing: {len(no_path)}. By doc_type: "
        + ", ".join(
            f"{t} {n}" for t, n in Counter(r.doc_type for r in no_path).most_common()
        )
        + ". The ones whose doc_type usually has numbering:",
        "",
        *_table(
            ["doc_id", "source", "doc_type", "pages", "sentences"],
            [
                [
                    f"`{r.doc_id[:12]}`",
                    r.source,
                    r.doc_type,
                    len(docs[r.doc_id].pages),
                    len(docs[r.doc_id].sentences),
                ]
                for r in no_path
                if r.doc_type
                in ("notice", "spec", "bid_instructions", "draft_contract")
            ],
        ),
        "",
        "## OCR and English sentences",
        "",
        f"Sentences from OCR pages (source `ocr`): {len(ocr_sentences)} in "
        f"{len({r.doc_id for r, _ in ocr_sentences})} documents, "
        f"{sum(bool(s.section_path) for _, s in ocr_sentences)} with a section path. "
        f"Sentences marked English (`language` en): {len(english)} in "
        f"{len({r.doc_id for r, _ in english})} documents "
        f"({sum(r.format == 'pdf' for r, _ in english)} in PDFs, "
        f"{sum(r.format == 'html' for r, _ in english)} in HTML), "
        f"{sum(len(s.section_path) == 1 for _, s in english)} of them with a "
        "one-level path (the Summary heading's). Documents with an English Summary "
        "heading: "
        f"{len({r.doc_id for r, s in english if s.section_titles == ['Summary']})}.",
        "",
        "## HTML notices",
        "",
        f"HTML documents: {len(html_rows)}, all read ({html_seconds:.1f} s). "
        f"{len(html_sentences)} sentences, "
        f"{html_with_path} ({html_with_path / max(len(html_sentences), 1):.0%}) "
        "with a section path. Anchors are offsets into the extracted text (D-37). "
        "By source:",
        "",
        *_table(
            ["source", "documents", "sentences", "with path", "no sentences"],
            _html_rows(html_rows, hdocs),
        ),
        "",
        "## Value converters",
        "",
        "Run on `text_norm` of every Japanese sentence, PDF and HTML (English ones are "
        "skipped). Found = the pattern matched; converted "
        "= a value came out. Everything else returned None with a reason.",
        "",
        *_table(
            ["kind", "found", "converted", "share"],
            [
                [k, t.found, t.converted, f"{t.converted / max(t.found, 1):.0%}"]
                for k, t in tallies.items()
            ],
        ),
        "",
        f"Dates converted **with a weekday warning** (DATE-5, the weekday written "
        f"disagrees with the calendar; the date is returned with both readings): "
        f"{tallies['dates'].warned}. "
        + "; ".join(tallies["dates"].warned_examples)
        + ".",
        "",
        "Deadline flags found: "
        + ", ".join(f"{k} {n}" for k, n in flags.most_common())
        + ". Tax wording found: "
        + ", ".join(f"{k} {n}" for k, n in tax.most_common())
        + ".",
        "",
        "Top 20 reasons a match did not convert. Examples are the matched string "
        "from `open` documents, else the location in a restricted one:",
        "",
        *_table(
            ["kind", "reason", "count", "examples"],
            [
                [k, reason, n, "; ".join(tallies[k].examples[reason])]
                for (k, reason), n in all_reasons.most_common(20)
            ],
        ),
        "",
        "## Two-column pages",
        "",
        "A page is listed when at least "
        f"{TWO_COLUMN_ROWS} rows have a body text line (not in a table, 6+ "
        "characters) entirely left of the page middle and another entirely right of "
        "it. `jumps` counts how often reading order switches between the halves: "
        "about two per row means the columns are interleaved line by line.",
        "",
    ]
    if two_col:
        md += _table(
            ["doc_id", "source", "page", "side-by-side rows", "jumps"],
            [
                [f"`{r.doc_id[:12]}`", r.source, n, rows_side, jumps]
                for r, n, rows_side, jumps in sorted(two_col, key=lambda x: -x[2])
            ],
        )
    else:
        md.append("None found.")
    md += [
        "",
        "## Review sample",
        "",
        f"{len(sample)} documents (`random.Random({SEED})`): "
        + ", ".join(f"{n} {t}" for t, n in SAMPLE_QUOTA.items())
        + ", the rest other doc types, a different source each where possible, "
        "open documents first. Each has `sentences.txt` "
        "(`<id> | <section path> | <text_orig>`) and one PNG per page under "
        "`debug/`.",
        "",
        *_table(
            ["doc_id", "source", "doc_type", "license", "pages", "sentences", "files"],
            [
                [
                    f"`{r.doc_id}`",
                    r.source,
                    r.doc_type,
                    r.license_class,
                    len(docs[r.doc_id].pages),
                    len(docs[r.doc_id].sentences),
                    f"`{PROCESSED_DIR / r.doc_id}/sentences.txt`, `debug/`",
                ]
                for r in sample
            ],
        ),
        "",
        "Restricted and unknown documents (D-22) stay on this machine: show a "
        "reviewer their sentences.txt only on screen or not at all.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
