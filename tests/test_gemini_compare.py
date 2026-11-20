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
