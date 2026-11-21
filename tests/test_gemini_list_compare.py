# ruff: noqa: E501
"""eval.gemini_list_compare: matching rules (made-up text)."""

from eval.gemini_list_compare import match_how, match_items, pieces


def test_pieces_cut_at_ellipsis_and_drop_short() -> None:
    assert pieces("入札参加資格を有する者…ア\n 法人であること") == ["入札参加資格を有する者", "法人であること"]  # fmt: skip


def test_text_and_cited_match() -> None:
    assert match_how("法人であること", [], "次の要件 法人であること。") == "text"
    assert match_how("x", ["甲は法人であること。乙は別。"], "法人であること") == "cited"
    assert match_how("ab", ["ab"], "ab") == ""  # under 3 characters
    assert match_how("法人であること", [], "") == ""


def test_match_items_both_directions() -> None:
    ours = [{"value_ja": "法人であること", "cited_text": []}, {"value_ja": "無関係な文章です", "cited_text": []}]  # fmt: skip
    theirs = [{"quote_ja": "法人であること"}, {"quote_ja": "別の要件の文章"}]
    o, g = match_items(ours, theirs)
    assert o == [(0, "text"), None] and g == [(0, "text"), None]
