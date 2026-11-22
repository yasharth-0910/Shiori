# ruff: noqa: E501
"""Document type from the first page (D-92): `notice`, `bid_instructions` or `spec`.

    detect_doc_type(first_page_lines(doc.pages[0]))

A rule on the title zone, no model: the first 6 non-furniture lines of page 1, whitespace
removed (入 札 公 告 is written with spaces), and only the short ones (45 characters or
fewer; a long line is body text that merely mentions 仕様書 or 公告). Each type has cue
words; the cue that appears earliest in the zone wins, because a title comes before the
body. No cue, or a cue only in a long line, gives `notice`, the safe default, so a cover
sheet or a scanned page without text is never guessed at. The match runs on a cleaned
copy; nothing here is stored or shown except the type name.

Ambiguous words are left out on purpose: 要領 alone (申請書記載要領 is a form guide),
説明書 alone, プロポーザル (in notices and in bid instructions alike) and 提案.
"""

import re
import unicodedata

from shiori_core.models import Page

DETECTED = ("notice", "bid_instructions", "spec")
ZONE_LINES = 6
MAX_LINE = 45

# Order does not matter: the earliest hit in the zone wins.
CUES: dict[str, tuple[str, ...]] = {
    "spec": ("仕様書", "要求書", "提案依頼書"),
    "bid_instructions": (
        "入札説明書",
        "募集要項",
        "募集要領",
        "公募要領",
        "応募要領",
        "応募要項",
        "公募説明書",
        "実施要領",
        "参加者募集",
        "提案指示書",  # also covers 企画提案指示書
    ),  # fmt: skip
    "notice": ("公告", "公示"),
}


def first_page_lines(page: Page) -> list[str]:
    """Text of the lines on a page that are not page furniture (headers, footers, numbers)."""
    return [x.text for x in page.lines if x.furniture is None and x.text.strip()]


def _zone(lines: list[str]) -> str:
    clean = (
        re.sub(r"\s+", "", unicodedata.normalize("NFKC", x)) for x in lines if x.strip()
    )
    return "".join(h for h in list(clean)[:ZONE_LINES] if len(h) <= MAX_LINE)


def detect_doc_type(lines: list[str]) -> str:
    """One of DETECTED. `lines` are the first page's lines in reading order."""
    zone = _zone(lines)
    best: tuple[int, str] | None = None
    for doc_type, cues in CUES.items():
        for cue in cues:
            i = zone.find(cue)
            if i >= 0 and (best is None or i < best[0]):
                best = (i, doc_type)
    return best[1] if best else "notice"
