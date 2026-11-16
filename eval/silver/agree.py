# ruff: noqa: E501
"""Do two candidates for the same field agree? (D-43)

Per field type: enums, bools, statuses and codes must match exactly; dates after
normalization; text when the citations overlap and the normalized values match or are
within a fuzzy threshold (difflib ratio, thresholds in config); list fields when every
item has a partner by citation overlap and normalized value. `value_en` is never
compared.

Relaxations (sv2) are named rules, each tested against the reviewed pilot items before
it is switched on (`eval.silver.replay`, D-47). `ACTIVE` holds the ones that never
auto-accepted a wrong candidate there. No rule loosens a status, enum, date or amount.
"""

import json
import re
from difflib import SequenceMatcher

from shiori_core.fields import BY_ID
from shiori_core.normalize import normalize

from eval.silver.config import FUZZY_LONG, FUZZY_SHORT
from eval.silver.model import Candidate

LONG_TEXT = {"scope_summary"}

RELAXATIONS = {
    "list_items_by_citation": "list items pair by citation overlap and their enum and "
    "date parts; item text similarity is not required",
    "officer_concat": "contracting_officer compares title + name as one string",
    "contact_concat": "contact compares phone digits, email and org + department as one "
    "string",
    "uq_category_normalized": "unified_qualification compares grades exactly and the "
    "category without brackets, quotes and list punctuation",
    "period_relative_optional": "performance_period compares relative_text only when "
    "both set it (start and end stay exact)",
    "text_without_citation_overlap": "text fields with the same value agree even when "
    "they cite different sentences",
    "eligibility_negation": "an eligibility item with polarity requirement whose text_ja "
    "keeps the negation (…ないこと, …ではないこと, …がない者であること) equals the same "
    "condition with polarity disqualification and the negation stripped",
}  # fmt: skip
# Switched on because the replay of the pilot review (D-47, eval/reports/
# silver_pilot_review.md) showed each settling an item correctly and none wrongly.
# Not switched on: period_relative_optional (would accept the wrong candidate of F-0025),
# list_items_by_citation and text_without_citation_overlap (no pilot item either way).
# eligibility_negation (D-58): replayed on all 56 reviewed items of every round
# (replay.shown_pair_replay), it settles none and accepts none wrongly; switched on by
# Yasharth's criterion (never accepts a rejected or replaced answer), because the sv4
# rule lets the same condition be written in either form.
ACTIVE: frozenset[str] = frozenset(
    {
        "officer_concat",
        "contact_concat",
        "uq_category_normalized",
        "eligibility_negation",
    }
)


def _n(s: str | None) -> str:
    return re.sub(r"\s+", "", normalize(s or "")[0])


def similar(a: str | None, b: str | None, threshold: float) -> bool:
    x, y = _n(a), _n(b)
    return x == y or SequenceMatcher(None, x, y).ratio() >= threshold


def overlap(a: list[str], b: list[str]) -> bool:
    return bool(set(a) & set(b))


def _match(xs: list, ys: list, same) -> bool:
    """Every item of both lists has a distinct partner in the other."""
    if len(xs) != len(ys):
        return False
    free = list(ys)
    for x in xs:
        hit = next((y for y in free if same(x, y)), None)
        if hit is None:
            return False
        free.remove(hit)
    return True


def item_same(
    field: str, x: dict, y: dict, rules: frozenset[str] = frozenset()
) -> bool:
    """Two items of a list field are the same item. Also used to deduplicate when
    chunk answers or the two candidates are unioned."""
    loose = "list_items_by_citation" in rules
    cites = overlap(x.get("citations", []), y.get("citations", []))
    if field == "deadlines":
        return (
            x.get("kind") == y.get("kind")
            and x.get("datetime") == y.get("datetime")
            and (loose or _n(x.get("relative_text")) == _n(y.get("relative_text")))
            and set(x.get("flags", [])) == set(y.get("flags", []))
            and cites
        )
    if field == "eligibility":
        tx, ty = x.get("text_ja"), y.get("text_ja")
        same_polarity = x.get("polarity") == y.get("polarity")
        if not same_polarity and "eligibility_negation" in rules:
            tx, ty = _negation_form(x), _negation_form(y)
            same_polarity = tx is not None and ty is not None
        return (
            x.get("kind") == y.get("kind")
            and same_polarity
            and cites
            and (loose or similar(tx, ty, FUZZY_LONG))
        )
    return cites and (loose or similar(x.get("name_ja"), y.get("name_ja"), FUZZY_SHORT))


# A requirement written with its negation kept: …ないこと, …ではないこと, …でないこと,
# …がない者であること, …しない者であること (SEM-3; sv4 guide rule, F-0042).
_NEGATION_END = re.compile(r"(?:では|で|が)?ない(?:者であること|こと|者)$")


def _negation_form(item: dict) -> str | None:
    """The text of an eligibility item in the disqualification form, when its polarity
    and wording allow the eligibility_negation rule: a requirement whose text ends in a
    negation gives the text without it; a disqualification whose text does not end in
    one gives its text. Anything else (a disqualification that keeps a negation, a
    requirement without one) gives None: no rule says those two forms are the same."""
    text = re.sub(r"[。．.]+$", "", _n(item.get("text_ja")))
    m = _NEGATION_END.search(text)
    if item.get("polarity") == "requirement":
        return text[: m.start()] if m else None
    if item.get("polarity") == "disqualification":
        return None if m else text
    return None


def union_items(field: str, lists: list[list[dict]]) -> list[dict]:
    """All items of several lists, in order, an item dropped when an earlier one is the
    same item (item_same); the kept item gets the union of both citation lists."""
    out: list[dict] = []
    for items in lists:
        for it in items:
            hit = next((o for o in out if item_same(field, o, it)), None)
            if hit is None:
                out.append(json.loads(json.dumps(it)))
            else:
                hit["citations"] += [
                    c for c in it.get("citations", []) if c not in hit["citations"]
                ]
    return out


_UQ_PUNCT = re.compile(r"[「」『』\"'“”‘’、,，・/／]|又は|及び|若しくは|または|および")


def _structured(field: str, x: dict, y: dict, rules: frozenset[str]) -> bool:
    joined = lambda d, ks: "".join(d.get(k) or "" for k in ks)  # noqa: E731
    if field == "contracting_officer":
        if "officer_concat" in rules:
            return similar(
                joined(x, ("title", "name")), joined(y, ("title", "name")), FUZZY_SHORT
            )
        return all(similar(x.get(k), y.get(k), FUZZY_SHORT) for k in ("title", "name"))
    if field == "unified_qualification":
        if "uq_category_normalized" in rules:
            cat = lambda d: _UQ_PUNCT.sub("", _n(d.get("category")))  # noqa: E731
            same_cat = cat(x) == cat(y)
        else:
            same_cat = similar(x.get("category"), y.get("category"), FUZZY_SHORT)
        return (
            set(x.get("grades", [])) == set(y.get("grades", []))
            and same_cat
            and similar(x.get("region"), y.get("region"), FUZZY_SHORT)
        )
    if field == "contact":
        digits = lambda v: re.sub(r"\D", "", v or "")  # noqa: E731
        same = (
            digits(x.get("phone")) == digits(y.get("phone"))
            and (x.get("email") or "").lower() == (y.get("email") or "").lower()
        )
        if "contact_concat" in rules:
            return same and similar(
                joined(x, ("org", "department")),
                joined(y, ("org", "department")),
                FUZZY_SHORT,
            )
        return (
            same
            and similar(x.get("org"), y.get("org"), FUZZY_SHORT)
            and similar(x.get("department"), y.get("department"), FUZZY_SHORT)
        )
    if field == "performance_period":
        rx, ry = x.get("relative_text"), y.get("relative_text")
        skip_rel = "period_relative_optional" in rules and not (rx and ry)
        return (
            x.get("start") == y.get("start")
            and x.get("end") == y.get("end")
            and (skip_rel or similar(rx, ry, FUZZY_SHORT))
        )
    if field == "submission_modes":
        return set(x.get("modes", [])) == set(y.get("modes", [])) and bool(
            x.get("mail_not_allowed")
        ) == bool(y.get("mail_not_allowed"))
    if field == "item_category":
        return set(x.get("codes", [])) == set(y.get("codes", []))
    return x == y  # enums, bools, dates, bonds, tax, language/currency


def agree(
    a: Candidate, b: Candidate, rules: frozenset[str] | None = None
) -> tuple[bool, str]:
    """`rules`: the relaxations to apply; ACTIVE when not given."""
    rules = ACTIVE if rules is None else rules
    if a.status != b.status:
        return False, f"status {a.status} vs {b.status}"
    if a.status == "absent":
        return True, ""
    spec = BY_ID[a.field]
    if a.status == "see_other_document":
        ra, rb = (
            (a.normalized or {}).get("ref", {}),
            (b.normalized or {}).get("ref", {}),
        )
        ok = ra.get("kind") == rb.get("kind")
        return ok, "" if ok else f"points at {ra.get('kind')} vs {rb.get('kind')}"
    if spec.kind == "text":
        thr = FUZZY_LONG if a.field in LONG_TEXT else FUZZY_SHORT
        if not overlap(a.citations, b.citations) and not (
            "text_without_citation_overlap" in rules
            and _n(a.value_ja) == _n(b.value_ja)
        ):
            return False, "citations do not overlap"
        ok = similar(a.value_ja, b.value_ja, thr)
        return ok, "" if ok else "value_ja differs"
    x, y = a.normalized or {}, b.normalized or {}
    if spec.kind == "list":
        ok = _match(x.get("items", []), y.get("items", []), lambda i, j: item_same(a.field, i, j, rules))  # fmt: skip
        return ok, "" if ok else "items differ"
    ok = _structured(a.field, x, y, rules)
    return ok, "" if ok else "values differ"
