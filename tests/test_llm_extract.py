# ruff: noqa: E501
"""core/shiori_core/extract/llm.py with a fake model (no server, no network). Sentences are
wording from collected open documents (doc id prefix in each test name)."""

import json

import pytest
from shiori_core.extract import llm
from shiori_core.models import Sentence
from shiori_core.normalize import normalize


def sent(i: str, text: str, titles: list[str] | None = None) -> Sentence:
    norm, m = normalize(text)
    t = titles or []
    return Sentence(id=i, page=0, section_path=[str(k) for k in range(len(t))], section_titles=t,
                    text_orig=text, text_norm=norm, norm_to_orig=m, boxes=[])  # fmt: skip


def fake(answers: dict[str, dict]):
    """A model that answers per field, found from the 'Field:' line of the prompt."""

    def complete(system: str, user: str, schema: dict, max_out: int) -> str:
        return json.dumps(
            answers[user.split("Field: ")[1].split("\n")[0]], ensure_ascii=False
        )

    return complete


DOC = [
    sent("h_s1", "調達情報の詳細"),
    sent("h_s2", "競争参加資格", ["競争参加資格"]),
    sent("h_s3", "(2)　予算決算及び会計令第71条の規定に該当しない者であること。", ["競争参加資格", "第71条"]),
    sent("h_s4", "(4)　入札書の受領期限　令和８年10月21日17時00分", ["入札書の提出場所等", "入札書の受領期限"]),
]  # fmt: skip


def test_retrieve_f19cddbd4cba_heading_cue_and_window() -> None:
    far = [sent(f"h_s{n}", "無関係") for n in range(10, 20)]
    got = llm.retrieve("eligibility", DOC + far)
    assert [s.id for s in got][:2] == [
        "h_s1",
        "h_s2",
    ]  # window reaches the sentence above the cue
    assert "h_s19" not in [s.id for s in got]


def test_retrieve_nothing_means_no_call() -> None:
    calls = []
    out = llm.extract_lists(
        "notice", [sent("h_s1", "無関係")], lambda *a: calls.append(a) or "{}"
    )
    assert out == {} and calls == []


def test_items_pass_the_checks_f19cddbd4cba() -> None:
    ok = {"kind": "legal", "polarity": "requirement", "text_ja": "予算決算及び会計令第71条の規定に該当しない者であること。", "citations": ["h_s3"]}  # fmt: skip
    bad_text = {**ok, "text_ja": "書いていない文", "citations": ["h_s3"]}
    bad_id = {**ok, "citations": ["p9_s9"]}
    stats: list[llm.CallStat] = []
    out = llm.extract_lists("notice", DOC, fake({"eligibility": {"items": [ok, bad_text, bad_id, ok]}, "deadlines": {"items": []}, "required_documents": {"items": []}}), stats)  # fmt: skip
    assert out["eligibility"].citations == ["h_s3"]
    assert len(out["eligibility"].normalized["items"]) == 1
    s = stats[0]
    assert (s.proposed, s.kept, s.dropped) == (4, 1, {"value_not_in_citation": 1, "unknown_id": 1, "duplicate": 1})  # fmt: skip
    assert (
        "deadlines" not in out and "required_documents" not in out
    )  # empty answer: not found


def test_deadline_date_and_time_checked_and_completed_f19cddbd4cba() -> None:
    item = {"kind": "other", "datetime": "2026-10-21", "relative_text": None, "flags": [], "citations": ["h_s4"]}  # fmt: skip
    out = llm.extract_lists("notice", DOC, fake({"eligibility": {"items": []}, "required_documents": {"items": []}, "deadlines": {"items": [item]}}))  # fmt: skip
    assert (
        out["deadlines"].normalized["items"][0]["datetime"]
        == "2026-10-21T17:00:00+09:00"
    )  # the lone time is added
    wrong = {
        **item,
        "datetime": "2026-10-22T17:00:00+09:00",
    }  # a date the sentence does not give
    out = llm.extract_lists("notice", DOC, fake({"eligibility": {"items": []}, "required_documents": {"items": []}, "deadlines": {"items": [wrong]}}))  # fmt: skip
    assert "deadlines" not in out


def test_flags_come_from_the_cited_wording() -> None:
    ss = [
        sent("h_s1", "提出期限", ["提出期限"]),
        sent("h_s2", "令和８年10月26日17時00分必着"),
    ]
    item = {"kind": "mail_arrival", "datetime": "2026-10-26T17:00:00+09:00", "relative_text": None, "flags": [], "citations": ["h_s2"]}  # fmt: skip
    out = llm.extract_lists("notice", ss, fake({"eligibility": {"items": []}, "required_documents": {"items": []}, "deadlines": {"items": [item]}}))  # fmt: skip
    assert out["deadlines"].normalized["items"][0]["flags"] == ["arrival_required"]


def test_a_failed_call_is_not_found_and_counted() -> None:
    def broken(*a: object) -> str:
        raise OSError("down")

    stats: list[llm.CallStat] = []
    assert llm.extract_lists("notice", DOC, broken, stats) == {}
    assert all(s.call_failed == "OSError" for s in stats)


def test_spec_documents_have_no_list_fields() -> None:
    assert llm.extract_lists("spec", DOC, lambda *a: "{}") == {}


def test_schema_allows_an_empty_list_and_has_no_translation_keys() -> None:
    for f in llm.LIST_FIELDS:
        s = llm.schema_for(f)
        assert s["properties"]["items"]["minItems"] == 0
        assert not any(
            k in d["properties"] for d in s["$defs"].values() for k in llm.DROP_PROPS
        )


def test_client_is_loopback_only() -> None:
    llm.Client(8792)
    with pytest.raises(ValueError):
        llm.Client(8792, host="example.com")


# --- time check: the time must sit in the date's own span (594c3cb6 h_s49) ---------------

OPENING = "(4) 開札の日時及び場所　令和８年10月２日　午前11時　内閣府庁舎１階第１入札室（郵送による場合は令和８年10月２日　午前９時30分までに必着のこと）"  # fmt: skip


def deadline(kind: str, when: str) -> dict:
    return {"kind": kind, "datetime": when, "relative_text": None, "flags": [], "citations": ["h_s49"]}  # fmt: skip


def run_deadline(item: dict) -> list[dict]:
    ss = [sent("h_s48", "(3) 提案書の提出期限　令和８年９月17日　正午", ["提案書の提出期限"]), sent("h_s49", OPENING)]  # fmt: skip
    empty = {"items": []}
    out = llm.extract_lists("notice", ss, fake({"eligibility": empty, "required_documents": empty, "deadlines": {"items": [item]}}))  # fmt: skip
    return out["deadlines"].normalized["items"] if "deadlines" in out else []


def test_mail_time_cannot_pass_for_the_bid_opening_594c3cb69c53() -> None:
    assert (
        run_deadline(deadline("bid_opening", "2026-10-02T09:30:00+09:00")) == []
    )  # the wrong time is dropped


def test_opening_time_passes_without_the_mail_flag_594c3cb69c53() -> None:
    (it,) = run_deadline(deadline("bid_opening", "2026-10-02T11:00:00+09:00"))
    assert it["flags"] == []  # 必着 belongs to the mail span, not to the opening


def test_mail_time_passes_for_the_mail_arrival_with_its_flag_594c3cb69c53() -> None:
    (it,) = run_deadline(deadline("mail_arrival", "2026-10-02T09:30:00+09:00"))
    assert it["flags"] == ["arrival_required"]
    assert run_deadline(deadline("mail_arrival", "2026-10-02T11:00:00+09:00")) == []


def test_a_lone_time_elsewhere_in_the_citations_does_not_count() -> None:
    ss = [sent("h_s1", "提出期限", ["提出期限"]), sent("h_s2", "令和８年９月17日"), sent("h_s3", "午後５時00分")]  # fmt: skip
    item = {"kind": "other", "datetime": "2026-09-17T17:00:00+09:00", "relative_text": None, "flags": [], "citations": ["h_s2", "h_s3"]}  # fmt: skip
    empty = {"items": []}
    out = llm.extract_lists("notice", ss, fake({"eligibility": empty, "required_documents": empty, "deadlines": {"items": [item]}}))  # fmt: skip
    assert "deadlines" not in out  # the time is in another sentence than the date


# --- failure rule: one retry, then not found; a cut answer is not retried --------------------


def answers(*steps):
    """A model that does each step in turn: an exception is raised, a string returned."""
    it = iter(steps)

    def complete(*a: object) -> str:
        step = next(it)
        if isinstance(step, Exception):
            raise step
        return step

    return complete


ITEM = {"kind": "legal", "polarity": "requirement", "text_ja": "予算決算及び会計令第71条の規定に該当しない者であること。", "citations": ["h_s3"]}  # fmt: skip
GOOD = json.dumps({"items": [ITEM]}, ensure_ascii=False)
ONLY_ELIGIBILITY = [sent("h_s2", "競争参加資格", ["競争参加資格"]), DOC[2]]


def test_one_retry_then_the_answer_counts() -> None:
    stats: list[llm.CallStat] = []
    out = llm.extract_lists("notice", ONLY_ELIGIBILITY, answers(TimeoutError(), GOOD, "{}", "{}"), stats)  # fmt: skip
    assert (
        "eligibility" in out and stats[0].retries == 1 and stats[0].call_failed is None
    )


def test_two_failures_are_not_found() -> None:
    stats: list[llm.CallStat] = []
    out = llm.extract_lists("notice", ONLY_ELIGIBILITY, answers(TimeoutError(), ValueError(), "{}", "{}", "{}", "{}"), stats)  # fmt: skip
    assert "eligibility" not in out and stats[0].call_failed == "ValueError"


def test_a_cut_answer_is_not_retried() -> None:
    calls: list[str] = []

    def cut(system: str, user: str, *a: object) -> str:
        calls.append(user.split("Field: ")[1].split("\n")[0])
        raise llm.Truncated("cap")

    llm.extract_lists("notice", ONLY_ELIGIBILITY, cut)
    assert len(calls) == len(set(calls))  # each field asked once


def test_schema_has_no_flags_and_bounded_arrays_58f13b9c() -> None:
    s = llm.schema_for("deadlines")
    assert "flags" not in s["$defs"]["DeadlineItem"]["properties"]
    assert s["properties"]["items"]["maxItems"] == llm.MAX_ITEMS
    assert (
        s["$defs"]["DeadlineItem"]["properties"]["citations"]["maxItems"]
        == llm.MAX_CITES
    )


def test_required_documents_reads_document_style_headings() -> None:
    """D-69 addendum: 書類, 入札方法 and 入札者に要求される事項 headings count for
    required_documents only (heading text taken from 563042df9941 and 84e9d0c8325c)."""
    ss = [sent(f"h_s{n}", "無関係な文") for n in range(1, 12)]
    ss[10] = sent("h_s11", "入札書を提出すること", ["競争入札に付する事項", "入札方法"])
    assert "h_s11" in [s.id for s in llm.retrieve("required_documents", ss)]
    assert llm.retrieve("eligibility", ss) == []  # other fields keep their own cues
