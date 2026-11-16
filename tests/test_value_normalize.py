"""value_normalize converters (japanese_rules.md sections 2 and 3).

Strings are copied from collected documents (doc_id prefix and page in the comment)
and run through normalize() first, as the pipeline does. Cases marked "constructed"
did not occur in the corpus and test a rule's edge."""

from datetime import date, time
from decimal import Decimal

import pytest
from shiori_core.normalize import normalize
from shiori_core.value_normalize import (
    DateRange,
    WeekdayMismatch,
    find_amounts,
    find_dates,
    find_deadline_flags,
    find_fiscal_years,
    find_tax_basis,
    find_times,
    parse_number,
)


def _n(text: str) -> str:
    return normalize(text)[0]


# --- dates ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value", "matched"),
    [
        # DATE-1 + DATE-5, open doc 937425e4 (Digital): Friday 6 Mar 2026.
        (
            "提出期限：令和8年3月6日（金）17時まで",
            date(2026, 3, 6),
            "令和8年3月6日(金)",
        ),
        # doc 2aa7506afc08 (JMA) p2.
        ("令和６年６月５日", date(2024, 6, 5), "令和6年6月5日"),
        # TXT-9 spacing, doc 2a4dacf5624b (Digital) p3.
        ("令和 2 年 12 月 25 日に閣議決定", date(2020, 12, 25), "令和2年12月25日"),
        # DATE-2 元年, doc 74aed2a543b8 (Digital) p1.
        ("（令和元年12月20日閣議決定）", date(2019, 12, 20), "令和元年12月20日"),
        # 平成31年 before the era change, doc d313a5093ec9 (Digital) p4.
        (
            "（平成31年４月18日各府省情報化統括責任者",
            date(2019, 4, 18),
            "平成31年4月18日",
        ),
        # DATE-4 abbreviations, doc fd1a4b7d9a7a (Digital) p22 and p2.
        ("R8.2.13", date(2026, 2, 13), "R8.2.13"),
        ("R7/11/7", date(2025, 11, 7), "R7/11/7"),
        # 曜日 spelled out, doc 4397a1092113 p2.
        (
            "令和8年10月16日（金曜日）午後4時までに",
            date(2026, 10, 16),
            "令和8年10月16日(金曜日)",
        ),
        # Western year with the era in brackets (DATE-4), constructed.
        ("令和8年（2026年）10月2日", date(2026, 10, 2), "令和8年(2026年)10月2日"),
        ("2026年10月2日", date(2026, 10, 2), "2026年10月2日"),
        # 末 = last day of the month, constructed from the 年度末 pattern.
        ("令和9年2月末まで", date(2027, 2, 28), "令和9年2月末"),
    ],
)
def test_dates_convert(text: str, value: date, matched: str) -> None:
    found = find_dates(_n(text))
    assert [(f.text, f.value, f.reason) for f in found] == [(matched, value, None)]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("令和元年4月30日", "before era start"),  # DATE-3, constructed
        ("平成31年6月1日", "after era end"),  # DATE-3, constructed
        ("令和7年2月29日", "no such day"),  # constructed
        ("令和8年（2025年）10月2日", "era and western year disagree"),  # constructed
        # Blank form fields: doc 0f7b9667dcd5 (Wakayama contract) p1, doc
        # 75a0c52799f9 (Digital draft contract) p1.
        ("契約期間は、令和８年 月 日から", "blank date (form field)"),
        ("令和  年  月  日", "blank date (form field)"),
        ("令和8年3月", "year and month only"),
        # Month and day only, doc ab5e74f19ac1 (Yokosuka) p7.
        ("11月21日（金）９時～17時", "no year"),
        ("8年10月2日", "year without era"),  # constructed
    ],
)
def test_dates_that_do_not_convert_say_why(text: str, reason: str) -> None:
    found = find_dates(_n(text))
    assert [(f.value, f.reason) for f in found] == [(None, reason)]


def test_weekday_mismatch_keeps_the_date_and_warns_with_both_readings() -> None:
    # DATE-5, constructed: 2 October 2026 is a Friday.
    [f] = find_dates(_n("令和8年10月2日（木）"))
    assert (f.value, f.reason) == (date(2026, 10, 2), None)
    assert f.warning == WeekdayMismatch(
        date=date(2026, 10, 2), actual_weekday="金", written_weekday="木"
    )


def test_weekday_mismatch_in_a_real_range() -> None:
    # doc 4a654d8861b5 (not open: string kept short): 3 March 2026 was a Tuesday, the
    # text says 水; the second date is right.
    found = find_dates(_n("令和8年3月3日(水)から令和8年3月16日(月)"))
    assert [f.value for f in found] == [date(2026, 3, 3), date(2026, 3, 16)]
    assert found[0].warning == WeekdayMismatch(
        date=date(2026, 3, 3), actual_weekday="火", written_weekday="水"
    )
    assert found[1].warning is None


def test_a_range_gives_two_dates_and_never_borrows_the_year() -> None:
    # doc 2aa7506afc08 (JMA) p1-style range; the second date has no year of its
    # own, and taking it from the first would be a guess.
    found = find_dates(_n("令和７年12月８日～12月10日"))
    assert [(f.value, f.reason) for f in found] == [
        (date(2025, 12, 8), None),
        (None, "no year"),
    ]


def test_spans_point_into_the_text() -> None:
    text = _n("提出期限 令和８年3月6日（金） 17 時必着")  # doc c8448fb9a328 p3
    [f] = find_dates(text)
    assert text[f.start : f.end] == f.text == "令和8年3月6日(金)"


# --- fiscal years -----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        # DATE-6, doc 2ed05ba95b66 p1.
        ("この業務に係る令和７年度の予算は", date(2025, 4, 1), date(2026, 3, 31)),
        # 年度末 is the last day, doc d69caea0a2c2 (Digital) p1.
        ("令和8年度末頃の本格リリース", date(2027, 3, 31), date(2027, 3, 31)),
        # Abbreviated era, doc 72cf89b9a2b7 (Wakayama) p1.
        ("R7年度の対象市町村", date(2025, 4, 1), date(2026, 3, 31)),
        # Three consecutive years, doc 2aa7506afc08 (JMA) p3.
        ("令和４･５･６年度国土交通省競争参加資格", date(2022, 4, 1), date(2025, 3, 31)),
        # Western fiscal year, doc 10be3ae3df34 (Digital) p2.
        ("（2025年度）から", date(2025, 4, 1), date(2026, 3, 31)),
    ],
)
def test_fiscal_years(text: str, start: date, end: date) -> None:
    [f] = find_fiscal_years(_n(text))
    assert f.value == DateRange(start=start, end=end)


def test_fiscal_year_problems() -> None:
    assert [f.reason for f in find_fiscal_years(_n("令和○年度に"))] == [
        "blank fiscal year (form field)"
    ]
    assert [f.reason for f in find_fiscal_years("令和7・9年度")] == [
        "fiscal years not consecutive"
    ]
    assert find_fiscal_years("1年度目以降") == []  # "from the first year", no era
    assert [f.reason for f in find_fiscal_years("0000年度")] == ["implausible year"]


# --- times ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "values"),
    [
        (
            "令和８年９月18日（金）午後５時00分   企画提案書提出期限",
            [time(17, 0)],
        ),  # open doc d4000027 (Wakayama)
        ("12時（正午）必着", [time(12, 0), time(12, 0)]),  # doc b04d58bd9f93 p3
        ("令和８年3月6日（金） 17 時必着", [time(17, 0)]),  # doc c8448fb9a328 p3
        # doc ab5e74f19ac1 (Yokosuka) p6: hours and the lunch break.
        (
            "※８時30分～17時（12時～13時を除く）",
            [time(8, 30), time(17), time(12), time(13)],
        ),
        ("R8.3.1 の13:00-15:00 に臨時メンテ", [time(13), time(15)]),  # fd1a4b7d9a7a
        ("午後3時半", [time(15, 30)]),  # constructed
    ],
)
def test_times(text: str, values: list[time]) -> None:
    assert [f.value for f in find_times(_n(text))] == values


def test_durations_are_not_times() -> None:
    # doc 47fcd6f239bc (JMA) p1: 24時間通年 = "24 hours, all year".
    assert find_times("24時間通年の確実な稼動") == []


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("午前0時", "ambiguous 午前0時"),  # DATE-7, constructed
        ("午後12時", "ambiguous 午後12時"),
        ("24時まで", "24:00 (end of day)"),
        ("25時", "hour out of range"),
    ],
)
def test_ambiguous_times(text: str, reason: str) -> None:
    assert [(f.value, f.reason) for f in find_times(text)] == [(None, reason)]


# --- deadline flags ---------------------------------------------------------


def test_deadline_flags() -> None:
    # DATE-8: doc e81e9338bfca (Asahikawa) p8 and doc bc1edf9db02c (Funabashi) p3.
    assert [f.value for f in find_deadline_flags("郵送（当日消印有効）")] == [
        "postmark_ok"
    ]
    assert [f.value for f in find_deadline_flags("令和8年5月25日 17時 (必着)")] == [
        "arrival_required"
    ]


# --- numbers and amounts ----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("二十五", 25),  # NUM-2
        ("三百六", 306),
        ("千二百", 1200),
        ("十", 10),
        ("二〇二六", 2026),  # positional kanji digits
        ("1億2,345万", 123_450_000),  # NUM-3
        ("500万", 5_000_000),
        ("3.5億", 350_000_000),
        ("一千万", 10_000_000),
        ("壱百弐拾萬", 1_200_000),  # NUM-4 大字
        ("5,000千", 5_000_000),
        ("123,450,000", 123_450_000),  # NUM-5
    ],
)
def test_parse_number(text: str, value: int) -> None:
    assert parse_number(text) == Decimal(value)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("1,23", "bad separators"),
        ("万", "no number before 万/億/兆"),
        ("1万2億", "units out of order"),
        ("百千", "units out of order"),
        ("5二", "mixed arabic and kanji digits"),
        ("〇〇", "placeholder"),
    ],
)
def test_parse_number_refuses(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        parse_number(text)


@pytest.mark.parametrize(
    ("text", "matched", "value"),
    [
        # doc 2ed05ba95b66 p1.
        ("令和７年度の予算は、47,179,000円（消費税及び", "47,179,000円", 47_179_000),
        # 千円 units, doc 8869632bb85c p1.
        ("（３）見積上限額 金1,100千円（消費税", "1,100千円", 1_100_000),
        # 万 and 億 mixed with digits, doc b8feb4d29162 p22.
        ("契約金額が300万円を超え1億円までの委託", "300万円", 3_000_000),
        ("年額3,619,200円（税抜）以下", "3,619,200円", 3_619_200),  # 325ad77bb521
        ("1億2,345万円", "1億2,345万円", 123_450_000),  # NUM-3, constructed
        ("金壱百弐拾萬円也", "壱百弐拾萬円", 1_200_000),  # NUM-4, constructed
        ("100 円未満", "100円", 100),  # TXT-9, doc 10be3ae3df34 p5
    ],
)
def test_amounts(text: str, matched: str, value: int) -> None:
    found = find_amounts(_n(text))
    assert [(f.text, f.value) for f in found][0] == (matched, value)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        # Blank form fields, doc 0f7b9667dcd5 (Wakayama contract) p1.
        ("契約保証金は、金     円とする。", "blank amount (form field)"),
        # Placeholder, doc 756d17c84006 (Digital) p33.
        ("契約金額(税込) ●円", "placeholder"),
        ("数万円", "no number before 万/億/兆"),
        ("1.5円", "fraction of a yen"),
    ],
)
def test_amounts_that_do_not_convert(text: str, reason: str) -> None:
    assert [(f.value, f.reason) for f in find_amounts(_n(text))] == [(None, reason)]


def test_unit_labels_are_not_amounts() -> None:
    assert find_amounts(_n("（単位：千円）")) == []
    assert find_amounts(_n("金額（千円）")) == []


# --- tax basis ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "basis"),
    [
        # NUM-6 award clause, doc 2f2f5bd33296 p2.
        (
            "入札書に記載された金額に当該金額の100分の10に相当する額を加算した金額",
            "tax_excluded",
        ),
        # The same clause with 10%, doc 2aa7506afc08 (JMA) p3.
        (
            "入札書に記載された金額に当該金額の10％に相当する額を加算した金額",
            "tax_excluded",
        ),
        # Spelled out, doc f19cddbd4cba (MOJ) h_s36.
        (
            "入札書に記載された金額に当該金額の10パーセントに相当する額を加算した金額",
            "tax_excluded",
        ),
        # doc d40000275df6 p8_s7: the form is not named, the amount written has the 10%.
        (
            "見積もった金額に100分の10に相当する額を加算した金額を記載すること。",
            "tax_included",
        ),
        (
            "見積もった契約金額の110分の100に相当する金額を入札書に記載すること。",
            "tax_excluded",
        ),
        # doc 88d80c6c71c6 p3.
        (
            "消費税及び地方消費税の額を含まない金額を入札書に入力すること。",
            "tax_excluded",
        ),
        # doc 2ed05ba95b66 p1.
        ("47,179,000円（消費税及び地方消費税の額を含む。）", "tax_included"),
        # doc 8869632bb85c p1.
        ("金1,100千円（消費税及び地方消費税の額10％を含む。）", "tax_included"),
        ("年額3,619,200円（税抜）以下とする。", "tax_excluded"),  # 325ad77bb521
        ("契約金額(税込) ●円", "tax_included"),  # 756d17c84006 p33
        # doc 28ad40ea4b1f p6_s10: the 10% is added before the amount is written.
        (
            "消費税及び地方消費税に係る課税事業者であるか免税事業者であるかに関わらず、"
            "見積もった金額に当該金額の１００分の１０に相当する額を加算した額を見積書に記載してください。",
            "tax_included",
        ),
    ],
)
def test_tax_basis(text: str, basis: str) -> None:
    assert [f.value for f in find_tax_basis(_n(text))] == [basis]


@pytest.mark.parametrize(
    "text",
    [
        # Tax added at the contract, not on the bid form.
        "入札金額に基づき契約金額を定め、契約締結時に当該金額の100分の10を加算する。",
        # An amount to write down, but nothing says it is the estimate.
        "金額に100分の10に相当する額を加算した額を記載すること。",
        # 加算 about something other than consumption tax (late-payment charge).
        "遅延日数に応じて年利3パーセントを加算した額を支払う。",
        "見積もった金額に年3パーセントの割合を加算した金額を記載すること。",
    ],
)
def test_addition_wording_that_is_not_the_estimate_plus_tax_stays_unanswered(
    text: str,
) -> None:
    assert find_tax_basis(_n(text)) == []


def test_performance_bond_percentage_is_not_tax() -> None:
    # 10% of the contract price as a performance bond: not about tax.
    text = _n("契約金額の100分の10に相当する額以上の契約保証金を納付すること。")
    assert find_tax_basis(text) == []
