"""The v1 field schema (docs/field_schema.md), frozen as SCHEMA_VERSION 1.0.0 (D-39).

One `FieldSpec` per field: its id, whether it is free text or structured, which
document types normally contain it, the heading cues that locate it, and the pydantic
model of its `normalized` value. docs/field_schema.md carries the same ids and
`applies_to` lists; tests/test_fields.py fails when the two disagree.

Changing a field id, an enum value or `applies_to` after the freeze needs a decision
entry and a relabel plan.

Conventions:
- Text fields (`model` is None): the value is `value_ja`, `normalized` is null.
- Structured fields: `normalized` validates against `model`. List fields hold their
  items in `items`, each item with its own `citations`.
- A field that does not apply to a document's type is `absent` (counts toward the
  hallucination rate). `not_stated` and `see_other_document` inside a value are what
  an extractor may emit; a label uses the field status `absent` / `see_other_document`
  instead, so each fact has one spelling.
- All datetimes are JST. Citations are Japanese sentence ids only; English Summary
  sentences are never cited.
"""

import re
from dataclasses import dataclass
from datetime import date
from datetime import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"

Status = Literal["present", "absent", "see_other_document"]
DocTypeName = str  # the manifest's doc_type values (collector.manifest.DocType)

NOTICE_LIKE = ("notice", "tender_page", "bid_instructions")
ALL_LABELED = (*NOTICE_LIKE, "spec")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- normalized values ---------------------------------------------------------------


class SeeOtherRef(Strict):
    """What a `see_other_document` field points at. `text_ja` is the pointer as written,
    for example `告示第808号`."""

    kind: Literal["spec", "bid_instructions", "other_notice", "kokuji", "other"]
    text_ja: str | None = None


class ContractingOfficer(Strict):
    title: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _one(self) -> "ContractingOfficer":
        if not (self.title or self.name):
            raise ValueError("title or name is required")
        return self


class NoticeDate(Strict):
    date: date


ProcurementTypeValue = Literal[
    "open_competitive",  # 一般競争入札
    "designated_competitive",  # 指名競争入札
    "proposal_competition",  # 企画競争
    "public_solicitation",  # 公募
    "negotiated",  # 随意契約
    "open_counter",  # オープンカウンター
    "other",
]


class ProcurementType(Strict):
    type: ProcurementTypeValue


class AwardMethod(Strict):
    method: Literal["lowest_price", "best_value", "other"]


class ItemCategory(Strict):
    codes: list[str] = Field(min_length=1)  # digits as written, e.g. "8", "14"


class PerformancePeriod(Strict):
    start: date | None = None
    end: date | None = None
    relative_text: str | None = None  # "契約締結の日から90日間"

    @model_validator(mode="after")
    def _one(self) -> "PerformancePeriod":
        if not (self.start or self.end or self.relative_text):
            raise ValueError("start, end or relative_text is required")
        return self


class DeliveryDeadline(Strict):
    date: date


EligibilityKind = Literal[
    "unified_qualification", "legal", "suspension", "experience", "certification",
    "other",
]  # fmt: skip


class EligibilityItem(Strict):
    kind: EligibilityKind
    polarity: Literal["requirement", "disqualification"]  # SEM-3
    text_ja: str = Field(min_length=1)
    text_en: str | None = None
    citations: list[str] = Field(min_length=1)


class Eligibility(Strict):
    items: list[EligibilityItem] = Field(min_length=1)


class UnifiedQualification(Strict):
    grades: list[Literal["A", "B", "C", "D"]] = []
    category: str | None = None  # 営業品目, as written
    region: str | None = None  # 競争参加地域, as written

    @model_validator(mode="after")
    def _one(self) -> "UnifiedQualification":
        if not (self.grades or self.category or self.region):
            raise ValueError("grades, category or region is required")
        return self


DeadlineKind = Literal[
    "bid_in_person", "mail_arrival", "electronic", "bid_opening", "question",
    "briefing", "document_request", "other",
]  # fmt: skip
DeadlineFlag = Literal["arrival_required", "postmark_ok"]  # DATE-8
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\+09:00$")


class DeadlineItem(Strict):
    kind: DeadlineKind
    # "2026-10-27" or "2026-10-27T14:00:00+09:00"; or relative_text, never both.
    datetime: str | None = None
    relative_text: str | None = None  # "入札説明書の交付後7日以内"
    flags: list[DeadlineFlag] = []
    citations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _when(self) -> "DeadlineItem":
        if (self.datetime is None) == (self.relative_text is None):
            raise ValueError("exactly one of datetime and relative_text")
        if self.datetime is not None:
            if not (_DATE.match(self.datetime) or _DATETIME.match(self.datetime)):
                raise ValueError(f"datetime {self.datetime!r}: not ISO date or JST")
            dt.fromisoformat(self.datetime)  # rejects 2026-02-30
        return self


class Deadlines(Strict):
    items: list[DeadlineItem] = Field(min_length=1)


class SubmissionModes(Strict):
    modes: list[Literal["in_person", "mail", "electronic"]] = []
    mail_not_allowed: bool = False  # 郵便等による入札は認めない

    @model_validator(mode="after")
    def _check(self) -> "SubmissionModes":
        if self.mail_not_allowed and "mail" in self.modes:
            raise ValueError("mail_not_allowed contradicts modes containing mail")
        if not (self.modes or self.mail_not_allowed):
            raise ValueError("a present value needs a mode or mail_not_allowed")
        return self


BondStatus = Literal["required", "waived", "waived_with_proviso", "not_stated"]


class Bond(Strict):
    status: BondStatus
    rate_percent: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def _rate(self) -> "Bond":
        if self.rate_percent is not None and self.status not in (
            "required",
            "waived_with_proviso",
        ):
            raise ValueError("rate_percent only with required or waived_with_proviso")
        return self


class SpecAccess(Strict):
    mode: Literal[
        "public", "email_after_pledge", "at_counter", "see_other_document", "not_stated"
    ]


class TaxBasis(Strict):
    basis: Literal["bid_excludes_tax", "bid_includes_tax"]


class LanguageCurrency(Strict):
    language: str | None = None  # ISO 639-1, "ja"
    currency: str | None = None  # ISO 4217, "JPY"

    @model_validator(mode="after")
    def _one(self) -> "LanguageCurrency":
        if not (self.language or self.currency):
            raise ValueError("language or currency is required")
        return self


class RequiredDocumentItem(Strict):
    name_ja: str = Field(min_length=1)
    name_en: str | None = None
    citations: list[str] = Field(min_length=1)


class RequiredDocuments(Strict):
    items: list[RequiredDocumentItem] = Field(min_length=1)


class Contact(Strict):
    org: str | None = None
    department: str | None = None
    phone: str | None = None  # copied exactly, never translated
    email: str | None = None

    @model_validator(mode="after")
    def _one(self) -> "Contact":
        if not (self.org or self.department or self.phone or self.email):
            raise ValueError("at least one part is required")
        return self


class WtoCovered(Strict):
    covered: bool  # False only when the text says the agreement does not apply


# --- field specs ---------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    id: str
    kind: Literal["text", "structured", "list"]
    applies_to: tuple[DocTypeName, ...]
    cues: tuple[str, ...]
    model: type[BaseModel] | None  # None for text fields


def _spec(
    id: str,
    kind: Literal["text", "structured", "list"],
    applies_to: tuple[str, ...],
    cues: tuple[str, ...],
    model: type[BaseModel] | None = None,
) -> FieldSpec:
    return FieldSpec(id, kind, applies_to, cues, model)


SPECS: tuple[FieldSpec, ...] = (
    _spec(
        "title", "text", ALL_LABELED,
        ("件名", "調達件名", "購入等件名", "業務名", "業務の名称"),
    ),
    _spec("issuer_org", "text", ALL_LABELED, ("発注機関", "調達機関")),
    _spec(
        "contracting_officer", "structured", NOTICE_LIKE,
        ("支出負担行為担当官", "契約担当官", "契約責任者"), ContractingOfficer,
    ),
    _spec("notice_date", "structured", ("notice", "tender_page"), (), NoticeDate),
    _spec(
        "procurement_type", "structured", NOTICE_LIKE,
        ("一般競争入札", "指名競争入札", "企画競争", "公募", "随意契約",
         "オープンカウンター"),
        ProcurementType,
    ),
    _spec(
        "award_method", "structured", NOTICE_LIKE,
        ("落札者の決定方法", "総合評価", "最低価格"), AwardMethod,
    ),
    _spec(
        "item_category", "structured", ("notice", "tender_page"),
        ("品目分類番号",), ItemCategory,
    ),
    _spec(
        "scope_summary", "text", ALL_LABELED,
        ("調達件名の特質等", "業務内容", "概要", "目的"),
    ),
    _spec(
        "performance_period", "structured", ALL_LABELED,
        ("履行期間", "契約期間", "履行期限", "委託期間", "業務の期間"),
        PerformancePeriod,
    ),
    _spec(
        "delivery_deadline", "structured", ALL_LABELED, ("納入期限",), DeliveryDeadline
    ),
    _spec("delivery_location", "text", ALL_LABELED, ("納入場所", "履行場所")),
    _spec(
        "eligibility", "list", NOTICE_LIKE,
        ("競争参加資格", "参加資格", "暴力団関係事業者", "指名停止"), Eligibility,
    ),
    _spec(
        "unified_qualification", "structured", NOTICE_LIKE,
        ("全省庁統一資格", "等級", "営業品目", "競争参加地域"), UnifiedQualification,
    ),
    _spec(
        "deadlines", "list", NOTICE_LIKE,
        ("入札日時", "入札書の受領期限", "提出期限", "受付期間", "開札の日時及び場所",
         "開札日時", "入札場所", "質問", "質疑", "質問書の提出期限", "入札説明会",
         "説明会", "受領期限", "必着"),
        Deadlines,
    ),  # fmt: skip
    _spec(
        "submission_modes", "structured", NOTICE_LIKE,
        ("電子調達システム", "電子入札", "持参", "郵送", "郵便等による入札の可否",
         "認めない"),
        SubmissionModes,
    ),  # fmt: skip
    _spec("bid_bond", "structured", NOTICE_LIKE, ("入札保証金",), Bond),
    _spec("performance_bond", "structured", NOTICE_LIKE, ("契約保証金",), Bond),
    _spec(
        "tax_basis", "structured", NOTICE_LIKE,
        ("消費税", "100分の10", "税抜", "税込"), TaxBasis,
    ),
    _spec(
        "language_currency", "structured", NOTICE_LIKE,
        ("使用する言語及び通貨",), LanguageCurrency,
    ),
    _spec(
        "required_documents", "list", NOTICE_LIKE,
        ("提出書類", "提出物", "必要書類"), RequiredDocuments,
    ),
    _spec(
        "contact", "structured", NOTICE_LIKE,
        ("問い合わせ先", "担当", "連絡先"), Contact,
    ),
    _spec(
        "wto_covered", "structured", NOTICE_LIKE,
        ("政府調達に関する協定", "WTO", "特定調達契約"), WtoCovered,
    ),
    _spec(
        "spec_access", "structured", NOTICE_LIKE,
        ("仕様書", "入札説明書の交付", "誓約書", "閲覧"), SpecAccess,
    ),
)  # fmt: skip

# Cues that mark a neighbouring section in the reviewed notices but belong to no v1
# field (D-39): 前金払 (advance payment), 契約書作成 (is a contract document drawn up).
UNMAPPED_CUES = ("前金払", "契約書作成")

FIELD_IDS: tuple[str, ...] = tuple(s.id for s in SPECS)
BY_ID: dict[str, FieldSpec] = {s.id: s for s in SPECS}


def validate_normalized(field: str, normalized: dict | None) -> BaseModel | None:
    """The pydantic model of a present value, or None for a text field. Raises
    pydantic.ValidationError (a ValueError) when it doesn't fit the schema."""
    spec = BY_ID[field]
    if spec.model is None:
        if normalized is not None:
            raise ValueError("text fields have normalized: null")
        return None
    return spec.model.model_validate(normalized)
