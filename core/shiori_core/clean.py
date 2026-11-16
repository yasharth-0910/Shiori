"""Flag headers, footers and page numbers (DOC-6), and mark which table cell each
line sits in. Lines are flagged, never deleted: segmentation leaves flagged lines out
of sentences (D-30), and the debug render shows what was flagged.

- page_number: a line near the top or bottom edge that is only a page number, like
  `- 3 -`, `3/12`, `－３－`, `P.3`, `3ページ`, or a short label, a dash and a number:
  `別-5` (Okayama attachments), `Ⅱ調査 - 12` (Hokkaido common spec).
- header_footer: a line near the top or bottom edge whose text (spaces ignored)
  repeats at the same position on at least 3 pages and half of the document's pages
  (D-30). Lines inside a ruled table cell are never flagged: a table header row
  repeated on continuation pages is part of the table (doc 3fc2a22e...). Digits are
  not masked: form labels like `（様式１）` ... `（様式６）` (doc 706d5a67...,
  Wakayama) sit in the same place on every page but name a different form each time.
"""

import re
from collections import defaultdict

from shiori_core.models import Line, Page, Rect

EDGE_ZONE = 0.12  # top and bottom 12% of the page height
MIN_PAGES = 3
MIN_SHARE = 0.5
POS_TOL_X = 0.03  # same position: centers within 3% of the width
POS_TOL_Y = 0.02  # ... and 2% of the height

_DASH = r"\-－‐−―—–ー"
_NUM = r"[0-9０-９]+"
PAGE_NUMBER = re.compile(
    rf"^(?:[^\d\s]{{1,6}}\s*[{_DASH}]\s*)?[{_DASH}\s]*"
    rf"(?:[pPｐＰ](?:age|[.．])?\s*)?"
    rf"{_NUM}(?:\s*[/／]\s*{_NUM})?"
    rf"\s*(?:ページ|頁)?[{_DASH}\s]*$"
)


def _in_edge_zone(line: Line, page: Page) -> bool:
    _, y0, _, y1 = line.bbox
    return y1 <= page.height * EDGE_ZONE or y0 >= page.height * (1 - EDGE_ZONE)


def _center(line: Line, page: Page) -> tuple[float, float]:
    x0, y0, x1, y1 = line.bbox
    return ((x0 + x1) / 2 / page.width, (y0 + y1) / 2 / page.height)


def mark_table_cells(lines: list[Line], cells: list[Rect]) -> None:
    """Set Line.cell in place: the smallest cell that holds the line's center."""
    for line in lines:
        x0, y0, x1, y1 = line.bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        inside = [c for c in cells if c[0] <= cx <= c[2] and c[1] <= cy <= c[3]]
        if inside:
            line.cell = min(inside, key=lambda c: (c[2] - c[0]) * (c[3] - c[1]))


def flag_furniture(pages: list[Page]) -> None:
    """Set Line.furniture in place."""
    seen: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    edge: list[tuple[Line, Page, str]] = []
    for page in pages:
        for line in page.lines:
            text = "".join(line.text.split())
            if not text or line.vertical or not _in_edge_zone(line, page):
                continue
            if PAGE_NUMBER.match(text):
                line.furniture = "page_number"
                continue
            if line.cell is not None:
                continue
            seen[text].append((page.number, *_center(line, page)))
            edge.append((line, page, text))

    need = max(MIN_PAGES, MIN_SHARE * len(pages))
    for line, page, key in edge:
        x, y = _center(line, page)
        pages_here = {
            n
            for n, ox, oy in seen[key]
            if abs(ox - x) <= POS_TOL_X and abs(oy - y) <= POS_TOL_Y
        }
        if len(pages_here) >= need:
            line.furniture = "header_footer"
