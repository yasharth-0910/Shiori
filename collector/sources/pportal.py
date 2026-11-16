"""調達ポータル (p-portal) notices as HTML (D-18). License 政府標準利用規約 2.0, "open".

The public search (a POST form with a session cookie and CSRF token, no JavaScript
needed) finds 一般競争入札 notices; each notice is then fetched by its GET permalink
and saved as served. One notice per bundle, keyed by 調達案件番号. The bid documents
sit on GEPS behind a contact form and are out of scope (D-15).

Order: IT notices first (a cue in the title), spread across issuing organizations
round-robin, at most MAX_PER_ORG kept per organization. Notices whose body is only a
pointer to an attachment ("別添のとおり") are skipped: the real text is on GEPS.
"""

import math
import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from bs4 import BeautifulSoup, Tag

from collector.collect import Candidate

SOURCE = "p-portal"
BASE_URL = "https://www.p-portal.go.jp/pps-web-biz/UAA01"
SEARCH_PAGE_URL = f"{BASE_URL}/OAA0101"
SEARCH_POST_URL = f"{BASE_URL}/OAA0100"
RESULTS_URL = BASE_URL + "/OAA0106?page={page}&size=50"
# cla=3: the 調達実施案件公示 column. chankbn=0, chancnt=0: the original notice, not a
# correction (訂正公告). lan=1: Japanese. Found in Digital Agency's links to p-portal.
PERMALINK = BASE_URL + "/OAA0122?anken={anken}&cla=3&chankbn=0&chancnt=0&lan=1"
LICENSE_NOTE = (
    "政府標準利用規約 第2.0版 (CC BY 4.0 compatible), checked "
    "https://www.p-portal.go.jp/pps-web-biz/resources/app/html/sitepolicy.html "
    "2026-10-02"
)

# Title words that mark an IT notice (part E brief). 運用 and 保守 also match
# building and equipment maintenance, so "IT" here is an upper bound.
IT_CUES = (
    "システム",
    "運用",
    "保守",
    "開発",
    "構築",
    "クラウド",
    "データ",
    "ソフトウェア",
)
MAX_PER_ORG = 8
MAX_NOTICES = 150  # notices kept per run; later pages are not fetched
# Shorter notice bodies are stubs like "別添のとおり。" (6 to 108 chars in the dry run,
# 2026-10-02); real notices there started at about 1,000.
MIN_NOTICE_CHARS = 200
NOTICE_TYPES = {"05": True, "10": False}  # 一般競争入札の入札公告: WTO対象 / 対象外
MAX_HITS = 500  # p-portal shows at most this many results per search


class SearchClient(Protocol):
    def get_page(self, url: str) -> bytes: ...
    def get_bytes(self, url: str) -> bytes: ...
    def post(self, url: str, data: dict[str, str | list[str]]) -> bytes: ...


@dataclass(frozen=True)
class Hit:
    anken: str  # 19-digit 調達案件番号
    title: str
    org: str  # 調達機関, as listed: the ministry or agency


def discover(client: SearchClient) -> list[Candidate]:
    hits: dict[str, Hit] = {}
    for keyword in ("", *IT_CUES):  # "" = every notice, for non-IT and the total
        for hit in search(client, keyword):
            hits.setdefault(hit.anken, hit)
    print(
        f"p-portal: {len(hits)} notices found, "
        f"{len({h.org for h in hits.values()})} orgs, "
        f"{sum(is_it(h.title) for h in hits.values())} IT by title"
    )
    fetched = 0

    def fetch(hit: Hit) -> Candidate | None:
        nonlocal fetched
        fetched += 1
        return notice_candidate(client, hit)

    candidates = pick(order(list(hits.values())), fetch)
    with_summary = sum(bool(c.has_english_summary) for c in candidates)
    print(
        f"p-portal: kept {len(candidates)} of {fetched} notice pages fetched "
        f"(others were stubs or gone), {len({c.issuer_org for c in candidates})} "
        f"orgs, English Summary in {with_summary}"
    )
    return candidates


def search(client: SearchClient, keyword: str) -> Iterator[Hit]:
    """Every result of one search for active 一般競争入札 notices (WTO and not)."""
    form = _csrf_form(client.get_bytes(SEARCH_PAGE_URL))
    form |= {
        "searchConditionBean.caseDivision": "0",  # 公開中の調達案件
        "searchConditionBean.cla": "01",  # all categories
        "searchConditionBean.synonymClassification": "01",  # exact words only
        "searchConditionBean.articleNm": keyword,
        "searchConditionBean.procurementClaBean.procurementImplementNotice": list(
            NOTICE_TYPES
        ),
        "OAA0102": "検索",
    }
    page = client.post(SEARCH_POST_URL, form)  # redirects to results page 0
    pages = math.ceil(min(result_count(page), MAX_HITS) / 50)
    yield from result_hits(page)
    for n in range(1, pages):  # result pages follow the session's last search
        yield from result_hits(client.get_bytes(RESULTS_URL.format(page=n)))


def result_count(page: bytes) -> int:
    """From "検索結果 236 件見つかりました"."""
    m = re.search(r"検索結果\s*([\d,]+)\s*件", _text(page))
    return int(m[1].replace(",", "")) if m else 0


def result_hits(page: bytes) -> list[Hit]:
    """Rows that have an original 調達実施案件公示 (the `koukoku` button)."""
    soup = BeautifulSoup(page, "html.parser")
    hits: list[Hit] = []
    for row in soup.select("table.main-summit-info > tbody > tr"):
        cells = {
            str(td.get("id", "")).rsplit("/", 1)[-1]: td
            for td in row.find_all("td", recursive=False)
        }
        notice = cells.get("procurementImplementNoticeBean")
        if notice is None or notice.select_one("a.koukoku") is None:
            continue
        hits.append(
            Hit(
                anken=cells["procurementItemNo"].get_text(strip=True),
                title=cells["articleNm"].get_text(" ", strip=True),
                org=cells["procurementOrgan"].get_text(strip=True),
            )
        )
    return hits


def is_it(title: str) -> bool:
    return any(cue in title for cue in IT_CUES)


def order(hits: list[Hit]) -> list[Hit]:
    """IT first, then round-robin across orgs (each org's 1st notice, then 2nd, ...).
    Stable, so search order breaks ties."""
    rank: Counter[str] = Counter()
    keyed: list[tuple[bool, int, Hit]] = []
    for hit in sorted(hits, key=lambda h: not is_it(h.title)):
        keyed.append((not is_it(hit.title), rank[hit.org], hit))
        rank[hit.org] += 1
    return [hit for *_, hit in sorted(keyed, key=lambda k: k[:2])]


def pick(
    ordered: list[Hit], fetch: Callable[[Hit], Candidate | None]
) -> list[Candidate]:
    """Fetch in order, keeping at most MAX_PER_ORG per org and MAX_NOTICES in all.
    An org at its cap is not fetched any more; a skipped notice frees its slot."""
    kept: list[Candidate] = []
    per_org: Counter[str] = Counter()
    for hit in ordered:
        if len(kept) >= MAX_NOTICES:
            break
        if per_org[hit.org] >= MAX_PER_ORG:
            continue
        if (c := fetch(hit)) is not None:
            kept.append(c)
            per_org[hit.org] += 1
    return kept


def notice_candidate(client: SearchClient, hit: Hit) -> Candidate | None:
    """Fetch the notice page (cached, so the real run re-reads it for free)."""
    url = PERMALINK.format(anken=hit.anken)
    fields = detail_fields(client.get_page(url))
    body = fields.get("公告内容", "")
    if len(body) < MIN_NOTICE_CHARS:  # not found, or a stub pointing to an attachment
        return None
    title = fields.get("調達案件名称", hit.title)
    return Candidate.model_validate(
        {
            "url": url,
            "landing_url": SEARCH_PAGE_URL,
            "issuer_org": fields.get("調達機関", hit.org),
            "title_ja": title,
            "doc_type": "notice",
            "notice_date": reiwa_date(fields.get("公開開始日", "")),
            "format": "html",
            "bundle_id": f"{SOURCE}:{hit.anken}",
            "bundle_title": title,
            "license_note": LICENSE_NOTE,
            "license_class": "open",
            "wto_covered": _wto(fields.get("調達種別", "")),
            "has_english_summary": has_english_summary(body),
        }
    )


def detail_fields(page: bytes) -> dict[str, str]:
    """th -> td text of the 調達情報の詳細 table. Empty if the notice wasn't found."""
    soup = BeautifulSoup(page, "html.parser")
    table = soup.select_one("table.main-table-pattern1")
    fields: dict[str, str] = {}
    if table is None:
        return fields
    for row in table.find_all("tr"):
        assert isinstance(row, Tag)
        tds = row.find_all("td")
        for th in row.find_all("th"):
            td = th.find_next_sibling("td")
            if td is not None and td in tds:
                fields.setdefault(
                    th.get_text(strip=True), td.get_text("\n", strip=True)
                )
    return fields


# "５　Summary" or "Summary" on its own line, after an optional section number.
_SUMMARY_HEADING = re.compile(r"^[\s0-9０-９.．、()（）]*Summary\b", re.MULTILINE)


def has_english_summary(notice_text: str) -> bool:
    """True if the notice body has the English Summary section of WTO notices."""
    return _SUMMARY_HEADING.search(notice_text) is not None


_REIWA = re.compile(r"令和\s*(\d+|元)\s*年\s*(\d+)\s*月\s*(\d+)\s*日")


def reiwa_date(text: str) -> date | None:
    """ "令和04年10月28日" -> 2022-10-28. Reiwa 1 is 2019; other eras give None."""
    m = _REIWA.search(text)
    if not m:
        return None
    year = 1 if m[1] == "元" else int(m[1])
    return date(2018 + year, int(m[2]), int(m[3]))


def _wto(notice_type: str) -> bool | None:
    if "WTO対象外" in notice_type:
        return False
    return True if "WTO対象" in notice_type else None


def _csrf_form(page: bytes) -> dict[str, str | list[str]]:
    token = BeautifulSoup(page, "html.parser").find("input", attrs={"name": "_csrf"})
    assert isinstance(token, Tag), "no CSRF token on the p-portal search page"
    return {"_csrf": str(token["value"])}


def _text(page: bytes) -> str:
    return BeautifulSoup(page, "html.parser").get_text(" ", strip=True)
