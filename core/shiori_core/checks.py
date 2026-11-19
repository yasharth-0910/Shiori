# ruff: noqa: E501
"""The pipeline's own checks on one extracted field (D-82). Each returns True, False, or
None when it does not apply. Moved here from eval/ so the sidecar can store them with
each field; eval/silver/checks.py and eval/validate_labels.py import them from this module.

`answer` is anything with field, status, value_ja, normalized and citations (an
`Extracted`, or the eval harness's `Candidate`). `by_id` maps sentence ids to sentences.
No document text is logged here.
"""

import re
from collections.abc import Callable
from datetime import date, time
from typing import Any, Protocol

from pydantic import ValidationError

from shiori_core.fields import BY_ID, SeeOtherRef, validate_normalized
from shiori_core.models import Sentence
from shiori_core.normalize import normalize
from shiori_core.value_normalize import (
    find_dates,
    find_deadline_flags,
    find_fiscal_years,
    find_tax_basis,
    find_times,
)


class Answer(Protocol):
    @property
    def field(self) -> str: ...
    @property
    def status(self) -> str: ...
    @property
    def value_ja(self) -> str | None: ...
    @property
    def normalized(self) -> dict | None: ...
    @property
    def citations(self) -> list[str]: ...


HEAD_CHARS = 15  # a cue counts at the start of a sentence, or in a section title
SHORT_CUE = 3  # cues this short trigger "both absent" only as a whole heading
_WORD = re.compile(r"[\u3005\u4e00-\u9fff\u30a0-\u30ffー]")  # kanji, 々, katakana
_NUMBERING = re.compile(
    r"^[\s　]*(?:第?[0-9０-９一二三四五六七八九十]+[条.．、]?|[(（][0-9０-９ア-ンa-zａ-ｚ]+[)）]|[ア-ン](?:[.．、]|(?=[\s　])))?[\s　]*"
)
_ELLIPSIS = re.compile(r"…+|⋯+|\.{3,}")

_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|パーセント)")
_PER_HUNDRED = re.compile(r"100分の(\d+(?:\.\d+)?)")
_ONE_IN_N = re.compile(r"(\d+)分の1(?!\d)")


def _strip(s: str) -> str:
    return re.sub(r"\s+", "", s)


# --- values read back through the converters ---


def _dates(ss: list[Sentence]) -> set[date]:
    out: set[date] = set()
    for s in ss:
        out |= {f.value for f in find_dates(s.text_norm) if f.value}
        for fy in find_fiscal_years(s.text_norm):
            if fy.value:
                out |= {fy.value.start, fy.value.end}
    return out


def _times(ss: list[Sentence]) -> set[time]:
    return {f.value for s in ss for f in find_times(s.text_norm) if f.value}


def _rates(ss: list[Sentence]) -> set[float]:
    out: set[float] = set()
    for s in ss:
        t = s.text_norm
        out |= {float(m.group(1)) for m in _PERCENT.finditer(t)}
        out |= {float(m.group(1)) for m in _PER_HUNDRED.finditer(t)}
        out |= {100 / int(m.group(1)) for m in _ONE_IN_N.finditer(t)}
    return out


def _has(ss: list[Sentence], needle: str) -> bool:
    n = re.sub(r"\s+", "", needle)
    return any(
        n in re.sub(r"\s+", "", t) for s in ss for t in (s.text_orig, s.text_norm)
    )


def check_deadline_item(item, ss: list[Sentence]) -> list[str]:
    errs: list[str] = []
    if item.datetime:
        if date.fromisoformat(item.datetime[:10]) not in _dates(ss):
            errs.append(
                f"deadline {item.kind}: date {item.datetime[:10]} not read in citations"
            )
        if len(item.datetime) > 10:
            hh, mm = int(item.datetime[11:13]), int(item.datetime[14:16])
            if time(hh, mm) not in _times(ss):
                errs.append(
                    f"deadline {item.kind}: time {item.datetime[11:16]} not read"
                )
    found = {f.value for s in ss for f in find_deadline_flags(s.text_norm)}
    for flag in item.flags:
        if flag not in found:
            errs.append(f"deadline {item.kind}: flag {flag} not read in citations")
    return errs


def check_values(
    field: str,
    model: Any,
    ss_of: Callable[[list[str]], list[Sentence]],
    cites: list[str],
) -> list[str]:
    """Re-run the converters on the cited sentences. `ss_of` maps ids to sentences."""
    ss = ss_of(cites)
    errs: list[str] = []
    if field in ("notice_date", "delivery_deadline"):
        d = model.date
        if d not in _dates(ss):
            errs.append(f"{field}: {d} not read in citations")
    elif field == "performance_period":
        for part in ("start", "end"):
            d = getattr(model, part)
            if d and d not in _dates(ss):
                errs.append(f"performance_period.{part}: {d} not read in citations")
    elif field == "deadlines":
        for item in model.items:
            errs += check_deadline_item(item, ss_of(item.citations))
    elif field in ("bid_bond", "performance_bond"):
        rate = model.rate_percent
        if rate is not None and not any(abs(rate - r) < 1e-9 for r in _rates(ss)):
            errs.append(f"{field}: rate {rate}% not read in citations")
    elif field == "tax_basis":
        want = "tax_excluded" if model.basis == "bid_excludes_tax" else "tax_included"
        if want not in {f.value for s in ss for f in find_tax_basis(s.text_norm)}:
            errs.append(f"tax_basis: {model.basis} not read in citations")
    elif field == "item_category":
        digits = {m for s in ss for m in re.findall(r"\d+", s.text_norm)}
        errs += [
            f"item_category: code {c} not in citations"
            for c in model.codes
            if c not in digits
        ]
    elif field == "unified_qualification":
        errs += [
            f"unified_qualification: grade {g} not in citations"
            for g in model.grades
            if not any(g in s.text_norm for s in ss)
        ]
    elif field == "contact":
        for part in ("phone", "email"):
            v = getattr(model, part)
            if v and not _has(ss, v):
                errs.append(f"contact.{part} not copied exactly from citations")
    return errs


# --- heading cues ---


def cue_in(cue: str, text: str, limit: int | None = None) -> bool:
    """`cue` occurs in `text` (starting within the first `limit` characters) and not in
    the middle of a longer word: 担当 inside 支出負担行為担当官 has a kanji on both sides
    and does not count. Japanese has no spaces, so a word is a run of kanji or katakana."""
    i = text.find(cue)
    while i != -1 and (limit is None or i < limit):
        j = i + len(cue)
        inside = (
            i > 0
            and j < len(text)
            and _WORD.match(text[i - 1])
            and _WORD.match(text[j])
        )
        if not inside:
            return True
        i = text.find(cue, i + 1)
    return False


def bare_heading(text: str) -> str:
    """A heading without its numbering (１．, (3), ア) and trailing colon."""
    return _NUMBERING.sub("", text).strip().rstrip("：:").strip()


def cue_at_heading(cue: str, s: Sentence) -> bool:
    return any(cue_in(cue, t) for t in s.section_titles) or cue_in(
        cue, s.text_orig, HEAD_CHARS
    )


def cue_is_heading(cue: str, s: Sentence) -> bool:
    """The whole heading is the cue: a section title or a sentence that says only 担当."""
    return any(bare_heading(t) == cue for t in (*s.section_titles, s.text_orig))


# --- checks on one answer ---


def _cited(c: Answer, by_id: dict[str, Sentence]) -> list[Sentence]:
    return [by_id[i] for i in c.citations if i in by_id]


def citations_exist(c: Answer, by_id: dict[str, Sentence]) -> bool | None:
    if c.status == "absent":
        return None
    return bool(c.citations) and all(
        i in by_id and by_id[i].language == "ja" for i in c.citations
    )


def _in_order(parts: list[str], pool: str) -> bool:
    i = 0
    for p in parts:
        j = pool.find(p, i)
        if j < 0:
            return False
        i = j + len(p)
    return True


def _in(text: str, ss: list[Sentence]) -> bool:
    """`text` (after the same normalization the sentences got) occurs in the cited
    sentences, spaces ignored, also across a join of several of them. A quote shortened
    with an ellipsis (… or ...) passes when its pieces occur in that order."""
    parts = [_strip(normalize(x)[0]) for x in _ELLIPSIS.split(text)]
    parts = [p for p in parts if p]
    if not parts:
        return True
    pool = [_strip(s.text_norm) for s in ss] + [_strip(s.text_orig) for s in ss]
    pool.append("".join(_strip(s.text_norm) for s in ss))
    return any(_in_order(parts, p) for p in pool)


def value_in_citation(c: Answer, by_id: dict[str, Sentence]) -> bool | None:
    if c.status != "present":
        return None
    ss = _cited(c, by_id)
    ok = all(_in(p, ss) for p in (c.value_ja or "").split("\n"))
    items = (
        (c.normalized or {}).get("items", []) if BY_ID[c.field].kind == "list" else []
    )
    for it in items:
        text = it.get("text_ja") or it.get("name_ja")
        if text and not _in(
            text, [by_id[i] for i in it.get("citations", []) if i in by_id]
        ):
            ok = False
    return ok


def values_roundtrip(c: Answer, by_id: dict[str, Sentence]) -> bool | None:
    """Dates, times, flags, rates, tax wording, codes, grades, phone and email re-run
    through the converters on the cited sentences (eval.validate_labels.check_values)."""
    if c.status != "present" or BY_ID[c.field].model is None:
        return None
    model = validate_normalized(c.field, c.normalized)
    ss_of = lambda ids: [by_id[i] for i in ids if i in by_id]  # noqa: E731
    return not check_values(c.field, model, ss_of, c.citations)


def label_dates(c: Answer) -> list[date]:
    n = c.normalized or {}
    raw: list[str | None] = []
    if c.field in ("notice_date", "delivery_deadline"):
        raw = [n.get("date")]
    elif c.field == "performance_period":
        raw = [n.get("start"), n.get("end")]
    elif c.field == "deadlines":
        raw = [it.get("datetime") for it in n.get("items", [])]
    out = []
    for r in raw:
        try:
            out.append(date.fromisoformat(r[:10])) if r else None
        except ValueError:
            pass
    return out


def weekday_consistent(c: Answer, by_id: dict[str, Sentence]) -> bool | None:
    """DATE-5: False when a labeled date is one whose written weekday disagrees with
    the calendar. The reviewer decides which part of the source is the typo."""
    ds = set(label_dates(c))
    if c.status != "present" or not ds:
        return None
    warned = {
        f.warning.date
        for s in _cited(c, by_id)
        for f in find_dates(s.text_norm)
        if f.warning
    }
    return not (ds & warned)


def heading_cue(c: Answer, by_id: dict[str, Sentence]) -> bool | None:
    """Soft: a cue of the field is in a cited sentence's section titles or its first
    15 characters, not inside a longer word."""
    cues = BY_ID[c.field].cues
    if c.status == "absent" or not cues:
        return None
    return any(cue_at_heading(k, s) for s in _cited(c, by_id) for k in cues)


def schema_valid(c: Answer) -> bool:
    """The answer fits its field's schema: a present value has text and citations, a
    pointer has a `ref`, and `normalized` validates (a text field has none)."""
    try:
        if c.status == "see_other_document":
            SeeOtherRef.model_validate((c.normalized or {}).get("ref"))
        elif c.status == "present":
            if not (c.value_ja or "").strip() or not c.citations:
                return False
            validate_normalized(c.field, c.normalized)
        else:
            return False
    except (ValidationError, ValueError, KeyError):
        return False
    return True


def run_checks(
    c: Answer, doc_type: str, by_id: dict[str, Sentence]
) -> list[tuple[str, bool]]:
    """(name, passed) for every check that applies to a found field, in a fixed order.
    Same order and names as eval.silver.checks.run_checks, minus era_plausible (needs the
    manifest's notice date) and en_summary_agrees (informational)."""
    out: list[tuple[str, bool | None]] = [("schema_valid", schema_valid(c))]
    if out[0][1]:
        applies = doc_type in BY_ID[c.field].applies_to
        out += [
            ("citations_exist", citations_exist(c, by_id)),
            ("field_applicable", applies),
        ]
        if applies:
            out += [
                ("value_in_citation", value_in_citation(c, by_id)),
                ("values_roundtrip", values_roundtrip(c, by_id)),
                ("weekday_consistent", weekday_consistent(c, by_id)),
                ("heading_cue", heading_cue(c, by_id)),
            ]
    return [(n, bool(v)) for n, v in out if v is not None]
