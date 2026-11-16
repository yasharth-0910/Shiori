"""Run extraction over every PDF in the manifest and write
data/manifests/extraction_report.md, plus debug renders for a hand-check sample.

    uv run python -m eval.extraction_report

Dev-time only. The report holds doc_ids, counts and code points, never document text.
"""

import gc
import random
import statistics
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from shiori_core.debug_render import PROCESSED_DIR, render
from shiori_core.ingest import PasswordProtectedError, load_document
from shiori_core.models import EXTRACTOR_VERSION, Document

from collector.manifest import ManifestRow, read_rows

REPORT_PATH = Path("data/manifests/extraction_report.md")
SAMPLE_SIZE = 20
SEED = 20261002
GARBLED_SHARE = 0.05  # a page is "garbled" if 5%+ of its characters are suspect
KINDS = ["text", "mixed", "scanned", "outlined", "blank"]


def _table(header: list[str], rows: list[list[object]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out


def _pick_sample(
    rows: list[ManifestRow], docs: dict[str, Document]
) -> list[ManifestRow]:
    """Every doc with a scanned or outlined page, then random docs round-robin over
    sources until SAMPLE_SIZE: sources not yet in the sample first, largest first."""
    hard = [
        r
        for r in rows
        if r.doc_id in docs
        and any(p.kind in ("scanned", "outlined") for p in docs[r.doc_id].pages)
    ]
    rng = random.Random(SEED)
    by_source: dict[str, list[ManifestRow]] = defaultdict(list)
    for r in rows:
        if r.doc_id in docs and r not in hard:
            by_source[r.source].append(r)
    for pool in by_source.values():
        rng.shuffle(pool)
    sample = list(hard)
    have = {r.source for r in hard}
    sources = sorted(by_source, key=lambda s: (s in have, -len(by_source[s]), s))
    while len(sample) < SAMPLE_SIZE and any(by_source.values()):
        for s in sources:
            if by_source[s] and len(sample) < SAMPLE_SIZE:
                sample.append(by_source[s].pop())
    return sample


def main() -> None:
    rows = [r for r in read_rows() if r.format == "pdf"]
    docs: dict[str, Document] = {}
    failures: list[tuple[ManifestRow, str]] = []
    seconds: dict[str, float] = {}
    for r in rows:
        start = time.perf_counter()
        try:
            docs[r.doc_id] = load_document(Path(r.path))
        except PasswordProtectedError:
            failures.append((r, "password protected"))
        except Exception as e:  # report every failure by type, keep going
            failures.append((r, type(e).__name__))
        seconds[r.doc_id] = time.perf_counter() - start
        # Kept documents hold ~2M Char objects; without this, full GC passes land
        # on whichever file is being timed (one 1-page file showed 868 ms vs 19 ms).
        gc.freeze()

    pages = [(r, p) for r in rows if r.doc_id in docs for p in docs[r.doc_id].pages]
    kinds = Counter(p.kind for _, p in pages)
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for r, p in pages:
        by_source[r.source][p.kind] += 1
    lines_per_page = [len(p.lines) for _, p in pages]
    total_s = sum(seconds[d] for d in docs)
    per_page = {d: seconds[d] / max(len(docs[d].pages), 1) for d in docs}

    furniture = Counter(
        line.furniture for _, p in pages for line in p.lines if line.furniture
    )
    docs_with_pn = sum(
        any(line.furniture == "page_number" for p in d.pages for line in p.lines)
        for d in docs.values()
    )
    docs_with_hf = sum(
        any(line.furniture == "header_footer" for p in d.pages for line in p.lines)
        for d in docs.values()
    )
    vertical = Counter(
        r.doc_id
        for r, p in pages
        for line in p.lines
        if line.vertical and line.text.strip()
    )
    pua: dict[str, Counter[str]] = defaultdict(Counter)
    for r, p in pages:
        for line in p.lines:
            for ch in line.chars:
                if 0xE000 <= ord(ch.c) <= 0xF8FF:
                    pua[r.doc_id][f"U+{ord(ch.c):04X}"] += 1
    suspect_docs = [
        (
            r,
            sum(p.suspect_chars for p in docs[r.doc_id].pages),
            sum(p.char_count for p in docs[r.doc_id].pages),
        )
        for r in rows
        if r.doc_id in docs and any(p.suspect_chars for p in docs[r.doc_id].pages)
    ]
    garbled = [
        (r, p)
        for r, p in pages
        if p.char_count and p.suspect_chars / p.char_count >= GARBLED_SHARE
    ]

    ocr_lines = [
        (r, p, line) for r, p in pages for line in p.lines if line.source == "ocr"
    ]
    ocr_pages = {(r.doc_id, p.number) for r, p, _ in ocr_lines}
    read_pages = kinds["scanned"] + kinds["outlined"]
    read_docs = {r.doc_id for r, p in pages if p.kind in ("scanned", "outlined")}
    sample = _pick_sample(rows, docs)
    rendered: dict[str, Path] = {}
    for r in sample:
        out_dir = PROCESSED_DIR / r.doc_id / "debug"
        render(Path(r.path), docs[r.doc_id], out_dir)
        rendered[r.doc_id] = out_dir

    md: list[str] = [
        "# Extraction report",
        "",
        f"Generated {date.today().isoformat()} by "
        f"`uv run python -m eval.extraction_report`, extractor version "
        f"{EXTRACTOR_VERSION}. Phase 2 parts A to C: characters, lines, page "
        "kinds, header/footer flags, and OCR (D-36) for scanned and outlined pages. "
        "Normalization and segmentation are in `segmentation_report.md`.",
        "",
        f"PDFs in manifest: {len(rows)}. Extracted: {len(docs)}. "
        f"Failed: {len(failures)}. "
        f"Pages: {len(pages)}.",
        "",
        "## Pages per kind",
        "",
        *_table(["kind", "pages"], [[k, kinds[k]] for k in KINDS]),
        "",
        "Rules in `core/shiori_core/ingest.py`. By source:",
        "",
        *_table(
            ["source", *KINDS],
            [[s, *(by_source[s][k] for k in KINDS)] for s in sorted(by_source)],
        ),
        "",
        "## Pages that are not plain text",
        "",
        *_table(
            [
                "doc_id",
                "source",
                "license",
                "page",
                "kind",
                "chars",
                "img",
                "paths",
                "producer",
            ],
            [
                [
                    f"`{r.doc_id[:12]}`",
                    r.source,
                    r.license_class,
                    p.number,
                    p.kind,
                    p.char_count,
                    f"{p.image_cover:.2f}",
                    p.drawing_count,
                    docs[r.doc_id].producer[:40],
                ]
                for r, p in pages
                if p.kind != "text"
            ],
        ),
        "",
        "## OCR",
        "",
        f"Pages read by OCR (scanned and outlined): {read_pages}, in "
        f"{len(read_docs)} documents; {len(ocr_pages)} of them gave text: "
        f"{len(ocr_lines)} lines, "
        f"{sum(len(line.text) for _, _, line in ocr_lines)} characters. Mixed pages "
        "keep their text layer. Quality is measured in `ocr_report.md`.",
        "",
        "## Failures",
        "",
    ]
    if failures:
        md += _table(
            ["doc_id", "source", "reason"],
            [[f"`{r.doc_id[:12]}`", r.source, why] for r, why in failures],
        )
    else:
        md.append("None.")
    md += [
        "",
        "Failures are per file: a file either loads or it doesn't; pages don't fail on "
        "their own.",
    ]
    md += [
        "",
        "## Timing",
        "",
        f"Total {total_s:.1f} s for {len(pages)} pages: "
        f"{1000 * total_s / max(len(pages), 1):.1f} ms per page on average "
        "(MacBook Air M4, includes reading the file, hashing it and, for the "
        f"{len(read_docs)} documents with scanned or outlined pages, loading the OCR "
        "models once and reading those pages).",
        "",
        "Slowest per page:",
        "",
        *_table(
            ["doc_id", "source", "pages", "ms per page"],
            [
                [
                    f"`{d[:12]}`",
                    next(r.source for r in rows if r.doc_id == d),
                    len(docs[d].pages),
                    f"{1000 * per_page[d]:.0f}",
                ]
                for d in sorted(per_page, key=lambda d: -per_page[d])[:5]
            ],
        ),
        "",
        "## Lines per page",
        "",
        f"Mean {statistics.mean(lines_per_page):.1f}, median "
        f"{statistics.median(lines_per_page):.0f}, max {max(lines_per_page)}. "
        "Counts include lines made only of space glyphs.",
        "",
        "## Headers, footers and page numbers",
        "",
        f"Lines flagged `page_number`: {furniture['page_number']} in "
        f"{docs_with_pn} documents. Lines flagged `header_footer`: "
        f"{furniture['header_footer']} in {docs_with_hf} "
        "documents.",
        "",
        "## Vertical lines",
        "",
        f"{sum(vertical.values())} non-blank lines flagged vertical in "
        f"{len(vertical)} documents.",
        "",
        *_table(
            ["doc_id", "vertical lines"],
            [[f"`{d[:12]}`", n] for d, n in vertical.most_common(10)],
        ),
        "",
        "## Unmapped or mis-mapped glyphs",
        "",
        "Suspect characters (`ingest.is_suspect`): U+FFFD, control characters, "
        "Phonetic Extensions and CJK Extension A. Documents with any:",
        "",
        *_table(
            ["doc_id", "source", "suspect chars", "chars"],
            [[f"`{r.doc_id[:12]}`", r.source, s, n] for r, s, n in suspect_docs],
        ),
        "",
        f"Pages where {GARBLED_SHARE:.0%} or more of the characters are suspect: "
        + (", ".join(f"`{r.doc_id[:12]}` p{p.number}" for r, p in garbled) or "none")
        + ".",
        "",
        "Private Use Area characters, kept as they are (TXT-11, TXT-12):",
        "",
        *_table(
            ["doc_id", "code points"],
            [
                [f"`{d[:12]}`", ", ".join(f"{cp} x{n}" for cp, n in c.most_common())]
                for d, c in sorted(pua.items())
            ],
        ),
        "",
        "## Sample for hand inspection",
        "",
        f"{len(sample)} documents: every document with a scanned or outlined "
        "page, then "
        f"random documents round-robin over sources (`random.Random({SEED})`). Renders "
        "are in the folder shown, one PNG per page.",
        "",
        *_table(
            ["doc_id", "source", "license", "pages", "kinds", "debug render"],
            [
                [
                    f"`{r.doc_id}`",
                    r.source,
                    r.license_class,
                    len(docs[r.doc_id].pages),
                    ", ".join(
                        f"{k} {n}"
                        for k, n in Counter(
                            p.kind for p in docs[r.doc_id].pages
                        ).most_common()
                    ),
                    f"`{rendered[r.doc_id]}/`",
                ]
                for r in sample
            ],
        ),
        "",
    ]
    REPORT_PATH.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
