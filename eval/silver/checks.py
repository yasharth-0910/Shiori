# ruff: noqa: E501
"""Automatic checks on one candidate label (D-43). Each returns True, False, or None
when it does not apply. `BLOCKING` ones stop a field from being accepted automatically;
`HARD` ones also stop a reviewer's answer from being imported. The rest are advisory."""

import json
import re
from datetime import date, timedelta

from pydantic import ValidationError
from shiori_core.checks import (  # noqa: F401  (moved to core, D-82; re-exported for eval)
    HEAD_CHARS,
    bare_heading,
    citations_exist,
    cue_at_heading,
    cue_in,
    cue_is_heading,
    heading_cue,
    label_dates,
    value_in_citation,
    values_roundtrip,
    weekday_consistent,
)
from shiori_core.fields import BY_ID
from shiori_core.models import Sentence
from shiori_core.normalize import normalize

from collector.manifest import ManifestRow
from eval.label_format import LabelLine, Provenance
from eval.silver.model import Candidate, from_row
from eval.silver.prompt import rows_of

HARD = ("schema_valid", "citations_exist", "value_in_citation", "values_roundtrip")
BLOCKING = (*HARD, "field_applicable", "era_plausible", "weekday_consistent")
ERA_YEARS = 5
SHORT_CUE = 3  # cues this short trigger "both absent" only as a whole heading


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


def field_applicable(c: Candidate, row: ManifestRow) -> bool | None:
    if c.status == "absent":
        return None
    return row.doc_type in BY_ID[c.field].applies_to


def era_plausible(c: Candidate, row: ManifestRow) -> bool | None:
    """A date more than 5 years from the document's own notice date is suspect (an OCR
    or model slip of an era). Not run when the manifest has no notice date."""
    ds = label_dates(c)
    if c.status != "present" or not ds or row.notice_date is None:
        return None
    gap = timedelta(days=366 * ERA_YEARS)
    return all(abs(d - row.notice_date) <= gap for d in ds)


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
