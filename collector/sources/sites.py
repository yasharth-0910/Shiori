"""Site configs for the listing adapter, by layout group (see city_survey.md).

License classes come from the survey (D-16). `unknown` stays `unknown` and is treated
as restricted. Restricted and unknown documents are used locally only (D-22).
"""

from collector.sources.listing import Site

# Title words that mark an IT or system tender, for IT-first ordering.
IT_CUES = (
    "システム",
    "ホームページ",
    "サイト",
    "ICT",
    "ＩＣＴ",
    "デジタル",
    "DX",
    "ＤＸ",
    "RPA",
    "ＲＰＡ",
    "アプリ",
    "クラウド",
    "ネットワーク",
    "情報処理",
    "電子計算",
    "端末",
    "サーバ",
    "ソフト",
    "ライセンス",
    "データ",
)

# Layout groups: how a tender page addresses its files.
GROUP_A_FILES = r"_d/fil/[^/]+$"  # p<id>.html or d<id>.html -> <page>_d/fil/<file>
GROUP_B_FILES = r"/uploaded/(attachment|life)/[^/]+$"
HOKKAIDO_FILES = r"/fs/(\d/)+_/[^/]+$"


def _reserved(terms_url: str) -> str:
    return (
        "All rights reserved; no reproduction without permission except private "
        f"use/quotation. Checked {terms_url} 2026-10-02. Local use only (D-22)."
    )


_UNKNOWN = (
    "No conclusive terms found in the city survey 2026-10-02; unknown, treated as "
    "restricted (D-16). Local use only (D-22)."
)

GROUP_A = [
    Site(
        source="funabashi",
        issuer_org="船橋市",
        listing_urls=(
            "https://www.city.funabashi.lg.jp/jigyou/nyusatsu/001/index.html",
        ),
        tender_href=r"/jigyou/nyusatsu/001/p\d+\.html$",
        file_href=GROUP_A_FILES,
        license_class="restricted",
        license_note=_reserved(
            "https://www.city.funabashi.lg.jp/other/0002/p011401.html"
        ),
        it_cues=IT_CUES,
    ),
    Site(
        source="wakayama_pref",
        issuer_org="和歌山県",
        listing_urls=("https://www.pref.wakayama.lg.jp/whatsnew/nyusatsu.html",),
        listing_section="入札・コンペ情報",  # later sections list other agencies
        tender_href=r"/prefg/.+\.html?$",
        file_href=GROUP_A_FILES,
        license_class="open",
        license_note=(
            "和歌山県ホームページ公開情報利用規約 (CC BY 4.0 compatible), checked "
            "https://www.pref.wakayama.lg.jp/prefg/000200/opendata/hpopendatakiyaku.html"
            " 2026-10-02"
        ),
        it_cues=IT_CUES,
    ),
    Site(
        source="asahikawa",
        issuer_org="旭川市",
        listing_urls=(
            "https://www.city.asahikawa.hokkaido.jp/500/565/566/5681/index.html",
            "https://www.city.asahikawa.hokkaido.jp/500/565/566/568/index.html",
        ),
        tender_href=r"/d\d+\.html$",  # p<id> pages here are form collections
        file_href=GROUP_A_FILES,
        license_class="restricted",
        license_note=_reserved(
            "https://www.city.asahikawa.hokkaido.jp/700/723/728/d054673.html"
        ),
        it_cues=IT_CUES,
    ),
    Site(
        source="hachioji",
        issuer_org="八王子市",
        listing_urls=(
            "https://www.city.hachioji.tokyo.jp/jigyosha/001/002/002/index.html",
        ),
        tender_href=r"/p\d+\.html$",
        file_href=GROUP_A_FILES,
        license_class="restricted",
        license_note=_reserved("https://www.city.hachioji.tokyo.jp/987/p012154.html"),
        it_cues=IT_CUES,
    ),
]

GROUP_B = [
    Site(
        source="okayama_pref",
        issuer_org="岡山県",
        listing_urls=("https://www.pref.okayama.jp/site/321/index-2.html",),
        tender_href=r"/site/[^/]+/\d+\.html$",
        file_href=GROUP_B_FILES,
        license_class="open",
        license_note=(
            "公共データ利用規約 第1.0版 (PDL1.0), checked "
            "https://www.pref.okayama.jp/page/detail-4318.html 2026-10-02"
        ),
        it_cues=IT_CUES,
    ),
    Site(
        source="koriyama",
        issuer_org="郡山市",
        listing_urls=(
            "https://www.city.koriyama.lg.jp/site/keiyakuportal/list87-226.html",
        ),
        tender_href=r"/site/keiyakuportal/\d+\.html$",
        file_href=GROUP_B_FILES,
        license_class="unknown",
        license_note=_UNKNOWN,
        it_cues=IT_CUES,
    ),
    Site(
        source="nara_city",
        issuer_org="奈良市",
        listing_urls=("https://www.city.nara.lg.jp/life/5/35/index-2.html",),
        tender_href=r"/soshiki/\d+/\d+\.html$",
        file_href=GROUP_B_FILES,
        license_class="restricted",
        license_note=_reserved("https://www.city.nara.lg.jp/site/userguide/8771.html"),
        it_cues=IT_CUES,
    ),
    Site(
        source="niigata_pref",
        issuer_org="新潟県",
        listing_urls=("https://www.pref.niigata.lg.jp/life/sub/8/",),
        tender_href=r"/(sec|site)/[^/]+/[^/]+\.html$",
        file_href=GROUP_B_FILES,
        license_class="restricted",
        license_note=_reserved(
            "https://www.pref.niigata.lg.jp/site/userguide/chosakuken.html"
        ),
        it_cues=IT_CUES,
    ),
]

# One site only: the notice is a PDF, everything else is one ZIP per tender (D-21).
# Documents are taken down after bid opening, so only active tenders have files.
HOKKAIDO = Site(
    source="hokkaido",
    issuer_org="北海道",
    listing_urls=(
        "https://www.pref.hokkaido.lg.jp/sm/kmc/a0005/b01/",  # 委託 (consignment)
        "https://www.pref.hokkaido.lg.jp/sm/kmc/a0001/b0001/",  # 物品 (goods)
    ),
    tender_href=r"/sm/kmc/\d+\.html$",
    file_href=HOKKAIDO_FILES,
    license_class="open",
    license_note=(
        "CC BY (all pages open data unless stated otherwise), checked "
        "https://www.pref.hokkaido.lg.jp/site-info/sitepolicy.html 2026-10-02"
    ),
    it_cues=IT_CUES,
)

ALL = [*GROUP_A, *GROUP_B, HOKKAIDO]
