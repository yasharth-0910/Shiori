"""Listing-page adapter for local-government CMS sites (city survey, part C).

Every surveyed group has the same shape: one or more listing pages link to one page
per tender, and each tender page links its files. The layout groups differ only in
how those files are addressed, so a site is a config (`Site`, see sites.py) and this
module does the parsing for all of them.

The tender page itself is saved as an html document (D-20): as the `notice` when no
PDF on the page reads as a notice, otherwise as `tender_page` (`result` or `qa` when
the title says the page only announces results or answers, see classify_page).
"""

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from collector.collect import (
    Candidate,
    Client,
    classify_doc_type,
    classify_page,
    clean_link_text,
    it_and_spec_first,
)
from collector.http import DisallowedError
from collector.manifest import LicenseClass


@dataclass(frozen=True)
class Site:
    source: str  # also the CLI name and the bundle_id prefix
    issuer_org: str
    listing_urls: tuple[str, ...]
    tender_href: str  # regex on the absolute URL of a tender page
    file_href: str  # regex on the absolute URL of an attachment (the layout group)
    license_class: LicenseClass
    license_note: str
    it_cues: tuple[str, ...]
    listing_section: str | None = None  # only links under the <h2> with this text


def discover(client: Client, site: Site) -> list[Candidate]:
    candidates: list[Candidate] = []
    for url in tender_links(client, site):
        try:
            page = client.get_page(url)
        except DisallowedError:  # e.g. Asahikawa lists pages under a disallowed path
            continue
        candidates += tender_candidates(page, url, site)
    return it_and_spec_first(candidates, site.it_cues)


def tender_links(client: Client, site: Site) -> list[str]:
    """Tender page URLs from all listing pages, same host only, in page order."""
    tender = re.compile(site.tender_href)
    urls: list[str] = []
    for listing in site.listing_urls:
        main = _main(client.get_page(listing))
        for a in _anchors(main, site.listing_section):
            url = urljoin(listing, str(a["href"])).split("#")[0]
            same_host = urlsplit(url).netloc == urlsplit(listing).netloc
            if same_host and tender.search(url) and url not in urls:
                urls.append(url)
    return urls


def tender_candidates(page: bytes, url: str, site: Site) -> list[Candidate]:
    main = _main(page)
    title = _title(main, page) or url
    stem = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
    bundle_id = f"{site.source}:{stem}"

    # The same file is often linked twice: once in the text, once in the attachment
    # list with a number and size. Keep the longest link text, then clean it.
    file_href = re.compile(site.file_href)
    texts: dict[str, str] = {}
    for a in main.find_all("a", href=True):
        file_url = urljoin(url, str(a["href"])).split("#")[0]
        if not file_href.search(file_url):
            continue
        text = a.get_text(" ", strip=True)
        if len(text) > len(texts.get(file_url, "")):
            texts[file_url] = text

    files = [
        _candidate(site, f, url, clean_link_text(t), _ext(f), bundle_id, title)
        for f, t in texts.items()
    ]
    has_pdf_notice = any(c.doc_type == "notice" and c.format == "pdf" for c in files)
    page_type = classify_page(title, has_pdf_notice)
    notice = _candidate(site, url, url, title, "html", bundle_id, title, page_type)
    return [notice, *files]


def _candidate(
    site: Site,
    url: str,
    landing_url: str,
    title: str,
    fmt: str,
    bundle_id: str,
    bundle_title: str,
    doc_type: str | None = None,
) -> Candidate:
    return Candidate.model_validate(
        {
            "url": url,
            "landing_url": landing_url,
            "issuer_org": site.issuer_org,
            "title_ja": title,
            "doc_type": doc_type or classify_doc_type(title),
            "notice_date": None,  # era dates in page text are not parsed yet
            "format": fmt,
            "bundle_id": bundle_id,
            "bundle_title": bundle_title,
            "license_note": site.license_note,
            "license_class": site.license_class,
        }
    )


def _ext(url: str) -> str:
    return urlsplit(url).path.rsplit(".", 1)[-1].lower()


def _main(page: bytes) -> Tag:
    soup = BeautifulSoup(page, "html.parser")
    main = soup.find(id="main") or soup.find("main") or soup.body or soup
    assert isinstance(main, Tag)
    return main


def _title(main: Tag, page: bytes) -> str:
    h1 = main.find("h1")
    if h1:
        return h1.get_text(" ", strip=True)
    title = BeautifulSoup(page, "html.parser").title
    return (
        title.get_text(strip=True).split("|")[0].split("｜")[0].strip() if title else ""
    )


def _anchors(main: Tag, heading: str | None) -> list[Tag]:
    """Links in `main`, or only those after the <h2> containing `heading` and before
    the next <h2>. Falls back to all links if the heading isn't there."""
    start = None
    if heading:
        start = next((h for h in main.find_all("h2") if heading in h.get_text()), None)
    if start is None:
        return [a for a in main.find_all("a", href=True) if isinstance(a, Tag)]
    anchors: list[Tag] = []
    for el in start.find_all_next(["a", "h2"]):
        if not isinstance(el, Tag) or el.name == "h2":
            break
        if el.get("href"):
            anchors.append(el)
    return anchors
