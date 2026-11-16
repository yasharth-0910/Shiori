# ruff: noqa: E501, F811  (F811: the env fixture is imported)
# pyright: reportOptionalSubscript=false
"""Silver pipeline sv4 (D-54, D-55): one prompt version and one grouped call for every
labeler, focused local calls behind a flag, per-labeler prompt versions in provenance,
the plain repair message for a present entry with no citations, the claude_code
reviewer, UNSURE notes and calibration. No real API call."""

import json
from dataclasses import replace

import pytest

from eval.label_format import LabelLine
from eval.silver import config, pipeline, review, run
from eval.silver.prompt import GUIDE, applicable_fields, guide_rules, system_prompt
from eval.validate_labels import validate_lines
from tests.test_silver import (  # noqa: F401  (env is a fixture)
    GOOD,
    LOCAL,
    SENTENCES,
    answer,
    env,
    flagged_env,
    labels_of,
    row,
)

# --- one prompt, one grouped call (D-54) ---------------------------------------------------


def test_every_labeler_uses_sv4_and_the_local_one_the_cloud_prompt(env):
    assert config.PROMPT_VERSION == config.LOCAL_PROMPT_VERSION == "sv4"
    assert {pipeline.prompt_for(p) for p in ("gemini", "groq", "local")} == {"sv4"}
    pipe = env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    run.run_docs([row()], 10, pipe=pipe)
    gem, loc = env.fakes["gemini"].seen, env.fakes[LOCAL].seen
    assert len(gem) == len(loc) == 1  # one grouped call each
    assert gem[0]["system"] == loc[0]["system"] == system_prompt(applicable_fields("notice"))  # fmt: skip
    assert gem[0]["user"] == loc[0]["user"]


def test_focused_local_calls_only_with_the_flag_and_under_their_own_version(env, monkeypatch):  # fmt: skip
    monkeypatch.setattr(config, "LOCAL_FOCUSED", True)
    assert pipeline.prompt_for("local") == "sv4-l1" and pipeline.prompt_for("gemini") == "sv4"  # fmt: skip
    from eval.silver.__main__ import main

    monkeypatch.setattr(config, "LOCAL_FOCUSED", True)
    main(["status"])  # the flag is read per command: absent means grouped
    assert config.LOCAL_FOCUSED is False
    main(["--local-focused", "status"])
    assert config.LOCAL_FOCUSED is True


# --- provenance: each pre-labeler's own prompt version -------------------------------------


def test_each_pre_labeler_records_its_own_prompt_version(env, monkeypatch):
    run.run_docs(
        [row()], 10, pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    )
    pv = labels_of(env)["bid_bond"]["provenance"]
    assert [(p["provider"], p["prompt_version"]) for p in pv["pre_labelers"]] == [
        ("gemini", "sv4"),
        ("local", "sv4"),
    ]
    raw = json.loads(pipeline.raw_path("d1", "local", "Qwen3.5-9B-Q4_K_M").read_text())
    assert raw["prompt_version"] == "sv4"


def test_an_item_stored_before_d54_gets_its_items_prompt_version_on_import(env):
    flagged_env(env)
    p = config.CACHE / "flagged.jsonl"
    items = [json.loads(x) for x in p.read_text().splitlines()]
    for it in items:  # the shape of F-0039: 3-element labelers, item prompt sv2
        it["labelers"] = [x[:3] for x in it["labelers"]]
        it["prompt_version"] = "sv2"
    p.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items))
    d = config.CACHE / "decisions" / "d1.json"
    d.write_text(json.dumps({"items": items}, ensure_ascii=False))
    assert review.import_answers("F-0001 | accept A") == (1, [])
    pv = labels_of(env)["procurement_type"]["provenance"]
    assert pv["prompt_version"] == "sv2"
    assert [x["prompt_version"] for x in pv["pre_labelers"]] == ["sv2", "sv2"]


def test_label_lines_with_and_without_pre_labeler_prompt_versions_validate():
    base = {"doc_id": "d1", "extractor_version": "0.3.0", "schema_version": "1.0.0",
            "field": "title", "status": "absent", "citations": []}  # fmt: skip
    old = {"provider": "gemini", "model": "m", "date": "2026-10-03"}
    for pl in (old, {**old, "prompt_version": "sv4"}):
        prov = {"pre_labelers": [pl, pl], "agreement": True, "final_state": "silver_consensus"}  # fmt: skip
        LabelLine.model_validate({**base, "provenance": prov})


# --- the plain repair message (D-54) -------------------------------------------------------


def test_plain_repair_message_explains_present_without_citations():
    msg = pipeline.plain_repair_message(["eligibility: present: at least one citation"])
    assert "no citations" in msg and "Cite the ids of the sentences that contain the value" in msg  # fmt: skip
    assert "or answer absent" in msg
    empty = pipeline.plain_repair_message(["deadlines: Input should be a valid dictionary"])  # fmt: skip
    assert "normalized.deadlines is empty" in empty


def test_present_without_citations_gets_the_plain_repair_and_is_fixed(env):
    bad = {
        **GOOD,
        "title": dict(status="present", value_ja="庁舎清掃業務", citations=[]),
    }
    pipe = env.make({"gemini": [answer(GOOD)], LOCAL: [answer(bad), answer(GOOD)]})
    run.run_docs([row()], 10, pipe=pipe)
    (first, fix) = env.fakes[LOCAL].seen
    assert "title: its status is present but it has no citations" in fix["repair"][1]
    assert labels_of(env)["title"]["citations"] == ["p1_s1"]


# --- the guide (sv4 rules in the prompt) ---------------------------------------------------


def test_sv4_rules_are_in_the_prompt_block_and_nothing_is_pending():
    text = GUIDE.read_text(encoding="utf-8")
    assert "Pending for sv4" not in text and "responsible-office" not in text
    block = guide_rules()
    for rule in ("polarity follows text_ja as written", "best_value", "work-content line",
                 "別紙「仕様書」のとおり", "委託業務名", "調達機関",
                 "a services contract has none",
                 "cite the sentences that name the client organization",
                 "contact uses the 問い合わせ先 or 担当 line",
                 "A delivery place is never the contact"):  # fmt: skip
        assert rule in block, rule
    # the contact vs delivery place line names two fields: it goes to every prompt
    assert "A delivery place is never the contact" in guide_rules(["title"])
    assert "client organization" not in guide_rules(["title"])  # issuer_org only


# --- claude_code reviewer, UNSURE, calibrate (D-55) ----------------------------------------


def test_claude_code_review_is_model_reviewed_never_human_audited(env):
    flagged_env(env)
    reply = "F-0001 | accept A | note=the type name is in p1_s1"
    assert review.import_answers(reply, "claude_code") == (1, [])
    pv = labels_of(env)["procurement_type"]["provenance"]
    assert (pv["reviewed_by"], pv["final_state"]) == ("claude_code", "silver_model_reviewed")  # fmt: skip
    assert pv["review_note"] == "accepted A; the type name is in p1_s1"
    lines = [json.loads(x) for x in pipeline.label_file(row(), {"北海道": "dev"}).read_text().splitlines()]  # fmt: skip
    assert validate_lines(lines, row(), SENTENCES) == []
    bad = {**lines[0], "provenance": {**pv, "final_state": "human_audited"}}
    with pytest.raises(ValueError):
        LabelLine.model_validate(bad)
    with pytest.raises(ValueError):
        review.import_answers(reply, "native_speaker")


def test_a_rerun_never_replaces_a_claude_code_line(env):
    flagged_env(env)
    review.import_answers("F-0001 | absent | note=x", "claude_code")
    run.run_docs(
        [row()], 10, pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    )
    ln = labels_of(env)["procurement_type"]
    assert ln["status"] == "absent" and ln["provenance"]["reviewed_by"] == "claude_code"


def test_custom_answer_of_claude_code_names_it_as_labeler(env):
    flagged_env(env)
    reply = 'F-0001 | custom | status=present | cites=p1_s1 | normalized={"type": "open_competitive"} | note=x'  # fmt: skip
    assert review.import_answers(reply, "claude_code") == (1, [])
    assert (
        labels_of(env)["procurement_type"]["provenance"]["reviewed_choice"] == "custom"
    )


def test_accept_takes_only_a_note():
    ok, errs = review.parse_reply("F-0001 | accept B | note=fine\nF-0002 | accept A")
    assert errs == [] and ok[0].kv == {"note": "fine"} and ok[1].kv == {}
    _, errs = review.parse_reply("F-0001 | accept B | status=present")
    assert errs and "only note=" in errs[0]


def test_unsure_lines_are_held_not_imported(env, capsys, tmp_path):
    flagged_env(env)
    f = tmp_path / "batch-01-answers.txt"
    f.write_text("F-0001 | absent | note=UNSURE: no type named\n")
    from eval.silver.__main__ import main

    assert main(["import", str(f), "--reviewer", "claude_code"]) == 0
    out = capsys.readouterr().out
    assert "imported 0 labels (reviewed_by claude_code)" in out
    assert "held 1 UNSURE items, not imported (F-0001)" in out
    assert "procurement_type" not in labels_of(env)  # nothing written for it
    assert [i["field"] for i in review.load_items()] == [
        "procurement_type"
    ]  # still open
    md, js = review.held_paths()
    text = md.read_text()
    assert "# Held UNSURE items (1)" in text and "## F-0001" in text
    assert "held answer (claude_code, not imported): F-0001 | absent | note=UNSURE: no type named" in text  # fmt: skip
    assert "F-0012 | custom" in text  # the answer format, so a chat can answer them
    # the chat answers it: imported as claude_chat, and it drops out of the held file
    assert review.import_answers("F-0001 | accept A") == (1, [])
    assert "## F-0001" not in md.read_text() and json.loads(js.read_text()) == {}
    assert review.unsure_ids("F-0002 | accept A\nF-0003 | absent | note=sure") == []


def test_unsure_and_sure_lines_in_one_file(env):
    a = {
        **GOOD,
        "procurement_type": dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "open_competitive"},
        ),
        "title": dict(status="present", value_ja="庁舎清掃業務", citations=["p1_s1"]),
    }
    b = {**a, "procurement_type": dict(status="present", citations=["p1_s1"], normalized={"type": "designated_competitive"}),
         "title": dict(status="present", value_ja="清掃", citations=["p1_s1"])}  # fmt: skip
    run.run_docs(
        [row()], 10, pipe=env.make({"gemini": [answer(a)], LOCAL: [answer(b)]})
    )
    review.export("dev", True, lambda s, o: [row()])
    ids = {v["field"]: k for k, v in json.loads((config.CACHE / "export" / "ids.json").read_text())["items"].items()}  # fmt: skip
    reply = f"{ids['procurement_type']} | accept A\n{ids['title']} | accept A | note=UNSURE: which line\n"
    assert review.import_answers(reply, "claude_code") == (1, [])
    assert review.unsure_ids(reply) == [ids["title"]]
    assert "procurement_type" in labels_of(env) and "title" not in labels_of(env)
    # a malformed line: nothing imported, nothing held
    review.held_paths()[1].unlink()
    assert review.import_answers(f"{ids['title']} | accept A | note=UNSURE: x\nF-0099 | accept A")[0] == 0  # fmt: skip
    assert not review.held_paths()[1].exists()


def test_calibrate_counts_same_answers_and_shows_differences(env):
    flagged_env(env)  # F-0001: A open_competitive, B designated_competitive
    same_as_a = 'F-0001 | custom | status=present | cites=p1_s1 | normalized={"type": "open_competitive"}'  # fmt: skip
    out = review.calibrate("F-0001 | accept A\n", same_as_a + "\n", "chat", "code")
    assert "Items in both: 1; same answer: 1 (100%)." in out and "differ" not in out
    out = review.calibrate("F-0001 | accept A\nF-0009 | absent\n",
                           "F-0001 | accept B | note=UNSURE: hm\n", "chat", "code")  # fmt: skip
    assert "same answer: 0 (0%)" in out and "Only in chat: F-0009." in out
    assert "UNSURE in code: 1 (F-0001)." in out
    assert "- chat: `F-0001 | accept A`" in out and "- code: `F-0001 | accept B | note=UNSURE: hm`" in out  # fmt: skip
    assert "(doc d1, procurement_type)" in out


def test_calibrate_after_import_compares_the_lines_without_notes(env):
    out = review.calibrate("F-0001 | absent | note=a\n", "F-0001 | custom | status=absent | note=b\n")  # fmt: skip
    assert "same answer: 1 (100%)" in out


def test_batch_items_show_the_license_class(env):
    (p,) = flagged_env(env)
    assert "| license open | field procurement_type" in p.read_text()


def test_show_prints_the_japanese_sentences_only(env, capsys, monkeypatch):
    monkeypatch.setattr(run, "ja_sentences", lambda r: [s for s in SENTENCES if s.language == "ja"])  # fmt: skip
    monkeypatch.setattr(run, "select", lambda *a: [row()])
    from eval.silver import __main__ as cli

    monkeypatch.setattr(cli, "select", lambda *a: [row()])
    assert cli.main(["show", "d1"]) == 0
    out = capsys.readouterr().out
    assert "license open" in out and "p1_s1 | - | 件名 庁舎清掃業務" in out
    assert "Bids are due" not in out


def test_review_session_doc_states_the_rules():
    text = (GUIDE.parent / "review_session.md").read_text(encoding="utf-8")
    for must in ("docs/labeling_guide.md", "data/cache/labeling/answers/<batch-name>-answers.txt",
                 "Never edit code", "Never run `import`", "UNSURE:", "restricted",
                 "--reviewer claude_code", "silver_model_reviewed"):  # fmt: skip
        assert must in text, must


# --- daily caps stop one provider, never the run (D-56) ------------------------------------


def test_a_capped_provider_stops_for_the_day_and_the_next_day_resumes(env):
    from eval.silver.config import PROVIDERS
    from eval.silver.limiter import Ledger

    d1, d2, d3 = row(doc_id="d1"), row(doc_id="d2"), row(doc_id="d3", license_class="restricted")  # fmt: skip
    led = Ledger(env.tmp / "cache" / "usage.jsonl")
    for _ in range(PROVIDERS["gemini"].rpd - 1):  # one Gemini request left today
        led.append(ts=env.clock.now(), provider="gemini", model="m", kind="label",
                   outcome="ok", ok=True, tokens_in=1, tokens_out=1)  # fmt: skip
    assert any("gemini" in n and "stops at the cap" in n for n in run.run_notes([d1, d2, d3], 100, env.clock.now()))  # fmt: skip
    scripts = {"gemini": [answer(GOOD)], "groq": [answer(GOOD)], LOCAL: [answer(GOOD)]}
    out = run.run_docs([d1, d2, d3], 100, pipe=env.make(scripts))
    assert out == {"resolved": 2, "compared": 0, "pending": 1, "skipped": 0}  # d2 waits
    assert env.fakes["gemini"].calls == 1 and env.fakes[LOCAL].calls == 3
    assert env.fakes["groq"].calls >= 1  # Groq went on after Gemini stopped
    assert any("gemini: daily cap reached" in x for x in env.log)
    env.clock.t += 86_400  # the next UTC day: the same plain run picks up d2 only
    out = run.run_docs([d1, d2, d3], 100, pipe=env.make(scripts))
    assert out["resolved"] == 3 and out["pending"] == 0
    assert env.fakes["gemini"].calls == 1 and env.fakes[LOCAL].calls == 0
    assert env.fakes["groq"].calls == 0


def test_plain_run_over_the_daily_budget_starts_instead_of_aborting(env, monkeypatch, capsys):  # fmt: skip
    from eval.silver import __main__ as cli
    from eval.silver.config import PROVIDERS
    from eval.silver.limiter import Ledger

    led = Ledger(env.tmp / "cache" / "usage.jsonl")
    for _ in range(PROVIDERS["gemini"].rpd):
        led.append(ts=env.clock.now(), provider="gemini", model="m", kind="label",
                   outcome="http_503", ok=False, tokens_in=0, tokens_out=0)  # fmt: skip
    monkeypatch.setattr(cli, "datetime", type("D", (), {"now": staticmethod(lambda tz: __import__("datetime").datetime.fromtimestamp(env.clock.now(), tz))}))  # fmt: skip
    monkeypatch.setattr(run, "ja_sentences", lambda r: [s for s in SENTENCES if s.language == "ja"])  # fmt: skip
    called = []
    monkeypatch.setattr(cli, "run_docs", lambda rows, n, retry: called.append((len(rows), n)) or {})  # fmt: skip
    assert cli.main(["run", "--split", "dev", "--yes", "--max-calls", "1"]) == 0
    out = capsys.readouterr().out
    assert called == [(1, 1)]
    assert (
        "gemini: daily cap already reached today" in out
        and "--max-calls 1 stops the run" in out
    )


def test_gemini_quota_day_is_pacific_groq_stays_utc(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path)  # no limits.json override
    from datetime import UTC, datetime

    from eval.silver.config import PROVIDERS
    from eval.silver.limiter import DailyCap, Ledger, Limiter

    led = Ledger(tmp_path / "usage.jsonl")
    ts = lambda s: datetime.fromisoformat(s).replace(tzinfo=UTC).timestamp()  # noqa: E731
    # 2026-10-03 09:10 UTC and 2026-10-04 04:41 UTC are both 2026-10-03 in Pacific time
    for t in (ts("2026-10-03T09:10:00"), ts("2026-10-04T04:41:00")):
        for p in ("gemini", "groq"):
            led.append(ts=t, provider=p, model="m", kind="label", outcome="http_503", ok=False, tokens_in=0, tokens_out=0)  # fmt: skip
    now = ts("2026-10-04T04:50:00")
    assert led.today("gemini", now, PROVIDERS["gemini"].quota_tz)["requests"] == 2
    assert led.today("groq", now, PROVIDERS["groq"].quota_tz)["requests"] == 1
    assert led.today("gemini", ts("2026-10-04T07:05:00"), "America/Los_Angeles")["requests"] == 0  # after Pacific midnight  # fmt: skip
    capped = replace(PROVIDERS["gemini"], rpd=2)
    with pytest.raises(DailyCap):
        Limiter(capped, led, lambda: now, lambda s: None).before(10)
    Limiter(capped, led, lambda: ts("2026-10-04T07:05:00"), lambda s: None).before(10)


# --- eligibility negation rule (D-58) ------------------------------------------------------


def test_eligibility_requirement_with_negation_equals_disqualification_without():
    from eval.silver.agree import ACTIVE, item_same

    # 28ad40ea4b1f p1_s14 (和歌山県 bid instructions): Gemini sv4 against the reviewed label
    req = {"kind": "legal", "polarity": "requirement", "citations": ["p1_s14"],
           "text_ja": "地方自治法施行令（昭和２２年政令第１６号）第１６７条の４第１項の規定に該当する者ではないこと。"}  # fmt: skip
    dis = {"kind": "legal", "polarity": "disqualification", "citations": ["p1_s14"],
           "text_ja": "地方自治法施行令（昭和２２年政令第１６号）第１６７条の４第１項の規定に該当する者"}  # fmt: skip
    assert "eligibility_negation" in ACTIVE
    assert item_same("eligibility", req, dis, ACTIVE)
    assert not item_same("eligibility", req, dis, ACTIVE - {"eligibility_negation"})
    # 28ad40ea4b1f p1_s19: …がない者であること is a negation too
    tax = {"kind": "legal", "polarity": "requirement", "citations": ["p1_s19"], "text_ja": "国税及び都道府県税の滞納がない者であること。"}  # fmt: skip
    assert item_same("eligibility", tax, {**tax, "polarity": "disqualification", "text_ja": "国税及び都道府県税の滞納"}, ACTIVE)  # fmt: skip
    # 563042df9941 h_s42: the label pairs disqualification with the negation kept; no
    # rule says that equals a requirement with the same text, so they stay different
    kept = {"kind": "legal", "citations": ["h_s42"], "text_ja": "予算決算及び会計令第７１条の規定に該当しない者であること。"}  # fmt: skip
    assert not item_same("eligibility", {**kept, "polarity": "requirement"}, {**kept, "polarity": "disqualification"}, ACTIVE)  # fmt: skip
    # a requirement without a negation never equals a disqualification
    pos = {"kind": "other", "citations": ["p1_s13"], "text_ja": "当該事業を的確に遂行する能力を有する民間事業者等"}  # fmt: skip
    assert not item_same("eligibility", {**pos, "polarity": "requirement"}, {**pos, "polarity": "disqualification"}, ACTIVE)  # fmt: skip


def test_no_active_rule_accepts_a_wrong_answer_in_any_review_round():
    from eval.silver import replay
    from eval.silver.agree import ACTIVE

    if not (config.CACHE / "export" / "ids.json").exists():
        pytest.skip("review answers not present")
    items = replay.load_reviews()
    assert len(items) >= 56
    for rule in ACTIVE:
        assert replay.shown_pair_replay(items, rule)["new_wrong"] == [], rule
    assert replay.shown_pair_replay(items, "period_relative_optional")["new_wrong"] == ["F-0025"]  # fmt: skip


# --- sv4 is frozen until dev and test are labeled (D-58) -----------------------------------

SV4_PROMPT_SHA256 = "c6e11d6e5df825a75de5349d079fae4dc7a65c7cff77c5e84f8f6ee8fb848919"


def test_prompt_sv4_is_frozen():
    """The prompt the gate and the dev run were made with. Editing the guide's prompt
    block, the rules, the field hints, examples or forms changes this hash: that is a
    new prompt version, which D-58 forbids until dev and test are both labeled."""
    import hashlib

    from eval.silver.prompt import local_system_prompt

    assert config.PROMPT_VERSION == config.LOCAL_PROMPT_VERSION == "sv4"
    text = "\n".join(system_prompt(applicable_fields(d)) for d in ("notice", "bid_instructions", "spec", "tender_page"))  # fmt: skip
    digest = hashlib.sha256((text + local_system_prompt()).encode()).hexdigest()
    assert digest == SV4_PROMPT_SHA256, "prompt sv4 is frozen until dev and test are labeled (D-58)"  # fmt: skip


# --- a truncated Groq part is split in two (D-59) ------------------------------------------


def test_truncated_groq_part_is_split_and_a_cached_one_is_split_by_the_next_run(env):
    from eval.silver.pipeline import field_groups, plan_parts
    from eval.silver.providers import Completion
    from tests.test_silver_sv3 import JA, part_answer

    r = row(license_class="restricted")
    first = plan_parts(r, JA, config.PROVIDERS["groq"])[0]
    h1, h2 = field_groups(first.field_ids, 2)
    cut = Completion("{", 1000, first.max_out, truncated=True)
    pipe = env.make({"groq": [cut, part_answer(h1, GOOD), part_answer(h2, GOOD), part_answer(first.field_ids, GOOD)]})  # fmt: skip
    ch = pipe.label(r, SENTENCES, "groq")["chunks"]["0"]
    assert ch["status"] == "ok" and ch["split_retry"]["first_error"].startswith(
        "truncated"
    )
    assert set(json.loads(ch["response"])["fields"]) == set(first.field_ids)
    assert env.fakes["groq"].seen[1]["max_out"] == first.max_out  # halves keep the cap

    # a part cached as truncated before this rule: the next plain run splits it from the
    # cache, with two half requests and no repeat of the whole part
    path = pipeline.raw_path(r.doc_id, "groq", "groq-model")
    raw = json.loads(path.read_text())
    raw["chunks"]["0"] = {"status": "failed", "error": "truncated at 1716 output tokens (cap 1716)",
                          "truncated": True, "attempts": 1, "field_ids": first.field_ids}  # fmt: skip
    path.write_text(json.dumps(raw))
    again = env.make({"groq": [part_answer(h1, GOOD), part_answer(h2, GOOD)]})
    ch = again.label(r, SENTENCES, "groq")["chunks"]["0"]
    assert ch["status"] == "ok" and env.fakes["groq"].calls == 2
    # a part already split is not split again, and a local part never is
    assert not pipeline.splittable(config.PROVIDERS["groq"], first, {**ch, "status": "failed", "truncated": True})  # fmt: skip
    assert not pipeline.splittable(pipeline.LOCAL_CFG, first, {"status": "failed", "truncated": True})  # fmt: skip
