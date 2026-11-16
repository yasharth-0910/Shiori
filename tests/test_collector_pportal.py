"""p-portal adapter against saved pages in tests/fixtures/collector/. Never live."""

from pathlib import Path

import pytest

pytest.importorskip("bs4")  # "collector" dependency group

from collector.collect import Candidate  # noqa: E402
from collector.sources import pportal  # noqa: E402
from collector.sources.pportal import Hit  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "collector"
SEARCH = (FIXTURES / "pportal_search_sys.html").read_bytes()  # システム, 6 of 236 rows
NOTICE = (FIXTURES / "pportal_notice_331517.html").read_bytes()  # WTO, 総務省
HIT_331517 = Hit("0000000000000331517", "from search", "総務省")


class FakeClient:
    """Serves the fixtures and records every request."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_page(self, url: str) -> bytes:
        self.calls.append(("page", url))
        if "anken=0000000000000331517" in url:
            return NOTICE
        return "<p>該当する調達案件情報が存在しません。</p>".encode()

    def get_bytes(self, url: str) -> bytes:
        self.calls.append(("bytes", url))
        return SEARCH

    def post(self, url: str, data: dict[str, str | list[str]]) -> bytes:
        self.calls.append(("post", url))
        assert data["_csrf"] == "test-token"
        assert data[
            "searchConditionBean.procurementClaBean.procurementImplementNotice"
        ] == ["05", "10"]
        return SEARCH


def test_search_results_rows_and_count() -> None:
    assert pportal.result_count(SEARCH) == 236
    hits = pportal.result_hits(SEARCH)
    assert len(hits) == 6
    assert hits[1] == Hit(
        "0000000000000331517",
        "恩給事務総合システムのガバメントクラウドへの移行に係る作業の請負",
        "総務省",
    )


def test_search_follows_result_pages_of_the_session() -> None:
    client = FakeClient()
    hits = list(pportal.search(client, "システム"))
    # 236 hits at 50 per page: the POST returns page 0, then pages 1 to 4 by GET.
    assert [kind for kind, _ in client.calls] == ["bytes", "post"] + ["bytes"] * 4
    assert client.calls[-1][1].endswith("OAA0106?page=4&size=50")
    assert len(hits) == 6 * 5


def test_notice_page_gives_open_html_notice_with_wto_and_summary() -> None:
    hit = Hit("0000000000000331517", "from search", "総務省")
    c = pportal.notice_candidate(FakeClient(), hit)
    assert c is not None
    assert (c.format, c.doc_type, c.license_class) == ("html", "notice", "open")
    assert (
        c.title_ja == "恩給事務総合システムのガバメントクラウドへの移行に係る作業の請負"
    )
    assert c.issuer_org == "総務省"
    assert str(c.notice_date) == "2022-10-28"  # 公開開始日 令和04年10月28日
    assert c.wto_covered is True  # 一般競争入札の入札公告（WTO対象）
    assert c.has_english_summary is True  # "５　Summary"
    assert c.bundle_id == "p-portal:0000000000000331517"
    assert "chankbn=0&chancnt=0" in c.url


def test_missing_notice_is_skipped() -> None:
    assert pportal.notice_candidate(FakeClient(), Hit("1", "t", "o")) is None


def test_english_summary_heading() -> None:
    assert pportal.has_english_summary(
        "(7) 詳細は入札説明書による。\n５　Summary\n(1) ..."
    )
    assert pportal.has_english_summary("Summary\n(1) Contracting entity")
    # The word in running text is not the section heading.
    assert not pportal.has_english_summary("(3) 調達案件の特質等 see the Summary below")
    assert not pportal.has_english_summary("１　調達内容\n２　競争参加資格")


def test_reiwa_dates() -> None:
    assert str(pportal.reiwa_date("令和04年10月28日")) == "2022-10-28"
    assert str(pportal.reiwa_date("令和元年5月1日")) == "2019-05-01"
    assert pportal.reiwa_date("平成31年4月1日") is None


def test_order_puts_it_first_round_robin() -> None:
    hits = [Hit(f"a{i}", "庁舎清掃業務", "A省") for i in range(3)]
    hits += [Hit(f"b{i}", "会計システム保守", "B省") for i in range(10)]
    hits += [Hit("c0", "データ分析業務", "C庁")]
    ids = [h.anken for h in pportal.order(hits)]
    assert ids[:4] == ["b0", "c0", "b1", "b2"]  # IT round-robin across B and C
    assert ids[-3:] == ["a0", "a1", "a2"]  # non-IT last


def test_pick_caps_kept_notices_per_org_and_refills_after_stubs() -> None:
    hits = [Hit(f"b{i}", "会計システム保守", "B省") for i in range(12)]
    stubs = {"b0", "b3"}
    fetched: list[str] = []

    def fetch(hit: Hit) -> Candidate | None:
        fetched.append(hit.anken)
        if hit.anken in stubs:
            return None
        return pportal.notice_candidate(FakeClient(), HIT_331517)

    kept = pportal.pick(hits, fetch)
    assert len(kept) == pportal.MAX_PER_ORG
    assert fetched == [f"b{i}" for i in range(10)]  # 2 stubs skipped, then cap


def test_stub_notice_is_skipped() -> None:
    class StubClient(FakeClient):
        def get_page(self, url: str) -> bytes:
            body = "<th>公告内容</th><td>別添のとおり。</td>"
            return (
                f'<table class="main-table-pattern1"><tr>{body}</tr></table>'.encode()
            )

    assert pportal.notice_candidate(StubClient(), HIT_331517) is None
