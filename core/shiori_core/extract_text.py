"""Characters with boxes from the text layer, grouped into lines in reading order.

The PDF library hands back fragments: runs of characters cut wherever the pen jumps.
Justified Japanese text and label-value rows come out as many fragments per visual
line (doc 209ff219..., JMA: `契` `約` `電` `力` are four fragments). Here fragments of
one MuPDF block are joined into lines:

- along the writing direction, when they sit on the same baseline with a gap of at
  most 1.5 character heights. Table cells in one row are further apart and stay
  separate lines. Text rotated on the page is joined the same way, in its own frame.
- vertically, when single characters are stacked in a column with a gap of at most
  0.2 character widths, across blocks (vertical labels in forms, doc ac58cfb9...,
  Hachioji). Those lines, 縦書き fragments (wmode 1) and rotated text are flagged
  `vertical`. Letter-spaced vertical text (doc 6b36d69a..., Okayama envelope) is not
  joined: its gaps overlap those between table rows.

No characters are added, removed or changed: a line's text is its fragments' text
joined, so `len(line.text) == len(line.chars)` always holds.
"""

from shiori_core.models import Char, Line, Rect
from shiori_core.pdf import Fragment, PdfFile

_MAX_GAP = 1.5  # join along a line: gap at most this many line heights
_TOUCHING = 0.1  # ... or this many when the fragments are in different blocks
# Vertical join: gap at most this many character widths. Measured on the corpus:
# solid vertical labels 0.10 to 0.13 (doc ac58cfb9..., Hachioji resume form),
# table rows with one character per cell 0.35 to 0.49 (○ marks, doc d97dc236...;
# digits, doc a0f13100...), letter-spaced vertical text 0.63 to 0.70 (envelope,
# doc 6b36d69a...). Joining table rows would turn ２ / ４ / ５ in three rows into
# one line, so only solid vertical text is joined; letter-spaced columns stay
# single characters (known limitation, japanese_rules.md DOC-6).
_MAX_STACK_GAP = 0.2


def _h(r: Rect) -> float:
    return r[3] - r[1]


def _w(r: Rect) -> float:
    return r[2] - r[0]


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _axis(f: Fragment) -> tuple[int, int]:
    """Writing direction rounded to one of the four axis directions."""
    dx, dy = f.direction
    return (round(dx), 0) if abs(dx) >= abs(dy) else (0, round(dy))


def _frame(f: Fragment) -> tuple[float, float, float, float]:
    """The box in the text's own frame: (start, end) along the writing direction,
    then (start, end) across it. Lets one rule join left-to-right text and text
    rotated on the page (diagram labels, DOC-6) alike."""
    x0, y0, x1, y1 = f.bbox
    match _axis(f):
        case (0, 1):
            return (y0, y1, x0, x1)
        case (0, -1):
            return (-y1, -y0, x0, x1)
        case (-1, 0):
            return (-x1, -x0, y0, y1)
        case _:
            return (x0, x1, y0, y1)


def _is_single(f: Fragment) -> bool:
    return len(f.text.strip()) <= 1


def _joins_right(last: Fragment, f: Fragment, max_gap: float = _MAX_GAP) -> bool:
    """f continues last's line: same direction and baseline, small gap."""
    if last.wmode or f.wmode or _axis(last) != _axis(f):
        return False
    a0, a1, ac0, ac1 = _frame(last)
    b0, b1, bc0, bc1 = _frame(f)
    thick = max(ac1 - ac0, bc1 - bc0)
    same_baseline = _overlap(ac0, ac1, bc0, bc1) >= 0.5 * min(ac1 - ac0, bc1 - bc0)
    gap = b0 - a1
    return same_baseline and -0.5 * thick <= gap <= max_gap * thick


def _is_vertical(line: list[Fragment]) -> bool:
    if any(f.wmode == 1 or abs(f.direction[1]) > 0.9 for f in line):
        return True
    # A stack: the second fragment starts below the first instead of to its right.
    return len(line) > 1 and line[1].bbox[1] >= line[0].bbox[3] - 0.2 * _h(line[0].bbox)


def _group_horizontal(fragments: list[Fragment]) -> list[list[Fragment]]:
    lines: list[list[Fragment]] = []
    for f in fragments:
        cur = lines[-1] if lines else None
        # Across blocks only when the glyph cells touch: a 外字 drawn as an image
        # starts a new MuPDF block mid-line (doc faef6e6a..., Nara: 都 | 祁南之庄町).
        # Table cells in one row are blocks too, but never that close.
        max_gap = _MAX_GAP if cur and cur[-1].block == f.block else _TOUCHING
        if cur and _joins_right(cur[-1], f, max_gap):
            cur.append(f)
        else:
            lines.append([f])
    return lines


def _stackable(f: Fragment) -> bool:
    """A wmode-1 run, or one upright non-ASCII character. ASCII is left out so a
    table column of row numbers (1, 2, 3) doesn't become a vertical line; vertical
    forms use full-width digits (８). Rotated characters are joined by _joins_right."""
    if f.wmode == 1:
        return True
    text = f.text.strip()
    return _axis(f) == (1, 0) and len(text) == 1 and not text.isascii()


def _glyph_box(f: Fragment) -> Rect:
    """Box of a stackable fragment's character, without padding spaces around it
    (a cell `   件 ` is 45 pt wide, its 件 11 pt; doc 1b0397f3..., Hachioji)."""
    if f.wmode == 1:
        return f.bbox
    return next(ch.bbox for ch in f.chars if not ch.c.isspace())


def _stacks_on(a: Rect, b: Rect) -> float | None:
    """Gap if b sits directly under a in the same column, else None."""
    width = min(_w(a), _w(b))
    if _overlap(a[0], a[2], b[0], b[2]) < 0.5 * width:
        return None
    gap = b[1] - a[3]
    ok = -0.2 * width <= gap <= _MAX_STACK_GAP * max(_w(a), _w(b))
    return gap if ok else None


def _stack_columns(groups: list[list[Fragment]]) -> list[list[Fragment]]:
    """Chain single characters (and wmode-1 runs) into vertical columns.

    Works across MuPDF blocks and ignores the PDF's order, because vertical forms
    can put every character in its own block and draw the columns row by row (doc
    6b36d69a..., Okayama envelope: 岡 山 県 知 事 interleaved with the next column).
    """
    singles = [i for i, g in enumerate(groups) if len(g) == 1 and _stackable(g[0])]
    singles.sort(key=lambda i: _glyph_box(groups[i][0])[1])
    below: dict[int, int] = {}
    taken: set[int] = set()
    # ponytail: O(n^2) over single-character fragments per page; fine at a few
    # hundred. Index by x if a page with thousands shows up in the timings.
    for i in singles:
        best: tuple[float, int] | None = None
        for j in singles:
            if j == i or j in taken:
                continue
            gap = _stacks_on(_glyph_box(groups[i][0]), _glyph_box(groups[j][0]))
            if gap is not None and (best is None or gap < best[0]):
                best = (gap, j)
        if best is not None:
            below[i] = best[1]
            taken.add(best[1])

    out: list[list[Fragment]] = []
    for i, g in enumerate(groups):
        if i in taken:
            continue  # part of a column started higher up
        column = list(g)
        while i in below:
            i = below[i]
            column += groups[i]
        out.append(column)
    return out


def _union(boxes: list[Rect]) -> Rect:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def page_lines(pdf: PdfFile, index: int) -> list[Line]:
    """Lines of page `index` (0-based), in reading order, IDs p{page}_l{n}."""
    groups = _stack_columns(_group_horizontal(pdf.fragments(index)))
    # Reading order: top to bottom, then left to right, per MuPDF block, in display
    # coordinates so rotated pages read the way they are shown. Lines inside a block
    # keep the PDF's order. Tops are bucketed to 4 pt so a block that starts a hair
    # higher on the same row doesn't jump ahead.
    # ponytail: no column detection; two-column pages interleave. Add an x-gap
    # column split if real two-column tenders turn up.
    block_box: dict[int, Rect] = {}
    for g in groups:
        b = g[0].block
        box = _union([f.bbox for f in g])
        block_box[b] = _union([block_box[b], box]) if b in block_box else box
    order = sorted(
        block_box, key=lambda b: (round(block_box[b][1] / 4), block_box[b][0])
    )
    rank = {b: i for i, b in enumerate(order)}
    groups.sort(key=lambda g: rank[g[0].block])  # stable: keeps order inside a block

    lines: list[Line] = []
    page = index + 1
    for n, g in enumerate(groups, start=1):
        chars = [Char(c=ch.c, bbox=ch.bbox) for f in g for ch in f.chars]
        lines.append(
            Line(
                id=f"p{page}_l{n}",
                page=page,
                text="".join(ch.c for ch in chars),
                chars=chars,
                bbox=_union([f.bbox for f in g]),
                vertical=_is_vertical(g),
            )
        )
    return lines
