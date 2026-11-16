"""The only module that touches the PDF library. Everything else in core goes through
`PdfFile`, so swapping PyMuPDF (AGPL, D-08, D-28) for another backend means rewriting
this file only. `tests/test_import_boundaries.py` fails if pymupdf is imported anywhere
else in core/.

Coordinates: every box returned here is in PDF points on the page as displayed, i.e.
after the page's /Rotate is applied, with the origin at the top-left and y growing
downwards. That is the same frame PDF.js uses at scale 1, so the viewer can draw
highlights without knowing about rotation.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, cast

import numpy as np
import pymupdf

Rect = tuple[float, float, float, float]  # x0, y0, x1, y1
Color = tuple[float, float, float]  # RGB, 0 to 1

# TEXT_INHIBIT_SPACES: by default MuPDF inserts a space wherever it sees a gap
# between two glyphs. Those spaces are not in the PDF; they caused the spaced-out
# digits in TXT-9 (`1 6 日`). With the flag set, only characters the PDF actually
# contains come out, real space glyphs included.
_TEXT_FLAGS = pymupdf.TEXTFLAGS_RAWDICT | pymupdf.TEXT_INHIBIT_SPACES

# find_tables prints an advert for a separate layout package once per process.
pymupdf.no_recommend_layout()


class PasswordProtectedError(Exception):
    """The PDF needs an open password; the empty password doesn't work."""


@dataclass(frozen=True)
class RawChar:
    c: str
    bbox: Rect


@dataclass(frozen=True)
class Fragment:
    """One run of characters as the PDF library groups them (a MuPDF "line").
    Fragments are cut at gaps, so one visual line is often several fragments;
    extract_text joins them."""

    block: int
    chars: list[RawChar]
    bbox: Rect
    direction: tuple[float, float]  # writing direction on the displayed page
    wmode: int  # 1 = vertical font (縦書き), else 0

    @property
    def text(self) -> str:
        return "".join(ch.c for ch in self.chars)


@dataclass(frozen=True)
class Overlay:
    """A box to draw on a debug render, with an optional label above its top-left."""

    bbox: Rect
    color: Color
    label: str = ""


def _is_pua(c: str) -> bool:
    return 0xE000 <= ord(c) <= 0xF8FF


def _union(a: Rect, b: Rect) -> Rect:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _rawdict(page: pymupdf.Page, **kwargs: Any) -> dict[str, Any]:
    # get_text's return type is a union over all output modes; rawdict is a dict.
    return cast(dict[str, Any], page.get_text("rawdict", **kwargs))


def _recover_pua(page: pymupdf.Page, out: list[Fragment]) -> list[Fragment]:
    """Put back Private Use Area characters that rawdict dropped.

    Word can draw a 外字 (TXT-12) as a small image tagged with /ActualText U+E27D
    (doc 94521ecf..., faef6e6a..., Nara City). MuPDF keeps that character in plain
    text but gives it an empty box, and rawdict drops empty boxes. A second pass with
    TEXT_ACCURATE_SIDE_BEARINGS keeps it, but that flag widens every other box by
    about one character, so it is only used to find what is missing. Only PUA
    characters are put back: the other characters this pass finds in the corpus are
    invisible zero-size duplicates (doc b65ec3de..., Matsue).

    The recovered character gets the full-width cell just before the character that
    follows it, which is exactly where the Nara glyph is drawn.
    ponytail: assumes left-to-right text and a square cell; fine for 外字 kanji.
    """
    flags = _TEXT_FLAGS | pymupdf.TEXT_ACCURATE_SIDE_BEARINGS
    wide = _rawdict(page, flags=flags)
    seq = [
        ch["c"]
        for block in wide["blocks"]
        for line in block.get("lines", [])
        for span in line["spans"]
        for ch in span["chars"]
    ]
    flat = [(fi, ci) for fi, f in enumerate(out) for ci in range(len(f.chars))]
    i = 0
    inserts: list[tuple[int, str]] = []  # (position in flat, character)
    for c in seq:
        if i < len(flat) and out[flat[i][0]].chars[flat[i][1]].c == c:
            i += 1
        elif _is_pua(c):
            inserts.append((i, c))
    if i != len(flat) or not flat:
        return out  # the passes don't line up; keep what we have rather than guess
    out = list(out)
    for pos, c in reversed(inserts):
        if pos < len(flat):
            fi, ci = flat[pos]
            x0, y0, _, y1 = out[fi].chars[ci].bbox
            box = (x0 - (y1 - y0), y0, x0, y1)
        else:
            fi, ci = flat[-1][0], len(out[flat[-1][0]].chars)
            _, y0, x1, y1 = out[fi].chars[-1].bbox
            box = (x1, y0, x1 + (y1 - y0), y1)
        f = out[fi]
        chars = [*f.chars[:ci], RawChar(c, box), *f.chars[ci:]]
        out[fi] = Fragment(f.block, chars, _union(f.bbox, box), f.direction, f.wmode)
    return out


def _rect(r: object, m: pymupdf.Matrix) -> Rect:
    t = pymupdf.Rect(r) * m  # type: ignore[arg-type]
    return (t.x0, t.y0, t.x1, t.y1)


class PdfFile:
    def __init__(self, path: Path) -> None:
        self._doc = pymupdf.open(path)
        self._scratch: pymupdf.Document | None = None  # copy that debug renders draw on
        if self._doc.needs_pass and not self._doc.authenticate(""):
            self._doc.close()
            raise PasswordProtectedError

    def __enter__(self) -> "PdfFile":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._scratch is not None:
            self._scratch.close()
        self._doc.close()

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    @property
    def producer(self) -> str:
        return str((self._doc.metadata or {}).get("producer") or "")

    def page_size(self, index: int) -> tuple[float, float]:
        """Width and height of the displayed (rotated) page in points."""
        r = self._doc[index].rect
        return (r.width, r.height)

    def rotation(self, index: int) -> int:
        return self._doc[index].rotation

    def fragments(self, index: int) -> list[Fragment]:
        """Text fragments in the PDF's own order, boxes on the displayed page."""
        page = self._doc[index]
        m = page.rotation_matrix  # unrotated page -> displayed page
        out: list[Fragment] = []
        textpage = page.get_textpage(flags=_TEXT_FLAGS)
        raw = _rawdict(page, textpage=textpage)
        for b, block in enumerate(raw["blocks"]):
            for line in block.get("lines", []):
                chars = [
                    RawChar(ch["c"], _rect(ch["bbox"], m))
                    for span in line["spans"]
                    for ch in span["chars"]
                ]
                if not chars:
                    continue
                dx, dy = line["dir"]
                # Rotate the direction vector too (no translation for vectors).
                d = (dx * m.a + dy * m.c, dx * m.b + dy * m.d)
                out.append(Fragment(b, chars, _rect(line["bbox"], m), d, line["wmode"]))
        plain = page.get_text("text", textpage=textpage)
        if sum(map(_is_pua, plain)) > sum(_is_pua(ch.c) for f in out for ch in f.chars):
            out = _recover_pua(page, out)
        return out

    def image_boxes(self, index: int) -> list[Rect]:
        """Where images are placed on the displayed page (no decoding)."""
        page = self._doc[index]
        m = page.rotation_matrix
        return [_rect(info["bbox"], m) for info in page.get_image_info()]

    def table_cells(self, index: int) -> list[Rect]:
        """Cells of ruled tables on the displayed page (MuPDF's find_tables, which
        reads drawn cell borders). Tables of one row are left out (D-31): some are
        built from invisible drawings around a plain heading (doc fb226cbd...,
        Hokkaido p2), and the cells of a real one-row table are separate lines
        anyway."""
        page = self._doc[index]
        m = page.rotation_matrix
        found = page.find_tables().tables  # pyright: ignore[reportOptionalMemberAccess]
        return [
            _rect(cell, m)
            for table in found
            if table.row_count > 1
            for cell in table.cells
            if cell is not None  # merged cells come back as None
        ]

    def drawing_count(self, index: int) -> int:
        """Number of vector path segments on the page. Text drawn as outlines
        (D-23, "Microsoft: Print To PDF") shows up as tens of thousands."""
        paths = self._doc[index].get_cdrawings() or []
        return sum(len(p.get("items", ())) for p in paths)

    def render_rgb(self, index: int, dpi: int) -> np.ndarray:
        """The displayed page as an RGB uint8 array (height, width, 3), for OCR. Pixels
        are `dpi / 72` per point, so a pixel box times `72 / dpi` is a box in points."""
        pix = self._doc[index].get_pixmap(
            dpi=dpi, colorspace=pymupdf.csRGB, alpha=False
        )
        return (
            np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3).copy()
        )

    def render_png(
        self,
        index: int,
        out: Path,
        overlays: Sequence[Overlay] = (),
        note: str = "",
        zoom: float = 2.0,
    ) -> None:
        """Render the displayed page to PNG, with overlays drawn on top.

        Drawing changes a page, so it happens on a separate in-memory copy of the
        document; text extracted from this PdfFile never contains the overlays.
        """
        if self._scratch is None:
            self._scratch = pymupdf.open(stream=self._doc.tobytes(), filetype="pdf")
        page = self._scratch[index]
        back = page.derotation_matrix  # displayed -> unrotated, for drawing
        shape = page.new_shape()
        for o in overlays:
            shape.draw_rect(pymupdf.Rect(o.bbox) * back)
            shape.finish(color=o.color, width=0.6)
        shape.commit()
        for o in overlays:
            if o.label:
                x0, y0, _, _ = o.bbox
                at = pymupdf.Point(max(x0, 1), max(y0 - 0.8, 4)) * back
                page.insert_text(
                    at, o.label, fontsize=4, color=o.color, rotate=page.rotation
                )
        if note:
            w = page.rect.width
            at = pymupdf.Point(w - 240, 12) * back
            page.insert_text(
                at, note, fontsize=8, color=(0.8, 0, 0.8), rotate=page.rotation
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).save(out)
