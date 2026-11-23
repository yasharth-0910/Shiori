# ruff: noqa: E501, F811  (F811: the env fixture is imported)
"""webimport (D-104): Gemini web-chat answers stored as the raw answers of labeler web.
Fake answer for dev document 2f2f5bd3 (open, Wakayama) on the sentences of
tests/test_silver.py, in a temp directory. No network, no model."""

import json

import pytest
from shiori_core.fields import BY_ID

from eval.silver import config, pipeline, run
from eval.silver.prompt import applicable_fields
from eval.silver.webimport import webimport
from tests.test_silver import (  # noqa: F401  (env is a fixture)
    GOOD,
    SENTENCES,
    env,
    row,
)

DOC = "2f2f5bd3" + "0" * 4


def reply(
    over: dict | None = None, notes: str = "* title | p1_s1 | kept the prefix\n"
) -> str:
    fields, norm = {}, {}
    for f in applicable_fields("notice"):
        e = {
            "status": "absent",
            "ref": None,
            "value_ja": "",
            "value_en": "",
            "citations": [],
            "reason": "r",
        }
        e.update(
            {
                k: v
                for k, v in {**GOOD, **(over or {})}.get(f, {}).items()
                if k != "normalized"
            }
        )
        fields[f] = e
        if BY_ID[f].kind != "text":
            norm[f] = {**GOOD, **(over or {})}.get(f, {}).get("normalized")
    body = json.dumps(
        {"fields": fields, "normalized": norm}, ensure_ascii=False, indent=2
    )
    return f"```json\n{body}\n```\n\n## Uncertain points\n\n{notes}"


@pytest.fixture
def web(env, monkeypatch):
    ls = env.tmp / "label_set.json"
    ls.write_text(json.dumps({"dev": [{"doc_id": DOC, "group": "notice", "license_class": "open"},
                                      {"doc_id": "d9", "group": "notice", "license_class": "restricted"}], "test": []}))  # fmt: skip
    monkeypatch.setattr(run, "LABEL_SET", ls)
    monkeypatch.setattr(run, "read_rows", lambda: [row(doc_id=DOC), row(doc_id="d9", license_class="restricted")])  # fmt: skip
    d = env.tmp / "answers"
    d.mkdir()
    return d, env.tmp / "check.md"


def test_good_answer_is_stored_checked_and_noted(web):
    d, rep = web
    (d / "2f2f5bd3.md").write_text(reply(), encoding="utf-8")
    text, n = webimport(d, rep)
    assert n == 0, text
    assert "| 2f2f5bd3 | notice | 23 | 23 | 0 | 1 | 1 |" in text
    raw = json.loads(pipeline.raw_path(DOC, "web", "gemini-web", "sv4-web").read_text())
    assert raw["prompt_version"] == "sv4-web" and raw["chunks"]["0"]["uncertain_notes"] == ["title | p1_s1 | kept the prefix"]  # fmt: skip
    got = pipeline.answers(raw, "web/gemini-web", applicable_fields("notice"))
    assert got["title"].value_ja == "庁舎清掃業務" and got["bid_bond"].normalized == {"status": "waived"}  # fmt: skip
    assert pipeline.raw_state(raw) == "complete"
    assert "- 2f2f5bd3 tax_basis heading_cue" in text  # advisory: listed, not counted
    assert text.isascii()  # ids, field names and counts only


def test_failing_checks_are_listed_and_answer_is_not_fixed(web):
    d, rep = web
    bad = {"title": {"status": "present", "value_ja": "別の件名", "citations": ["p1_s1"]},
           "bid_bond": {"status": "present", "citations": ["p9_s9"], "normalized": {"status": "waived"}}}  # fmt: skip
    (d / "2f2f5bd3.md").write_text(reply(bad), encoding="utf-8")
    text, n = webimport(d, rep)
    assert n == 2
    assert "- 2f2f5bd3 title value_in_citation" in text and "- 2f2f5bd3 bid_bond citations_exist" in text  # fmt: skip
    raw = json.loads(pipeline.raw_path(DOC, "web", "gemini-web", "sv4-web").read_text())
    assert "別の件名" in raw["chunks"]["0"]["response"]  # stored as sent


def test_refuses_restricted_excluded_and_unparsable(web):
    d, rep = web
    (d / "d9.md").write_text(reply(), encoding="utf-8")
    (d / "52bba5f9.md").write_text(reply(), encoding="utf-8")
    (d / "2f2f5bd3.md").write_text("no json here", encoding="utf-8")
    text, n = webimport(d, rep)
    assert n == 3
    assert (
        "not open (D-62)" in text
        and "excluded (D-102)" in text
        and "0 json blocks" in text
    )
    assert not (config.CACHE / "raw").exists()


def test_missing_field_is_a_structure_failure(web):
    d, rep = web
    t = reply()
    body = json.loads(t.split("```")[1][4:])
    del body["fields"]["title"]
    (d / "2f2f5bd3.md").write_text(
        "```json\n" + json.dumps(body) + "\n```\n", encoding="utf-8"
    )
    text, n = webimport(d, rep)
    assert n == 1 and "- 2f2f5bd3 title structure: missing" in text
