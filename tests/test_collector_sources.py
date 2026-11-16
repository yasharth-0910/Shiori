"""Adapters against saved HTML in tests/fixtures/collector/. Never live sites."""

from pathlib import Path

import pytest

pytest.importorskip("bs4")  # "collector" dependency group

from dataclasses import replace  # noqa: E402

from bs4 import BeautifulSoup  # noqa: E402

from collector.http import DisallowedError  # noqa: E402
from collector.sources import digital, listing  # noqa: E402
from collector.sources.sites import GROUP_A, GROUP_B, HOKKAIDO  # noqa: E402

FUNABASHI, WAKAYAMA = GROUP_A[0], GROUP_A[1]
OKAYAMA = GROUP_B[0]
WAKAYAMA_IT_PAGE = (
    "https://www.pref.wakayama.lg.jp/prefg/120100/nyusatsu/d00222761.html"
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "collector"
OFFER_URL = "https://www.digital.go.jp/procurement/24d6cfea-9b50-4510-9365-64b29f9d5796"


def fixture(name: str) -> bytes:
    return (FIXTURES / f"{name}.html").read_bytes()


class FixtureClient:
    """Serves fixtures by URL. Every 公募 detail page gets the one saved detail page."""

    def __init__(
        self, pages: dict[str, bytes], default_detail: bytes | None = None
    ) -> None:
        self.pages = pages
        self.default_detail = default_detail

    def get_page(self, url: str) -> bytes:
        if url in self.pages:
            return self.pages[url]
        assert self.default_detail is not None, url
        return self.default_detail

    def get_bytes(self, url: str) -> bytes:
        raise AssertionError("adapters must not download files")


def test_digital_offer_page_gives_html_notice_and_typed_files() -> None:
    cands = digital.offer_candidates(
        fixture("digital_offer_24d6cfea"), OFFER_URL, "件名", None
    )
    assert [(c.format, c.doc_type) for c in cands] == [
        ("html", "notice"),
        ("pdf", "bid_instructions"),  # 応募要領
        ("pdf", "forms"),  # 様式1 参加申込書
        ("pdf", "draft_contract"),  # 【別記1】契約書（案）
        ("pdf", "spec"),  # 仕様書
    ]
    assert {c.bundle_id for c in cands} == {
        "digital:24d6cfea-9b50-4510-9365-64b29f9d5796"
    }
    assert cands[-1].title_ja == "仕様書"
    assert all(c.license_class == "open" for c in cands)


def test_digital_closed_offers_listing() -> None:
    main = BeautifulSoup(fixture("digital_closed_offers"), "html.parser")
    links = digital.offer_links(main)
    assert len(links) > 50
    url, title, notice_date = links[0]
    assert url.startswith("https://www.digital.go.jp/procurement/")
    assert title.startswith("防災庁のガバメントソリューションサービスへの移行")
    assert str(notice_date) == "2026-08-14"


def test_digital_rfi_items_become_bundles() -> None:
    main = BeautifulSoup(fixture("digital_closed_rfi"), "html.parser")
    cands = digital.rfi_candidates(main, digital.CLOSED_RFI_URL)
    by_bundle: dict[str, list] = {}
    for c in cands:
        by_bundle.setdefault(c.bundle_id, []).append(c)
    # The sample spec from the source survey sits in a 4-file RFI bundle.
    (bundle,) = [
        b
        for b in by_bundle.values()
        if any("オンライン決済サービスの提供等業務" in c.title_ja for c in b)
    ]
    assert [c.format for c in bundle] == ["pdf", "pdf", "pdf", "docx"]
    # Every RFI file is rfi_material, even the draft 調達仕様書 (bundle[2]).
    assert {c.doc_type for c in bundle} == {"rfi_material"}
    assert str(bundle[0].notice_date) == "2025-11-20"


def test_digital_discover_puts_it_then_spec_bundles_first() -> None:
    client = FixtureClient(
        {
            digital.INDEX_URL: fixture("digital_index"),
            digital.CLOSED_OFFERS_URL: fixture("digital_closed_offers"),
            digital.CLOSED_RFI_URL: fixture("digital_closed_rfi"),
        },
        default_detail=fixture("digital_offer_24d6cfea"),
    )
    cands = digital.discover(client)
    keys = [
        (
            any(cue in c.bundle_title for cue in digital.IT_CUES),
            any(d.doc_type == "spec" for d in cands if d.bundle_id == c.bundle_id),
        )
        for c in cands
    ]
    assert keys == sorted(keys, reverse=True)
    assert keys[0] == (True, True)
    # The taxi tender (タクシー) has a spec but no IT cue, so it is not first.
    taxi = next(i for i, c in enumerate(cands) if "タクシー" in c.bundle_title)
    assert keys[taxi] == (False, True)
    assert any(c.bundle_id.startswith("digital:rfi-") for c in cands)


def test_group_a_funabashi_page_dedupes_links_and_cleans_titles() -> None:
    url = "https://www.city.funabashi.lg.jp/jigyou/nyusatsu/001/p900001.html"
    cands = listing.tender_candidates(fixture("funabashi_p146281"), url, FUNABASHI)
    # No PDF on the page reads as a notice, so the page itself is the notice (D-20).
    assert cands[0].format == "html" and cands[0].doc_type == "notice"
    files = {c.url.rsplit("/", 1)[-1]: c for c in cands[1:]}
    assert sorted(files) == sorted(
        ["result.pdf", "answers.pdf", "spec.pdf", "questions.docx",
         "entry_form.docx", "guidelines.pdf", "criteria.pdf"]
    )  # fmt: skip
    assert files["spec.pdf"].title_ja == "架空市図書予約システム導入業務仕様書"
    assert files["spec.pdf"].doc_type == "spec"
    assert files["criteria.pdf"].doc_type == "evaluation_criteria"
    assert {c.bundle_id for c in cands} == {"funabashi:p900001"}
    assert all(c.license_class == "restricted" for c in cands)


def test_group_a_funabashi_index_links() -> None:
    client = FixtureClient({FUNABASHI.listing_urls[0]: fixture("funabashi_index")})
    links = listing.tender_links(client, FUNABASHI)
    assert len(links) == 31
    assert links[0].endswith("/jigyou/nyusatsu/001/p900131.html")


def test_group_a_wakayama_listing_keeps_only_the_tender_section() -> None:
    client = FixtureClient({WAKAYAMA.listing_urls[0]: fixture("wakayama_listing")})
    links = listing.tender_links(client, WAKAYAMA)
    assert len(links) > 100
    # Other agencies' pages (later <h2> sections, other hosts) are left out.
    assert all(u.startswith("https://www.pref.wakayama.lg.jp/prefg/") for u in links)
    assert WAKAYAMA_IT_PAGE in links


def test_group_a_wakayama_page_with_pdf_notice() -> None:
    cands = listing.tender_candidates(
        fixture("wakayama_d00222761"), WAKAYAMA_IT_PAGE, WAKAYAMA
    )
    by_title = {c.title_ja: c for c in cands[1:]}
    assert by_title["入札公告"].doc_type == "notice"
    assert by_title["入札説明書"].doc_type == "bid_instructions"
    # A PDF notice exists, so the page itself is the tender page around it.
    assert (cands[0].format, cands[0].doc_type) == ("html", "tender_page")
    assert all(c.license_class == "open" for c in cands)


def test_group_b_okayama_page() -> None:
    url = "https://www.pref.okayama.jp/site/321/1055020.html"
    cands = listing.tender_candidates(fixture("okayama_1055020"), url, OKAYAMA)
    types = {c.title_ja: (c.format, c.doc_type) for c in cands[1:]}
    # Link text "入札公告  [PDFファイル／193KB]" is cleaned to the title.
    assert types["入札公告"] == ("pdf", "notice")
    assert types["入札説明書"] == ("pdf", "bid_instructions")
    assert types["仕様書"] == ("pdf", "spec")
    assert {c.bundle_id for c in cands} == {"okayama_pref:1055020"}


def test_hokkaido_page_has_notice_pdf_and_zip() -> None:
    url = "https://www.pref.hokkaido.lg.jp/sm/kmc/267662.html"
    cands = listing.tender_candidates(fixture("hokkaido_267662"), url, HOKKAIDO)
    formats = [c.format for c in cands[1:]]
    assert "zip" in formats
    notice = next(c for c in cands if c.format == "pdf" and c.doc_type == "notice")
    assert notice.title_ja.startswith("北海道告示第11341号")
    assert cands[0].doc_type == "tender_page"


def test_listing_skips_pages_robots_disallows() -> None:
    page = b'<div id="main"><a href="/x/d1.html">a</a><a href="/x/d2.html">b</a></div>'

    class Client(FixtureClient):
        def get_page(self, url: str) -> bytes:
            if url.endswith("d1.html"):
                raise DisallowedError(url)
            return super().get_page(url)

    site = replace(
        FUNABASHI, listing_urls=("https://t.test/list",), tender_href=r"/d\d+\.html$"
    )
    client = Client({"https://t.test/list": page}, default_detail=b"<h1>t</h1>")
    assert {c.bundle_id for c in listing.discover(client, site)} == {"funabashi:d2"}
