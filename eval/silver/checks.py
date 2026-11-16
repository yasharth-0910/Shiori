# ruff: noqa: E501
"""Automatic checks on one candidate label (D-43). Each returns True, False, or None
when it does not apply. `BLOCKING` ones stop a field from being accepted automatically;
`HARD` ones also stop a reviewer's answer from being imported. The rest are advisory."""

import json
import re
from datetime import date, timedelta

from pydantic import ValidationError
from shiori_core.fields import BY_ID, validate_normalized
from shiori_core.models import Sentence
from shiori_core.normalize import normalize
from shiori_core.value_normalize import find_dates

from collector.manifest import ManifestRow
from eval.label_format import LabelLine, Provenance
from eval.silver.model import Candidate, from_row
from eval.silver.prompt import rows_of
from eval.validate_labels import check_values

HARD = ("schema_valid", "citations_exist", "value_in_citation", "values_roundtrip")
BLOCKING = (*HARD, "field_applicable", "era_plausible", "weekday_consistent")
ERA_YEARS = 5
HEAD_CHARS = 15  # a cue counts at the start of a sentence, or in a section title
SHORT_CUE = 3  # cues this short trigger "both absent" only as a whole heading
_WORD = re.compile(r"[\u3005\u4e00-\u9fff\u30a0-\u30ffー]")  # kanji, 々, katakana
_NUMBERING = re.compile(
    r"^[\s　]*(?:第?[0-9０-９一二三四五六七八九十]+[条.．、]?|[(（][0-9０-９ア-ンa-zａ-ｚ]+[)）]|[ア-ン](?:[.．、]|(?=[\s　])))?[\s　]*"
)
_ELLIPSIS = re.compile(r"…+|⋯+|\.{3,}")


def _strip(s: str) -> str:
    return re.sub(r"\s+", "", s)


# --- heading cues (step 6 of sv2) --------------------------------------------------------


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


def line_dict(c: Candidate, row: ManifestRow | None) -> dict:
    return {
        "doc_id": row.doc_id if row else "x",
        "extractor_version": "x",
        "schema_version": "1.0.0",
        "field": c.field,
        "status": c.status,
        "value_ja": c.value_ja,
        "normalized": c.normalized,
        "value_en": c.value_en,
        "citations": c.citations,
        "provenance": Provenance(final_state="silver_unreviewed").model_dump(),
    }


def schema_valid(c: Candidate, row: ManifestRow | None) -> tuple[bool, str]:
    if c.parse_error:
        return False, c.parse_error
    try:
        LabelLine.model_validate(line_dict(c, row))
    except ValidationError as e:
        return False, "; ".join(x["msg"] for x in e.errors())[:200]
    return True, ""


def shape_errors(text: str, field_ids: list[str]) -> list[str]:
    """What a strict schema would have refused in a JSON-mode answer (D-49): not JSON,
    not the answer shape, a listed field missing, an entry or `normalized` value that
    does not fit the field (schema_valid). Content checks (citations, quotes, dates)
    are not here: they stay with the consensus, so a repair never gives one labeler a
    second try at content the other one does not get."""
    try:
        d = json.loads(text)
    except ValueError as e:
        return [f"the answer is not valid JSON ({e})"]
    rows = rows_of(d) if isinstance(d, dict) else None
    if rows is None:
        return ['the answer is not {"fields": {...}, "normalized": {...}}']
    got = {str(r.get("field")): r for r in rows}
    errs = [f"{f}: missing from fields" for f in field_ids if f not in got]
    for f in field_ids:
        if f in got:
            ok, why = schema_valid(from_row(got[f], ""), None)
            if not ok:
                errs.append(f"{f}: {why}")
    return errs


def _cited(c: Candidate, by_id: dict[str, Sentence]) -> list[Sentence]:
    return [by_id[i] for i in c.citations if i in by_id]


def citations_exist(c: Candidate, by_id: dict[str, Sentence]) -> bool | None:
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


def value_in_citation(c: Candidate, by_id: dict[str, Sentence]) -> bool | None:
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


def values_roundtrip(c: Candidate, by_id: dict[str, Sentence]) -> bool | None:
    """Dates, times, flags, rates, tax wording, codes, grades, phone and email re-run
    through the converters on the cited sentences (eval.validate_labels.check_values)."""
    if c.status != "present" or BY_ID[c.field].model is None:
        return None
    model = validate_normalized(c.field, c.normalized)
    ss_of = lambda ids: [by_id[i] for i in ids if i in by_id]  # noqa: E731
    return not check_values(c.field, model, ss_of, c.citations)


def field_applicable(c: Candidate, row: ManifestRow) -> bool | None:
    if c.status == "absent":
        return None
    return row.doc_type in BY_ID[c.field].applies_to


def label_dates(c: Candidate) -> list[date]:
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


def era_plausible(c: Candidate, row: ManifestRow) -> bool | None:
    """A date more than 5 years from the document's own notice date is suspect (an OCR
    or model slip of an era). Not run when the manifest has no notice date."""
    ds = label_dates(c)
    if c.status != "present" or not ds or row.notice_date is None:
        return None
    gap = timedelta(days=366 * ERA_YEARS)
    return all(abs(d - row.notice_date) <= gap for d in ds)


def weekday_consistent(c: Candidate, by_id: dict[str, Sentence]) -> bool | None:
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


def heading_cue(c: Candidate, by_id: dict[str, Sentence]) -> bool | None:
    """Soft: a cue of the field is in a cited sentence's section titles or its first
    15 characters, not inside a longer word."""
    cues = BY_ID[c.field].cues
    if c.status == "absent" or not cues:
        return None
    return any(cue_at_heading(k, s) for s in _cited(c, by_id) for k in cues)


# --- English Summary cross-check (informational) ---------------------------------------

_MONTHS = ("january february march april may june july august september october "
           "november december").split()  # fmt: skip
_EN_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\d[\d\- ()]{7,}\d")


def en_dates(text: str) -> set[date]:
    out = set()
    for d, m, y in _EN_DATE.findall(text):
        if m.lower() in _MONTHS:
            try:
                out.add(date(int(y), _MONTHS.index(m.lower()) + 1, int(d)))
            except ValueError:
                pass
    return out


def en_summary_agrees(
    c: Candidate, en_text: str, by_id: dict[str, Sentence]
) -> bool | None:
    """Dates (bid deadlines), emails, phone numbers and the title must agree with the
    English Summary text. None when the document has no Summary or has nothing to
    compare. Informational: the Summary is a cross-check, not evidence (D-37)."""
    if not en_text or c.status != "present":
        return None
    n = c.normalized or {}
    if c.field == "deadlines":
        bid = {
            date.fromisoformat(it["datetime"][:10])
            for it in n.get("items", [])
            if it.get("datetime")
            and it.get("kind") in ("bid_in_person", "mail_arrival", "electronic")
        }
        theirs = en_dates(en_text)
        return None if not bid or not theirs else bool(bid & theirs)
    if c.field == "contact":
        found = [(n.get("email"), _EMAIL), (n.get("phone"), _PHONE)]
        checks = []
        for val, rx in found:
            if val and rx.search(en_text):
                checks.append(
                    re.sub(r"\D", "", val) in re.sub(r"\D", "", en_text)
                    if rx is _PHONE
                    else val.lower() in en_text.lower()
                )
        return all(checks) if checks else None
    if c.field == "title":
        toks = re.findall(r"[A-Za-z0-9]{2,}", normalize(c.value_ja or "")[0])
        return all(t.lower() in en_text.lower() for t in toks) if toks else None
    return None


def run_checks(
    c: Candidate,
    row: ManifestRow,
    by_id: dict[str, Sentence],
    en_text: str = "",
) -> list[tuple[str, bool]]:
    """(name, passed) for every check that applies, in a fixed order."""
    ok, why = schema_valid(c, row)
    out: list[tuple[str, bool | None]] = [("schema_valid", ok)]
    c.check_notes["schema_valid"] = why
    if ok:
        out += [
            ("citations_exist", citations_exist(c, by_id)),
            ("field_applicable", field_applicable(c, row)),
        ]
        if out[1][1] is not False:
            out += [
                ("value_in_citation", value_in_citation(c, by_id)),
                ("values_roundtrip", values_roundtrip(c, by_id)),
                ("era_plausible", era_plausible(c, row)),
                ("weekday_consistent", weekday_consistent(c, by_id)),
                ("heading_cue", heading_cue(c, by_id)),
                ("en_summary_agrees", en_summary_agrees(c, en_text, by_id)),
            ]
    return [(n, bool(v)) for n, v in out if v is not None]


def failed(checks: list[tuple[str, bool]], names: tuple[str, ...]) -> list[str]:
    return [n for n, v in checks if not v and n in names]
