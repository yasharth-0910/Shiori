"""Digital Agency (デジタル庁) procurement pages. License PDL1.0, so "open" (D-16).

Two kinds of bundle:
- 公募 (public offer) detail pages, open and closed. The 公募公告 itself is the page's
  HTML text; the attached PDFs are 応募要領, 様式, 契約書（案）, 仕様書 and so on.
- RFI (情報提供依頼) items, open and closed. One list item per RFI, with its files.
  These often include a draft 調達仕様書.

Not covered yet: 一般競争 notices (they link to p-portal, D-18), 意見招請回答 (answers
only), and the 技術的対話 page (several tenders per page, no clean grouping).
"""

import hashlib
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from collector.collect import (
    Candidate,
    Client,
    classify_doc_type,
    clean_link_text,
    it_and_spec_first,
    parse_notice_date,
)

SOURCE = "digital"
BASE_URL = "https://www.digital.go.jp"
INDEX_URL = f"{BASE_URL}/procurement"
CLOSED_OFFERS_URL = f"{BASE_URL}/procurement/closed-calls-for-public-offers"
CLOSED_RFI_URL = f"{BASE_URL}/procurement/closed-request-for-information"
ISSUER = "デジタル庁"
LICENSE_NOTE = (
    "公共データ利用規約 第1.0版 (PDL1.0), checked on site "
    "https://www.digital.go.jp/copyright-policy 2026-10-02"
)

# Title words that mark an IT or system tender.
IT_CUES = ("システム", "運用保守", "開発", "構築", "クラウド", "データ")

_DETAIL_HREF = re.compile(r"^/procurement/[0-9a-f]{8}-[0-9a-f-]{27}/?$")


def discover(client: Client) -> list[Candidate]:
    index = _article(client.get_page(INDEX_URL))
    closed_offers = _article(client.get_page(CLOSED_OFFERS_URL))
    closed_rfi = _article(client.get_page(CLOSED_RFI_URL))

    candidates: list[Candidate] = []
    for url, title, notice_date in offer_links(
        _section_list(index, "public_tender")
    ) + offer_links(closed_offers):
        candidates += offer_candidates(client.get_page(url), url, title, notice_date)
    candidates += rfi_candidates(
        _section_list(index, "request_for_information"), INDEX_URL
    )
    candidates += rfi_candidates(closed_rfi, CLOSED_RFI_URL)
    return it_and_spec_first(candidates, IT_CUES)


def offer_links(container: Tag) -> list[tuple[str, str, date | None]]:
    """(detail URL, title, 公告日) for each 公募 detail page linked in `container`."""
    found: list[tuple[str, str, date | None]] = []
    seen: set[str] = set()
    for a in container.find_all("a", href=_DETAIL_HREF):
        url = urljoin(BASE_URL, str(a["href"]).rstrip("/"))
        if url in seen:
            continue
        seen.add(url)
        item = a.find_parent("li")
        date_text = item.get_text(" ", strip=True) if item else ""
        found.append(
            (url, a.get_text(" ", strip=True), _date_after(date_text, "公告日"))
        )
    return found


def offer_candidates(
    page: bytes, url: str, title: str, notice_date: date | None
) -> list[Candidate]:
    """The page itself as the notice, plus every file linked from its article."""
    bundle_id = f"{SOURCE}:{url.rsplit('/', 1)[-1]}"
    notice = _candidate(
        url, url, title, "html", bundle_id, title, notice_date, "notice"
    )
    return [notice] + _file_candidates(
        _article(page), url, bundle_id, title, notice_date
    )


def rfi_candidates(container: Tag, landing_url: str) -> list[Candidate]:
    """One bundle per top-level list item that links files."""
    candidates: list[Candidate] = []
    for ul in container.find_all("ul"):
        if ul.find_parent("li") is not None:
            continue
        for item in ul.find_all("li", recursive=False):
            title = next(item.stripped_strings, "")
            first_file = item.find("a", href=re.compile("^/assets/"))
            if not title or first_file is None:
                continue
            # Keyed on the first file, not the title: yearly re-runs of an RFI
            # reuse the same title.
            key = hashlib.sha256(str(first_file["href"]).encode()).hexdigest()[:12]
            notice_date = _date_after(item.get_text(" ", strip=True), "公告日")
            files = _file_candidates(
                item, landing_url, f"{SOURCE}:rfi-{key}", title, notice_date
            )
            # Even a draft 調達仕様書 in an RFI is RFI material, not a tender spec.
            candidates += [
                c.model_copy(update={"doc_type": "rfi_material"}) for c in files
            ]
    return candidates


def _file_candidates(
    container: Tag,
    landing_url: str,
    bundle_id: str,
    bundle_title: str,
    notice_date: date | None,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for a in container.find_all("a", href=re.compile("^/assets/")):
        url = urljoin(BASE_URL, str(a["href"]))
        if url in seen:
            continue
        seen.add(url)
        title = clean_link_text(a.get_text(" ", strip=True))
        fmt = url.rsplit(".", 1)[-1].lower()
        candidates.append(
            _candidate(
                url, landing_url, title, fmt, bundle_id, bundle_title, notice_date
            )
        )
    return candidates


def _candidate(
    url: str,
    landing_url: str,
    title: str,
    fmt: str,
    bundle_id: str,
    bundle_title: str,
    notice_date: date | None,
    doc_type: str | None = None,
) -> Candidate:
    return Candidate.model_validate(
        {
            "url": url,
            "landing_url": landing_url,
            "issuer_org": ISSUER,
            "title_ja": title,
            "doc_type": doc_type or classify_doc_type(title),
            "notice_date": notice_date,
            "format": fmt,
            "bundle_id": bundle_id,
            "bundle_title": bundle_title,
            "license_note": LICENSE_NOTE,
            "license_class": "open",
        }
    )


def _article(page: bytes) -> Tag:
    soup = BeautifulSoup(page, "html.parser")
    article = soup.find("article") or soup.find("main") or soup
    assert isinstance(article, Tag)
    return article


def _section_list(article: Tag, heading_id: str) -> Tag:
    """The list right after the heading with this id on the index page."""
    heading = article.find(id=heading_id)
    found = heading.find_next_sibling("ul") if heading else None
    return found if isinstance(found, Tag) else Tag(name="ul")


def _date_after(text: str, label: str) -> date | None:
    i = text.find(label)
    return parse_notice_date(text[i:]) if i >= 0 else None
