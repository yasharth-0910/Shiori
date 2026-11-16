"""Lines -> sentences with IDs, boxes and section paths (TXT-6, DOC-1, DOC-2).

    sentences = segment(pages)

Which lines: every line that is not blank and not flagged as furniture (D-30).

Where a sentence ends (TXT-6):
- after `。！？`, unless inside brackets `（「『【` that are still open. A `。` that
  ends a line always ends the sentence, so an unclosed bracket can't swallow a page.
- before a line that starts with a list marker or bullet (MARKER).
- at table cell boundaries: lines in different ruled cells (Line.cell) never join.
- around `記` and `以上` lines, and after a table-of-contents entry.
- where the next line is not the wrapped continuation of the previous one. It is
  when the previous line reaches the right margin (within 2 character heights) and
  the next one sits right under it, not left of where the previous one started; or
  when the next line starts with hiragana or closing punctuation, which never start
  an item. A blank line in between breaks it, except at a page break. Short lines
  without `。` are label-value items or headings and stay separate. Two more cases
  continue a line that is not full, because the break is the source's layout:
  the sentence has an unclosed bracket (`（Deadline ... : 5:00 p.m. 26` / `October
  2026）`), or the next line starts with a lowercase Latin letter (`...system and` /
  `lease of equipment`), both doc 2f2f5bd3..., Wakayama p3. Where a join puts two
  Latin letters or digits side by side, text_norm gets a space (normalize.py).
- HTML (`soft_breaks` given): lines never join across the boundary of an element
  (`<p>`, `<li>`, `<td>`, a heading); only across a `<br>` inside one, and then only by
  the three text rules above (hiragana start, unclosed bracket, lowercase start).

IDs are p{page}_s{n}: n counts from 1 on each page, over sentences that start there.
A sentence can run onto the next lines and the next page; every line span gets a box.

Section paths (DOC-2), D-32: a sentence that starts with a numbering marker opens a
level. Levels are not fixed in advance, because notices start at `1`, contracts at
`第1条`, and Digital Agency specs at `1.` or `1.1`. A style seen for the first time
goes one level below the current one; a style already on the stack closes everything
below it and takes that level. Guards against line starts that only look like
markers: a new level must start at its first value (bare numbers also at 2, for
law-style paragraphs), and a sibling may not jump more than 2 ahead. `記` resets the
stack (the body starts), `以上` resets it again (the body ended). Numbering inside a
table goes on its own stack, appended to the body path (`3 > 1 > 1.1`) and dropped
when the table ends: some specs are one big table (doc 3fc2a22e..., Okayama), but
row numbers must not leak into the text after a table.

English (D-37): WTO notices end with a `Summary` section in English. The heading
(`14 Summary`) opens a level like any heading; every sentence after it is marked "en"
and gets the path of that heading only, whatever numbering the English text has
(`(1) Contracting entity`). A sentence that is mostly Japanese again ends the Summary.
Elsewhere, a sentence with no Japanese characters that reads as English prose (see
`is_english`) is also "en"; its numbering works as for any sentence.
"""

import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass, field

from shiori_core.models import Line, LineBox, Page, Rect, Sentence
from shiori_core.normalize import normalize

ENDS = "。！？"
OPEN = "（(「『【［〔"
CLOSE = "）)」』】］〕"
_SP = r"[ 　]"
_D = r"[0-9０-９]"
_KANJI_NUM = "一二三四五六七八九十"
_KATA = (
    "アイウエオカキクケコサシスセソタチツテトナニヌネノ"
    "ハヒフヘホマミムメモヤユヨラリルレロワヲン"
)
# After a bare number and a space, these mean a quantity, not a heading: `12 月`,
# `100 円`, `10 件` (TXT-9 spacing). A digit is fine (`５ １次選考`, doc ab5e74f1...)
# unless a unit follows it (`1 6 日`).
_UNIT = "年月日時分円万億%％件人回社個台枚頁週秒歳号点割倍"

# A list marker at the start of a line, before NFKC (TXT-3, TXT-13). Each named
# group is one numbering style; the order of alternatives matters (longest first).
MARKER = re.compile(
    rf"""^{_SP}*(?:
      (?P<dai>第(?:{_D}{{1,2}}|[{_KANJI_NUM}]{{1,3}})[章条節款項部編]?)(?={_SP}|$|[(（])
    | (?P<dotted>{_D}{{1,2}}(?:[.．]{_D}{{1,2}}){{1,3}})[.．]?(?={_SP})
    | (?P<paren_num>[(（]{_D}{{1,2}}[)）]|[⑴-⒇])
    | (?P<paren_kata>[(（][{_KATA}][)）])
    | (?P<paren_alpha>[(（][a-zａ-ｚ][)）])
    | (?P<paren_roman>[(（][\u2170-\u217b][)）])
    | (?P<roman>[\u2160-\u216b])(?={_SP}|[.．])
    | (?P<circled>[①-⑳㉑-㉟㊱-㊿])
    | (?P<circled_kata>[㋐-㋾])
    | (?P<num_dot>{_D}{{1,2}}[.．])(?!{_D})
    | (?P<num>{_D}{{1,2}})(?={_SP}+(?!{_D}*{_SP}?[{_UNIT}])\S)
    | (?P<kanji>[{_KANJI_NUM}]{{1,2}})(?={_SP})
    | (?P<kata>[{_KATA}])(?:(?={_SP})|[.．、])
    | (?P<alpha>[a-zａ-ｚ])(?:(?={_SP}+[^\x00-\x7f])|[.．)）])
    | (?P<bullet>[・●○◎◆◇■□▪⚫※-])
    )""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class Marker:
    style: str
    label: str  # normalized: "1", "(1)", "ア", "(ア)", "①", "第1条", "2.1"
    end: int  # index in the text just after the marker


def _ordinal(style: str, label: str) -> int | None:
    """Position of a marker value in its series, from 1, or None if unknown."""
    core = label.strip("()第章条節款項部編.")
    if style.startswith("dotted"):
        core = label.rsplit(".", 1)[1]
    if style == "circled" or style.endswith("roman"):
        return int(unicodedata.numeric(core))
    if style == "circled_kata":
        return ord(core) - 0x32D0 + 1
    if core.isascii() and core.isdigit():
        return int(core)
    if core in _KATA:
        return _KATA.index(core) + 1
    if len(core) == 1 and "a" <= core <= "z":
        return ord(core) - ord("a") + 1
    if len(core) == 1 and core in _KANJI_NUM:
        return _KANJI_NUM.index(core) + 1
    return None


def parse_marker(text: str) -> Marker | None:
    """The list marker at the start of `text` (a line), if any."""
    m = MARKER.match(text)
    if not m or m.lastgroup is None:
        return None
    style = m.lastgroup
    raw = m.group(style)
    if style in ("circled", "circled_kata", "roman", "paren_roman") or (
        0xE000 <= ord(raw[0]) <= 0xF8FF
    ):
        label = raw.replace("（", "(").replace("）", ")")
    else:
        label = unicodedata.normalize("NFKC", raw).rstrip(".、")
    if style == "dotted" and "0" in label.split("."):
        return None  # 1.0 is a version number, 3.0秒 a measurement
    if style == "num_dot":
        style = "num"  # `1.` and `1 ` are the same level in practice
    if style == "dai":
        style = "dai" + (label[-1] if label[-1] in "章条節款項部編" else "")
    if style == "dotted":
        style = f"dotted{label.count('.')}"
    return Marker(style, label, m.end())


# A table-of-contents entry: dot leader, then a page number. Each one is a sentence
# of its own; TOC lines are full width with no `。`, so they would otherwise chain
# (doc 8a00ce8d..., Digital spec p2).
_TOC_ENTRY = re.compile(r"(?:[.．…‥・･]{4,}|…{2,})[ \u3000]*[0-9０-９]+[ \u3000]*$")


def _is_ki(text: str) -> bool:
    return "".join(text.split()) == "記"


def _is_ijo(text: str) -> bool:
    return "".join(text.split()) == "以上"


@dataclass
class _Draft:
    spans: list[tuple[Line, int, int]] = field(default_factory=list)
    marker: Marker | None = None
    depth: int = 0  # open brackets


def _strip(text: str) -> tuple[int, int]:
    a, b = 0, len(text)
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    return a, b


def _start_x(line: Line) -> float:
    """Left edge of the line's first visible character (indent spaces ignored)."""
    for ch in line.chars:
        if not ch.c.isspace():
            return ch.bbox[0]
    return line.bbox[0]


def _end_x(line: Line) -> float:
    """Right edge of the line's last visible character (trailing spaces ignored)."""
    for ch in reversed(line.chars):
        if not ch.c.isspace():
            return ch.bbox[2]
    return line.bbox[2]


def _h(line: Line) -> float:
    return line.bbox[3] - line.bbox[1]


def _right_margins(pages: list[Page], body: set[str]) -> dict[int, float]:
    """Per page, where full body lines end: 90th percentile of line ends, so one
    overlong line (a URL) does not move the margin."""
    out: dict[int, float] = {}
    for page in pages:
        ends = sorted(
            _end_x(line)
            for line in page.lines
            if line.id in body and line.cell is None and len(line.text.strip()) >= 10
        )
        if ends:
            out[page.number] = ends[min(len(ends) - 1, int(0.9 * len(ends)))]
    return out


def _is_full(line: Line, margins: dict[int, float]) -> bool:
    right = line.cell[2] if line.cell else margins.get(line.page, line.bbox[2])
    return _end_x(line) >= right - 2 * _h(line)


# A line starting with one of these can't be a new item: hiragana, or punctuation
# that never starts a line. `ます。` after `...公正かつ厳正に行い` (doc ab5e74f1...,
# Yokosuka p6, where the source breaks the line early).
_TAIL_START = re.compile(r"[\s\u3000]*[\u3041-\u309f、。，．）」』】]")


# A line that starts in lowercase Latin can't be a new item: `lease of equipment`
# after `...system and` (doc 2f2f5bd3..., Wakayama p3). Markers (`a.`, `(a)`) were
# already split off before this is asked. The line before must end in a letter or a
# comma: `FAX 073-423-3502` and `e-mail a@b.jp` are two label-value lines.
_LOWER_START = re.compile(r"[\s\u3000]*[a-z\uff41-\uff5a]")
_OPEN_END = re.compile(r"[A-Za-z\uff21-\uff3a\uff41-\uff5a,]$")


def _text_continues(prev: Line, line: Line, depth: int) -> bool:
    """The text alone says `line` carries on the sentence before it: it starts like a
    tail, or the sentence has an unclosed bracket, or it starts in lowercase Latin
    after a line that ends in a letter."""
    return bool(
        _TAIL_START.match(line.text)
        or depth > 0
        or (_LOWER_START.match(line.text) and _OPEN_END.search(prev.text.rstrip()))
    )


def _same_row(prev: Line, line: Line) -> bool:
    """`line` carries on `prev`'s visual line: same baseline, touching or
    overlapping it. The extractor sometimes cuts one visual line in two where two
    blocks overlap (doc 209ff219..., JMA p4: `「競争参加者の資格に関する公示」` |
    `（令和８年３月`, 12 pt of overlap). Lines with a real gap between them stay
    apart: the extractor already joins those within a block, so a gap means a
    table cell or a column (`６月 ９日（火）17時` | `企画提案書 締切`)."""
    if prev.page != line.page or prev.vertical or line.vertical:
        return False
    if len(prev.text.strip()) < 2 or len(line.text.strip()) < 2:
        return False  # letter-spaced vertical text, one character per line
    h = min(_h(prev), _h(line))
    overlap = min(prev.bbox[3], line.bbox[3]) - max(prev.bbox[1], line.bbox[1])
    gap = _start_x(line) - _end_x(prev)
    return overlap >= 0.5 * h and -1.5 * h <= gap <= 0.3 * h


def _continues(
    prev: Line,
    line: Line,
    margins: dict[int, float],
    gap: bool,
    row_x: float,
    depth: int,
    soft_breaks: Collection[str] | None,
) -> bool:
    """`line` reads as the wrapped continuation of `prev`. `gap`: a blank line
    came between them. `row_x`: where prev's visual line starts. `depth`: brackets
    still open in the sentence so far. `soft_breaks`: HTML, see the module docstring."""
    if soft_breaks is not None:
        return line.id in soft_breaks and _text_continues(prev, line, depth)
    if prev.vertical or line.vertical or prev.cell != line.cell:
        return False
    if _same_row(prev, line):
        return True
    wrapped = _is_full(prev, margins) or _text_continues(prev, line, depth)
    if line.page != prev.page:
        # Blank lines at the page foot don't count; geometry doesn't carry over.
        ok = line.page == prev.page + 1 and line.cell is None
        return ok and wrapped
    if gap:
        return False
    if not wrapped:
        return False
    h = _h(prev)
    below = line.bbox[1] >= prev.bbox[1] + 0.5 * h
    near = line.bbox[1] - prev.bbox[3] <= 2.5 * h
    # A wrapped line starts at the paragraph's left edge or right of it (hanging
    # indent). One that starts well left of the previous line follows a centred or
    # right-aligned line: a title or a signature (doc 209ff219..., JMA p1).
    aligned = row_x <= _start_x(line) + 2 * h
    return below and near and aligned


def _union(boxes: list[Rect]) -> Rect:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _cut(text: str, a: int, b: int, depth: int) -> tuple[list[int], int]:
    """Sentence ends in text[a:b] (index after each end, closing brackets right after
    the end included) and the bracket depth carried to the next line."""
    cuts: list[int] = []
    i = a
    while i < b:
        c = text[i]
        if c in OPEN:
            depth += 1
        elif c in CLOSE:
            depth = max(0, depth - 1)
        elif c in ENDS and (depth == 0 or i == b - 1):
            i += 1
            while i < b and text[i] in CLOSE:
                i += 1
            cuts.append(i)
            depth = 0
            continue
        i += 1
    return cuts, depth


@dataclass
class _Section:
    style: str
    label: str
    title: str


def _title(text_norm: str, norm_to_orig: list[int], marker_end: int) -> str:
    """Heading text of a section: what follows the marker up to the first space or
    `。`, at most 40 characters. `(2) 調達件名及び数量 インターネット...` gives
    `調達件名及び数量`."""
    k = next((i for i, o in enumerate(norm_to_orig) if o >= marker_end), len(text_norm))
    rest = text_norm[k:].lstrip(" .、")
    return re.split(r"[\s。]", rest, maxsplit=1)[0][:40]


def _cells_together(lines: list[Line]) -> list[Line]:
    """Reading order with each table cell's lines kept together, at the place of the
    cell's first line. MuPDF's block order can interleave the lines of cells in one
    row (doc 3f8e45974117..., a Q&A table: `...（税込1,100` | next cell |
    `千円）とは別に...`), and only consecutive lines join into a sentence."""
    groups: dict[object, list[Line]] = {}
    for line in lines:
        key = line.cell if line.cell is not None else line.id
        groups.setdefault(key, []).append(line)
    return [line for group in groups.values() for line in group]


def segment(
    pages: list[Page], soft_breaks: Collection[str] | None = None
) -> list[Sentence]:
    """Sentences of `pages`. `soft_breaks`: only for HTML text (html_ingest), the IDs
    of lines that start after a `<br>` inside an element."""
    body = {
        line.id
        for page in pages
        for line in page.lines
        if line.text.strip() and not line.furniture
    }
    margins = _right_margins(pages, body)
    drafts: list[_Draft] = []
    cur = _Draft()
    prev: Line | None = None
    row_x = 0.0  # where prev's visual line starts
    gap = False

    def flush() -> None:
        nonlocal cur
        if cur.spans:
            drafts.append(cur)
        cur = _Draft()

    for page in pages:
        for line in _cells_together(page.lines):
            if not line.text.strip():
                gap = True
                continue
            if line.id not in body:
                continue  # furniture: skipped, does not break a running sentence
            text = line.text
            a, b = _strip(text)
            marker = None if line.vertical else parse_marker(text)
            standalone = _is_ki(text) or _is_ijo(text)
            toc = bool(_TOC_ENTRY.search(text))
            if cur.spans and (
                marker
                or standalone
                or prev is None
                or not _continues(
                    prev, line, margins, gap, row_x, cur.depth, soft_breaks
                )
            ):
                flush()
            if not cur.spans:
                cur.marker = marker
            cuts, cur.depth = _cut(text, a, b, cur.depth)
            start = a
            for end in cuts:
                cur.spans.append((line, start, end))
                flush()
                start = end
                while start < b and text[start].isspace():
                    start += 1
            if start < b:
                cur.spans.append((line, start, b))
            if standalone or toc:
                flush()
            if prev is None or not _same_row(prev, line):
                row_x = _start_x(line)
            prev = line
            gap = False
    flush()
    return _build(drafts)


_JA = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff々]")


def _latin(text: str) -> int:
    return sum(c.isascii() and c.isalpha() for c in text)


def is_english(text_norm: str) -> bool:
    """English by script: no Japanese characters, no address, URL or path, at least
    three words of two or more Latin letters of which two have a lowercase letter, and
    letters are at least half of the text. `FAX 073-423-3502`, `TEL 03-XXXX-XXXX`,
    `e-mail a@b.jp` and `category/work/exabout` are not English."""
    if _JA.search(text_norm) or re.search(r"[@_/]", text_norm):
        return False
    words = re.findall(r"[A-Za-z]{2,}", text_norm)
    visible = sum(not c.isspace() for c in text_norm)
    mixed = sum(any(c.islower() for c in w) for w in words)
    return len(words) >= 3 and mixed >= 2 and _latin(text_norm) * 2 >= visible


def _is_summary_heading(
    text_norm: str, marker_end: int, norm_to_orig: list[int]
) -> bool:
    """`14 Summary`, `5 Summary`, `Summary`: after the marker there is just that."""
    k = next((i for i, o in enumerate(norm_to_orig) if o >= marker_end), len(text_norm))
    return text_norm[k:].strip(" .、:：").lower() == "summary"


def _build(drafts: list[_Draft]) -> list[Sentence]:
    out: list[Sentence] = []
    per_page: dict[int, int] = {}
    body: list[_Section] = []
    table: list[_Section] = []  # numbering inside the current table
    # Inside an English Summary: the (labels, titles) every sentence there carries.
    summary: tuple[list[str], list[str]] | None = None
    for d in drafts:
        first = d.spans[0][0]
        text_orig = "".join(line.text[s:e] for line, s, e in d.spans)
        # parse_marker ran on the whole line; the sentence starts after its indent.
        marker_end = d.marker.end - d.spans[0][1] if d.marker else 0
        joins, at = [], 0
        for _, s, e in d.spans[:-1]:
            at += e - s
            joins.append(at)
        text_norm, norm_to_orig = normalize(text_orig, marker_end, joins)
        in_table = first.cell is not None

        if summary is not None and len(_JA.findall(text_norm)) > _latin(text_norm):
            summary = None  # Japanese again: the Summary is over
        language = "ja"
        if summary is not None:
            language = "en"
            labels, titles = summary
        else:
            if not in_table:
                table = []
            heading = _is_summary_heading(text_norm, marker_end, norm_to_orig)
            if _is_ki(text_orig) or _is_ijo(text_orig):
                body, table = [], []
            elif d.marker:
                title = _title(text_norm, norm_to_orig, marker_end)
                if in_table:
                    table = _push(table, d.marker, title)
                else:
                    body = _push(body, d.marker, title)
            stack = body + table
            labels, titles = [s.label for s in stack], [s.title for s in stack]
            if heading:
                summary, language = (labels, titles), "en"
            elif is_english(text_norm):
                language = "en"

        n = per_page[first.page] = per_page.get(first.page, 0) + 1
        out.append(
            Sentence(
                id=f"p{first.page}_s{n}",
                page=first.page,
                section_path=list(labels),
                section_titles=list(titles),
                text_orig=text_orig,
                text_norm=text_norm,
                norm_to_orig=norm_to_orig,
                boxes=[
                    LineBox(
                        line_id=line.id,
                        page=line.page,
                        start=s,
                        end=e,
                        bbox=_union([ch.bbox for ch in line.chars[s:e]]),
                    )
                    for line, s, e in d.spans
                ],
                in_table=in_table,
                source="ocr"
                if any(ln.source == "ocr" for ln, _, _ in d.spans)
                else "text_layer",
                language=language,  # pyright: ignore[reportArgumentType]
            )
        )
    return out


def _push(stack: list[_Section], marker: Marker, title: str) -> list[_Section]:
    """The section stack after a sentence that starts with `marker`."""
    if marker.style == "bullet":
        return stack
    new = _Section(marker.style, marker.label, title)
    n = _ordinal(marker.style, marker.label)
    for i, s in enumerate(stack):
        if s.style == marker.style:
            # A sibling. Going back is allowed (a parent heading whose number is
            # not in the text layer, doc 756d17c8..., Digital spec), but a jump of
            # more than 2 ahead is a wrapped line that starts with a number.
            last = _ordinal(s.style, s.label)
            if n is not None and last is not None and n > last + 2:
                return stack
            return [*stack[:i], new]
    # A new level starts at its first value. Bare numbers may start at 2: law-style
    # articles leave the first paragraph unnumbered (`第７条 ...` then `２ 甲は`,
    # doc 0f7b9667..., Wakayama contract). Other styles at 2 are usually an inline
    # list wrapped onto a line start: `...次により（ａ）参加申込書...、` then
    # `（ｂ）法人の登記事項証明書` (doc ab5e74f1..., Yokosuka p5).
    if n != 1 and not (n == 2 and marker.style == "num"):
        return stack
    return [*stack, new]
