"""One label line = one field of one document (eval_protocol.md, "Label files").

These models check a line on its own: schema version, status rules, the shape of
`normalized`, provenance states. Checks that need the document (citations exist,
converters re-run, applicability, paths) are in eval/validate_labels.py.

Dev-time only. Labels hold source text, so where a file lives depends on the
document's license class (D-24).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shiori_core.fields import (
    BY_ID,
    FIELD_IDS,
    SUPPORTED_SCHEMA_VERSIONS,
    SeeOtherRef,
    Status,
    validate_normalized,
)

Reviewer = Literal["claude_chat", "claude_code", "yasharth", "native_speaker"]
FinalState = Literal[
    "silver_unreviewed", "silver_consensus", "silver_model_reviewed", "human_audited"
]
# Only a native speaker's review makes a label human_audited. Yasharth's check (he
# reads at beginner level) and a model's review never do, whether in chat
# (claude_chat) or in a Claude Code review session (claude_code, D-55). Reports must
# not call anything else "human-verified".
STATES_BY_REVIEWER: dict[str | None, set[str]] = {
    None: {"silver_unreviewed", "silver_consensus"},
    "yasharth": {"silver_unreviewed", "silver_consensus"},
    "claude_chat": {"silver_model_reviewed"},
    "claude_code": {"silver_model_reviewed"},
    "native_speaker": {"human_audited"},
}
# Inner values an extractor may emit; a label says the same thing with its status.
FORBIDDEN_INNER = {"not_stated", "see_other_document"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreLabeler(Strict):
    provider: str
    model: str
    date: date
    # The labeler's own prompt version (D-54); None on lines written before it.
    prompt_version: str | None = None


class AutoCheck(Strict):
    name: str
    passed: bool


class Provenance(Strict):
    pre_labelers: list[PreLabeler] = []
    # True: all pre-labelers gave the same normalized value. False: they differ.
    # None: fewer than two pre-labelers.
    agreement: bool | None = None
    auto_checks: list[AutoCheck] = []
    reviewed_by: Reviewer | None = None
    review_note: str | None = None
    final_state: FinalState
    # Silver pipeline (D-43, D-45): the prompt that made the pre-labels, and whether a
    # local model stood in for a cloud provider. Phase 4 reports benchmark scores with
    # and without labeler_overlap lines.
    prompt_version: str | None = None
    labeler_overlap: bool = False
    # Review import (sv2): which candidate the reviewer took: a provider name, "union"
    # (candidate C of a list field) or "custom" (their own answer, or absent).
    reviewed_choice: str | None = None

    @model_validator(mode="after")
    def _states(self) -> "Provenance":
        if (len(self.pre_labelers) >= 2) != (self.agreement is not None):
            raise ValueError("agreement is set exactly when there are 2+ pre_labelers")
        if self.final_state not in STATES_BY_REVIEWER[self.reviewed_by]:
            raise ValueError(
                f"final_state {self.final_state} does not fit "
                f"reviewed_by {self.reviewed_by}"
            )
        if self.final_state == "silver_consensus" and self.agreement is not True:
            raise ValueError("silver_consensus needs agreement true")
        return self


class LabelLine(Strict):
    doc_id: str
    extractor_version: str
    schema_version: str
    field: str
    status: Status
    value_ja: str | None = None
    normalized: dict | None = None
    value_en: str | None = None
    citations: list[str] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def _status_rules(self) -> "LabelLine":
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version {self.schema_version} not in "
                f"{SUPPORTED_SCHEMA_VERSIONS}"
            )
        if self.field not in FIELD_IDS:
            raise ValueError(f"unknown field {self.field!r}")
        if len(set(self.citations)) != len(self.citations):
            raise ValueError("duplicate citations")
        if self.status == "absent":
            if self.value_ja or self.normalized or self.value_en or self.citations:
                raise ValueError(
                    "absent: value_ja, normalized, value_en, citations empty"
                )
            return self
        if not self.citations:
            raise ValueError(f"{self.status}: at least one citation")
        if self.status == "see_other_document":
            if not self.normalized or set(self.normalized) != {"ref"}:
                raise ValueError('see_other_document: normalized is {"ref": {...}}')
            SeeOtherRef.model_validate(self.normalized["ref"])
            return self
        spec = BY_ID[self.field]
        if spec.kind == "text" and not self.value_ja:
            raise ValueError("present text field needs value_ja")
        model = validate_normalized(self.field, self.normalized)
        if model is None:
            return self
        for inner in ("status", "mode"):
            if getattr(model, inner, None) in FORBIDDEN_INNER:
                raise ValueError(
                    f"{self.field}.{inner} = {getattr(model, inner)}: "
                    "use field status absent or see_other_document"
                )
        if spec.kind == "list":
            items = model.model_dump()["items"]
            union = {c for it in items for c in it["citations"]}
            if union != set(self.citations):
                raise ValueError(
                    "line citations must be the union of the item citations"
                )
        return self
