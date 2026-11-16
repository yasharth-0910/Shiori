"""Data classes that cross module boundaries (docs/architecture.md, "Data model").

Phase 2: Document, Page, Line, Char and Sentence. FieldResult and Summary come later.

Boxes are PDF points on the page as displayed (after /Rotate), origin top-left,
y downwards: (x0, y0, x1, y1). See shiori_core.pdf. HTML sources have no boxes: their
sentences carry a TextAnchor into Document.text instead (D-37).
"""

from typing import Literal

from pydantic import BaseModel

# Bump when anything that changes chars, lines, line IDs, page kinds, sentences,
# sentence IDs or section paths changes. Labels record the version they were made
# with (architecture.md).
EXTRACTOR_VERSION = "0.3.0"

Rect = tuple[float, float, float, float]

# text: usable text layer. scanned: page is an image, no usable text layer.
# outlined: no text layer, text drawn as vector paths (D-23). mixed: text layer plus
# images covering half the page or more (drawings, maps, screenshots) whose text is
# not in the layer. blank: nothing on the page.
PageKind = Literal["text", "scanned", "outlined", "mixed", "blank"]

# header_footer: repeats at the same place on many pages. page_number: "- 3 -", "3/12".
Furniture = Literal["header_footer", "page_number"]


class Char(BaseModel):
    c: str  # exactly as in the PDF: no normalization, PUA code points kept (TXT-11/12)
    bbox: Rect


class Line(BaseModel):
    id: str  # "p{page}_l{n}", n from 1 in reading order
    page: int  # 1-based
    text: str  # "".join(c.c for c in chars)
    chars: list[Char]
    bbox: Rect
    # Text runs top to bottom on the displayed page: 縦書き, a stack of single
    # characters, or rotated text. Flagged only; vertical reading order is not solved.
    vertical: bool = False
    furniture: Furniture | None = None  # flagged, never deleted
    # The ruled table cell the line sits in (clean.mark_table_cells), else None.
    # Lines in different cells never join into one sentence.
    cell: Rect | None = None
    # ocr: text read from a rendered page (shiori_core.ocr). Boxes are line-level;
    # the character boxes are spread evenly over the line box (an estimate).
    source: Literal["text_layer", "ocr"] = "text_layer"


class Page(BaseModel):
    number: int  # 1-based
    width: float
    height: float
    rotation: int
    kind: PageKind
    # Measurements the kind was decided from, kept so thresholds can be tuned.
    char_count: int  # non-space characters in the text layer
    suspect_chars: int  # characters that look unmapped or mis-mapped (see ingest)
    image_cover: float  # share of the page area under images, 0 to 1
    drawing_count: int | None  # vector path segments; only counted on thin pages
    lines: list[Line]


class LineBox(BaseModel):
    """The part of one line that belongs to a sentence: line.text[start:end]."""

    line_id: str
    page: int
    start: int
    end: int
    bbox: Rect  # union of the boxes of those characters


class TextAnchor(BaseModel):
    """Where an HTML sentence sits: Document.text[start:end] == Sentence.text_orig."""

    start: int
    end: int


class Sentence(BaseModel):
    # PDF: "p{page}_s{n}", n from 1 per page for sentences that start there.
    # HTML: "h_s{n}", n from 1 over the whole document.
    id: str
    page: int  # page the sentence starts on, it may run onto the next; 0 for HTML
    # 公用文 numbering above and including this sentence, e.g. ["1", "(2)", "ア"],
    # with the heading text of each level in section_titles (same length).
    section_path: list[str]
    section_titles: list[str]
    text_orig: str  # "".join(line.text[b.start:b.end] for b in boxes), exact
    text_norm: str  # for matching only, never for display (normalize.py)
    norm_to_orig: list[int]  # index in text_norm -> index in text_orig
    boxes: list[LineBox]  # one per line span, in reading order
    in_table: bool = False
    # ocr when any of its lines came from OCR, html for HTML text (D-37).
    source: Literal["text_layer", "ocr", "html"] = "text_layer"
    # "en" for English text: sentences under a Summary heading, or Latin-only text
    # (segment.is_english). Later stages must not read those as Japanese.
    language: Literal["ja", "en"] = "ja"
    anchor: TextAnchor | None = None  # HTML only; boxes is empty then


class Document(BaseModel):
    id: str  # sha256 of the file bytes
    extractor_version: str = EXTRACTOR_VERSION
    filename: str  # base name only, never a full path (privacy.md)
    producer: str  # PDF metadata; "Microsoft: Print To PDF" hints at outlined text
    format: Literal["pdf", "html"] = "pdf"
    pages: list[Page]  # empty for HTML
    # HTML: the extracted text, stored so highlights can be drawn from the anchors.
    text: str | None = None
    sentences: list[Sentence] = []
