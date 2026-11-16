"""HTML notices (p-portal, local-government tender pages) -> Document (D-37).

    doc = load_html_document(path)

There are no boxes to highlight, so a sentence is anchored by character offsets into
`Document.text`, the extracted text, which is stored with the document. The app
highlights `doc.text[anchor.start:anchor.end]`. The extracted text is what a reader
sees: tags dropped, runs of white space collapsed, one line per element (`<p>`,
`<li>`, `<td>`, a heading, `<br>`). Sentences come from the same segmenter as PDFs,
so section paths and
English handling (the Summary section of WTO notices) are the same; lines join only
across a `<br>` inside one element, by the text rules (segment.py, `soft_breaks`).

Which part of the page is the document: the first element found of, in this order,
`#main_body` (Okayama, Koriyama, Nara, Niigata), `<main>` (Digital Agency, Hokkaido),
`<article>` (p-portal), `.boxEntryBody` (Funabashi, Hachioji), `#content` (Wakayama,
Asahikawa), `#main`, else `<body>`. Navigation, footers, scripts and hidden elements
inside it are left out.
"""

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

from shiori_core.models import Char, Document, Line, Page, Sentence, TextAnchor
from shiori_core.segment import segment

# Priority list, see the module docstring: (tag or None, id or None, class or None).
CONTAINERS: list[tuple[str | None, str | None, str | None]] = [
    (None, "main_body", None),
    ("main", None, None),
    ("article", None, None),
    (None, None, "boxEntryBody"),
    (None, "content", None),
    (None, "main", None),
    ("body", None, None),
]
BLOCK = {
    "p", "div", "li", "ul", "ol", "dl", "dt", "dd", "tr", "td", "th", "table",
    "caption", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header",
    "main", "blockquote", "pre", "address", "figure", "figcaption", "form",
    "fieldset", "hr",
}  # fmt: skip
SKIP = {"script", "style", "noscript", "nav", "footer", "aside", "template", "select",
        "button", "iframe", "svg", "head"}  # fmt: skip
HIDDEN = {"hide", "hidden", "screen-reader-text", "sr-only", "visually-hidden"}
VOID = {"br", "img", "hr", "input", "meta", "link", "area", "base", "col", "wbr"}


def decode(raw: bytes) -> str:
    """UTF-8, else the Japanese legacy encodings (bytes are saved as served)."""
    for enc in ("utf-8", "cp932", "euc_jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    return set((dict(attrs).get("class") or "").split())


def _matches(
    sel: tuple[str | None, str | None, str | None],
    tag: str,
    attrs: list[tuple[str, str | None]],
) -> bool:
    want_tag, want_id, want_class = sel
    a = dict(attrs)
    return (
        (want_tag is None or tag == want_tag)
        and (want_id is None or a.get("id") == want_id)
        and (want_class is None or want_class in _classes(attrs))
    )


class _Scan(HTMLParser):
    """Which container selector occurs in the page."""

    def __init__(self) -> None:
        super().__init__()
        self.found: set[int] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.found.update(
            i for i, sel in enumerate(CONTAINERS) if _matches(sel, tag, attrs)
        )


class _Extract(HTMLParser):
    def __init__(self, selector: tuple[str | None, str | None, str | None]) -> None:
        super().__init__()
        self.selector = selector
        self.container: str | None = None  # tag name of the open container
        self.depth = 0  # nesting of that tag name inside the container
        self.skipping: list[str] = []  # open skipped elements
        self.done = False
        self.buf: list[str] = []
        self.lines: list[str] = []
        self.soft: list[bool] = []  # per line: started after a <br> in the same element
        self.next_soft = False

    @property
    def inside(self) -> bool:
        return self.container is not None and not self.skipping and not self.done

    def _flush(self) -> bool:
        text = re.sub(r"[ \t\r\n]+", " ", "".join(self.buf)).strip(" 　\xa0")
        self.buf = []
        if not text:
            return False
        self.lines.append(text)
        self.soft.append(self.next_soft)
        self.next_soft = False
        return True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.done:
            return
        if self.container is None:
            if _matches(self.selector, tag, attrs):
                self.container, self.depth = tag, 1
            return
        if tag == self.container:
            self.depth += 1
        if self.skipping:
            if tag == self.skipping[-1]:
                self.skipping.append(tag)
            return
        a = dict(attrs)
        hidden = (
            tag in SKIP
            or bool(_classes(attrs) & HIDDEN)
            or a.get("aria-hidden") == "true"
            or "display:none" in (a.get("style") or "").replace(" ", "")
        )
        if hidden and tag not in VOID:
            self._flush()
            self.next_soft = False
            self.skipping.append(tag)
        elif tag == "br":
            self.next_soft = self._flush()
        elif tag in BLOCK:
            self._flush()
            self.next_soft = False

    def handle_endtag(self, tag: str) -> None:
        if self.container is None or self.done:
            return
        if self.skipping and tag == self.skipping[-1]:
            self.skipping.pop()
        elif not self.skipping and tag in BLOCK:
            self._flush()
            self.next_soft = False
        if tag == self.container:
            self.depth -= 1
            if self.depth == 0:
                self._flush()
                self.done = True

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.buf.append(data)


def extract_lines(html: str) -> tuple[list[str], list[bool]]:
    """Lines of the document's text, and per line whether it starts after a `<br>`."""
    scan = _Scan()
    scan.feed(html)
    for i in range(len(CONTAINERS)):
        if i in scan.found:
            break
    else:
        return [], []
    ex = _Extract(CONTAINERS[i])
    ex.feed(html)
    ex._flush()
    return ex.lines, ex.soft


def _page(lines: list[str]) -> Page:
    """The text as one page of invented geometry, so `segment` can run on it. Its rows
    are 12 points apart and a character is 1 point wide; segment ignores geometry in
    HTML mode (it joins lines by `soft_breaks` only)."""
    out = []
    for i, text in enumerate(lines):
        y = 12.0 * i
        chars = [
            Char(c=c, bbox=(float(j), y, j + 1.0, y + 10.0)) for j, c in enumerate(text)
        ]
        out.append(
            Line(
                id=f"p1_l{i + 1}",
                page=1,
                text=text,
                chars=chars,
                bbox=(0.0, y, float(len(text)), y + 10.0),
            )
        )
    return Page(
        number=1,
        width=1000.0,
        height=12.0 * len(lines) + 12.0,
        rotation=0,
        kind="text",
        char_count=sum(len(t) for t in lines),
        suspect_chars=0,
        image_cover=0.0,
        drawing_count=None,
        lines=out,
    )


def load_html_document(path: Path) -> Document:
    """Read an HTML notice into a Document: `text` and sentences anchored in it. A page
    with no readable text (an empty container, a stub) gives a Document with no
    sentences, not an error."""
    raw = path.read_bytes()
    lines, soft = extract_lines(decode(raw))
    text = "\n".join(lines)
    starts = [0]
    for t in lines[:-1]:
        starts.append(starts[-1] + len(t) + 1)
    by_id = {f"p1_l{i + 1}": starts[i] for i in range(len(lines))}
    soft_ids = {f"p1_l{i + 1}" for i, s in enumerate(soft) if s}
    sentences: list[Sentence] = []
    if lines:
        for n, s in enumerate(segment([_page(lines)], soft_breaks=soft_ids), 1):
            a = by_id[s.boxes[0].line_id] + s.boxes[0].start
            b = by_id[s.boxes[-1].line_id] + s.boxes[-1].end
            sentences.append(
                s.model_copy(
                    update={
                        "id": f"h_s{n}",
                        "page": 0,
                        "boxes": [],
                        "source": "html",
                        "anchor": TextAnchor(start=a, end=b),
                    }
                )
            )
    return Document(
        id=hashlib.sha256(raw).hexdigest(),
        filename=path.name,
        producer="",
        format="html",
        pages=[],
        text=text,
        sentences=sentences,
    )
