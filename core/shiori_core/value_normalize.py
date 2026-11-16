"""Deterministic converters for dates, fiscal years, times, deadline flags, amounts
and tax wording (japanese_rules.md sections 2 and 3).

Every `find_*` function takes normalized text (Sentence.text_norm, see normalize.py)
and returns one `Found` per match, in text order, with its span. A converter never
guesses: when the string is incomplete or contradicts itself, `value` is None and
`reason` says why ("no year", "no such day", ...). A date whose weekday disagrees with
the calendar is the one exception (DATE-5): it is returned with its value and a
`WeekdayMismatch` warning holding both readings, since the date itself is exact and
only the weekday is wrong, or the other way round; the verifier decides how to show
it. Map spans back to the original with Sentence.norm_to_orig.
"""

import calendar
import re
from datetime import date, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class WeekdayMismatch(BaseModel):
    """`令和8年3月3日(水)`: the date as written, the weekday that date really falls on,
    and the weekday the text gives. One of the two is a typo; we can't tell which."""

    date: date
    actual_weekday: str  # one of 月火水木金土日
    written_weekday: str


class Found[V](BaseModel):
    start: int
    end: int  # text[start:end] is what matched
    text: str
    value: V | None
    reason: str | None = None  # why value is None
    warning: WeekdayMismatch | None = None  # value is set, but see the warning


class DateRange(BaseModel):
    start: date
    end: date


DeadlineFlag = Literal["arrival_required", "postmark_ok"]
TaxBasis = Literal["tax_included", "tax_excluded"]


def _scan(
    text: str, rules: list[tuple[re.Pattern[str], object]]
) -> list[tuple[re.Match[str], object]]:
    """Non-overlapping matches; earlier rules win where they overlap."""
    taken = [False] * len(text)
    out: list[tuple[re.Match[str], object]] = []
    for rx, tag in rules:
        for m in rx.finditer(text):
            if m.end() > m.start() and not any(taken[m.start() : m.end()]):
                out.append((m, tag))
                for k in range(m.start(), m.end()):
                    taken[k] = True
    return sorted(out, key=lambda mt: mt[0].start())


# --- dates (DATE-1 to DATE-5) -------------------------------------------------

# (name, first day, offset: gregorian year = era year + offset)
ERAS = {
    "令和": (date(2019, 5, 1), 2018),
    "平成": (date(1989, 1, 8), 1988),
    "昭和": (date(1926, 12, 25), 1925),
    "大正": (date(1912, 7, 30), 1911),
    "明治": (date(1868, 1, 25), 1867),  # ponytail: 1868-01-25 = Meiji 1-1-1 (lunar)
}
# Abbreviations (DATE-4). ㋿ and ㍻ are already 令和 and 平成 after NFKC.
ERA_ABBR = {
    "R": "令和", "H": "平成", "S": "昭和", "令": "令和", "平": "平成", "昭": "昭和"
}  # fmt: skip
WEEKDAYS = "月火水木金土日"  # Monday first, like date.weekday()

_Y = r"(?P<y>\d{1,2}|元)"
_WD = (
    r"(?:\s*\(\s*(?P<wd>[月火水木金土日])(?:曜日?)?"
    r"(?:\s*[・､、,]?\s*(?:祝日?|休日))?\s*\))?"
)
_ERA = r"(?P<era>令和|平成|昭和|大正|明治)"
_BLANK = r"[\s○〇●◯]*"
_M = r"(?P<m>\d{1,2})\s*月"
_DAY = r"(?P<d>\d{1,2})\s*日"
# Tried in order; an earlier rule wins where two overlap. The last four only find
# strings that can't be converted, so the report can count them.
DATE_RULES: list[tuple[re.Pattern[str], object]] = [
    (re.compile(rf"{_ERA}\s*{_Y}\s*年\s*(?:\(\s*(?P<gy2>\d{{4}})\s*年?\s*\)\s*)?"
                rf"{_M}\s*{_DAY}{_WD}"), "era"),
    (re.compile(rf"(?<![A-Za-z])(?P<ab>[RHS令平昭])\.?\s?{_Y}\s?[./]\s?"
                rf"(?P<m>\d{{1,2}})\s?[./]\s?(?P<d>\d{{1,2}})(?![\d./]){_WD}"), "abbr"),
    (re.compile(rf"(?<!\d)(?P<gy>\d{{4}})\s*(?:年\s*{_M}\s*{_DAY}"
                rf"|/(?P<m2>\d{{1,2}})/(?P<d2>\d{{1,2}})(?![\d/])){_WD}"), "western"),
    (re.compile(rf"{_ERA}\s*{_Y}\s*年\s*{_M}\s*(?P<eom>末日?)"), "eom"),
    (re.compile(rf"(?:令和|平成)\s*(?:\d{{1,2}}|元)?{_BLANK}年{_BLANK}月{_BLANK}日"),
     "blank date (form field)"),
    (re.compile(rf"{_ERA}\s*{_Y}\s*年\s*\d{{1,2}}\s*月(?!\s*\d)"),
     "year and month only"),
    (re.compile(r"(?<![\d年度])\d{1,2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日"),
     "year without era"),
    (re.compile(rf"(?<![\d年])\d{{1,2}}\s*月\s*\d{{1,2}}\s*日{_WD}"), "no year"),
]  # fmt: skip


def _era_year(era: str, y: str) -> int:
    return ERAS[era][1] + (1 if y == "元" else int(y))


def _make_date(era: str | None, year: int, m: int, d: int) -> tuple[date | None, str]:
    try:
        value = date(year, m, d)
    except ValueError:
        return None, "no such day"
    if era is not None:
        start = ERAS[era][0]
        later = [s for s, _ in ERAS.values() if s > start]
        if value < start:
            return None, "before era start"  # 令和元年4月30日 (DATE-3)
        if later and value >= min(later):
            return None, "after era end"  # 平成31年6月 (DATE-3)
    return value, ""


def _date_from(
    m: re.Match[str], tag: str
) -> tuple[date | None, str | None, WeekdayMismatch | None]:
    g = m.groupdict()
    if tag not in ("era", "abbr", "western", "eom"):
        return None, tag, None
    era = ERA_ABBR[g["ab"]] if tag == "abbr" else g.get("era")
    if tag == "western":
        year, month = int(g["gy"]), int(g["m"] or g["m2"])
        day = int(g["d"] or g["d2"])
        era = None
    else:
        assert era is not None
        year, month = _era_year(era, g["y"]), int(g["m"])
        if tag == "eom":
            if not 1 <= month <= 12:
                return None, "no such day", None
            day = calendar.monthrange(year, month)[1]  # 3月末 = 31 March
        else:
            day = int(g["d"])
    value, why = _make_date(era, year, month, day)
    if value is None:
        return None, why, None
    if g.get("gy2") and int(g["gy2"]) != value.year:
        return None, "era and western year disagree", None  # 令和8年（2025年）
    wd = g.get("wd")
    if wd and WEEKDAYS[value.weekday()] != wd:  # DATE-5
        return (
            value,
            None,
            WeekdayMismatch(
                date=value, actual_weekday=WEEKDAYS[value.weekday()], written_weekday=wd
            ),
        )
    return value, None, None


def find_dates(text: str) -> list[Found[date]]:
    """Calendar dates: `令和8年10月2日（金）`, `R8.10.2`, `2026年10月2日`,
    `令和9年3月末` (last day of the month). Incomplete ones are returned with
    value None: no year, year and month only, a blank form field. A wrong weekday keeps
    the value and sets `warning` (DATE-5)."""
    out: list[Found[date]] = []
    for m, tag in _scan(text, DATE_RULES):
        value, reason, warning = _date_from(m, str(tag))
        out.append(
            Found[date](
                start=m.start(),
                end=m.end(),
                text=m.group(),
                value=value,
                reason=reason,
                warning=warning,
            )
        )
    return out


# --- fiscal years (DATE-6) ----------------------------------------------------

_FY_LIST = r"(?P<ys>(?:\d{1,2}|元)(?:\s*[・･,、]\s*(?:\d{1,2}|元))*)"
FY_RULES: list[tuple[re.Pattern[str], object]] = [
    (re.compile(rf"(?:{_ERA}|(?P<ab>(?<![A-Za-z])[RH]))\s*{_FY_LIST}\s*年度(?P<end>末)?"),
     "era"),
    (re.compile(r"(?<!\d)(?P<gy>\d{4})\s*年度(?P<end>末)?"), "western"),
    (re.compile(rf"(?:令和|平成){_BLANK}年度"), "blank fiscal year (form field)"),
]  # fmt: skip


def _fy(start_year: int) -> DateRange:
    return DateRange(start=date(start_year, 4, 1), end=date(start_year + 1, 3, 31))


def find_fiscal_years(text: str) -> list[Found[DateRange]]:
    """Japanese fiscal years, 1 April to 31 March: `令和8年度` -> 2026-04-01 to
    2027-03-31. `令和8年度末` is the single day 2027-03-31. A list of consecutive
    years (`令和7・8・9年度`) gives one range. Era limits are not checked here:
    offices write both `平成31年度` and `令和元年度` for FY2019."""
    out: list[Found[DateRange]] = []
    for m, tag in _scan(text, FY_RULES):
        g = m.groupdict()
        value: DateRange | None = None
        reason: str | None = str(tag)
        if tag == "western":
            year = int(g["gy"])
            if 1868 <= year <= 2200:
                value, reason = _fy(year), None
            else:
                reason = "implausible year"  # 0000年度, a template
        elif tag == "era":
            era = g["era"] or ERA_ABBR[g["ab"]]
            years = [_era_year(era, y) for y in re.split(r"\s*[・･,、]\s*", g["ys"])]
            if all(b == a + 1 for a, b in zip(years, years[1:], strict=False)):
                value = DateRange(start=_fy(years[0]).start, end=_fy(years[-1]).end)
                reason = None
            else:
                reason = "fiscal years not consecutive"
        if value is not None and g.get("end"):
            value = DateRange(start=value.end, end=value.end)
        out.append(Found[DateRange](start=m.start(), end=m.end(), text=m.group(),
                                    value=value, reason=reason))  # fmt: skip
    return out


# --- times (DATE-7) -----------------------------------------------------------

TIME_RULES: list[tuple[re.Pattern[str], object]] = [
    (re.compile(r"正午"), "noon"),
    (re.compile(r"(?P<ampm>午前|午後)\s*(?P<h>\d{1,2})\s*時(?!間)"
                r"(?:\s*(?P<mi>\d{1,2})\s*分|\s*(?P<half>半))?"), "ampm"),
    (re.compile(r"(?<![\d:.])(?P<h>\d{1,2})\s*時(?!間)"
                r"(?:\s*(?P<mi>\d{1,2})\s*分|\s*(?P<half>半))?"), "24h"),
    (re.compile(r"(?<![\d:.])(?P<h>\d{1,2}):(?P<mi>\d{2})(?![\d:])"), "24h"),
]  # fmt: skip


def _time_from(m: re.Match[str], tag: str) -> tuple[time | None, str | None]:
    if tag == "noon":
        return time(12, 0), None
    g = m.groupdict()
    h = int(g["h"])
    mi = 30 if g.get("half") else int(g["mi"] or 0)
    if mi > 59:
        return None, "minute out of range"
    if tag == "ampm":
        if h in (0, 12):
            return None, f"ambiguous {g['ampm']}{h}時"  # DATE-7
        if h > 12:
            return None, "hour out of range"
        h += 12 if g["ampm"] == "午後" else 0
    if h == 24 and mi == 0:
        return None, "24:00 (end of day)"
    if h > 23:
        return None, "hour out of range"
    return time(h, mi), None


def find_times(text: str) -> list[Found[time]]:
    """Clock times: `午後3時30分` -> 15:30, `正午`, `17時00分`, `17:00`. `2時間`
    (a duration) is not a time."""
    out: list[Found[time]] = []
    for m, tag in _scan(text, TIME_RULES):
        value, reason = _time_from(m, str(tag))
        out.append(Found[time](start=m.start(), end=m.end(), text=m.group(),
                               value=value, reason=reason))  # fmt: skip
    return out


# --- deadline flags (DATE-8) --------------------------------------------------


def find_deadline_flags(text: str) -> list[Found[DeadlineFlag]]:
    """`必着`: must arrive by the deadline. `消印有効`: the postmark date counts."""
    out: list[Found[DeadlineFlag]] = []
    for m in re.finditer(r"必着|消印有効", text):
        flag: DeadlineFlag = (
            "arrival_required" if m.group() == "必着" else "postmark_ok"
        )
        out.append(
            Found[DeadlineFlag](
                start=m.start(), end=m.end(), text=m.group(), value=flag
            )
        )
    return out


# --- numbers and amounts (NUM-1 to NUM-5) -------------------------------------

KANJI_DIGITS = {
    "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
    "九": 9, "壱": 1, "壹": 1, "弐": 2, "貳": 2, "参": 3, "參": 3,
}  # fmt: skip
SMALL_UNITS = {
    "十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "阡": 1000, "仟": 1000
}  # fmt: skip
BIG_UNITS = {"万": 10**4, "萬": 10**4, "億": 10**8, "兆": 10**12}
_ARABIC = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def parse_number(s: str) -> Decimal:
    """Arabic, kanji, 大字 and mixed numerals: `1億2,345万` -> 123450000,
    `二十五` -> 25, `千二百` -> 1200, `5,000千` -> 5000000, `壱百弐拾萬` -> 1200000.
    Raises ValueError with the reason when the string is not one number."""
    if s and set(s) <= {"〇"}:
        raise ValueError("placeholder")
    total = Decimal(0)
    section = Decimal(0)  # the part below the last 万/億/兆
    cur: Decimal | None = None
    cur_kanji = False  # cur came from kanji digits (二〇二六 is positional)
    last_big = last_small = 10**13
    seen_digit = False
    i = 0
    while i < len(s):
        c = s[i]
        if c.isascii() and (c.isdigit() or c in ",."):
            m = _ARABIC.match(s, i)
            if m is None or cur is not None:
                raise ValueError("bad separators")
            cur = Decimal(m.group().replace(",", ""))
            cur_kanji, seen_digit = False, True
            i = m.end()
            continue
        if c in KANJI_DIGITS:
            if cur is not None and not cur_kanji:
                raise ValueError("mixed arabic and kanji digits")
            cur = (cur or Decimal(0)) * 10 + KANJI_DIGITS[c]
            cur_kanji = seen_digit = True
        elif c in SMALL_UNITS:
            mult = SMALL_UNITS[c]
            if mult >= last_small:
                raise ValueError("units out of order")
            section += (cur if cur is not None else 1) * mult
            cur, last_small, seen_digit = None, mult, True
        elif c in BIG_UNITS:
            mult = BIG_UNITS[c]
            if mult >= last_big:
                raise ValueError("units out of order")
            section += cur or 0
            if section == 0:
                raise ValueError("no number before 万/億/兆")
            total += section * mult
            section, cur, last_big, last_small = Decimal(0), None, mult, 10**13
        else:
            raise ValueError("not a number")
        i += 1
    if not seen_digit:
        raise ValueError("no digits")
    total += section + (cur or 0)
    return total


_NUM_CHARS = r"[0-9.,〇一二三四五六七八九十拾百佰千阡仟万萬億兆壱壹弐貳参參]"
AMOUNT_RULES: list[tuple[re.Pattern[str], object]] = [
    (re.compile(rf"{_NUM_CHARS}+\s*円"), "amount"),
    (re.compile(r"金\s+円"), "blank amount (form field)"),
    (re.compile(r"[●○◯×＊*]+\s*円"), "placeholder"),
]
# A unit in a table header, `（単位：千円）` or `金額（千円）`, is not an amount.
_UNIT_LABEL = re.compile(r"(?:単位\s*[:：]?|[(（:：/])\s*$")


def find_amounts(text: str) -> list[Found[int]]:
    """Yen amounts: `1億2,345万円`, `500万円`, `3.5億円`, `1,100千円`, `壱百萬円`.
    The value is whole yen. Blank form fields (`金　　円`) and placeholders come
    back with value None."""
    out: list[Found[int]] = []
    for m, tag in _scan(text, AMOUNT_RULES):
        start = m.start()
        value: int | None = None
        reason: str | None = str(tag)
        if tag == "amount":
            run = m.group().rstrip("円").rstrip()
            lead = len(run) - len(run.lstrip(",."))
            run, start = run[lead:], start + lead
            if not run:
                continue
            if not re.search(r"[0-9〇一二三四五六七八九壱壹弐貳参參]", run) and (
                _UNIT_LABEL.search(text[:start])
            ):
                continue  # 単位：千円
            try:
                n = parse_number(run)
                if n != n.to_integral_value():
                    reason = "fraction of a yen"
                else:
                    value, reason = int(n), None
            except ValueError as e:
                reason = str(e)
        out.append(Found[int](start=start, end=m.end(), text=text[start : m.end()],
                              value=value, reason=reason))  # fmt: skip
    return out


# --- tax wording (NUM-6) ------------------------------------------------------

_TAX_RATE = r"(?:100分の(?:10|8)|(?:10|8)\s*(?:%|パーセント))"
_CT = r"消費税(?:及び地方消費税)?等?(?:相当額|の額|額)?(?:\s*\d+%)?"
TAX_RULES: list[tuple[re.Pattern[str], object]] = [
    # The amount written already has the 10% added, so it includes tax. Only when the
    # sentence itself says the amount to write is the estimate plus the tax (doc
    # 28ad40ea4b1f p6_s10: 見積もった金額に当該金額の100分の10に相当する額を加算した額を
    # 見積書に記載; doc d40000275df6 p8_s7: ... 加算した金額を記載する). Before the
    # award clause below, which shares its second half.
    (re.compile(r"見積もった(?:契約)?金額に(?:当該金額の)?" + _TAX_RATE
                + r"に相当する(?:金)?額を加算した(?:金)?額を"
                r"(?:(?:見積書|入札書)に)?(?:記載|記入|入力)"),
     "tax_included"),
    # The award clause: the bid is written without tax, and 10% is added to it
    # (doc 2aa7506a..., JMA: 入札書に記載された金額に当該金額の10%に相当する額を加算).
    # Not when the added amount is the one to write down: that is the rule above or,
    # without 見積もった, no answer.
    (re.compile(_TAX_RATE + r"に相当する(?:金)?額を加算"
                r"(?!した(?:金)?額を(?:(?:見積書|入札書)に)?(?:記載|記入|入力))"),
     "tax_excluded"),
    # ... or: write 100/110 of the tax-inclusive price on the bid form.
    (re.compile(r"(?:110|108)分の100に相当する(?:金)?額を入札(?:書に記載|金額と)"),
     "tax_excluded"),
    (re.compile(rf"{_CT}を?(?:含まない|含まず|除いた|除く|別)"), "tax_excluded"),
    (re.compile(rf"{_CT}を?(?:含む|含み|込み?)"), "tax_included"),
    (re.compile(rf"{_CT}を加算"), "tax_excluded"),
    (re.compile(r"税込み?|内税"), "tax_included"),
    (re.compile(r"税抜き?|税別|外税"), "tax_excluded"),
]  # fmt: skip


def find_tax_basis(text: str) -> list[Found[TaxBasis]]:
    """Wording that says whether an amount includes consumption tax. `tax_excluded`
    also covers the standard award clause, where 10% is added to the bid. Which
    amount the wording belongs to is for the caller to decide."""
    out: list[Found[TaxBasis]] = []
    for m, tag in _scan(text, TAX_RULES):
        basis: TaxBasis = "tax_included" if tag == "tax_included" else "tax_excluded"
        out.append(Found[TaxBasis](start=m.start(), end=m.end(), text=m.group(),
                                   value=basis))  # fmt: skip
    return out
