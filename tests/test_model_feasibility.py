"""Checks for the dev-time model bench (eval/model_feasibility.py)."""

import json

import pytest

from eval.model_feasibility import DOCS, ROOT, check_json, html_sentences


def test_check_json_requires_schema_and_known_ids() -> None:
    ok = json.dumps({"found": True, "deadline_text": "x", "sentence_ids": ["a"]})
    assert check_json(ok, {"a"}) == (True, True)
    assert check_json(ok, {"b"}) == (True, False)  # valid JSON, invented id
    assert check_json('{"found": "yes"}', set()) == (False, False)
    assert check_json('{"found": true, "deadline_', set()) == (False, False)  # cut off


@pytest.mark.corpus
def test_html_sentences_joins_wrapped_lines() -> None:
    path = ROOT / DOCS["wto_notice"]  # p-portal doc 70e1f40de5ce..., wraps at ~20 chars
    if not path.exists():
        pytest.skip("data/raw missing")
    texts = [t for _, t in html_sentences(path)]
    assert "(4) 入札書の受領期限 令和８年10月13日17時00分" in texts
    assert not any("Summary" in t for t in texts)
