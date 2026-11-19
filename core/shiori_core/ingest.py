"""Open a PDF, extract every page's lines, and classify each page.

Page kinds (models.PageKind), decided per page because one text PDF can hold a
single scanned page (D-23, Asahikawa). Thresholds were set on the Phase 1 corpus
(data/manifests/extraction_report.md):

- a page with 20+ usable characters is "text", or "mixed" when images cover half
  of it or more (engineering drawings, maps and screenshots with text in the image).
- otherwise "scanned" if images cover 40%+ (copier scans cover 95-100%; Asahikawa's
  scanned pages inside text PDFs cover 51%),
- "outlined" if it has 2,000+ path segments and no text (Print To PDF pages have
  9,700 to 46,000; thin pages that are not outlined have under 5),
- "blank" if it has no characters at all, else "text" (a short page, e.g. only a title).

OCR (D-36): "scanned" and "outlined" pages are rendered and read by an OCR engine;
their lines replace the (empty or nearly empty) text layer and have source "ocr".
"mixed" pages keep their text layer as it is: the text in their images is not read
(open question). "text" and "blank" pages are untouched.
"""

import hashlib
from pathlib import Path

from shiori_core.clean import flag_furniture, mark_table_cells
from shiori_core.extract_text import page_lines
from shiori_core.models import Document, Line, Page, PageKind
from shiori_core.ocr import OcrEngine, default_engine, ocr_page
from shiori_core.pdf import PasswordProtectedError, PdfFile
from shiori_core.segment import segment

__all__ = ["PasswordProtectedError", "classify", "load_document", "suspect_count"]

MIN_TEXT_CHARS = 20
MIXED_IMAGE_COVER = 0.5
SCANNED_IMAGE_COVER = 0.4
OUTLINED_MIN_PATHS = 2000


def is_suspect(ch: str) -> bool:
    """True for a character that is probably an unmapped or mis-mapped glyph.

    U+FFFD and control characters are what MuPDF gives for glyphs with no Unicode
    mapping. Phonetic Extensions (U+1D00-1DBF) and CJK Extension A (U+3400-4DBF)
    are not used in tender text; in this corpus they only appear where vertical-form
    brackets and long-vowel marks were mapped to the wrong code point (doc
    6b36d69a..., Okayama: ᶌ for the vertical ー). PUA characters are not counted:
    they are bullets or 外字 (TXT-11, TXT-12) and are kept as they are.
    """
    o = ord(ch)
    return (
        o == 0xFFFD
        or (o < 0x20 and ch not in "\t\n\r")
        or 0x1D00 <= o <= 0x1DBF
        or 0x3400 <= o <= 0x4DBF
    )


def suspect_count(lines: list[Line]) -> int:
    return sum(is_suspect(ch.c) for line in lines for ch in line.chars)


def _image_cover(
    boxes: list[tuple[float, float, float, float]], w: float, h: float
) -> float:
    # ponytail: overlapping images are counted twice; capped at 1. Use a union
    # if layered images ever push a text page into "mixed" by mistake.
    area = sum(
        max(0.0, min(x1, w) - max(x0, 0.0)) * max(0.0, min(y1, h) - max(y0, 0.0))
        for x0, y0, x1, y1 in boxes
    )
    return min(area / (w * h), 1.0) if w and h else 0.0


def classify(
    char_count: int, suspect: int, image_cover: float, drawing_count: int | None
) -> PageKind:
    usable = char_count - suspect
    if usable >= MIN_TEXT_CHARS:
        return "mixed" if image_cover >= MIXED_IMAGE_COVER else "text"
    if image_cover >= SCANNED_IMAGE_COVER:
        return "scanned"
    if drawing_count is not None and drawing_count >= OUTLINED_MIN_PATHS:
        return "outlined"
    return "blank" if char_count == 0 else "text"


def _page(pdf: PdfFile, index: int, ocr: OcrEngine | bool) -> Page:
    w, h = pdf.page_size(index)
    lines = page_lines(pdf, index)
    chars = sum(1 for line in lines for ch in line.chars if not ch.c.isspace())
    suspect = suspect_count(lines)
    cover = _image_cover(pdf.image_boxes(index), w, h)
    # Counting paths is slow on busy pages, and only matters when text is thin.
    drawings = pdf.drawing_count(index) if chars - suspect < MIN_TEXT_CHARS else None
    kind = classify(chars, suspect, cover, drawings)
    if kind in ("text", "mixed"):  # outlined pages are slow to search and have no text
        mark_table_cells(lines, pdf.table_cells(index))
    elif kind in ("scanned", "outlined") and ocr is not False:
        # No table cells on OCR pages: scans have no drawn borders to find.
        engine = default_engine() if ocr is True else ocr
        lines = ocr_page(engine, pdf, index)
    return Page(
        number=index + 1,
        width=w,
        height=h,
        rotation=pdf.rotation(index),
        kind=kind,
        char_count=chars,
        suspect_chars=suspect,
        image_cover=round(cover, 3),
        drawing_count=drawings,
        lines=lines,
    )


def read_pages(path: Path, ocr: OcrEngine | bool = True) -> Document:
    """Pipeline steps 1 to 4: lines, page kinds, furniture. No sentences yet (the
    sidecar reports ingest and segment as two stages, D-82). Same arguments and errors
    as `load_document`."""
    doc_id = hashlib.sha256(path.read_bytes()).hexdigest()
    with PdfFile(path) as pdf:
        pages = [_page(pdf, i, ocr) for i in range(pdf.page_count)]
        producer = pdf.producer
    flag_furniture(pages)
    return Document(id=doc_id, filename=path.name, producer=producer, pages=pages)


def load_document(path: Path, ocr: OcrEngine | bool = True) -> Document:
    """Read a PDF into a Document with its sentences (pipeline steps 1 to 5).
    `ocr`: True reads scanned and outlined pages with the default engine (loaded on
    the first such page), an engine instance uses that one, False leaves them empty.
    Raises PasswordProtectedError for locked files, which callers skip."""
    doc = read_pages(path, ocr)
    doc.sentences = segment(doc.pages)
    return doc
