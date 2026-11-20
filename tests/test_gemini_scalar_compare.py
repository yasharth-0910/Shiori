"""eval.gemini_scalar_compare: variants and extra comparisons (made-up text)."""

from shiori_core.extract import llm
from shiori_core.extract.rules import Extracted

from eval.gemini_scalar_compare import B2, OLD_SYSTEM, VARIANTS, B, compare


def ex(field: str, value_ja: str, normalized: dict | None = None) -> Extracted:
    return Extracted(
        field=field, value_ja=value_ja, normalized=normalized or {}, citations=["s1"]
    )


def test_variants_are_pinned_to_the_old_prompt() -> None:
    assert "When unsure" in OLD_SYSTEM
    assert "When unsure" not in B and B2.startswith(B) and len(B2) > len(B)
    assert set(VARIANTS) == {"B", "B2"}
    assert "When unsure" not in llm.SCALAR_SYSTEM  # the shipped prompt moved on (D-95)


def test_delivery_deadline_by_iso_date() -> None:
    d = ex("delivery_deadline", "x", {"date": "2027-03-30"})
    assert compare("delivery_deadline", d, "x", "令和9年3月30日") == "both_found_agree"
    assert compare("delivery_deadline", d, "x", "令和9年3月31日") == "both_found_differ"
    assert compare("delivery_deadline", None, "Not stated", "") == "both_not_found"


def test_scope_and_location_contain_either_way() -> None:
    s = ex("scope_summary", "サンプル システムの保守業務")
    assert (
        compare("scope_summary", s, "x", "サンプルシステムの保守業務一式")
        == "both_found_agree"
    )
    assert (
        compare("delivery_location", None, "x", "サンプル市役所")
        == "gemini_found_we_not_found"
    )
    assert (
        compare("delivery_location", ex("delivery_location", "甲"), "Not stated", "")
        == "we_found_gemini_not_stated"
    )
