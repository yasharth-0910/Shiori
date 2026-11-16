"""The frozen schema (D-39): docs/field_schema.md and fields.py agree, and the models
accept the shapes the doc shows and reject the ones it forbids."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from shiori_core.fields import BY_ID, FIELD_IDS, SCHEMA_VERSION, validate_normalized

DOC = Path(__file__).resolve().parent.parent / "docs/field_schema.md"


def doc_table() -> dict[str, set[str]]:
    """field id -> applies_to, read from the rows of the v1 fields table."""
    out: dict[str, set[str]] = {}
    for line in DOC.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.fullmatch(r"`(\w+)`", cells[0]) if line.startswith("| `") else None
        if m and len(cells) >= 3:
            out[m.group(1)] = {t.strip() for t in cells[2].split(",")}
    return out


def test_doc_and_code_have_the_same_field_ids() -> None:
    assert list(doc_table()) == list(FIELD_IDS)


def test_doc_and_code_have_the_same_applies_to() -> None:
    for field, types in doc_table().items():
        assert types == set(BY_ID[field].applies_to), field


def test_doc_names_the_schema_version() -> None:
    assert f"schema_version {SCHEMA_VERSION}" in DOC.read_text()


def test_field_count_and_removed_draft_fields() -> None:
    assert len(FIELD_IDS) == 23
    for gone in (
        "submission_deadline",
        "bid_opening",
        "question_deadline",
        "briefing_session",
        "submission_method",
    ):
        assert gone not in FIELD_IDS


def test_wakayama_deadlines_2f2f5bd3() -> None:
    n = validate_normalized(
        "deadlines",
        {
            "items": [
                {
                    "kind": "bid_in_person",
                    "datetime": "2026-10-27T14:00:00+09:00",
                    "citations": ["p3_s30"],
                },
                {
                    "kind": "mail_arrival",
                    "datetime": "2026-10-26T17:00:00+09:00",
                    "flags": ["arrival_required"],
                    "citations": ["p3_s31"],
                },
                {
                    "kind": "question",
                    "datetime": "2026-10-01T17:00:00+09:00",
                    "citations": ["p3_s20"],
                },
            ]
        },
    )
    assert n is not None


@pytest.mark.parametrize(
    "field, value",
    [
        ("deadlines", {"items": [{"kind": "question", "citations": ["a"]}]}),
        (
            "deadlines",
            {
                "items": [
                    {"kind": "question", "datetime": "2026-02-30", "citations": ["a"]}
                ]
            },
        ),
        (
            "deadlines",
            {
                "items": [
                    {
                        "kind": "question",
                        "datetime": "2026-10-01",
                        "relative_text": "x",
                        "citations": ["a"],
                    }
                ]
            },
        ),
        ("deadlines", {"items": []}),
        (
            "deadlines",
            {
                "items": [
                    {
                        "kind": "question",
                        "datetime": "2026-10-01T17:00:00",
                        "citations": ["a"],
                    }
                ]
            },
        ),  # no offset
        ("submission_modes", {"modes": ["mail"], "mail_not_allowed": True}),
        ("submission_modes", {"modes": []}),
        ("bid_bond", {"status": "waived", "rate_percent": 5}),
        ("bid_bond", {"status": "required", "rate_percent": 0}),
        ("tax_basis", {"basis": "unknown"}),
        ("contact", {}),
        ("title", {"x": 1}),
    ],
)
def test_models_reject(field: str, value: dict) -> None:
    with pytest.raises((ValidationError, ValueError)):
        validate_normalized(field, value)


def test_models_accept_documented_shapes() -> None:
    validate_normalized("bid_bond", {"status": "required", "rate_percent": 5})
    validate_normalized("bid_bond", {"status": "waived_with_proviso"})
    validate_normalized(
        "submission_modes", {"modes": ["in_person"], "mail_not_allowed": True}
    )
    validate_normalized("spec_access", {"mode": "email_after_pledge"})
    validate_normalized("wto_covered", {"covered": False})
    validate_normalized("title", None)
