"""Candidate labels as parsed from a labeler's answer."""

import dataclasses
import json
from dataclasses import dataclass

from shiori_core.fields import BY_ID


@dataclass
class Candidate:
    field: str
    status: str = "absent"
    value_ja: str | None = None
    value_en: str | None = None
    normalized: dict | None = None
    citations: list[str] = dataclasses.field(default_factory=list)
    reason: str = ""  # the labeler's one-liner; stays in the raw cache, never exported
    parse_error: str | None = None
    labeler: str = ""  # "provider/model"
    check_notes: dict[str, str] = dataclasses.field(default_factory=dict)
    # Other answers from other parts of a split document that disagree with this one
    # (pipeline.merge); the field is then flagged.
    alternatives: list["Candidate"] = dataclasses.field(default_factory=list)

    def key(self) -> str:
        return json.dumps([self.status, self.normalized, self.value_ja], sort_keys=True)


def parse_normalized(raw: object) -> tuple[dict | None, str | None]:
    """`normalized` as a labeler sent it: an object (sv2 schema), a JSON string (sv1),
    or a JSON string wrapped in another string, which is parsed once more before it
    counts as a failure. Returns (value, parse_error); empty or null is (None, None)."""
    v = raw
    for _ in range(2):
        if not isinstance(v, str):
            break
        if not v.strip():
            return None, None
        try:
            v = json.loads(v)
        except ValueError:
            return None, "normalized is not valid JSON"
    if v is None:
        return None, None
    if not isinstance(v, dict):
        return None, "normalized is not a JSON object"
    return v, None


def from_row(r: dict, labeler: str) -> Candidate:
    """One entry of the answer's `fields` array -> Candidate. Empty strings mean none.
    A list field's line citations are the union of its items' (the prompt does not ask
    the model to keep two copies in step)."""
    fid = str(r.get("field", ""))
    c = Candidate(
        fid,
        status=str(r.get("status", "")),
        value_ja=(r.get("value_ja") or None),
        value_en=(r.get("value_en") or None),
        citations=[str(x) for x in (r.get("citations") or [])],
        reason=str(r.get("reason") or ""),
        labeler=labeler,
    )
    raw = r.get("normalized")
    if c.status == "absent":
        c.value_ja = c.value_en = None
        c.citations = []
    elif c.status == "see_other_document" and isinstance(r.get("ref"), dict):
        c.normalized = {"ref": r["ref"]}  # sv2 sends the ref beside normalized
    elif (
        BY_ID.get(fid)
        and BY_ID[fid].kind == "text"
        and c.status != "see_other_document"
    ):
        pass  # a present text field has no normalized value; a pointer has its ref
    else:
        c.normalized, c.parse_error = parse_normalized(raw)
    if (
        fid in BY_ID
        and BY_ID[fid].kind == "list"
        and c.normalized
        and isinstance(c.normalized.get("items"), list)
    ):
        union: list[str] = []
        for it in c.normalized["items"]:
            for cid in it.get("citations", []) if isinstance(it, dict) else []:
                if cid not in union:
                    union.append(cid)
        c.citations = union
    return c


_ENGLISH = {"text_en", "name_en"}


def _strip_english(v: object) -> object:
    if isinstance(v, dict):
        return {k: _strip_english(x) for k, x in v.items() if k not in _ENGLISH}
    if isinstance(v, list):
        return [_strip_english(x) for x in v]
    return v


def canonical(c: Candidate) -> str:
    """Strict identity of an answer, for "is this the answer the reviewer gave": status;
    for see_other_document the ref kind; for text fields value_ja (spaces ignored); for
    the rest the normalized value without English text, list items in any order. Not
    the agreement rule (agree.py): nothing here is fuzzy."""
    if c.status == "absent":
        return "absent"
    if c.status == "see_other_document":
        ref = (c.normalized or {}).get("ref") or {}
        return json.dumps(["see_other_document", ref.get("kind")])
    if BY_ID.get(c.field) and BY_ID[c.field].kind == "text":
        text = "".join((c.value_ja or "").split())
        return json.dumps(["present", text], ensure_ascii=False)
    n = _strip_english(c.normalized or {})
    if isinstance(n, dict) and isinstance(n.get("items"), list):
        dump = lambda i: json.dumps(i, sort_keys=True, ensure_ascii=False)  # noqa: E731
        n = {**n, "items": sorted(dump(i) for i in n["items"])}
    return json.dumps(["present", n], sort_keys=True, ensure_ascii=False)
