"""eval.gemini_compare: the comparison rules, on made-up strings (no document text)."""

from shiori_core.extract.rules import Extracted

from eval.gemini_compare import compare, gemini_found, officer_tokens


def ex(field: str, value_ja: str, normalized: dict | None = None) -> Extracted:
    return Extracted(
        field=field, value_ja=value_ja, normalized=normalized or {}, citations=["s1"]
    )


def test_not_stated_variants():
    assert not gemini_found("Not stated (see the other file)")
    assert not gemini_found("In another document: X")
    assert gemini_found("Notice of Withdrawal")  # a real title that starts with "Not"


def test_title_contains():
    assert (
        compare(
            "title", ex("title", "令和8年度 テスト業務"), "x", "令和8年度テスト業務"
        )[0]
        == "both_found_agree"
    )
    assert compare("title", ex("title", "甲"), "x", "乙")[0] == "both_found_differ"


def test_issuer_uses_answer_en():
    c = compare(
        "issuer_org",
        ex("issuer_org", "テスト県知事"),
        "Test Prefecture — テスト県 (Tesuto-ken)",
        "",
    )
    assert c[0] == "both_found_agree"


def test_officer_name_and_title_only():
    assert officer_tokens("Governor, 山田 太郎 (Yamada Taro)") == [
        "山田",
        "太郎",
    ] or officer_tokens("x 山田太郎 y") == ["山田太郎"]
    ours = ex("contracting_officer", "x", {"name": "山田 太郎"})
    assert (
        compare("contracting_officer", ours, "Governor, 山田 太郎 (Yamada Taro)", "")[0]
        == "both_found_agree"
    )
    assert (
        compare(
            "contracting_officer",
            ours,
            "Head (individual name not stated) 会計担当参事官",
            "",
        )[0]
        == "we_found_gemini_not_stated"
    )


def test_dates():
    n = ex("notice_date", "x", {"date": "2026-09-15"})
    assert compare("notice_date", n, "x", "令和8年9月15日")[0] == "both_found_agree"
    assert compare("notice_date", n, "x", "令和8年9月16日")[0] == "both_found_differ"
    p = ex("performance_period", "x", {"start": None, "end": "2027-03-31"})
    assert (
        compare("performance_period", p, "x", "契約締結日から令和9年3月31日まで")[0]
        == "both_found_agree"
    )
    assert (
        compare("performance_period", None, "x", "令和9年3月31日まで")[0]
        == "gemini_found_we_not_found"
    )
    assert compare("performance_period", None, "Not stated", "")[0] == "both_not_found"


def rf(field, normalized, status="present"):
    return Extracted(
        field=field,
        value_ja="x",
        normalized=normalized,
        citations=["s1"],
        status=status,
    )


def test_rule_fields_enums_and_unmapped():
    pt = rf("procurement_type", {"type": "open_competitive"})
    assert (
        compare("procurement_type", pt, "Open competitive bidding", "")[0]
        == "both_found_agree"
    )
    assert (
        compare("procurement_type", pt, "Proposal competition (x)", "")[0]
        == "both_found_differ"
    )
    # two types in the head, or none: counted as unmapped, not guessed
    assert (
        compare(
            "procurement_type", pt, "Proposal competition / public solicitation", ""
        )[0]
        == "unmapped"
    )
    assert compare("award_method", None, "Something else entirely", "")[0] == "unmapped"
    assert (
        compare("tax_basis", None, "Both tax-excluded and tax-included", "")[0]
        == "unmapped"
    )
    tb = rf("tax_basis", {"basis": "bid_excludes_tax"})
    assert (
        compare("tax_basis", tb, "Excludes consumption tax (includes 10% later)", "")[0]
        == "both_found_agree"
    )
    assert compare("wto_covered", None, "Not stated", "")[0] == "both_not_found"
    wt = rf("wto_covered", {"covered": True})
    assert (
        compare("wto_covered", wt, "Yes, governed by an order", "")[0]
        == "both_found_agree"
    )


def test_rule_fields_bond_modes_pointer():
    b = rf("bid_bond", {"status": "required", "rate_percent": 5.0})
    assert (
        compare("bid_bond", b, "Required at 5/100 (5%); waived with conditions", "")[0]
        == "both_found_agree"
    )
    assert compare("bid_bond", b, "Required at 10/100", "")[0] == "both_found_differ"
    assert compare("bid_bond", b, "Waived", "")[0] == "both_found_differ"
    m = rf("submission_modes", {"modes": ["electronic"], "mail_not_allowed": False})
    assert (
        compare("submission_modes", m, "Electronic (by email)", "")[0]
        == "both_found_agree"
    )
    assert (
        compare("submission_modes", m, "In person or by mail", "")[0]
        == "both_found_differ"
    )
    sp = rf("spec_access", {"ref": {"kind": "spec"}}, status="see_other_document")
    assert (
        compare("spec_access", sp, "In another document: the spec", "")[0]
        == "both_found_agree"
    )
    assert (
        compare("bid_bond", None, "In another document: x", "")[0] == "both_not_found"
    )
    uq = rf("unified_qualification", {"grades": ["A", "B"]})
    assert (
        compare("unified_qualification", uq, "Unified qualification, Grade A or B", "")[
            0
        ]
        == "both_found_agree"
    )
    assert (
        compare("unified_qualification", uq, "Local equivalent: city list", "")[0]
        == "both_found_differ"
    )


def test_submission_refusal_wording():
    m = rf(
        "submission_modes", {"modes": ["in_person", "mail"], "mail_not_allowed": False}
    )
    assert (
        compare(
            "submission_modes",
            m,
            "In person or by mail. Mail is permitted (not refused).",
            "",
        )[0]
        == "both_found_agree"
    )
    assert (
        compare(
            "submission_modes",
            m,
            "In person or registered mail only (ordinary mail is invalid)",
            "",
        )[0]
        == "both_found_agree"
    )
    r = rf("submission_modes", {"modes": ["in_person"], "mail_not_allowed": True})
    assert (
        compare("submission_modes", r, "In person. Mail bids are refused.", "")[0]
        == "both_found_agree"
    )
