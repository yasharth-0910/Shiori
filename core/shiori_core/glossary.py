# ruff: noqa: E501
"""Fixed Japanese -> English renderings for procurement terms (docs/japanese_rules.md,
section 5, "the glossary the app uses"). A small subset (plus regions): the terms that a model is most
likely to render in several ways. translate.py puts the ones that occur in a sentence into
its prompt. Keep this in step with the table in japanese_rules.md."""

GLOSSARY: dict[str, str] = {
    "入札公告": "Bid notice",
    "一般競争入札": "Open competitive bidding",
    "指名競争入札": "Selective bidding",
    "予算決算及び会計令": "Order for Budgets, Settlement of Accounts and Accounting",
    "随意契約": "Negotiated contract",
    "企画競争": "Proposal competition",
    "総合評価落札方式": "Best-value award (price + technical score)",
    "最低価格落札方式": "Lowest-price award",
    "落札者": "Winning bidder",
    "予定価格": "Ceiling price",
    "入札説明書": "Bid instructions",
    "仕様書": "Specification",
    "提案書": "Proposal",
    "競争参加資格": "Eligibility to bid",
    "全省庁統一資格": "Unified qualification (all ministries)",
    "入札書": "Bid form",
    "受領期限": "Receipt deadline",
    "開札": "Bid opening",
    "入札保証金": "Bid bond",
    "契約保証金": "Performance bond",
    "履行期間": "Performance period",
    "納入期限": "Delivery deadline",
    "支出負担行為担当官": "Contracting officer",
    "契約担当官": "Contracting officer",
    "入札説明会": "Bidders' briefing",
    "電子調達システム": "E-procurement system (GEPS)",
    "指名停止": "Suspension from bidding",
    "暴力団排除": "Exclusion of organized crime groups",
    "再委託": "Subcontracting",
}

# Regions of the unified qualification (全省庁統一資格) and the like. A region is named exactly as
# listed: none added, none dropped. The compound blocks (関東・甲信越) are one name each. 中国 is not
# here: it is also the word for China, and the sentence alone does not say which (docs/decisions.md).
REGIONS: dict[str, str] = {
    "関東・甲信越": "Kanto-Koshinetsu",
    "関東甲信越": "Kanto-Koshinetsu",
    "東海・北陸": "Tokai-Hokuriku",
    "東海北陸": "Tokai-Hokuriku",
    "九州・沖縄": "Kyushu-Okinawa",
    "九州沖縄": "Kyushu-Okinawa",
    "北海道": "Hokkaido",
    "東北": "Tohoku",
    "近畿": "Kinki",
    "四国": "Shikoku",
}

# Official English names of central ministries and agencies, for the Issuer card (D-91). Only these
# eight, none added; matched against the whole extracted issuer value, never inside a longer name
# (a bureau or a prefecture is not listed and shows its Japanese). Keep in step with japanese_rules.md
# section 5 and with ISSUERS in app/src/fieldview.ts.
ISSUERS: dict[str, str] = {
    "法務省": "Ministry of Justice",
    "厚生労働省": "Ministry of Health, Labour and Welfare",
    "総務省": "Ministry of Internal Affairs and Communications",
    "内閣府": "Cabinet Office",
    "農林水産省": "Ministry of Agriculture, Forestry and Fisheries",
    "国土交通省": "Ministry of Land, Infrastructure, Transport and Tourism",
    "気象庁": "Japan Meteorological Agency",
    "出入国在留管理庁": "Immigration Services Agency of Japan",
}


def issuer_en(value_ja: str | None) -> str | None:
    """The official English name when the whole value (spaces ignored) is a listed body, else None."""
    return ISSUERS.get("".join((value_ja or "").split()))


def terms_in(text: str) -> list[tuple[str, str]]:
    """The glossary entries whose Japanese occurs in `text`, longest first."""
    return sorted(
        ((ja, en) for ja, en in {**GLOSSARY, **REGIONS}.items() if ja in text),
        key=lambda t: -len(t[0]),
    )
