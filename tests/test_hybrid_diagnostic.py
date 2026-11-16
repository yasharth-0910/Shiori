# ruff: noqa: E501
"""eval/hybrid.py classify: the four reasons a label item is missed (no model, no corpus)."""

from shiori_core.extract.llm import CallStat

from eval.hybrid import classify


def req(text: str, ids: list[str], kind: str = "legal") -> dict:
    return {"kind": kind, "polarity": "requirement", "text_ja": text, "citations": ids}


def test_each_category() -> None:
    gold = [req("あ" * 12, ["h_s1"]), req("い" * 12, ["h_s2"]), req("う" * 12, ["h_s3"]), req("え" * 12, ["h_s4"], "other"), req("お" * 12, ["h_s9"])]  # fmt: skip
    stat = CallStat("eligibility", retrieved=["h_s1", "h_s2", "h_s3", "h_s4", "h_s5"])
    stat.trace = [
        (req("あ" * 12, ["h_s1"]), "kept"),  # hit
        (req("う" * 12, ["h_s3"]), "value_not_in_citation"),  # c
        (req("え" * 12, ["h_s4"], "legal"), "kept"),  # d: kind differs
    ]
    got = classify("eligibility", gold, stat)
    assert [c for c, _ in got] == ["hit", "b", "c", "d", "a"]
    assert got[2][1] == "value_not_in_citation" and got[3][1].startswith("d1")


def test_subcauses() -> None:
    from eval.hybrid import subcause

    g = req("予算決算及び会計令第７０条の規定に該当しない者であること。なお、未成年者は同意を得ている場合に該当する。", ["h_s1", "h_s2"])  # fmt: skip
    part = req("なお、未成年者は同意を得ている場合に該当する。", ["h_s2"], "other")
    assert subcause("eligibility", g, [part]) == (
        "d3",
        "real",
    )  # the なお sentence cut off
    neg = req("予算決算及び会計令第７１条の規定に該当しないこと", ["h_s3"])
    gold_neg = {**neg, "polarity": "disqualification"}
    assert subcause("eligibility", gold_neg, [neg]) == (
        "d2",
        "convention",
    )  # a kept negation
    assert subcause("eligibility", req("あ" * 30, ["h_s4"]), [req("い" * 30, ["h_s4"])]) == ("d4", "real")  # fmt: skip
    dl = {"kind": "mail_arrival", "datetime": "2026-09-15T11:00:00+09:00", "relative_text": None, "flags": [], "citations": ["h_s94", "h_s95"]}  # fmt: skip
    assert subcause("deadlines", dl, [{**dl, "kind": "bid_in_person"}]) == (
        "d1",
        "real",
    )
    assert subcause("deadlines", dl, [{**dl, "flags": ["arrival_required"]}]) == (
        "d5",
        "real",
    )


def test_diagnose_of_a_subset_counts_only_the_traced_documents() -> None:
    """The hold-out run traced 5 documents; the 9 other labeled ones are not its items."""
    from types import SimpleNamespace

    from eval.hybrid import State, traced_rows

    rows = [SimpleNamespace(doc_id=d * 12 + "x" * 52) for d in "abc"]
    State.stats = [
        ("a" * 12, CallStat("eligibility")),
        ("c" * 12, CallStat("deadlines")),
    ]
    try:
        assert [r.doc_id[0] for r in traced_rows(rows)] == ["a", "c"]  # type: ignore[arg-type]
    finally:
        State.stats = []
