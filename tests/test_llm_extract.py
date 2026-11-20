# ruff: noqa: E501
"""core/shiori_core/extract/llm.py with a fake model (no server, no network). Sentences are
wording from collected open documents (doc id prefix in each test name)."""

import json
import threading

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


# --- Phase 5 fix 1 (eval/reports/phase5_fix1_changelog.md) -------------------------------------

BID = "(4)　入札書の受領期限　令和８年10月15日13時30分（ただし、郵送による入札は、令和８年10月14日16時00分必着）"
NONE = {"eligibility": {"items": []}, "required_documents": {"items": []}}


def deadline_run(
    item: dict, ss: list[Sentence], stats: list[llm.CallStat] | None = None
):
    return llm.extract_lists("notice", ss, fake({**NONE, "deadlines": {"items": [item]}}), stats)  # fmt: skip


def test_deadline_without_datetime_is_recovered_from_the_cited_sentence_f19cddbd4cba() -> (
    None
):
    ss = [sent("h_s44", "入札書の受領期限", ["入札書の受領期限"]), sent("h_s45", BID)]
    stats: list[llm.CallStat] = []
    mail = {
        "kind": "mail_arrival",
        "citations": ["h_s45"],
    }  # the model left datetime out
    other = {"kind": "other", "citations": ["h_s45"]}
    got = deadline_run(mail, ss, stats)["deadlines"].normalized["items"][0]
    assert got["datetime"] == "2026-10-14T16:00:00+09:00" and got["flags"] == ["arrival_required"]  # fmt: skip
    dl = next(x for x in stats if x.field == "deadlines")
    assert dl.recovered == 1 and dl.dropped == {}
    got = deadline_run(other, ss)["deadlines"].normalized["items"][0]
    assert got["datetime"] == "2026-10-15T13:30:00+09:00"  # the kind picks the span


def test_deadline_without_datetime_is_dropped_when_the_sentence_gives_no_single_date_f19cddbd4cba() -> None:  # fmt: skip
    two = sent(
        "h_s45", "受付期間　令和８年10月１日から令和８年10月15日まで", ["受付期間"]
    )
    stats: list[llm.CallStat] = []
    assert "deadlines" not in deadline_run({"kind": "other", "citations": ["h_s45"]}, [two], stats)  # fmt: skip
    dl = next(x for x in stats if x.field == "deadlines")
    assert dl.dropped == {"schema": 1} and dl.recovered == 0
    none = sent("h_s45", "入札書の受領期限は別途通知する。", ["入札書の受領期限"])
    assert "deadlines" not in deadline_run({"kind": "other", "citations": ["h_s45"]}, [none])  # fmt: skip
    cited_unknown = {"kind": "other", "citations": ["p9_s9"]}
    assert "deadlines" not in deadline_run(cited_unknown, [two])


def test_eligibility_kept_negation_is_a_requirement_f19cddbd4cba() -> None:
    text = "予算決算及び会計令第71条の規定に該当しない者であること。"
    ss = [
        sent("h_s2", "競争参加資格", ["競争参加資格"]),
        sent("h_s3", text, ["競争参加資格"]),
    ]

    def run(text_ja: str, pol: str) -> tuple[dict, llm.CallStat]:
        item = {
            "kind": "legal",
            "polarity": pol,
            "text_ja": text_ja,
            "citations": ["h_s3"],
        }
        stats: list[llm.CallStat] = []
        out = llm.extract_lists("notice", ss, fake({**NONE, "eligibility": {"items": [item]}, "deadlines": {"items": []}}), stats)  # fmt: skip
        return out["eligibility"].normalized["items"][0], stats[0]

    got, stat = run(text, "disqualification")  # guide: negation kept = requirement
    assert got["polarity"] == "requirement" and stat.polarity_set == 1
    got, stat = run(text, "requirement")
    assert got["polarity"] == "requirement" and stat.polarity_set == 0
    stripped = (
        "予算決算及び会計令第71条の規定に該当する者"  # not in the sentence: dropped
    )
    assert llm._polarity({"text_ja": stripped, "polarity": "disqualification"}) == "disqualification"  # fmt: skip


# --- fix 3: なお/ただし proviso merged into the item before it; 第73条 item is kind other (D-71) ---

S70 = "予算決算及び会計令第70条の規定に該当しない者であること。"
NAOSHI = "なお、未成年者、被保佐人又は被補助人であって、契約締結のために必要な同意を得ている者は、同条中、特別の理由がある場合に該当する。"
S73 = "予算決算及び会計令第73条の規定に基づき、支出負担行為担当官が定める資格を有する者であること。"


def elig(ss: list[Sentence], items: list[dict]) -> tuple[list[dict], llm.CallStat]:
    stats: list[llm.CallStat] = []
    ans = {"eligibility": {"items": items}, "deadlines": {"items": []}, "required_documents": {"items": []}}  # fmt: skip
    out = llm.extract_lists("notice", ss, fake(ans), stats)
    return (out["eligibility"].normalized["items"] if "eligibility" in out else []), next(s for s in stats if s.field == "eligibility")  # fmt: skip


def item(text: str, ids: list[str], kind: str = "legal") -> dict:
    return {"kind": kind, "polarity": "requirement", "text_ja": text, "citations": ids}


def test_proviso_is_merged_into_the_item_before_it_f19cddbd4cba() -> None:
    # h_s38 / h_s39 (and h_s40): the model gave the なお sentence as its own item
    ss = [sent("h_s37", "競争参加資格", ["競争参加資格"]), sent("h_s38", "(1)　" + S70, ["競争参加資格"]),
          sent("h_s39", NAOSHI, ["競争参加資格"]), sent("h_s40", "(2)　予算決算及び会計令第71条の規定に該当しない者であること。", ["競争参加資格"])]  # fmt: skip
    got, stat = elig(ss, [item(S70, ["h_s38"]), item(NAOSHI, ["h_s39"], "other"), item("予算決算及び会計令第71条の規定に該当しない者であること。", ["h_s40"])])  # fmt: skip
    assert [g["citations"] for g in got] == [["h_s38", "h_s39"], ["h_s40"]]
    assert got[0]["text_ja"] == S70 + "\n" + NAOSHI and got[0]["kind"] == "legal"
    assert stat.merged == 1 and stat.kept == 2 and [v for _, v in stat.trace] == ["kept", "merged", "kept"]  # fmt: skip


def test_proviso_the_model_left_out_is_added_563042df9941() -> None:
    # h_s40 / h_s41 (ただし, full-width numbers): the model cited only h_s40 and never mentioned h_s41
    t = "予算決算及び会計令第７０条の規定に該当しない者であること。"
    tadashi = "ただし、未成年者、被保佐人又は被補助人であって、契約締結のために必要な同意を得ている者については、この限りではない。"
    ss = [sent("h_s39", "競争参加資格", ["競争参加資格"]), sent("h_s40", "（１）" + t, ["競争参加資格"]), sent("h_s41", tadashi, ["競争参加資格"])]  # fmt: skip
    got, stat = elig(ss, [item(t, ["h_s40"])])
    assert (
        got[0]["citations"] == ["h_s40", "h_s41"]
        and got[0]["text_ja"] == t + "\n" + tadashi
    )
    assert stat.merged == 1


def test_proviso_with_no_item_before_it_stays_5d75d4a67c71() -> None:
    # h_s35 as the only item: nothing to merge into, so it is kept as it is
    ss = [sent("h_s33", "競争参加資格", ["競争参加資格"]), sent("h_s34", "(1)　" + S70, ["競争参加資格"]), sent("h_s35", NAOSHI, ["競争参加資格"])]  # fmt: skip
    got, stat = elig(ss, [item(NAOSHI, ["h_s35"], "other")])
    assert got == [{**item(NAOSHI, ["h_s35"], "other")}] and stat.merged == 0
    # the model already merged both: nothing follows h_s35, nothing changes
    got, _ = elig(ss, [item(S70 + "\n" + NAOSHI, ["h_s34", "h_s35"])])
    assert got[0]["text_ja"] == S70 + NAOSHI and got[0]["citations"] == [
        "h_s34",
        "h_s35",
    ]  # _check drops the model's line break (as before)


def test_article_73_item_is_kind_other_f19cddbd4cba_5d75d4a67c71() -> None:
    # f19cddbd4cba h_s43, 5d75d4a67c71 h_s38: the model said legal
    ss = [
        sent("h_s37", "競争参加資格", ["競争参加資格"]),
        sent("h_s43", "(4)　" + S73, ["競争参加資格"]),
    ]
    got, stat = elig(ss, [item(S73, ["h_s43"])])
    assert got[0]["kind"] == "other" and stat.kind_set == 1
    other = "予算決算及び会計令第73条の規定に該当しない者であること。"  # no own-qualification wording: unchanged
    ss2 = [
        sent("h_s37", "競争参加資格", ["競争参加資格"]),
        sent("h_s43", other, ["競争参加資格"]),
    ]
    got, stat = elig(ss2, [item(other, ["h_s43"])])
    assert got[0]["kind"] == "legal" and stat.kind_set == 0


# D-72: one event said twice with different kinds (5d75d4a67c71 h_s45 to h_s47)
DEADLINE_SENTS = {
    s.id: s
    for s in [
        sent("h_s45", "(2)　提出書類等の提出期限　令和８年10月２日17時00分までの平日又は電子調達システム", ["入札書の提出場所等", "提出書類等の提出期限"]),
        sent("h_s46", "(3)　入札書の提出期限　令和８年10月14日17時00分までの平日又は電子調達システム", ["入札書の提出場所等", "入札書の提出期限"]),
        sent("h_s47", "(4)　開札の日時及び場所　令和８年10月15日11時　市原刑務所庁舎大会議室及び電子調達システム", ["入札書の提出場所等", "開札の日時及び場所"]),
        sent("h_s60", "(5)　説明会の日時　令和８年10月２日17時00分", ["説明会"]),
    ]
}  # fmt: skip


def _read_deadlines(
    items: list[tuple[str, str, str]],
) -> tuple[list[dict], llm.CallStat]:
    raw = [{"kind": k, "datetime": d, "relative_text": None, "flags": [], "citations": [c]} for k, d, c in items]  # fmt: skip
    stat = llm.CallStat("deadlines")
    out = llm.read_items("deadlines", json.dumps({"items": raw}), DEADLINE_SENTS, stat)
    return out, stat


def test_deadline_same_datetime_same_sentence_keeps_the_cue_kind_5d75d4a67c71() -> None:
    out, stat = _read_deadlines([
        ("other", "2026-10-02T17:00:00+09:00", "h_s45"), ("electronic", "2026-10-02T17:00:00+09:00", "h_s45"),
        ("other", "2026-10-14T17:00:00+09:00", "h_s46"), ("electronic", "2026-10-14T17:00:00+09:00", "h_s46"),
        ("bid_opening", "2026-10-15T11:00:00+09:00", "h_s47"), ("electronic", "2026-10-15T11:00:00+09:00", "h_s47"),
    ])  # fmt: skip
    assert [(i["citations"][0], i["kind"]) for i in out] == [("h_s45", "other"), ("h_s46", "electronic"), ("h_s47", "bid_opening")]  # fmt: skip
    assert (stat.proposed, stat.kept, stat.dropped) == (6, 3, {"same_sentence": 3})
    assert [v for _, v in stat.trace].count("same_sentence") == 3


def test_deadline_same_datetime_different_sentences_both_stay_5d75d4a67c71() -> None:
    out, stat = _read_deadlines([
        ("other", "2026-10-02T17:00:00+09:00", "h_s45"), ("briefing", "2026-10-02T17:00:00+09:00", "h_s60"),
    ])  # fmt: skip
    assert [i["citations"][0] for i in out] == ["h_s45", "h_s60"] and stat.dropped == {}


def test_deadline_copies_stay_when_the_cue_picks_no_single_item_5d75d4a67c71() -> None:
    both = [("other", "2026-10-02T17:00:00+09:00", "h_s60"), ("briefing", "2026-10-02T17:00:00+09:00", "h_s60")]  # fmt: skip
    assert len(_read_deadlines(both)[0]) == 2  # h_s60 has no cue: nothing is guessed
    neither = [("briefing", "2026-10-14T17:00:00+09:00", "h_s46"), ("question", "2026-10-14T17:00:00+09:00", "h_s46")]  # fmt: skip
    assert (
        len(_read_deadlines(neither)[0]) == 2
    )  # cue says electronic or bid_in_person, neither is there


# --- fix 5 (D-73): copies of a merged proviso item; bid receipt other is electronic on an electronic notice ---


def test_copy_of_a_merged_proviso_item_is_dropped_d230e51e2805() -> None:
    # d230e51e2805 h_s40 / h_s41 (Qwen3.5-9B): one item cites h_s40 only and takes the proviso in
    # the merge; another, already citing h_s40 and h_s41, says the same thing afterwards
    ss = [sent("h_s39", "競争参加資格", ["競争参加資格"]), sent("h_s40", "(1)　" + S70, ["競争参加資格"]), sent("h_s41", NAOSHI, ["競争参加資格"])]  # fmt: skip
    got, stat = elig(ss, [item(S70, ["h_s40"]), item(S70 + NAOSHI, ["h_s40", "h_s41"])])
    assert [g["citations"] for g in got] == [["h_s40", "h_s41"]]
    assert (
        got[0]["text_ja"] == S70 + "\n" + NAOSHI
    )  # the merged item stays, not the copy
    assert (stat.merged, stat.copies, stat.kept) == (1, 1, 1)
    assert [v for _, v in stat.trace] == ["kept", "merged_copy"]
    # citations inside the merged item's, other text: also a copy
    part = "予算決算及び会計令第70条の規定に該当しない者"  # a shorter wording from the same sentence
    got, stat = elig(ss, [item(S70, ["h_s40"]), item(part, ["h_s40"])])
    assert [g["citations"] for g in got] == [["h_s40", "h_s41"]] and stat.copies == 1


def test_copy_rule_leaves_other_polarity_and_other_sentences_d230e51e2805() -> None:
    ss = [sent("h_s39", "競争参加資格", ["競争参加資格"]), sent("h_s40", "(1)　" + S70, ["競争参加資格"]), sent("h_s41", NAOSHI, ["競争参加資格"]),
          sent("h_s42", "(2)　予算決算及び会計令第71条の規定に該当しない者であること。", ["競争参加資格"])]  # fmt: skip
    other_pol = {
        **item(S70 + NAOSHI, ["h_s40", "h_s41"]),
        "polarity": "disqualification",
    }
    got, stat = elig(ss, [item(S70, ["h_s40"]), other_pol, item("予算決算及び会計令第71条の規定に該当しない者であること。", ["h_s42"])])  # fmt: skip
    assert [g["citations"] for g in got] == [["h_s40", "h_s41"], ["h_s40", "h_s41"], ["h_s42"]]  # fmt: skip
    assert (
        stat.copies == 0
    )  # another polarity is not a copy; h_s42 is outside the merged item


RECEIPT = {"h_s49": sent("h_s49", "(4)　入札書の受領期限　令和８年10月21日17時00分", ["入札書の提出場所等", "入札書の受領期限"]),
           "h_s60": sent("h_s60", "(5)　説明会の日時　令和８年10月２日17時00分", ["説明会"])}  # fmt: skip


def _receipt(kind: str, cite: str, electronic: bool, dt: str = "2026-10-21T17:00:00+09:00") -> tuple[dict, llm.CallStat]:  # fmt: skip
    raw = [
        {
            "kind": kind,
            "datetime": dt,
            "relative_text": None,
            "flags": [],
            "citations": [cite],
        }
    ]
    stat = llm.CallStat("deadlines")
    return llm.read_items("deadlines", json.dumps({"items": raw}), RECEIPT, stat, electronic)[0], stat  # fmt: skip


def test_bid_receipt_other_is_electronic_on_an_electronic_notice_f19cddbd4cba() -> None:
    # f19cddbd4cba h_s49: 入札書の受領期限, model said other, label (guide line 124) says electronic
    got, stat = _receipt("other", "h_s49", True)
    assert got["kind"] == "electronic" and stat.cue_kind_set == 1


def test_bid_receipt_rule_does_not_fire_f19cddbd4cba() -> None:
    assert (
        _receipt("other", "h_s49", False)[0]["kind"] == "other"
    )  # not an electronic notice
    got, stat = _receipt(
        "bid_in_person", "h_s49", True
    )  # a kind other than other is never overridden
    assert got["kind"] == "bid_in_person" and stat.cue_kind_set == 0
    got, stat = _receipt(
        "other", "h_s60", True, "2026-10-02T17:00:00+09:00"
    )  # no bid receipt cue
    assert got["kind"] == "other" and stat.cue_kind_set == 0


def test_notice_is_electronic_only_when_the_rules_say_so_f19cddbd4cba() -> None:
    e = sent("h_s20", "入札は電子調達システムで行う。", ["入札方法"])
    deadline = {"kind": "other", "datetime": "2026-10-21", "relative_text": None, "flags": [], "citations": ["h_s4"]}  # fmt: skip
    ans = {"eligibility": {"items": []}, "required_documents": {"items": []}, "deadlines": {"items": [deadline]}}  # fmt: skip

    def kind(ss: list[Sentence]) -> str:
        out = llm.extract_lists("notice", ss, fake(ans))
        return out["deadlines"].normalized["items"][0]["kind"]

    assert kind([*DOC, e]) == "electronic"
    assert kind(DOC) == "other"  # no sentence says the notice is electronic


# --- api_key: llama-server started with --api-key needs a bearer token ----------------------


def _serve_once():
    """A loopback server that answers one chat request and keeps its Authorization header."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen: list[str | None] = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            seen.append(self.headers.get("Authorization"))
            body = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}).encode()  # fmt: skip
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a: object) -> None:
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    return srv, seen


@pytest.mark.parametrize("key,want", [("k-123", "Bearer k-123"), (None, None)])
def test_client_sends_the_api_key_as_a_bearer_token(key, want) -> None:
    srv, seen = _serve_once()
    try:
        out = llm.Client(srv.server_port, api_key=key).complete("s", "u", {}, 8)
    finally:
        srv.server_close()
    assert out == "{}" and seen == [want]


def test_on_field_is_optional_and_changes_nothing() -> None:
    ok = {"kind": "legal", "polarity": "requirement", "text_ja": "予算決算及び会計令第71条の規定に該当しない者であること。", "citations": ["h_s3"]}  # fmt: skip
    answers = {
        "eligibility": {"items": [ok]},
        "deadlines": {"items": []},
        "required_documents": {"items": []},
    }
    order: list[str] = []

    def complete(system: str, user: str, schema: dict, max_out: int) -> str:
        f = user.split("Field: ")[1].split("\n")[0]
        order.append("call:" + f)
        return json.dumps(answers[f], ensure_ascii=False)

    plain = llm.extract_lists("notice", DOC, complete)
    order.clear()
    seen = []

    def on_field(x) -> None:
        seen.append(x.field)
        order.append("done:" + x.field)

    hooked = llm.extract_lists("notice", DOC, complete, on_field=on_field)
    assert hooked == plain  # the same answers, field by field
    assert seen == ["eligibility"]
    assert order.index("done:eligibility") < order.index(
        "call:deadlines"
    )  # called as the field finishes


def _slow_server(hold: float = 10.0):
    """A llama-server stand-in that takes its time. Returns (server, requests seen, released event)."""
    import http.server
    import socketserver

    got = threading.Event()
    done = threading.Event()
    n: list[int] = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            n.append(1)
            got.set()
            done.wait(hold)  # "generating"

        def log_message(self, *a: object) -> None:
            pass

    class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    srv = S(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, n, got, done


def test_abort_ends_the_request_in_flight_within_a_second() -> None:
    import time

    srv, n, got, done = _slow_server()
    client = llm.Client(srv.server_port)
    out: list[BaseException] = []

    def call() -> None:
        try:
            client.complete("s", "u", {}, 8)
        except BaseException as e:  # noqa: BLE001
            out.append(e)

    t = threading.Thread(target=call)
    t.start()
    assert got.wait(5)  # the server has the request and is "generating"
    t0 = time.monotonic()
    client.abort()
    t.join(5)
    took = time.monotonic() - t0
    done.set()
    srv.shutdown()
    srv.server_close()
    assert not t.is_alive() and took < 1.0
    assert len(out) == 1 and isinstance(
        out[0], OSError
    )  # the caller's own error handling (retry, then not found) applies
    assert len(n) == 1
    client.abort()  # nothing in flight: no effect, no error


def test_a_request_after_an_abort_works_and_the_answer_is_unchanged() -> None:
    srv, seen = _serve_once()
    try:
        client = llm.Client(srv.server_port)
        client.abort()  # idle abort
        assert client.complete("s", "u", {}, 8) == "{}"
    finally:
        srv.server_close()


def test_http_error_is_still_an_oserror() -> None:
    import http.server

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a: object) -> None:
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    try:
        with pytest.raises(OSError):
            llm.Client(srv.server_port).complete("s", "u", {}, 8)
    finally:
        srv.server_close()


# --- scalar fallback (D-95) ---------------------------------------------------------------

SPEC = [
    sent("h_s1", "委託業務仕様書（案）"),
    sent("h_s2", "１．業務の名称わかやま空き家ポータルサイト構築及び保守管理運営業務"),
    sent("h_s3", "３．委託期間"),
    sent("h_s4", "契約締結日から令和１１年３月３１日まで"),
]


def scalars(
    answer: dict,
    doc: list[Sentence] = SPEC,
    have: set[str] | None = None,
    doc_type: str = "spec",
):
    calls: list[str] = []

    def complete(system: str, user: str, schema: dict, max_out: int) -> str:
        calls.append(user)
        return json.dumps(answer, ensure_ascii=False)

    out = llm.extract_scalars(doc_type, doc, complete, have or set(), [])
    return out, calls


def test_scalars_4965207bb115_cited_and_quoted_answer_is_kept() -> None:
    a = {"title": {"value_ja": "わかやま空き家ポータルサイト構築及び保守管理運営業務", "citations": ["h_s2"]},
         "performance_period": {"value_ja": "契約締結日から令和１１年３月３１日まで", "citations": ["h_s4"], "start": None, "end": "2029-03-31", "relative_text": "契約締結日"}}  # fmt: skip
    out, calls = scalars(a)
    assert len(calls) == 1  # one grouped call for every missing field
    assert out["title"].citations == ["h_s2"] and out["title"].normalized == {}
    assert out["performance_period"].normalized["end"] == "2029-03-31"


def test_scalars_4965207bb115_unknown_citation_quote_not_in_it_or_unread_date_are_dropped() -> (
    None
):
    a = {"title": {"value_ja": "わかやま空き家ポータルサイト構築及び保守管理運営業務", "citations": ["h_s99"]},
         "scope_summary": {"value_ja": "空き家を活用する", "citations": ["h_s2"]},
         "performance_period": {"value_ja": "契約締結日から令和１１年３月３１日まで", "citations": ["h_s4"], "start": None, "end": "2030-03-31", "relative_text": None}}  # fmt: skip
    out, _ = scalars(a)
    assert out == {}


def test_scalars_4965207bb115_null_answers_and_fields_the_rules_found_are_not_asked() -> (
    None
):
    out, calls = scalars({"scope_summary": None, "delivery_deadline": None, "delivery_location": None}, have={"title", "performance_period", "issuer_org"})  # fmt: skip
    assert out == {} and "title:" not in calls[0].split("Sentences to read")[0].split("Fields:")[1]  # fmt: skip


def test_scalars_nothing_missing_makes_no_call() -> None:
    out, calls = scalars({}, have={"title", "issuer_org", "scope_summary", "performance_period", "delivery_deadline", "delivery_location"})  # fmt: skip
    assert out == {} and calls == []


def test_scalars_a_failed_call_is_not_found() -> None:
    def boom(system: str, user: str, schema: dict, max_out: int) -> str:
        raise OSError("down")

    assert llm.extract_scalars("spec", SPEC, boom, set(), []) == {}


def test_scalar_sentences_2f2f5bd3_first_40_always_go_in_once_and_in_order() -> None:
    doc = [sent(f"p1_s{n}", f"無関係な文{n}") for n in range(1, 61)]
    doc.insert(
        10, sent("p1_s11b", "契約期間", ["契約期間"])
    )  # a cue hit inside the head must not repeat
    got = [s.id for s in llm.scalar_sentences(["performance_period"], doc)]
    assert got[:40] == [s.id for s in doc[:40]] and len(got) == len(set(got))
    assert "p1_s60" not in got  # past the head and far from any cue


def test_scalar_schema_caps_the_quoted_value() -> None:
    props = llm.scalar_schema(["title"])["properties"]["title"]["anyOf"][0][
        "properties"
    ]
    assert props["value_ja"]["maxLength"] == llm.SCALAR_VALUE_MAX
