"""OCR behind one interface (D-36), so the engine can be swapped.

An engine reads one rendered page image and returns text lines with boxes in
reading order. `ocr_page` renders a PDF page, runs the engine and gives back the same
`Line` objects the text layer produces, in displayed-page points, with source "ocr".
From there they flow through clean, normalize and segment unchanged.

Boxes are line-level: that is what the engine gives. A Line must carry one box per
character (segment cuts sentences at character offsets), so the line box is spread
over the characters in proportion to their width, half-width characters counting
half. Character boxes are therefore estimates; the line box is not.
"""

import unicodedata
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from shiori_core.models import Char, Line, Rect
from shiori_core.pdf import PdfFile

OCR_DPI = 200  # render resolution; the engine's detector is built for about this
# A line whose shorter side is more than this share of the page's shorter side is not
# a line of text but a region the detector boxed whole (a drawing, a photo): the
# recogniser reads such a box as filler (`the comple the the the`, Nara
# `e102e3ce787c...` p4, Niigata `4c51f1da8161...` p2). Titles in 100 pt type are fine.
MAX_LINE_SHARE = 0.2


class OcrUnavailableError(Exception):
    """The engine or its model files are missing."""


@dataclass(frozen=True)
class OcrLine:
    text: str
    bbox: Rect  # x0, y0, x1, y1 in pixels of the image the engine was given
    vertical: bool  # taller than wide


class OcrEngine(Protocol):
    name: str

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        """`image`: RGB, uint8, shape (height, width, 3). Lines in reading order."""
        ...


_default: OcrEngine | None = None


def default_engine() -> OcrEngine:
    """The shared NDLOCR-Lite engine, loaded on first use (about 4 s)."""
    global _default
    if _default is None:
        from shiori_core.ocr.ndlocr import NdlocrEngine

        _default = NdlocrEngine()
    return _default


def _weight(ch: str) -> float:
    return 0.5 if unicodedata.east_asian_width(ch) in ("Na", "H", "N") else 1.0


def _chars(text: str, box: Rect, vertical: bool) -> list[Char]:
    weights = [_weight(c) for c in text]
    total = sum(weights)
    x0, y0, x1, y1 = box
    lo, hi = (y0, y1) if vertical else (x0, x1)
    out: list[Char] = []
    pos = lo
    for c, w in zip(text, weights, strict=True):
        nxt = pos + (hi - lo) * w / total
        out.append(
            Char(c=c, bbox=(x0, pos, x1, nxt) if vertical else (pos, y0, nxt, y1))
        )
        pos = nxt
    return out


def drop_regions(lines: list[OcrLine], width: float, height: float) -> list[OcrLine]:
    """Lines of an image `width` x `height` pixels without the boxes that are regions,
    not lines (MAX_LINE_SHARE)."""
    limit = MAX_LINE_SHARE * min(width, height)
    return [
        ln
        for ln in lines
        if min(ln.bbox[2] - ln.bbox[0], ln.bbox[3] - ln.bbox[1]) <= limit
    ]


def to_lines(ocr_lines: list[OcrLine], page: int, scale: float) -> list[Line]:
    """Engine lines -> Lines on the page. `scale`: points per pixel (72 / dpi)."""
    out: list[Line] = []
    for ol in ocr_lines:
        if not ol.text.strip():
            continue
        box = (
            ol.bbox[0] * scale,
            ol.bbox[1] * scale,
            ol.bbox[2] * scale,
            ol.bbox[3] * scale,
        )
        out.append(
            Line(
                id=f"p{page}_l{len(out) + 1}",
                page=page,
                text=ol.text,
                chars=_chars(ol.text, box, ol.vertical),
                bbox=box,
                vertical=ol.vertical,
                source="ocr",
            )
        )
    return out


def ocr_page(
    engine: OcrEngine, pdf: PdfFile, index: int, dpi: int = OCR_DPI
) -> list[Line]:
    """Render page `index` (0-based) and read it. Boxes are in displayed-page points,
    the same frame as text-layer lines (D-29)."""
    image = pdf.render_rgb(index, dpi)
    lines = drop_regions(engine.recognize(image), image.shape[1], image.shape[0])
    return to_lines(lines, index + 1, 72 / dpi)
