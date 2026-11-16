# ruff: noqa: E501, E731, F811  (F811: the env fixture is imported)
# pyright: reportOptionalSubscript=false, reportOptionalMemberAccess=false
"""Silver pipeline sv3 (D-49 to D-51): Gemini in JSON mode with one repair request,
the local model's field groups and truncation, Groq's half-split retry, the provider
policy, labeler_overlap, reopening a consensus, the guide's forms block and comparison
scoring. No real API call; providers are the scripted fakes of test_silver.py, sentences
the real ones quoted there."""

import json
from dataclasses import replace

from shiori_core.fields import BY_ID

from eval.silver import config, pipeline, review, run
from eval.silver.compare import score
from eval.silver.limiter import Ledger
from eval.silver.model import Candidate
from eval.silver.pipeline import field_groups, plan_parts
from eval.silver.prompt import (
    GUIDE,
    applicable_fields,
    est_output,
    forms_markdown,
    line,
    system_prompt,
)
from eval.silver.providers import Completion, Gemini, ProviderError
from tests.test_silver import (  # noqa: F401  (env is a fixture)
    GOOD,
    LOCAL,
    SENTENCES,
    answer,
    env,
    labels_of,
    row,
)
from tests.test_silver_sv2 import sv2_answer

JA = [s for s in SENTENCES if s.language == "ja"]
QWEN = "Qwen3.5-9B-Q4_K_M"


def part_answer(field_ids: list[str], over: dict | None = None) -> str:
    """An sv2/sv3-shaped answer that covers only these fields (what one request of a
    field group returns)."""
    full = json.loads(sv2_answer(over))
    return json.dumps({"fields": {f: full["fields"][f] for f in field_ids},
                       "normalized": {f: v for f, v in full["normalized"].items() if f in field_ids}},
                      ensure_ascii=False)  # fmt: skip


# --- Gemini: JSON mode and the repair request (D-49) -------------------------------------


def test_gemini_json_mode_repair_round_trip(env):
    bad = json.loads(answer(GOOD))
    bad["fields"] = [
        r for r in bad["fields"] if r["field"] != "title"
    ]  # one field left out
    for r in bad["fields"]:
        if r["field"] == "bid_bond":
            r["normalized"] = json.dumps({"status": "maybe"})  # not a Bond status
    bad_text = json.dumps(bad, ensure_ascii=False)
    pipe = env.make({"gemini": [bad_text, answer(GOOD)]})
    raw = pipe.label(row(), SENTENCES, "gemini")
    ch = raw["chunks"]["0"]
    g = env.fakes["gemini"]
    assert g.calls == 2 and g.seen[0]["schema"] is None  # no strict schema is sent
    assert g.seen[0]["repair"] is None
    prev, message = g.seen[1]["repair"]
    assert (
        prev == bad_text
        and "title: missing from fields" in message
        and "bid_bond" in message
    )
    assert ch["status"] == "ok" and ch["repair"]["kept"] == "repair"
    assert ch["repair"]["errors_after"] == [] and len(ch["repair"]["errors"]) == 2
    assert (ch["tokens_in"], ch["tokens_out"], ch["attempts"]) == (2000, 1000, 2)
    u = Ledger(env.tmp / "cache" / "usage.jsonl").today("gemini", env.clock.now())
    assert u["requests"] == 2 and u["outcomes"] == {
        "ok": 2
    }  # the repair is in the ledger


def test_gemini_valid_answer_needs_no_repair_and_a_worse_repair_is_not_kept(env):
    pipe = env.make({"gemini": [answer(GOOD)]})
    ch = pipe.label(row(), SENTENCES, "gemini")["chunks"]["0"]
    assert env.fakes["gemini"].calls == 1 and "repair" not in ch
    missing = json.loads(answer(GOOD))
    missing["fields"] = missing["fields"][1:]
    pipe = env.make({"gemini": [json.dumps(missing), "not json at all"]})
    ch = pipe.label(row(doc_id="d2"), SENTENCES, "gemini")["chunks"]["0"]
    assert ch["status"] == "ok" and ch["repair"]["kept"] == "first"


def test_gemini_request_body_in_json_mode_with_a_repair_turn():
    sent: list = []

    def post(url, headers, body):
        sent.append(body)
        return {"candidates": [{"content": {"parts": [{"text": "{}"}]}, "finishReason": "MAX_TOKENS"}],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 9}}  # fmt: skip

    c = Gemini("k", post=post).complete(
        "sys", "user", None, 100, ("old answer", "fix this")
    )
    gen = sent[0]["generationConfig"]
    assert (
        "responseJsonSchema" not in gen
        and gen["responseMimeType"] == "application/json"
    )
    assert [m["role"] for m in sent[0]["contents"]] == ["user", "model", "user"]
    assert sent[0]["contents"][1]["parts"][0]["text"] == "old answer"
    assert c.truncated  # MAX_TOKENS


def test_gemini_gets_one_group_unless_its_answer_would_pass_the_output_cap():
    gem = config.PROVIDERS["gemini"]
    assert gem.strict_schema is False
    assert len(plan_parts(row(), JA, gem)) == 1
    small = replace(gem, max_out=est_output(23) - 1)  # a 23-field answer no longer fits
    parts = plan_parts(row(), JA, small)
    assert len(parts) == 2 and sorted(sum((p.field_ids for p in parts), [])) == sorted(applicable_fields("notice"))  # fmt: skip


# --- local model: field groups and truncation (D-50) --------------------------------------


def test_local_groups_keep_each_answer_under_60_percent_of_its_cap(monkeypatch):
    cfg = pipeline.LOCAL_CFG
    ids = applicable_fields("notice")
    (whole,) = plan_parts(row(), JA, cfg)  # sv4 default: one grouped call (D-54)
    assert whole.field_ids == ids and est_output(len(ids)) <= 0.6 * whole.max_out
    monkeypatch.setattr(config, "LOCAL_FOCUSED", True)
    single = [f for f in ids if BY_ID[f].kind == "list" or f == "contact"]
    parts = plan_parts(
        row(), JA, cfg
    )  # focused (sv3-l1): one request per field, then one grouped
    assert [p.field_ids for p in parts] == [[f] for f in single] + [[f for f in ids if f not in single]]  # fmt: skip
    for p in parts:
        assert p.max_out == min(
            config.LOCAL_MAX_OUT, config.LOCAL_CTX - p.est_in() - pipeline.CTX_MARGIN
        )
        assert est_output(len(p.field_ids)) <= 0.6 * p.max_out
    tight = replace(cfg, max_out=4096)  # 60% of 4,096 holds about 15 fields
    parts = plan_parts(row(), JA, tight)
    assert len(parts) == 2 + len(single)  # the grouped request is cut in two
    assert all(est_output(len(q.field_ids)) <= 0.6 * q.max_out for q in parts)
    assert sorted(sum((q.field_ids for q in parts), [])) == sorted(ids)


def test_local_cap_shrinks_to_what_the_context_leaves():
    cfg = replace(
        pipeline.LOCAL_CFG,
        request_cap=pipeline.overhead(applicable_fields("notice")) + 7000,
    )
    for q in plan_parts(row(), JA, cfg):
        assert q.max_out <= cfg.request_cap - q.est_in() - pipeline.CTX_MARGIN
        assert est_output(len(q.field_ids)) <= 0.6 * q.max_out


def test_truncated_local_answer_fails_at_once_and_is_reported(env):
    cut = Completion(
        '{"fields": {"title": {"status": "pres', 4000, 8192, truncated=True
    )
    pipe = env.make({LOCAL: [cut]})
    raw = pipe.label(row(), SENTENCES, LOCAL)
    ch = raw["chunks"]["0"]
    # temperature 0: the same request would be cut again, so each part is asked once
    assert env.fakes[LOCAL].calls == raw["n_chunks"]
    assert ch["status"] == "failed" and ch["truncated"] is True
    assert "truncated at 8192 output tokens" in ch["error"] and ch["max_out"] > 0
    assert pipeline.raw_state(raw) == "failed"


# --- Groq: half-split retry on json_validate_failed (D-50) --------------------------------


def test_groq_json_validate_failed_part_is_retried_as_two_half_groups(env):
    r = row(license_class="restricted")
    first = plan_parts(r, JA, config.PROVIDERS["groq"])[0]
    h1, h2 = field_groups(first.field_ids, 2)
    bad = ProviderError("bad_request", "HTTP 400 json_validate_failed", code=400)
    pipe = env.make(
        {"groq": [bad, part_answer(h1, GOOD), part_answer(h2, GOOD), sv2_answer(GOOD)]}
    )
    raw = pipe.label(r, SENTENCES, "groq")
    ch = raw["chunks"]["0"]
    g = env.fakes["groq"]
    assert ch["status"] == "ok" and ch["split_retry"]["first_error"].endswith(
        "json_validate_failed"
    )
    assert [h["status"] for h in ch["split_retry"]["halves"]] == ["ok", "ok"]
    assert set(json.loads(ch["response"])["fields"]) == set(first.field_ids)
    # the halves ask half the fields each, with the whole part's output cap
    assert [
        list(s["schema"]["properties"]["fields"]["properties"]) for s in g.seen[1:3]
    ] == [h1, h2]
    assert all(s["max_out"] == first.max_out for s in g.seen[1:3])
    assert ch["attempts"] == 3 and pipeline.raw_state(raw) == "complete"


def test_groq_split_retry_fails_the_part_when_a_half_fails(env):
    r = row(license_class="restricted")
    bad = ProviderError("bad_request", "HTTP 400 json_validate_failed", code=400)
    pipe = env.make({"groq": [bad, bad]})
    ch = pipe.label(r, SENTENCES, "groq")["chunks"]["0"]
    assert ch["status"] == "failed" and ch["error"].startswith("split retry:")
    assert len(ch["split_retry"]["halves"]) == 1  # the second half is not asked


def test_other_bad_requests_are_not_split(env):
    r = row(license_class="restricted")
    pipe = env.make(
        {"groq": [ProviderError("bad_request", "HTTP 400 other", code=400)]}
    )
    ch = pipe.label(r, SENTENCES, "groq")["chunks"]["0"]
    assert ch["status"] == "failed" and "split_retry" not in ch


# --- provider policy and labeler_overlap (D-50) ---------------------------------------------


def test_policy_end_to_end_open_never_needs_groq_restricted_never_reaches_gemini(env):
    pipe = env.make(
        {"gemini": [answer(GOOD)], "groq": [sv2_answer(GOOD)], LOCAL: [answer(GOOD)]}
    )
    open_, closed = row(doc_id="d1"), row(doc_id="d2", license_class="restricted")
    out = run.run_docs([open_, closed], 100, pipe=pipe)
    assert out["resolved"] == 2
    cache = env.tmp / "cache" / "raw"
    assert sorted(p.name.split("__")[0] for p in (cache / "d1").glob("*.json")) == [
        "gemini",
        "local",
    ]
    assert sorted(p.name.split("__")[0] for p in (cache / "d2").glob("*.json")) == [
        "groq",
        "local",
    ]
    per_doc = len(plan_parts(open_, SENTENCES, pipeline.LOCAL_CFG))
    assert env.fakes["gemini"].calls == 1 and env.fakes[LOCAL].calls == 2 * per_doc
    assert run.run_notes([open_], 100, env.clock.now()) == []
    tallies, _ = run.price([open_])
    assert set(tallies) == {
        "gemini",
        LOCAL,
    }  # the plan for an open document has no Groq


def test_labels_the_local_model_contributed_to_carry_labeler_overlap(env):
    a = {**GOOD, "procurement_type": dict(status="present", citations=["p1_s1"], normalized={"type": "open_competitive"})}  # fmt: skip
    b = {**GOOD, "procurement_type": dict(status="present", citations=["p1_s1"], normalized={"type": "designated_competitive"})}  # fmt: skip
    run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(a)], LOCAL: [answer(b)]})
    )
    lab = labels_of(env)
    assert (
        lab["bid_bond"]["provenance"]["labeler_overlap"] is True
    )  # consensus with Qwen
    review.export("dev", True, lambda s, o: [row()])
    assert review.import_answers("F-0001 | accept A") == (1, [])  # Gemini's answer won
    prov = labels_of(env)["procurement_type"]["provenance"]
    assert (
        prov["reviewed_choice"] == "gemini" and prov["labeler_overlap"] is True
    )  # Qwen was shown
    spec = row("spec", doc_id="d2")
    run.run_docs(
        [spec],
        100,
        pipe=env.make({"gemini": [answer({}, "spec")], LOCAL: [answer({}, "spec")]}),
    )
    rule_absent = labels_of(env, spec)["deadlines"]["provenance"]
    assert rule_absent["pre_labelers"] == [] and rule_absent["labeler_overlap"] is False


# --- reopening a consensus (D-51, document 4c40bbd831fe) ------------------------------------


def test_reopen_turns_a_consensus_into_a_review_item_with_a_third_candidate(env):
    # Mechanics: p1_s2 stands in for a 納入期限 sentence (its date is 2026-09-10).
    a = {**GOOD, "procurement_type": dict(status="present", citations=["p1_s1"], normalized={"type": "open_competitive"})}  # fmt: skip
    run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(a)], LOCAL: [answer(GOOD)]})
    )
    assert labels_of(env)["delivery_deadline"]["status"] == "absent"  # both said absent
    extra = {"delivery_deadline": dict(status="present", value_ja="令和８年（2026年）９月10日", citations=["p1_s2"], normalized={"date": "2026-09-10"})}  # fmt: skip
    path = pipeline.raw_path("d1", "local", "Other-9B", config.PROMPT_VERSION)
    path.write_text(json.dumps({"provider": "local", "model": "Other-9B", "n_chunks": 1, "chunks": {"0": {
        "status": "ok", "response": answer(extra), "date": "2026-10-03"}}}))  # fmt: skip
    item = review.reopen(
        row(), "delivery_deadline", "the third labeler found a date", "Other-9B"
    )
    assert len(item["sides"]) == 3 and item["agreement"] is False
    assert "delivery_deadline" not in labels_of(env)
    (p,) = review.export("dev", True, lambda s, o: [row()])
    text = p.read_text().split("field delivery_deadline")[1]
    assert (
        "C: status=present" in text and "p1_s2 |" in text and "p1_s4 |" in text
    )  # cited + neighbours
    iid = next(k for k, v in json.loads((config.CACHE / "export" / "ids.json").read_text())["items"].items()
               if v["field"] == "delivery_deadline")  # fmt: skip
    assert (
        json.loads((config.CACHE / "export" / "mapping.json").read_text())[iid]["C"]
        == "local"
    )
    assert review.import_answers(f"{iid} | accept C") == (1, [])
    ln = labels_of(env)["delivery_deadline"]
    assert ln["normalized"] == {"date": "2026-09-10"}
    assert ln["provenance"]["labeler_overlap"] is True
    assert [p["model"] for p in ln["provenance"]["pre_labelers"]][-1] == "Other-9B"


def test_reopen_a_written_label_shows_the_label_against_another_prompts_answer(env):
    # f19cddbd4cba issuer_org (D-52): the sv1 label against Gemini's sv3 answer. Here the
    # label's title 庁舎清掃業務 against an answer from prompt sv9 that quotes less of p1_s1.
    from eval.silver.config import PROVIDERS

    run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    )
    splits = json.loads(run.SPLITS.read_text())
    lf = pipeline.label_file(row(), splits)
    written = lf.read_text()
    newer = {**GOOD, "title": dict(status="present", value_ja="庁舎清掃", citations=["p1_s1"])}  # fmt: skip
    path = pipeline.raw_path("d1", "gemini", PROVIDERS["gemini"].model, "sv9")
    path.write_text(json.dumps({"provider": "gemini", "model": PROVIDERS["gemini"].model, "n_chunks": 1,
                                "chunks": {"0": {"status": "ok", "response": answer(newer), "date": "2026-10-03"}}}))  # fmt: skip
    item = review.reopen(
        row(), "title", "org rule changed", "gemini@sv9", show_label=True
    )
    a, b = (s["candidate"] for s in item["sides"])
    assert (a["labeler"], a["value_ja"]) == (
        f"label/{config.PROMPT_VERSION}",
        "庁舎清掃業務",
    )
    assert (b["labeler"], b["value_ja"]) == ("gemini/gemini-3.8-flash", "庁舎清掃")
    assert "title" not in pipeline.read_resolved("d1")
    assert lf.read_text() == written  # untouched until the review is imported
    (p,) = review.export("dev", True, lambda s, o: [row()])
    assert (
        "p1_s1 |" in p.read_text() and "p1_s3 |" in p.read_text()
    )  # cited + neighbours
    iid = next(k for k, v in json.loads((config.CACHE / "export" / "ids.json").read_text())["items"].items()
               if v["field"] == "title")  # fmt: skip
    mapping = json.loads((config.CACHE / "export" / "mapping.json").read_text())[iid]
    assert mapping == {"A": "label", "B": "gemini"}
    assert review.import_answers(f"{iid} | accept B") == (1, [])
    ln = labels_of(env)["title"]  # the label file, rewritten through the review
    assert (
        ln["value_ja"] == "庁舎清掃" and ln["provenance"]["reviewed_choice"] == "gemini"
    )
    assert ln["provenance"]["pre_labelers"][-1]["model"] == "gemini-3.8-flash"
    assert len(lf.read_text().splitlines()) == len(written.splitlines())
    try:
        review.reopen(row(), "title", "again")
        raise AssertionError("reopened a reviewed line")
    except ValueError as e:
        assert "not an accepted consensus" in str(e)


# --- prompt: the forms come from fields.py, and the guide shows the same ones ---------------


def test_guide_forms_block_matches_fields_py():
    text = GUIDE.read_text(encoding="utf-8")
    block = text.split("<!-- forms:start -->")[1].split("<!-- forms:end -->")[0]
    assert block.strip() == forms_markdown(), (
        "paste prompt.forms_markdown() into the guide"
    )


def test_prompt_describes_the_answer_shape_and_each_form():
    sp = system_prompt(["bid_bond", "title"])
    assert (
        '{"fields": {"<field>"' in sp
        and '"normalized": {"<field>": value or null}' in sp
    )
    assert (
        '- bid_bond: {"status": required|waived|waived_with_proviso, "rate_percent": number|null}.'
        in sp
    )
    assert "- title: text (value_ja only, no normalized)." in sp
    assert "not_stated" not in sp  # inner values a label never uses are not offered


def test_guide_org_rule_for_local_bodies_is_in_the_prompt():
    sp = system_prompt(["contact", "issuer_org"])
    assert "和歌山県教育庁" in sp and "教育庁" in sp and "警察本部" in sp


# --- comparison scoring ---------------------------------------------------------------------


def gold(field: str, status: str = "present", **kw) -> dict:
    return {"field": field, "status": status, "value_ja": kw.get("value_ja"), "value_en": None,
            "normalized": kw.get("normalized"), "citations": kw.get("citations", []),
            "provenance": {}}  # fmt: skip


def test_comparison_scoring_uses_the_agreement_rule_per_field():
    golds = {
        "title": gold("title", value_ja="庁舎清掃業務", citations=["p1_s1"]),
        "bid_bond": gold("bid_bond", normalized={"status": "waived"}, citations=["p1_s4"]),
        "deadlines": gold("deadlines", normalized={"items": [{"kind": "bid_in_person", "datetime": "2026-09-10T13:30:00+09:00", "flags": [], "citations": ["p1_s2"]}]}, citations=["p1_s2"]),
        "award_method": gold("award_method", "absent"),
    }  # fmt: skip
    cands = {
        "title": Candidate("title", "present", "庁舎清掃業務 ", citations=["p1_s1"]),  # spaces only
        "bid_bond": Candidate("bid_bond", "present", normalized={"status": "required"}, citations=["p1_s4"]),
        "deadlines": Candidate("deadlines", "present", normalized=golds["deadlines"]["normalized"], citations=["p1_s2"]),
        "award_method": Candidate("award_method", "present", normalized={"method": "best_value"}, citations=["p1_s1"]),
    }  # fmt: skip
    got = dict(score(row(), cands, golds))
    assert got == {
        "title": True,
        "deadlines": True,
        "bid_bond": False,
        "award_method": False,
    }
    assert {BY_ID[f].kind for f in got} == {"text", "structured", "list"}
    cands["title"] = Candidate("title", parse_error="normalized is not valid JSON")
    assert dict(score(row(), cands, golds))["title"] is False


def test_comparison_report_scores_each_labeler_and_writes_no_label(env, monkeypatch):
    from eval.silver import compare

    run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    )
    before = pipeline.resolved_path("d1").read_text()
    monkeypatch.setattr(pipeline, "PROMPT_VERSION", "sv9")
    monkeypatch.setattr(pipeline, "LOCAL_PROMPT_VERSION", "sv9")  # both bumped
    other = {**GOOD, "bid_bond": dict(status="present", citations=["p1_s4"], normalized={"status": "required"})}  # fmt: skip
    out = run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(other)], LOCAL: [answer(GOOD)]})
    )
    assert out == {"resolved": 0, "compared": 1, "pending": 0, "skipped": 0}
    assert pipeline.resolved_path("d1").read_text() == before
    text = compare.REPORT.read_text()
    k = {kind: sum(BY_ID[f].kind == kind for f in applicable_fields("notice")) for kind in ("list", "structured", "text")}  # fmt: skip
    n = sum(k.values())
    assert (
        f"| gemini | {k['list']} of {k['list']} | {k['structured'] - 1} of {k['structured']} | {k['text']} of {k['text']} | {n - 1} of {n} "
        in text
    )
    assert (
        f"| {QWEN} | {k['list']} of {k['list']} | {k['structured']} of {k['structured']} | {k['text']} of {k['text']} | {n} of {n} (100%) |"
        in text
    )
    assert "gemini, mismatches (1): d1 bid_bond (consensus)" in text
    assert (
        "slightly favors Gemini" in text
        and "## Projection for the full dev set" in text
    )


# --- the local model: shape check and one repair request (D-52) --------------------------

# what Qwen did on 28ad40ea4b1f in the sv3 pilot: a structured field marked present with
# `normalized` null (the strict schema allows null, so the grammar cannot stop it)
EMPTY = {
    **GOOD,
    "bid_bond": dict(status="present", citations=["p1_s4"], normalized=None),
}


def test_local_answer_gets_the_shape_check_and_one_repair_request(env):
    bad = answer(EMPTY)
    n = len(plan_parts(row(), SENTENCES, pipeline.LOCAL_CFG))
    # the single-field requests answer well; the grouped one (last, holds bid_bond) does not
    pipe = env.make({LOCAL: [answer(GOOD)] * (n - 1) + [bad, answer(GOOD)]})
    raw = pipe.label(row(), SENTENCES, LOCAL)
    ch = raw["chunks"][str(n - 1)]
    q = env.fakes[LOCAL]
    assert q.calls == n + 1  # one repair request
    assert all(s["schema"] is not None for s in q.seen)  # grammar kept
    prev, message = q.seen[n]["repair"]
    assert prev == bad and "bid_bond" in message and "title" not in message
    assert ch["status"] == "ok" and ch["repair"]["kept"] == "repair"
    assert ch["response"] == answer(GOOD) and ch["repair"]["first_response"] == bad
    assert [e.split(":")[0] for e in ch["repair"]["errors"]] == ["bid_bond"]


def test_local_repair_message_is_plain_words_with_the_fields_form_and_an_example():
    errs = ["bid_bond: Input should be a valid dictionary or instance of Bond",
            "title: missing from fields", "the answer is not valid JSON (x)"]  # fmt: skip
    msg = pipeline.plain_repair_message(errs)
    assert "valid dictionary" not in msg and "instance of" not in msg
    assert "bid_bond: its status is present but normalized.bid_bond is empty" in msg
    assert 'Example: {"status": "waived", "rate_percent": null}' in msg
    assert '- title: there is no entry for title in "fields"; add one.' in msg
    assert (
        "- the answer is not valid JSON (x)" in msg
    )  # whole-answer problems as they are
    # Gemini keeps the validator's own message (its prompt version did not change)
    assert "valid dictionary" in pipeline.repair_message(errs)


def cache_local(doc_id: str, bad_grouped: bool) -> None:
    """Local answers cached before the shape check existed (no `repair` key), one per
    part of the plan; with bad_grouped, the grouped part's (the last) answer has an
    empty value."""
    parts = plan_parts(row(doc_id=doc_id), SENTENCES, pipeline.LOCAL_CFG)
    chunks = {str(i): {"status": "ok", "response": answer(EMPTY if bad_grouped and i == len(parts) - 1 else GOOD),
                       "tokens_in": 4000, "tokens_out": 900, "attempts": 1, "seconds": 600.0,
                       "max_out": 8192, "field_ids": p.field_ids,
                       "sentence_ids": [s.id for s in p.sentences], "date": "2026-10-03"}
              for i, p in enumerate(parts)}  # fmt: skip
    path = pipeline.raw_path(doc_id, "local", QWEN)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"provider": "local", "model": QWEN, "n_chunks": len(parts), "chunks": chunks}))  # fmt: skip


def test_cached_local_answer_is_repaired_without_a_full_rerun(env):
    from eval.silver.compare import before_repair

    cache_local("d1", bad_grouped=True)
    cache_local("d2", bad_grouped=False)
    pipe = env.make({LOCAL: [answer(GOOD)]})
    *rest, got = pipe.repair_cached(row(), SENTENCES, LOCAL)
    assert env.fakes[LOCAL].calls == 1  # the repair request only
    assert env.fakes[LOCAL].seen[0]["repair"][0] == answer(EMPTY)
    assert (got["before"], got["after"], got["kept"]) == (["bid_bond"], [], "repair")
    assert all(r["before"] == [] for r in rest)  # the other parts needed nothing
    raw = pipeline.load_raw(pipeline.raw_path("d1", "local", QWEN))
    last = str(raw["n_chunks"] - 1)
    ch = raw["chunks"][last]
    assert ch["response"] == answer(GOOD) and ch["attempts"] == 2
    assert (ch["tokens_in"], ch["tokens_out"]) == (5000, 1400)  # cached + repair
    assert (ch["repair"]["tokens_in"], ch["repair"]["tokens_out"]) == (1000, 500)
    assert before_repair(raw)["chunks"][last]["response"] == answer(EMPTY)
    assert pipe.repair_cached(row(), SENTENCES, LOCAL) == []  # done once
    clean = pipe.repair_cached(row(doc_id="d2"), SENTENCES, LOCAL)
    assert all(c["before"] == [] for c in clean) and env.fakes[LOCAL].calls == 1
    d2 = pipeline.load_raw(pipeline.raw_path("d2", "local", QWEN))["chunks"]["0"]
    assert d2["shape_checked"] is True and "repair" not in d2


def test_single_source_projection_settles_only_tier_two_fields_with_one_usable_side():
    from eval.silver.compare import single_source
    from eval.silver.pipeline import Resolved

    ok = [("schema_valid", True), ("citations_exist", True)]
    bad = [("schema_valid", False)]

    def flagged(field, a_checks, b_checks):
        sides = [{"candidate": {"status": "present"}, "checks": a_checks},
                 {"candidate": {"status": "present"}, "checks": b_checks}]  # fmt: skip
        return Resolved(field, "flagged", None, ["B failed schema_valid"], sides, False)

    assert single_source(
        flagged("title", ok, bad)
    )  # tier 2, Gemini clean, local unusable
    assert not single_source(flagged("deadlines", ok, bad))  # tier 1: never
    assert not single_source(
        flagged("title", ok, ok)
    )  # a real disagreement stays flagged
    assert not single_source(flagged("title", bad, bad))  # Gemini must pass every check
    assert not single_source(flagged("title", ok + [("heading_cue", False)], ok))


# --- focused local calls (sv3-l1, D-53; behind --local-focused since sv4, D-54) ------------


def test_local_calls_start_with_the_same_bytes_and_ask_list_fields_one_at_a_time(env, monkeypatch):  # fmt: skip
    monkeypatch.setattr(config, "LOCAL_FOCUSED", True)
    t = {"cache_n": 4000, "prompt_n": 120, "prompt_ms": 900.0, "predicted_n": 300, "predicted_ms": 40000.0}  # fmt: skip
    pipe = env.make({LOCAL: [Completion(answer(GOOD), 1000, 500, timings=t)]})
    raw = pipe.label(row(), SENTENCES, LOCAL)
    seen = env.fakes[LOCAL].seen
    assert len({s["system"] for s in seen}) == 1  # one system prompt for every call
    doc = "Sentences (id | section | text):\n" + "\n".join(line(s) for s in SENTENCES)
    assert all(s["user"].startswith(doc + "\n\nDocument type: notice\n\nFields:\n") for s in seen)  # fmt: skip
    asked = [s["user"].split("Fields:\n")[1] for s in seen]
    for f in ("eligibility", "deadlines", "required_documents", "contact"):
        assert sum(a.startswith(f"- {f}:") and a.count("\n- ") == 0 for a in asked) == 1
    assert "- title:" in asked[-1] and "- eligibility:" not in asked[-1]  # grouped last
    assert raw["chunks"]["1"]["timings"] == [t]  # llama-server's cache counters kept


def test_cloud_and_local_answers_are_cached_under_their_own_prompt_versions(env, monkeypatch):  # fmt: skip
    monkeypatch.setattr(config, "LOCAL_FOCUSED", True)
    run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    )
    names = sorted(p.name for p in (env.tmp / "cache" / "raw" / "d1").glob("*.json"))
    assert [n.split("__")[2] for n in names] == ["sv4", "sv4-l1"]  # gemini, local
    assert (
        pipeline.prompt_for("gemini") == "sv4" and pipeline.prompt_for("groq") == "sv4"
    )
    prov = labels_of(env)["bid_bond"]["provenance"]
    assert prov["prompt_version"] == "sv4"
    assert [p["prompt_version"] for p in prov["pre_labelers"]] == ["sv4", "sv4-l1"]
    again = env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    run.run_docs([row()], 100, pipe=again)
    assert env.fakes["gemini"].calls == 0 and env.fakes[LOCAL].calls == 0  # all cached


def test_reopen_a_reviewed_line_gets_a_new_item_and_is_resolved_by_import(env):
    # 563042df9941 scope_summary (D-53): reviewed as F-0024, reopened as a new item and
    # answered with see_other_document through the normal import.
    a = {**GOOD, "procurement_type": dict(status="present", citations=["p1_s1"], normalized={"type": "open_competitive"})}  # fmt: skip
    run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(a)], LOCAL: [answer(GOOD)]})
    )
    review.export("dev", True, lambda s, o: [row()])
    assert review.import_answers("F-0001 | accept A") == (1, [])
    try:
        review.reopen(row(), "procurement_type", "x")
        raise AssertionError("reopened a reviewed line without --reviewed")
    except ValueError as e:
        assert "--reviewed" in str(e)
    item = review.reopen(row(), "procurement_type", "pointer", reviewed=True, show_label=True)  # fmt: skip
    assert item["kind"] == "reopened"
    review.export("dev", True, lambda s, o: [row()])
    ids = json.loads((config.CACHE / "export" / "ids.json").read_text())["items"]
    (iid,) = [k for k, v in ids.items() if v["kind"] == "reopened"]
    assert iid == "F-0002"  # a new id; F-0001 keeps the first review
    line_ = f"{iid} | custom | status=absent | note=no procedure named"
    assert review.import_answers(line_) == (1, [])
    ln = labels_of(env)["procurement_type"]
    assert ln["status"] == "absent" and ln["provenance"]["reviewed_by"] == "claude_chat"
    recs = [
        json.loads(x) for x in (config.CACHE / "reviews.jsonl").read_text().splitlines()
    ]
    assert [r["iid"] for r in recs] == ["F-0001", iid]
