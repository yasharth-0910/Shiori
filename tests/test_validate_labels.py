"""Label models and the document-level validator (eval_protocol.md, Label files).

Sentence text is from real notices: Hokkaido fb226cbd... p1_s22 (the bid time).
"""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from shiori_core.fields import FIELD_IDS, SCHEMA_VERSION
from shiori_core.models import EXTRACTOR_VERSION, Sentence
from shiori_core.normalize import normalize

from collector.manifest import ManifestRow
from eval.label_format import LabelLine, Provenance
from eval.validate_labels import check_path, validate_lines

BID = "(2) 入札日時 令和８年（2026年）９月10日（木）午後１時30分"
BOND = "入札保証金 免除。契約保証金 契約金額の100分の10以上とする。"


def sent(id: str, text: str, language: str = "ja") -> Sentence:
    norm, idx = normalize(text)
    return Sentence.model_validate(
        dict(
            id=id,
            page=1,
            section_path=[],
            section_titles=[],
            text_orig=text,
            text_norm=norm,
            norm_to_orig=idx,
            boxes=[],
            language=language,
        )
    )


SENTENCES = [
    sent("p1_s22", BID),
    sent("p1_s23", BOND),
    sent("p1_s24", "Bids are due 10 September 2026 at 13:30.", "en"),
]


def row(doc_type: str = "notice", license_class: str = "open") -> ManifestRow:
    return ManifestRow.model_validate(
        dict(
            doc_id="d1",
            source="hokkaido",
            url="u",
            landing_url="l",
            issuer_org="北海道",
            title_ja="t",
            doc_type=doc_type,
            notice_date=None,
            wto_covered=None,
            jetro_ref=None,
            pages=1,
            text_layer="full",
            fetched_at=datetime(2026, 10, 2),
            license_note="",
            license_class=license_class,
            format="pdf",
            is_it=False,
            path="p",
        )
    )


def prov(**kw: object) -> dict:
    return {"final_state": "silver_unreviewed", **kw}


def line(field: str, status: str = "absent", **kw: object) -> dict:
    return {
        "doc_id": "d1",
        "extractor_version": EXTRACTOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "field": field,
        "status": status,
        "provenance": prov(),
        **kw,
    }


def deadline(
    dt: str = "2026-09-10T13:30:00+09:00", cites: list[str] | None = None
) -> dict:
    cites = cites or ["p1_s22"]
    return line(
        "deadlines",
        "present",
        citations=cites,
        normalized={
            "items": [{"kind": "bid_in_person", "datetime": dt, "citations": cites}]
        },
    )


def file(**over: dict) -> list[dict]:
    """All 23 fields absent, with `over` replacing some by field id."""
    return [over.get(f, line(f)) for f in FIELD_IDS]


def test_valid_file_has_no_errors() -> None:
    lines = file(
        deadlines=deadline(),
        bid_bond=line(
            "bid_bond",
            "present",
            value_ja="入札保証金 免除",
            citations=["p1_s23"],
            normalized={"status": "waived"},
        ),
        performance_bond=line(
            "performance_bond",
            "present",
            citations=["p1_s23"],
            normalized={"status": "required", "rate_percent": 10},
        ),
    )
    assert validate_lines(lines, row(), SENTENCES) == []


def test_date_and_time_must_be_readable_in_the_citation() -> None:
    errs = validate_lines(
        file(deadlines=deadline("2026-09-11T13:30:00+09:00")), row(), SENTENCES
    )
    assert any("2026-09-11" in e for e in errs)
    errs = validate_lines(
        file(deadlines=deadline("2026-09-10T14:00:00+09:00")), row(), SENTENCES
    )
    assert any("14:00" in e for e in errs)


def test_bond_rate_must_be_in_the_citation() -> None:
    bad = line(
        "performance_bond",
        "present",
        citations=["p1_s23"],
        normalized={"status": "required", "rate_percent": 5},
    )
    errs = validate_lines(file(performance_bond=bad), row(), SENTENCES)
    assert any("rate 5.0%" in e for e in errs)


def test_citations_must_exist_and_be_japanese() -> None:
    errs = validate_lines(file(deadlines=deadline(cites=["p9_s1"])), row(), SENTENCES)
    assert any("p9_s1" in e for e in errs)
    errs = validate_lines(file(deadlines=deadline(cites=["p1_s24"])), row(), SENTENCES)
    assert any("English" in e for e in errs)


def test_field_that_does_not_apply_must_be_absent() -> None:
    errs = validate_lines(file(deadlines=deadline()), row("spec"), SENTENCES)
    assert any("does not apply to doc_type spec" in e for e in errs)


def test_one_line_per_field_and_versions() -> None:
    errs = validate_lines(file()[:-1], row(), SENTENCES)
    assert any("missing" in e for e in errs)
    old = [{**x, "extractor_version": "0.2.0"} for x in file()]
    assert any("extractor_version" in e for e in validate_lines(old, row(), SENTENCES))
    with pytest.raises(ValidationError):
        LabelLine.model_validate({**line("title"), "schema_version": "0.9"})


@pytest.mark.parametrize(
    "kw",
    [
        {"reviewed_by": "claude_chat", "final_state": "human_audited"},
        {"reviewed_by": "yasharth", "final_state": "human_audited"},
        {"reviewed_by": None, "final_state": "human_audited"},
        {"reviewed_by": "native_speaker", "final_state": "silver_consensus"},
        {"reviewed_by": "claude_chat", "final_state": "silver_unreviewed"},
        {"final_state": "silver_consensus"},  # no agreement
        {"agreement": True, "final_state": "silver_unreviewed"},  # one labeler or none
    ],
)
def test_only_native_speaker_review_is_human_audited(kw: dict) -> None:
    with pytest.raises(ValidationError):
        Provenance.model_validate(kw)


def test_provenance_accepts_the_documented_states() -> None:
    two = [{"provider": "a", "model": "m", "date": "2026-10-03"}] * 2
    Provenance.model_validate(
        {"pre_labelers": two, "agreement": True, "final_state": "silver_consensus"}
    )
    Provenance.model_validate(
        {"reviewed_by": "native_speaker", "final_state": "human_audited"}
    )
    Provenance.model_validate(
        {
            "reviewed_by": "yasharth",
            "review_note": "heading cue ok",
            "final_state": "silver_unreviewed",
        }
    )


@pytest.mark.parametrize(
    "bad",
    [
        line("title", "absent", value_ja="x"),
        line("title", "present", citations=["p1_s22"]),  # no value_ja
        line(
            "bid_bond",
            "present",
            citations=["p1_s23"],
            normalized={"status": "not_stated"},
        ),
        line(
            "spec_access",
            "present",
            citations=["p1_s23"],
            normalized={"mode": "see_other_document"},
        ),
        line("spec_access", "see_other_document", citations=["p1_s23"]),  # no ref
        line(
            "deadlines",
            "present",
            citations=["p1_s22", "p1_s23"],
            normalized={
                "items": [
                    {"kind": "other", "relative_text": "x", "citations": ["p1_s22"]}
                ]
            },
        ),
    ],
)
def test_status_rules(bad: dict) -> None:
    with pytest.raises(ValidationError):
        LabelLine.model_validate(bad)


def test_see_other_document_with_ref() -> None:
    LabelLine.model_validate(
        line(
            "eligibility",
            "see_other_document",
            citations=["p1_s23"],
            normalized={"ref": {"kind": "kokuji", "text_ja": "告示第11351号"}},
        )
    )


def test_d24_path_rule_and_split_dir() -> None:
    splits = {"北海道": "test"}
    ok = Path("data/eval/test/labels/d1.jsonl")
    assert check_path(ok, row(), splits) == []
    assert check_path(
        Path("data/eval/test/labels/d1.jsonl"), row(license_class="restricted"), splits
    )
    assert check_path(Path("data/eval_private/test/labels/d1.jsonl"), row(), splits)
    assert check_path(Path("data/eval/dev/labels/d1.jsonl"), row(), splits)
    assert (
        check_path(
            Path("data/eval_private/test/labels/d1.jsonl"),
            row(license_class="unknown"),
            splits,
        )
        == []
    )


# Text fields with see_other_document (sv2 step 0). h_s30 is real: doc 563042df9941
# (内閣府 notice), section 2(3), the delivery place is per the bid instructions. The
# present-value sentence p1_s1 is made up.
PLACE = "東京都千代田区永田町１－６－１"
POINTER = [sent("h_s30", "入札説明書による。"), sent("p1_s1", "納入場所 " + PLACE)]


def test_text_field_see_other_document_label_is_valid() -> None:
    ref = {"ref": {"kind": "bid_instructions", "text_ja": "入札説明書による。"}}
    lines = file(
        delivery_location=line(
            "delivery_location", "see_other_document", value_ja="入札説明書による。",
            normalized=ref, citations=["h_s30"],
        )
    )  # fmt: skip
    assert validate_lines(lines, row(), POINTER) == []
    # the ref is stored in normalized exactly as for structured fields; without it the
    # line is refused
    bad = line("delivery_location", "see_other_document", citations=["h_s30"])
    with pytest.raises(ValidationError, match="ref"):
        LabelLine.model_validate(bad)


def test_present_text_field_label_has_no_normalized() -> None:
    ok = line("delivery_location", "present", value_ja=PLACE, citations=["p1_s1"])
    assert validate_lines(file(delivery_location=ok), row(), POINTER) == []
    with pytest.raises(ValidationError, match="text fields have normalized: null"):
        LabelLine.model_validate({**ok, "normalized": {"x": 1}})
