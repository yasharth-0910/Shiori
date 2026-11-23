# ruff: noqa: E501, E731
# pyright: reportOptionalSubscript=false
"""Silver-label pipeline (eval/silver). No test calls a real API or needs a key: the
providers are fakes with scripted answers. Sentence text is from real open notices
(Hokkaido fb226cbd... p1_s22, the standard NUM-6 clause, Wakayama 4a654d88... weekday
typo) or the wording the field cues come from."""

import json
from dataclasses import replace
from datetime import date

import pytest
from shiori_core.fields import FIELD_IDS, SCHEMA_VERSION
from shiori_core.models import Sentence
from shiori_core.normalize import normalize

from collector.manifest import ManifestRow
from eval.silver import checks, config, pipeline, review, run
from eval.silver.agree import agree
from eval.silver.config import PROVIDERS
from eval.silver.limiter import DailyCap, Ledger, Limiter
from eval.silver.model import Candidate
from eval.silver.pipeline import Pipeline
from eval.silver.prompt import (
    FIELD_HELP,
    applicable_fields,
    est_tokens,
    line,
    overhead,
    split_document,
)  # fmt: skip
from eval.silver.providers import Completion, Gemini, Groq, Provider, ProviderError
from eval.validate_labels import check_path, validate_lines

SECRET_G = "AIzaSyFAKEFAKEFAKEFAKEFAKEFAKE12345"
SECRET_Q = "gsk_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE12"


def sent(
    id: str, text: str, language: str = "ja", path: list[str] | None = None
) -> Sentence:
    norm, idx = normalize(text)
    return Sentence.model_validate(
        dict(id=id, page=1, section_path=path or [], section_titles=[],
             text_orig=text, text_norm=norm, norm_to_orig=idx, boxes=[], language=language)
    )  # fmt: skip


SENTENCES = [
    sent("p1_s1", "件名 庁舎清掃業務"),
    sent("p1_s2", "(2) 入札日時 令和８年（2026年）９月10日（木）午後１時30分"),
    sent("p1_s3", "(3) 郵便等による入札は認めない。"),
    sent("p1_s4", "入札保証金 免除。"),
    sent("p1_s5", "契約保証金 契約金額の100分の10以上とする。"),
    sent("p1_s6", "落札者の決定に当たっては、入札書に記載された金額に当該金額の100分の10に相当する額を加算した金額をもって落札価格とする。"),  # clause from open doc 2f2f5bd3 (Wakayama), parenthetical removed
    sent("p1_s7", "Bids are due 10 September 2026 at 13:30.", "en"),
]  # fmt: skip


def row(
    doc_type="notice", license_class="open", org="北海道", doc_id="d1"
) -> ManifestRow:
    return ManifestRow.model_validate(
        dict(doc_id=doc_id, source="hokkaido", url="u", landing_url="l", issuer_org=org,
             title_ja="t", doc_type=doc_type, notice_date=date(2026, 8, 19),
             wto_covered=None, jetro_ref=None, pages=1, text_layer="full",
             fetched_at="2026-10-02T00:00:00", license_note="n",
             license_class=license_class, format="pdf", is_it=False, path="p")
    )  # fmt: skip


# what both labelers say about the sentences above
GOOD = {
    "title": dict(status="present", value_ja="庁舎清掃業務", citations=["p1_s1"]),
    "deadlines": dict(status="present", citations=["p1_s2"], normalized={"items": [
        {"kind": "bid_in_person", "datetime": "2026-09-10T13:30:00+09:00", "flags": [], "citations": ["p1_s2"]}]}),
    "submission_modes": dict(status="present", citations=["p1_s3"], normalized={"modes": [], "mail_not_allowed": True}),
    "bid_bond": dict(status="present", citations=["p1_s4"], normalized={"status": "waived"}),
    "performance_bond": dict(status="present", citations=["p1_s5"], normalized={"status": "required", "rate_percent": 10}),
    "tax_basis": dict(status="present", citations=["p1_s6"], normalized={"basis": "bid_excludes_tax"}),
}  # fmt: skip


def answer(over: dict | None = None, doc_type: str = "notice") -> str:
    rows = []
    for f in applicable_fields(doc_type):
        e = dict(
            field=f,
            status="absent",
            value_ja="",
            value_en="",
            normalized="",
            citations=[],
            reason="r",
        )
        e.update((over or {}).get(f, {}))
        if isinstance(e["normalized"], dict):
            e["normalized"] = json.dumps(e["normalized"])
        rows.append(e)
    return json.dumps({"fields": rows}, ensure_ascii=False)


class Fake(Provider):
    def __init__(self, name: str, model: str, script: list, local: bool = False):
        self.name, self.model, self.local = name, model, local
        self.script, self.calls, self.seen = list(script), 0, []

    def complete(self, system, user, schema, max_out, repair=None):
        self.calls += 1
        self.seen.append({"system": system, "user": user, "schema": schema, "max_out": max_out, "repair": repair})  # fmt: skip
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, Completion) else Completion(item, 1000, 500)


class Clock:
    t = 1_800_000_000.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(pipeline, "EVAL_DIR", tmp_path / "eval")
    monkeypatch.setattr(pipeline, "PRIVATE_DIR", tmp_path / "eval_private")
    monkeypatch.setenv("GEMINI_API_KEY", SECRET_G)
    monkeypatch.setenv("GROQ_API_KEY", SECRET_Q)
    splits = tmp_path / "splits.json"
    splits.write_text(json.dumps({"北海道": "dev"}))
    monkeypatch.setattr(run, "SPLITS", splits)
    ls = tmp_path / "label_set.json"
    entry = {"doc_id": "d1", "group": "notice", "license_class": "open"}
    ls.write_text(json.dumps({"dev": [entry], "test": []}))
    monkeypatch.setattr(run, "LABEL_SET", ls)
    monkeypatch.setattr(review, "SPLITS", splits)
    monkeypatch.setattr(run, "load_sentences", lambda r: SENTENCES)
    monkeypatch.setattr(review, "load_sentences", lambda r: SENTENCES)
    monkeypatch.setattr(review, "read_rows", lambda: [row(), row(doc_id="d2")])
    monkeypatch.setattr(config, "SPOT_CHECK_PERCENT", 0)
    from eval.silver import compare

    monkeypatch.setattr(compare, "REPORT", tmp_path / "silver_pilot.md")
    monkeypatch.setattr(run, "read_rows", lambda: [row(), row(doc_id="d2")])
    clock, log = Clock(), []
    fakes: dict[str, Fake] = {}

    def make(scripts: dict[str, list]) -> Pipeline:
        for k, sc in scripts.items():
            fakes[k] = Fake("local" if k.startswith("local:") else k, "Qwen3.5-9B-Q4_K_M" if k.startswith("local:") else k + "-model", sc, k.startswith("local:"))  # fmt: skip

        def factory(key):
            if key not in fakes:
                raise AssertionError(f"{key} must not be called")
            return fakes[key]

        return Pipeline(
            factory,
            Ledger(tmp_path / "cache" / "usage.jsonl"),
            clock.now,
            clock.sleep,
            log.append,
        )

    return type(
        "Env",
        (),
        {
            "make": staticmethod(make),
            "fakes": fakes,
            "log": log,
            "tmp": tmp_path,
            "clock": clock,
        },
    )


LOCAL = "local:Qwen3.5-9B-Q4_K_M.gguf"


def assigned(r):
    a = pipeline.assign(r)
    assert not isinstance(a, str), a
    return a


# --- prompt and splitting ----------------------------------------------------------------


def test_field_help_covers_every_field():
    assert set(FIELD_HELP) == set(FIELD_IDS)


def test_only_applicable_fields_are_asked():
    assert "deadlines" not in applicable_fields("spec")
    assert len(applicable_fields("notice")) == 23


def test_prompt_lines_are_id_section_text():
    s = sent("p2_s3", "第１ 入札", path=["1", "(2)"])
    assert line(s) == "p2_s3 | 1/(2) | 第１ 入札"


def test_split_keeps_every_sentence_and_respects_the_budget():
    ss = [sent(f"p1_s{i}", "あ" * 40, path=[str(1 + i // 10)]) for i in range(40)]
    chunks = split_document(ss, 300, overlap=2)
    assert len(chunks) > 1
    assert {s.id for c in chunks for s in c} == {s.id for s in ss}
    assert all(sum(est_tokens(line(s)) + 2 for s in c) <= 300 for c in chunks)
    # a section that fits stays whole: sections are 10 sentences ~ 480 tokens > 300 here,
    # so the pieces repeat the last two sentences
    assert chunks[1][0].id == chunks[0][-2].id


def test_split_packs_whole_sections_together():
    ss = [sent(f"p1_s{i}", "あ" * 20, path=[str(1 + i // 2)]) for i in range(8)]
    chunks = split_document(ss, 10_000)
    assert len(chunks) == 1


def test_groq_needs_splitting_and_gemini_does_not():
    ss = [sent(f"p1_s{i}", "あ" * 60, path=[str(1 + i // 5)]) for i in range(120)]
    r = row()
    assert len(pipeline.plan_parts(r, ss, PROVIDERS["groq"])) > 1
    assert len(pipeline.plan_parts(r, ss, PROVIDERS["gemini"])) == 1
    parts = pipeline.plan_parts(r, ss, PROVIDERS["groq"])
    assert all(p.est_in() + p.max_out <= 8000 for p in parts)
    # every field is asked about every sentence, once per field group
    fields = applicable_fields("notice")
    groups = {tuple(p.field_ids) for p in parts}
    assert sorted(f for g in groups for f in g) == sorted(fields)
    for g in groups:
        seen = {s.id for p in parts if tuple(p.field_ids) == g for s in p.sentences}
        assert seen == {s.id for s in ss}
    assert all(overhead(p.field_ids) < 8000 for p in parts)


# --- provider policy (D-44, D-50) ---------------------------------------------------------


def test_open_document_gets_gemini_and_the_local_model_never_groq():
    a = assigned(row())
    assert a.keys == {"A": "gemini", "B": LOCAL} and a.overlap


def test_restricted_and_unknown_documents_never_go_to_gemini():
    for lc in ("restricted", "unknown"):
        a = assigned(row(license_class=lc))
        assert a.keys == {"A": "groq", "B": LOCAL} and "gemini" not in a.keys.values()


def test_unknown_flag_blocks_a_provider_for_restricted_documents(monkeypatch):
    monkeypatch.setitem(
        PROVIDERS, "groq", replace(PROVIDERS["groq"], may_train_on_inputs=None)
    )
    assert isinstance(pipeline.assign(row(license_class="restricted")), str)  # skipped
    assert isinstance(pipeline.assign(row(license_class="unknown")), str)
    assert assigned(row()).keys["A"] == "gemini"  # open documents are unaffected


def test_local_model_family_differs_from_the_cloud_provider():
    # Gemini (Google): Gemma is Google too, so Qwen. Groq (OpenAI's gpt-oss): Qwen.
    assert pipeline.local_model_for("google") == LOCAL[6:]
    assert pipeline.local_model_for("openai") == LOCAL[6:]


def test_restricted_document_reaches_only_groq_and_the_local_model(env):
    pipe = env.make({"groq": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    r = row(license_class="restricted")
    out = run.run_docs([r], 10, pipe=pipe)
    assert out["resolved"] == 1 and "gemini" not in env.fakes
    groq_parts = len(pipeline.plan_parts(r, SENTENCES, PROVIDERS["groq"]))
    local_parts = len(pipeline.plan_parts(r, SENTENCES, pipeline.LOCAL_CFG))
    assert (
        env.fakes["groq"].calls == groq_parts and env.fakes[LOCAL].calls == local_parts
    )
    prov = labels_of(env, r)["deadlines"]["provenance"]
    assert [p["provider"] for p in prov["pre_labelers"]] == ["groq", "local"]
    assert prov["labeler_overlap"] is True


# --- end to end with fakes ---------------------------------------------------------------


def labels_of(env, r=None):
    r = r or row()
    return {x["field"]: x for x in pipeline.read_resolved(r.doc_id).values()}


def test_agreement_writes_consensus_labels_that_pass_the_validator(env):
    pipe = env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    out = run.run_docs([row()], 10, pipe=pipe)
    assert out == {"resolved": 1, "compared": 0, "pending": 0, "skipped": 0}
    path = pipeline.label_file(row(), json.loads(run.SPLITS.read_text()))
    assert path.exists() and path.parent.parent.parent.name == "eval"
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    assert [x["field"] for x in lines] == list(FIELD_IDS)
    by = {x["field"]: x for x in lines}
    assert by["deadlines"]["provenance"]["final_state"] == "silver_consensus"
    assert by["deadlines"]["provenance"]["agreement"] is True
    assert by["deadlines"]["provenance"]["prompt_version"] == config.PROMPT_VERSION
    # the local model voted on every consensus line (D-50); rule-absent lines had no labeler
    assert by["deadlines"]["provenance"]["labeler_overlap"] is True
    assert by["bid_bond"]["status"] == "present"
    assert by["procurement_type"]["status"] == "absent"
    # not applicable to a notice? every notice field applies; the spec-only rule is below
    errs = validate_lines(lines, row(), SENTENCES)
    assert errs == []


def test_cached_rerun_costs_nothing(env):
    pipe = env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    run.run_docs([row()], 10, pipe=pipe)
    n = (env.fakes["gemini"].calls, env.fakes[LOCAL].calls)
    pipe2 = env.make({})
    run.run_docs([row()], 10, pipe=pipe2)
    assert (env.fakes["gemini"].calls, env.fakes[LOCAL].calls) == n


def test_disagreement_is_flagged_and_writes_no_label_file(env):
    a = dict(
        GOOD,
        procurement_type=dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "open_competitive"},
        ),
    )
    b = dict(
        GOOD,
        procurement_type=dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "designated_competitive"},
        ),
    )
    pipe = env.make({"gemini": [answer(a)], LOCAL: [answer(b)]})
    run.run_docs([row()], 10, pipe=pipe)
    items = review.load_items()
    flagged = [i for i in items if i["kind"] == "flagged"]
    assert [i["field"] for i in flagged] == ["procurement_type"]
    assert flagged[0]["reasons"][0].startswith("disagree")
    assert "procurement_type" not in labels_of(env)
    assert not pipeline.label_file(
        row(), {"北海道": "dev"}
    ).exists()  # incomplete document


def test_blocking_check_failure_flags_even_when_both_agree(env):
    wrong = dict(
        GOOD,
        deadlines=dict(
            GOOD["deadlines"],
            normalized={
                "items": [
                    {
                        "kind": "bid_in_person",
                        "datetime": "2026-09-11T13:30:00+09:00",
                        "flags": [],
                        "citations": ["p1_s2"],
                    }
                ]
            },
        ),
    )
    pipe = env.make({"gemini": [answer(wrong)], LOCAL: [answer(wrong)]})
    run.run_docs([row()], 10, pipe=pipe)
    (item,) = [i for i in review.load_items() if i["kind"] == "flagged"]
    assert item["field"] == "deadlines"
    assert any("values_roundtrip" in r for r in item["reasons"])


def test_both_absent_with_a_heading_cue_is_flagged_but_absent_without_one_is_accepted(
    env,
):
    nobond = {
        k: v for k, v in GOOD.items() if k != "bid_bond"
    }  # 入札保証金 is in p1_s4
    pipe = env.make({"gemini": [answer(nobond)], LOCAL: [answer(nobond)]})
    run.run_docs([row()], 10, pipe=pipe)
    flagged = {i["field"]: i for i in review.load_items() if i["kind"] == "flagged"}
    assert list(flagged) == ["bid_bond"]
    assert "heading cue 入札保証金" in flagged["bid_bond"]["reasons"][0]
    assert labels_of(env)["award_method"]["status"] == "absent"  # no cue anywhere


def test_invalid_json_is_retried_once(env):
    pipe = env.make({"gemini": ["not json", answer(GOOD)], LOCAL: [answer(GOOD)]})
    run.run_docs([row()], 10, pipe=pipe)
    assert env.fakes["gemini"].calls == 2
    assert (
        labels_of(env)["deadlines"]["provenance"]["final_state"] == "silver_consensus"
    )


def test_invalid_json_twice_records_a_failure_and_the_document_stays_pending(env):
    pipe = env.make({"gemini": ["not json", "{}"], LOCAL: [answer(GOOD)]})
    out = run.run_docs([row()], 10, pipe=pipe)
    assert out["pending"] == 1 and not pipeline.read_resolved("d1")
    raw = pipeline.load_raw(pipeline.raw_path("d1", "gemini", "gemini-model"))
    assert pipeline.raw_state(raw) == "failed"
    assert "1 failed chunks" in run.status_text("dev")
    # a later run with --retry-failed asks again
    env.fakes["gemini"].script = [answer(GOOD)]
    out = run.run_docs([row()], 10, retry_failed=True, pipe=pipe)
    assert out["resolved"] == 1


def test_daily_cap_stops_the_provider_and_the_next_run_resumes(env):
    pipe = env.make(
        {"gemini": [ProviderError("daily_quota", "per day")], LOCAL: [answer(GOOD)]}
    )
    out = run.run_docs([row()], 10, pipe=pipe)
    assert out["pending"] == 1 and "gemini" in pipe.down
    assert Ledger(env.tmp / "cache" / "usage.jsonl").today("gemini", env.clock.now())[
        "blocked"
    ]
    # same day: the guard refuses while the cap stands
    with pytest.raises(DailyCap):
        pipe.limiter("gemini").before(10)
    env.clock.t += 86_400  # next day
    env.fakes["gemini"].script = [answer(GOOD)]
    out = run.run_docs([row()], 10, pipe=env.make({}))
    assert out["resolved"] == 1


def test_max_calls_stops_the_run(env):
    pipe = env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    out = run.run_docs([row()], 1, pipe=pipe)
    assert out["pending"] == 1 and env.fakes["gemini"].calls == 1


def test_non_applicable_fields_are_rule_absent_not_asked(env):
    r = row("spec")
    spec_good = {
        "title": dict(status="present", value_ja="庁舎清掃業務", citations=["p1_s1"])
    }
    pipe = env.make(
        {"gemini": [answer(spec_good, "spec")], LOCAL: [answer(spec_good, "spec")]}
    )
    run.run_docs([r], 10, pipe=pipe)
    lines = [
        json.loads(x)
        for x in pipeline.label_file(r, {"北海道": "dev"}).read_text().splitlines()
    ]
    by = {x["field"]: x for x in lines}
    assert by["deadlines"]["status"] == "absent"
    assert by["deadlines"]["provenance"]["pre_labelers"] == []
    assert by["deadlines"]["provenance"]["final_state"] == "silver_unreviewed"
    assert by["title"]["provenance"]["final_state"] == "silver_consensus"
    assert validate_lines(lines, r, SENTENCES) == []


def test_d24_path_rule(env):
    splits = {"北海道": "dev"}
    assert (
        pipeline.label_file(row(), splits)
        == env.tmp / "eval" / "dev" / "labels" / "d1.jsonl"
    )
    p = pipeline.label_file(row(license_class="restricted"), splits)
    assert p == env.tmp / "eval_private" / "dev" / "labels" / "d1.jsonl"
    assert check_path(pipeline.label_file(row(), splits), row(), splits) == []
    assert check_path(p, row(license_class="restricted"), splits) == []
    assert check_path(
        p, row(), splits
    )  # an open document under eval_private is an error


# --- review export and import ------------------------------------------------------------


def flagged_env(env):
    a = dict(
        GOOD,
        procurement_type=dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "open_competitive"},
        ),
    )
    b = dict(
        GOOD,
        procurement_type=dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "designated_competitive"},
        ),
    )
    run.run_docs(
        [row()], 10, pipe=env.make({"gemini": [answer(a)], LOCAL: [answer(b)]})
    )
    select = lambda split, open_only: [row()]  # noqa: E731
    return review.export("dev", True, select)


def test_export_batches_carry_the_answer_format_and_the_sentences(env):
    (p,) = flagged_env(env)
    text = p.read_text()
    assert (
        "F-0012 | accept A" in text and "F-0012 | custom" in text
    )  # the answer format
    assert "## F-0001" in text and "procurement_type" in text
    assert "A: status=present" in text and "B: status=present" in text
    assert "p1_s1 | - | 件名 庁舎清掃業務" in text  # cited sentence
    assert "p1_s3 | - |" in text  # a neighbour (two on each side)
    assert "Bids are due" not in text  # English sentences are never shown
    assert len(text) < review.MAX_CHARS


def test_export_orders_tier_one_first_and_caps_batches(env):
    items = [
        {"doc_id": "d1", "field": f, "kind": "flagged", "reasons": ["x"], "agreement": False,
         "labelers": [["gemini", "m", "2026-10-02"], ["groq", "m", "2026-10-02"]],
         "sides": [{"labeler": "a", "candidate": dict(status="absent", value_ja=None, value_en=None, normalized=None, citations=[], labeler="a", parse_error=None), "checks": []}] * 2}
        for f in ["title", "scope_summary", "deadlines", "bid_bond"] * 5
    ]  # fmt: skip
    p = config.CACHE / "flagged.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(i) + "\n" for i in items))
    paths = review.export("dev", True, lambda s, o: [row()])
    assert len(paths) == 2  # 20 items, 12 per batch
    first = paths[0].read_text()
    assert first.index("field deadlines") < first.index("field title")
    assert first.count("## F-") == 12


def test_import_round_trip_accept_custom_and_absent(env):
    (p,) = flagged_env(env)
    out, errs = review.import_answers("Sure, here you go:\nF-0001 | accept A\n")
    assert (out, errs) == (1, [])
    ln = labels_of(env)["procurement_type"]
    assert ln["normalized"] == {"type": "open_competitive"}
    pv = ln["provenance"]
    assert (
        pv["reviewed_by"] == "claude_chat"
        and pv["final_state"] == "silver_model_reviewed"
    )
    assert pv["review_note"] == "accepted A" and pv["agreement"] is False
    assert len(pv["pre_labelers"]) == 2
    # the document is now complete: the label file exists, in the right place, and validates
    path = pipeline.label_file(row(), {"北海道": "dev"})
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    assert validate_lines(lines, row(), SENTENCES) == []
    assert review.load_items() == []  # nothing left to review


def test_import_custom_answer_is_rechecked_and_written(env):
    flagged_env(env)
    reply = 'F-0001 | custom | status=present | cites=p1_s1 | normalized={"type": "open_competitive"} | note=read it myself'
    assert review.import_answers(reply) == (1, [])
    assert (
        labels_of(env)["procurement_type"]["provenance"]["review_note"]
        == "read it myself"
    )


def test_import_absent_answer(env):
    flagged_env(env)
    assert review.import_answers("F-0001 | absent | note=not stated") == (1, [])
    assert labels_of(env)["procurement_type"]["status"] == "absent"


def test_import_malformed_lines_import_nothing(env):
    flagged_env(env)
    reply = "\n".join([
        "F-0001 | accept A",
        "F-0001 | accept B",  # twice
        "F-9999 | accept A",  # unknown
        "F-0002 | maybe",
        "F-0003 | custom | status=present | colour=red",
        "F-0004",
        "F-0005 | custom | cites=p1_s1",  # no status
    ])  # fmt: skip
    n, errs = review.import_answers(reply)
    assert n == 0 and len(errs) >= 6
    assert "procurement_type" not in labels_of(env)  # nothing written
    assert any("answered twice" in e for e in errs) and any(
        "unknown item" in e for e in errs
    )


def test_import_rejects_a_custom_answer_that_fails_the_hard_checks(env):
    flagged_env(env)
    bad = 'F-0001 | custom | status=present | value_ja=存在しない文 | cites=p1_s1 | normalized={"type": "open_competitive"}'
    n, errs = review.import_answers(bad)
    assert n == 0 and "value_in_citation" in errs[0]
    bad2 = 'F-0001 | custom | status=present | cites=p1_s7 | normalized={"type": "open_competitive"}'  # English sentence
    assert "citations_exist" in review.import_answers(bad2)[1][0]


def test_spot_check_items_are_exported_and_reviewed_answers_measure_the_error_rate(
    env, monkeypatch
):
    monkeypatch.setattr(config, "SPOT_CHECK_PERCENT", 100)
    run.run_docs(
        [row()],
        10,
        pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]}),
    )
    spots = [i for i in review.load_items() if i["kind"] == "spot"]
    assert {i["field"] for i in spots} == set(FIELD_IDS)
    review.export("dev", True, lambda s, o: [row()])
    reg = json.loads((config.CACHE / "export" / "ids.json").read_text())
    tid = next(k for k, v in reg["items"].items() if v["field"] == "title")
    bid = next(k for k, v in reg["items"].items() if v["field"] == "bid_bond")
    n, errs = review.import_answers(f"{tid} | accept A\n{bid} | absent | note=wrong")
    assert (n, errs) == (2, [])
    assert "2 reviewed, 1 changed" in run.status_text("dev")
    assert (
        labels_of(env)["title"]["provenance"]["final_state"] == "silver_model_reviewed"
    )
    assert labels_of(env)["bid_bond"]["status"] == "absent"
    # a re-run never replaces a reviewed line
    run.run_docs([row()], 10, pipe=env.make({}))
    assert labels_of(env)["bid_bond"]["provenance"]["reviewed_by"] == "claude_chat"


def test_spot_check_selection_is_seeded_and_about_five_percent():
    picks = [pipeline.spot_checked(f"doc{i}", f) for i in range(100) for f in FIELD_IDS]
    assert 0.03 < sum(picks) / len(picks) < 0.07
    assert picks == [
        pipeline.spot_checked(f"doc{i}", f) for i in range(100) for f in FIELD_IDS
    ]


# --- the key never leaves the environment ------------------------------------------------


def test_a_key_in_the_environment_never_reaches_any_file_or_log(env, capsys):
    leak = f"echo of {SECRET_G} and {SECRET_Q}"
    reply = answer(GOOD).replace('"reason": "r"', f'"reason": "{leak}"')
    pipe = env.make({
        "gemini": [ProviderError("bad_request", leak), reply],
        LOCAL: [reply],
    })  # fmt: skip
    run.run_docs([row()], 10, pipe=pipe)  # gemini fails the first request, then answers
    pipe2 = env.make({"gemini": [ProviderError("auth", leak)], LOCAL: [reply]})
    run.run_docs(
        [row(doc_id="d2")], 10, pipe=pipe2
    )  # a second document that fails outright
    review.export("dev", True, lambda s, o: [row(), row(doc_id="d2")])
    print(run.status_text("dev"))
    seen = capsys.readouterr().out + "\n".join(env.log)
    for f in config.CACHE.rglob("*"):
        if f.is_file():
            seen += f.read_text(errors="replace")
    assert "d1" in seen  # the scan covered something
    assert SECRET_G not in seen and SECRET_Q not in seen
    assert "AIzaSy" not in seen and "gsk_FAKE" not in seen


def test_requests_carry_the_key_only_in_a_header():
    sent_: list = []

    def post(url, headers, body):
        sent_.append((url, headers, body))
        if "generativelanguage" in url:
            return {"candidates": [{"content": {"parts": [{"text": "x", "thought": True}, {"text": '{"fields": []}'}]}}],
                    "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 5, "thoughtsTokenCount": 7}}  # fmt: skip
        return {
            "choices": [{"message": {"content": '{"fields": []}'}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }

    g = Gemini(SECRET_G, post=post).complete("sys", "user", {"type": "object"}, 100)
    q = Groq(SECRET_Q, post=post).complete("sys", "user", {"type": "object"}, 100)
    assert (g.text, g.tokens_in, g.tokens_out) == (
        '{"fields": []}',
        11,
        12,
    )  # thought text skipped, thought tokens counted
    assert (q.tokens_in, q.tokens_out) == (3, 2)
    for url, _headers, body in sent_:
        assert SECRET_G not in url + json.dumps(
            body
        ) and SECRET_Q not in url + json.dumps(body)
    gb, qb = sent_[0][2], sent_[1][2]
    assert gb["generationConfig"]["temperature"] == 0 and qb["temperature"] == 0
    assert (
        qb["response_format"]["type"] == "json_schema"
        and qb["model"] == "openai/gpt-oss-120b"
    )
    assert sent_[0][1] == {"x-goog-api-key": SECRET_G}


# --- limiter and quota guard --------------------------------------------------------------


def test_limiter_waits_for_the_minute_window_and_stops_at_the_daily_cap(tmp_path):
    clock = Clock()
    led = Ledger(tmp_path / "u.jsonl")
    lim = Limiter(PROVIDERS["groq"], led, clock.now, clock.sleep)
    lim.record("m", 4000, 3000, "ok")  # 7000 of the 8000 tokens/min
    t0 = clock.t
    lim.before(2000)  # does not fit this minute: waits
    assert clock.t - t0 >= 59
    for _ in range(40):  # the day's tokens
        lim.record("m", 4000, 1000, "ok")
        clock.t += 61
    with pytest.raises(DailyCap):
        lim.before(5000)
    clock.t += 86_400
    lim.before(5000)  # a new day


def test_limits_json_overrides_the_assumed_gemini_numbers(env):
    from eval.silver.limiter import effective_cfg

    assert not effective_cfg(PROVIDERS["gemini"]).published
    (config.CACHE).mkdir(parents=True, exist_ok=True)
    (config.CACHE / "limits.json").write_text('{"gemini": {"rpd": 20}}')
    c = effective_cfg(PROVIDERS["gemini"])
    assert c.rpd == 20 and c.published


def test_run_without_yes_and_max_calls_does_nothing(capsys):
    from eval.silver.__main__ import main

    assert main(["run", "--pilot"]) == 2
    assert main(["run", "--pilot", "--yes"]) == 2
    assert "needs both" in capsys.readouterr().out


def test_run_notes_say_what_the_caps_allow_and_never_block(env, monkeypatch):
    monkeypatch.setattr(
        run, "ja_sentences", lambda r: [s for s in SENTENCES if s.language == "ja"]
    )
    # 1 Gemini call + 1 local one (sv4: one grouped call per labeler, D-54)
    assert any("--max-calls 1 stops the run" in n for n in run.run_notes([row()], 1, env.clock.now()))  # fmt: skip
    assert run.run_notes([row()], 2, env.clock.now()) == []
    led = Ledger(env.tmp / "cache" / "usage.jsonl")
    for _ in range(PROVIDERS["gemini"].rpd):
        led.append(
            ts=env.clock.now(),
            provider="gemini",
            model="m",
            tokens_in=1,
            tokens_out=1,
            ok=True,
        )
    notes = run.run_notes([row()], 6, env.clock.now())
    assert any("gemini" in n and "sits this run out" in n for n in notes)
    plan = run.plan_text("x", [row()])
    assert "gemini" in plan and "days of free quota" in plan and "groq" not in plan


# --- auto checks on real sentences ---------------------------------------------------------

BY_ID = {s.id: s for s in SENTENCES}


def cand(field, status="present", value_ja=None, normalized=None, citations=()):
    return Candidate(field, status, value_ja, None, normalized, list(citations))


def test_check_citations_exist_and_japanese():
    assert checks.citations_exist(cand("title", citations=["p1_s1"]), BY_ID) is True
    assert checks.citations_exist(cand("title", citations=["p9_s9"]), BY_ID) is False
    assert (
        checks.citations_exist(cand("title", citations=["p1_s7"]), BY_ID) is False
    )  # English
    assert checks.citations_exist(cand("title", citations=[]), BY_ID) is False
    assert checks.citations_exist(cand("title", "absent"), BY_ID) is None


def test_check_value_in_citation_after_normalization():
    ok = cand("title", value_ja="庁舎 清掃業務", citations=["p1_s1"])  # spaces ignored
    assert checks.value_in_citation(ok, BY_ID) is True
    full = cand(
        "deadlines", value_ja="令和8年(2026年)9月10日", citations=["p1_s2"]
    )  # full-width digits in source
    assert checks.value_in_citation(full, BY_ID) is True
    assert (
        checks.value_in_citation(
            cand("title", value_ja="別の件名", citations=["p1_s1"]), BY_ID
        )
        is False
    )


def test_check_value_roundtrip_dates_rates_tax():
    good = cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "bid_in_person",
                    "datetime": "2026-09-10T13:30:00+09:00",
                    "flags": [],
                    "citations": ["p1_s2"],
                }
            ]
        },
        citations=["p1_s2"],
    )
    assert checks.values_roundtrip(good, BY_ID) is True
    bad = cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "bid_in_person",
                    "datetime": "2026-09-10T14:30:00+09:00",
                    "flags": [],
                    "citations": ["p1_s2"],
                }
            ]
        },
        citations=["p1_s2"],
    )
    assert checks.values_roundtrip(bad, BY_ID) is False
    rate = cand(
        "performance_bond",
        normalized={"status": "required", "rate_percent": 10},
        citations=["p1_s5"],
    )
    assert checks.values_roundtrip(rate, BY_ID) is True
    assert (
        checks.values_roundtrip(
            cand(
                "performance_bond",
                normalized={"status": "required", "rate_percent": 5},
                citations=["p1_s5"],
            ),
            BY_ID,
        )
        is False
    )
    tax = cand(
        "tax_basis", normalized={"basis": "bid_excludes_tax"}, citations=["p1_s6"]
    )
    assert checks.values_roundtrip(tax, BY_ID) is True
    assert (
        checks.values_roundtrip(
            cand(
                "tax_basis",
                normalized={"basis": "bid_includes_tax"},
                citations=["p1_s6"],
            ),
            BY_ID,
        )
        is False
    )


def test_check_arrival_flag_roundtrip():
    s = sent("p1_s9", "令和８年10月26日（月）午後５時00分 必着")
    c = cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "mail_arrival",
                    "datetime": "2026-10-26T17:00:00+09:00",
                    "flags": ["arrival_required"],
                    "citations": ["p1_s9"],
                }
            ]
        },
        citations=["p1_s9"],
    )
    assert checks.values_roundtrip(c, {"p1_s9": s}) is True
    c.normalized["items"][0]["flags"] = ["postmark_ok"]
    assert checks.values_roundtrip(c, {"p1_s9": s}) is False


def test_check_era_plausibility_against_the_notice_date():
    r = row()  # notice 2026-08-19
    near = cand("notice_date", normalized={"date": "2026-08-19"})
    far = cand("delivery_deadline", normalized={"date": "2032-03-31"})
    assert checks.era_plausible(near, r) is True
    assert checks.era_plausible(far, r) is False  # more than 5 years away
    assert checks.era_plausible(cand("title", value_ja="x"), r) is None


def test_check_weekday_warning_is_surfaced():
    s = sent(
        "p1_s9", "令和8年3月3日(水)"
    )  # 3 March 2026 is a Tuesday (doc 4a654d88...)
    c = cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "other",
                    "datetime": "2026-03-03",
                    "flags": [],
                    "citations": ["p1_s9"],
                }
            ]
        },
        citations=["p1_s9"],
    )
    assert checks.weekday_consistent(c, {"p1_s9": s}) is False
    assert (
        checks.weekday_consistent(
            cand(
                "deadlines",
                normalized={
                    "items": [
                        {
                            "kind": "bid_in_person",
                            "datetime": "2026-09-10",
                            "flags": [],
                            "citations": ["p1_s2"],
                        }
                    ]
                },
                citations=["p1_s2"],
            ),
            BY_ID,
        )
        is True
    )


def test_check_field_applicability():
    assert (
        checks.field_applicable(cand("deadlines", citations=["p1_s2"]), row("spec"))
        is False
    )
    assert checks.field_applicable(cand("title", value_ja="x"), row("spec")) is True
    assert checks.field_applicable(cand("deadlines", "absent"), row("spec")) is None


def test_check_heading_cue_is_soft_evidence():
    assert (
        checks.heading_cue(cand("deadlines", citations=["p1_s2"]), BY_ID) is True
    )  # 入札日時
    assert checks.heading_cue(cand("deadlines", citations=["p1_s1"]), BY_ID) is False
    assert (
        checks.heading_cue(
            cand("notice_date", normalized={"date": "2026-08-19"}, citations=["p1_s1"]),
            BY_ID,
        )
        is None
    )


def test_check_english_summary_agreement():
    en = "(7) Time-limit for tender: 17:00 21 October, 2025 (8) Contact: x@example.go.jp 03-1234-5678"
    d = lambda iso: cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "electronic",
                    "datetime": iso,
                    "flags": [],
                    "citations": ["p1_s2"],
                }
            ]
        },
    )  # noqa: E731
    assert checks.en_summary_agrees(d("2025-10-21T17:00:00+09:00"), en, BY_ID) is True
    assert checks.en_summary_agrees(d("2025-10-22T17:00:00+09:00"), en, BY_ID) is False
    assert checks.en_summary_agrees(d("2025-10-22"), "", BY_ID) is None  # no Summary
    ct = lambda **kw: cand("contact", normalized=kw)  # noqa: E731
    assert (
        checks.en_summary_agrees(
            ct(email="x@example.go.jp", phone="03-1234-5678"), en, BY_ID
        )
        is True
    )
    assert checks.en_summary_agrees(ct(email="y@example.go.jp"), en, BY_ID) is False


def test_check_schema_valid_catches_bad_normalized_json():
    from eval.silver.model import from_row

    c = from_row(
        dict(
            field="tax_basis", status="present", normalized="{oops", citations=["p1_s6"]
        ),
        "x",
    )
    assert checks.schema_valid(c, row())[0] is False
    c2 = from_row(
        dict(
            field="tax_basis",
            status="present",
            normalized='{"basis": "maybe"}',
            citations=["p1_s6"],
        ),
        "x",
    )
    assert checks.schema_valid(c2, row())[0] is False


# --- agreement ----------------------------------------------------------------------------


def test_agreement_by_field_type():
    a = cand("title", value_ja="庁舎清掃業務", citations=["p1_s1"])
    assert agree(
        a, cand("title", value_ja="庁舎清掃業務 ", citations=["p1_s1", "p1_s2"])
    )[0]
    assert not agree(a, cand("title", value_ja="庁舎清掃業務", citations=["p1_s9"]))[
        0
    ]  # no overlap
    assert not agree(
        a, cand("title", value_ja="全く違う件名です", citations=["p1_s1"])
    )[0]
    assert not agree(a, cand("title", "absent"))[0]
    assert agree(cand("title", "absent"), cand("title", "absent"))[0]
    e = lambda t: cand("procurement_type", normalized={"type": t})  # noqa: E731
    assert (
        agree(e("open_competitive"), e("open_competitive"))[0]
        and not agree(e("open_competitive"), e("other"))[0]
    )
    dl = lambda iso, cites: cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "bid_in_person",
                    "datetime": iso,
                    "flags": [],
                    "citations": cites,
                }
            ]
        },
    )  # noqa: E731
    assert agree(dl("2026-09-10", ["p1_s2"]), dl("2026-09-10", ["p1_s2", "p1_s3"]))[0]
    assert not agree(dl("2026-09-10", ["p1_s2"]), dl("2026-09-11", ["p1_s2"]))[0]
    two = cand(
        "deadlines",
        normalized={"items": dl("2026-09-10", ["p1_s2"]).normalized["items"] * 2},
    )
    assert not agree(two, dl("2026-09-10", ["p1_s2"]))[0]
    ref = lambda k: cand(
        "spec_access",
        "see_other_document",
        normalized={"ref": {"kind": k}},
        citations=["p1_s1"],
    )  # noqa: E731
    assert (
        agree(ref("spec"), ref("spec"))[0] and not agree(ref("spec"), ref("kokuji"))[0]
    )


# --- review reply grammar -------------------------------------------------------------------


def test_parse_reply_grammar():
    ok, errs = review.parse_reply(
        "hello\nF-0012 | accept B\nF-0013 | absent | note=x\nF-0014 | custom | status=present | value_ja=a | cites=p1_s1,p1_s2 | note=n"
    )
    assert errs == [] and [a.action for a in ok] == ["accept B", "absent", "custom"]
    assert ok[2].kv["cites"] == "p1_s1,p1_s2"
    _, errs = review.parse_reply(
        "F-12 | accept A\nF-0001 | accept A | extra\nF-0002 | absent | status=present"
    )
    assert len(errs) == 3


# --- cited sentences that follow each other are also read as one text (D-107) ---


def _deadline(dt: str, cites: list[str], kind: str = "electronic"):
    return cand(
        "deadlines",
        normalized={
            "items": [{"kind": kind, "datetime": dt, "flags": [], "citations": cites}]
        },
        citations=cites,
    )


def test_roundtrip_time_split_across_two_adjacent_records_262e3a41_h_s77_h_s78():
    by = {
        "h_s77": sent("h_s77", "令和８年12月８日午後"),
        "h_s78": sent("h_s78", "５時00分"),
    }
    c = _deadline("2026-12-08T17:00:00+09:00", ["h_s77", "h_s78"])
    assert checks.values_roundtrip(c, by) is True
    # read alone, neither record has the time: the join is what makes it pass
    assert checks.values_roundtrip(_deadline("2026-12-08T17:00:00+09:00", ["h_s77"]), by) is False  # fmt: skip


def test_roundtrip_time_split_inside_午後_262e3a41_h_s79_h_s80():
    by = {
        "h_s79": sent("h_s79", "令和８年12月９日午"),
        "h_s80": sent("h_s80", "後１時15分"),
    }
    c = _deadline("2026-12-09T13:15:00+09:00", ["h_s79", "h_s80"], "bid_opening")
    assert checks.values_roundtrip(c, by) is True


def test_roundtrip_tax_phrase_split_across_four_records_262e3a41_h_s43_to_h_s46():
    by = {
        "h_s43": sent("h_s43", "とするので、入札者は、消費税に係る課税事"),
        "h_s44": sent("h_s44", "業者であるか免税事業者であるかを問わず、"),
        "h_s45": sent("h_s45", "見積もった契約金額の110分の100に相当する"),
        "h_s46": sent("h_s46", "金額を入札書に記載すること。"),
    }
    ids = list(by)
    ok = cand("tax_basis", normalized={"basis": "bid_excludes_tax"}, citations=ids)
    assert checks.values_roundtrip(ok, by) is True
    # the first record alone has no tax wording to read
    alone = cand("tax_basis", normalized={"basis": "bid_excludes_tax"}, citations=["h_s43"])  # fmt: skip
    assert checks.values_roundtrip(alone, by) is False


def test_roundtrip_does_not_join_sentences_that_are_not_adjacent():
    by = {
        "h_s77": sent("h_s77", "令和８年12月８日午後"),
        "h_s78": sent("h_s78", "他の記載事項"),
        "h_s79": sent("h_s79", "５時00分"),
    }
    c = _deadline("2026-12-08T17:00:00+09:00", ["h_s77", "h_s79"])  # h_s78 not cited
    assert checks.values_roundtrip(c, by) is False


def test_roundtrip_time_in_no_cited_run_still_fails():
    by = {
        "h_s77": sent("h_s77", "令和８年12月８日午後"),
        "h_s78": sent("h_s78", "５時00分"),
    }
    c = _deadline("2026-12-08T09:30:00+09:00", ["h_s77", "h_s78"])
    assert checks.values_roundtrip(c, by) is False


def test_import_keeps_schema_version_on_lines_of_an_old_resolved_store(env):
    """The resolved store of the dev documents still holds 1.0.0 lines (D-97 bumped only
    the label files). An import rewrites the whole label file from that store, so every
    line must come out at the current version, not just the reviewed one."""
    flagged_env(env)
    p = pipeline.resolved_path(row().doc_id)
    old = [json.loads(x) for x in p.read_text().splitlines()]
    assert old
    p.write_text("".join(json.dumps({**x, "schema_version": "1.0.0"}) + "\n" for x in old))  # fmt: skip
    out, errs = review.import_answers("F-0001 | accept A\n")
    assert (out, errs) == (1, [])
    path = pipeline.label_file(row(), {"北海道": "dev"})
    versions = {json.loads(x)["schema_version"] for x in path.read_text().splitlines()}
    assert versions == {SCHEMA_VERSION}
