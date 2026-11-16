# ruff: noqa: E501, E731, F811
"""The gold daemon (eval/silver/daemon.py, D-62). Fake providers, an injected clock, no
network and no llama-server."""

import json
import os
import subprocess

import pytest
from shiori_core.fields import FIELD_IDS

from eval.silver import __main__ as cli
from eval.silver import config, daemon, pipeline, review, run
from eval.silver.prompt import applicable_fields
from tests.test_silver import (  # noqa: F401  (env is a fixture)
    GOOD,
    LOCAL,
    answer,
    env,
    row,
)

NO_BATTERY = lambda: False  # noqa: E731


def make(env, rows, max_calls=100, battery=NO_BATTERY, scripts=None):
    scripts = scripts or {"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]}
    env.make(scripts)
    env.fakes["gemini"].model = config.PROVIDERS[
        "gemini"
    ].model  # the cache path uses the real name
    d = daemon.Daemon(1, rows, max_calls, env.fakes.__getitem__, env.clock.now, env.clock.sleep, battery)  # fmt: skip
    return d


def events(env):
    p = config.CACHE / "daemon.log"
    return [x.split()[1] for x in p.read_text().splitlines()] if p.exists() else []


def total_calls(env):
    return sum(f.calls for f in env.fakes.values())


def fill_gemini(env, left: int):
    from eval.silver.limiter import Ledger

    led = Ledger(env.tmp / "cache" / "usage.jsonl")
    for _ in range(config.PROVIDERS["gemini"].rpd - left):
        led.append(ts=env.clock.now(), provider="gemini", model="m", kind="label",
                   outcome="ok", ok=True, tokens_in=1, tokens_out=1)  # fmt: skip


def test_tier1_concepts_map_to_real_unambiguous_field_ids():
    assert daemon.tier1_problems() == []
    assert set(daemon.CONCEPTS.values()) == set(config.TIER1) <= set(FIELD_IDS)
    assert len(daemon.CONCEPTS) == len(set(daemon.CONCEPTS.values())) == 10


def test_a_bad_mapping_is_listed_not_guessed(monkeypatch):
    monkeypatch.setitem(daemon.CONCEPTS, "bid bond", "bid_security")
    monkeypatch.setitem(daemon.CONCEPTS, "tax basis", "performance_bond")
    probs = daemon.tier1_problems()
    assert any("bid_security" in p and "not in schema" in p for p in probs)
    assert any("performance_bond" in p and "more than one" in p for p in probs)


def test_a_capped_provider_stops_the_other_goes_on_and_the_pacific_reset_wakes_it(env):
    d1, d2 = row(doc_id="d1"), row(doc_id="d2")
    fill_gemini(env, left=1)  # one Gemini request left today
    d = make(env, [d1, d2])
    t0 = env.clock.now()
    reset = daemon.next_reset("gemini", t0)
    reason = d.start()
    assert reason == "wave resolved"
    ev = events(env)
    assert ev.index("cap") < ev.index("sleep") < ev.index("woke")
    # the local model finished d2 before the daemon slept
    log = (config.CACHE / "daemon.log").read_text().splitlines()
    assert any("labeled provider=local" in x and "doc=d2" in x for x in log[: ev.index("sleep")])  # fmt: skip
    assert env.clock.now() >= reset  # slept through the Pacific midnight
    assert env.fakes["gemini"].calls == 2 and env.fakes[LOCAL].calls == 2  # nothing repeated  # fmt: skip
    assert all(daemon.is_done(r) for r in (d1, d2))


def test_pacific_reset_is_midnight_los_angeles(env):
    t0 = env.clock.now()  # 2027-01-15 08:00 UTC = midnight Pacific (PST)
    assert daemon.next_reset("gemini", t0) == t0 + 86_400
    assert daemon.next_reset("gemini", t0 + 3600) == t0 + 86_400


def test_a_restart_repeats_no_completed_request(env):
    rows = [row(doc_id="d1"), row(doc_id="d2")]
    d = make(env, rows, max_calls=1)
    assert "--max-calls 1 reached" in d.start()
    assert total_calls(env) == 1
    d = make(env, rows)  # a new start, same fakes' counters are reset by make
    first = total_calls(env)
    assert d.start() == "wave resolved"
    # 2 documents x (gemini + local) = 4 requests in all: one done before, none repeated
    assert 1 + total_calls(env) - first == 4


def test_a_document_that_is_not_open_never_reaches_a_cloud_provider(env):
    r = row(doc_id="d1", license_class="restricted")
    d = make(env, [r])
    d.start()
    assert "refused" in events(env)
    assert total_calls(env) == 0
    assert not daemon.is_done(r)


def test_gold_rows_refuses_what_gold_set_lists_but_is_not_open_or_not_dev(
    env, monkeypatch
):
    rows = [row(doc_id="d1"), row(doc_id="d2", license_class="restricted"), row(doc_id="d3", org="東京都")]  # fmt: skip
    monkeypatch.setattr(run, "read_rows", lambda: rows)
    gs = env.tmp / "gold_set.json"
    gs.write_text(json.dumps({"waves": [{"wave": 1, "docs": [{"doc_id": r.doc_id} for r in rows] + [{"doc_id": "zz"}]}]}))  # fmt: skip
    monkeypatch.setattr(daemon, "GOLD_SET", gs)
    ok, refused = daemon.gold_rows(1)
    assert [r.doc_id for r in ok] == ["d1"]
    assert {d for d, _ in refused} == {"d2", "d3", "zz"}


def test_a_live_pid_file_refuses_a_start_and_a_stale_one_does_not(env):
    pid = config.CACHE / "daemon.pid"
    pid.parent.mkdir(parents=True)
    pid.write_text(str(os.getpid()))
    d = make(env, [row(doc_id="d1")])
    assert d.start().startswith("refused: process")
    assert total_calls(env) == 0 and pid.read_text() == str(os.getpid())
    dead = subprocess.Popen(["true"])
    dead.wait()
    pid.write_text(str(dead.pid))
    assert make(env, [row(doc_id="d1")]).start() == "wave resolved"
    assert not pid.exists()  # removed on exit


def test_the_stop_file_is_honored_between_requests(env):
    stop = config.CACHE / "STOP"
    d = make(env, [row(doc_id="d1"), row(doc_id="d2")])
    g = env.fakes["gemini"]
    orig = g.complete
    g.complete = lambda *a, **k: (lambda r: (stop.touch(), r)[1])(orig(*a, **k))
    assert d.start() == "stop file"
    assert total_calls(env) == 1  # the next request was never sent
    assert any(e.startswith("stop_stop_file") for e in events(env))
    assert make(env, [row(doc_id="d1")]).start().startswith("refused: stop file")  # until removed  # fmt: skip


def test_three_failures_in_a_row_from_one_provider_stop_the_run(env):
    from eval.silver.providers import ProviderError

    boom = ProviderError("server", "x", code=503)
    d = make(env, [row(doc_id="d1"), row(doc_id="d2")], scripts={"gemini": [boom], LOCAL: [answer(GOOD)]})  # fmt: skip
    assert d.start() == "3 failures in a row from gemini"


def test_the_laptop_on_battery_pauses_and_goes_on_when_plugged_in(env):
    power = iter([True, True, False] + [False] * 50)
    d = make(env, [row(doc_id="d1")], battery=lambda: next(power))
    t0 = env.clock.now()
    assert d.start() == "wave resolved"
    assert "paused_battery" in events(env) and "resumed_ac" in events(env)
    assert env.clock.now() - t0 >= 120  # it waited


def test_plan_makes_no_call_and_writes_nothing(env, monkeypatch, capsys):
    rows = [row(doc_id="d1"), row(doc_id="d2")]
    monkeypatch.setattr(run, "read_rows", lambda: rows)
    gs = env.tmp / "gold_set.json"
    gs.write_text(json.dumps({"waves": [{"wave": 1, "docs": [{"doc_id": "d1"}, {"doc_id": "d2"}]}]}))  # fmt: skip
    monkeypatch.setattr(daemon, "GOLD_SET", gs)

    def boom(*a, **k):
        raise AssertionError("a request was made")

    monkeypatch.setattr(pipeline, "_default_factory", boom)
    monkeypatch.setattr(daemon, "_default_factory", boom)
    monkeypatch.setattr(pipeline.Pipeline, "label", boom)
    monkeypatch.setattr(daemon, "on_battery", NO_BATTERY)
    for argv in (["daemon", "--gold", "--wave", "1", "--plan"], ["daemon", "--gold", "--wave", "1"], ["daemon", "--gold", "--wave", "1", "--yes", "--plan"]):  # fmt: skip
        assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "submission deadline(s)   -> deadlines" in out and "no request has been made" in out  # fmt: skip
    assert "gemini:" in out and "next reset" in out
    assert not (config.CACHE / "daemon.pid").exists() and not (config.CACHE / "daemon.log").exists()  # fmt: skip
    assert (
        cli.main(["daemon", "--gold", "--wave", "1", "--yes"]) == 2
    )  # --yes needs --max-calls


def test_tier1_always_exported_and_the_sample_is_the_same_on_two_runs(env):
    r = row(doc_id="d1")
    make(env, [r]).start()
    tier1 = [f for f in config.TIER1 if f in applicable_fields("notice")]

    def exported():
        items = json.loads(pipeline.decisions_path("d1").read_text())["items"]
        return {i["field"]: i for i in items}

    first = exported()
    assert set(tier1) <= set(first)  # every tier 1 field, agreed or flagged
    assert all(first[f]["kind"] == "spot" and "tier 1" in first[f]["reasons"][0] for f in tier1 if "gold" in first[f]["reasons"][0])  # fmt: skip
    rest = {f for f in first if f not in tier1}
    sample = {f for f in applicable_fields("notice") if f not in tier1 and daemon.gold_sample("d1", f)}  # fmt: skip
    assert rest <= sample | {f for f in first if first[f]["kind"] == "flagged"}
    # run it again from the raw cache alone: same items, no request
    calls = total_calls(env)
    pipeline.decisions_path("d1").unlink()
    import shutil

    shutil.rmtree(config.CACHE / "resolved")
    make(env, [r]).start()
    assert total_calls(env) == 0 < calls
    assert exported().keys() == first.keys()
    # wave-tagged export, nothing imported
    assert (config.CACHE / "export" / "batch-w1-01.md").exists()
    assert "gold wave 1" in (config.CACHE / "export" / "batch-w1-01.md").read_text()
    assert not (config.CACHE / "reviews.jsonl").exists()


def test_a_document_resolved_before_the_gold_policy_gets_its_tier1_items_without_a_request(
    env,
):
    r = row(doc_id="d1")
    make(env, [r]).start()
    p = pipeline.decisions_path("d1")
    old = json.loads(p.read_text())
    old["items"] = []  # as after the D-43 policy: nothing agreed was exported
    p.write_text(json.dumps(old))
    assert daemon.tier1_not_in_review(r)
    d = make(env, [r])
    assert d.start() == "wave resolved"
    assert total_calls(env) == 0
    assert not daemon.tier1_not_in_review(r)
    assert "regold" in events(env)


def bad400():
    from eval.silver.providers import ProviderError

    return ProviderError("bad_request", "x", code=400)


def gemini_entries(env):
    from eval.silver.limiter import Ledger

    return Ledger(env.tmp / "cache" / "usage.jsonl").entries("gemini")


def test_a_failed_part_is_skipped_without_the_flag_and_retried_with_it_for_a_doc_outside_label_set(
    env,
):
    r = row(doc_id="d9")  # not in label_set.json (the env's label set holds d1 only)
    reason = make(
        env, [r], scripts={"gemini": [bad400()], LOCAL: [answer(GOOD)]}
    ).start()
    assert reason.startswith("stalled") and "daemon --gold --wave 1 --retry-failed" in reason and "not `run`" in reason  # fmt: skip
    assert env.fakes["gemini"].calls == 1 and len(gemini_entries(env)) == 1
    # same cache, no flag: the failed part is not asked again
    make(env, [r]).start()
    assert env.fakes["gemini"].calls == 0 and len(gemini_entries(env)) == 1
    # with the flag: asked once more, recorded as one request, and the document resolves
    d = make(env, [r])
    d.retry_failed = True
    assert d.start() == "wave resolved"
    assert env.fakes["gemini"].calls == 1
    ents = gemini_entries(env)
    assert len(ents) == 2 and ents[-1]["outcome"] == "ok" and ents[0]["outcome"] == "http_400"  # fmt: skip
    assert (
        env.fakes[LOCAL].calls == 0
    )  # its part was cached: only the failed one was asked


def test_a_retry_that_fails_again_counts_toward_the_three_in_a_row(env):
    r = row(doc_id="d9")
    make(env, [r], scripts={"gemini": [bad400()], LOCAL: [answer(GOOD)]}).start()
    rows = [r, row(doc_id="d8"), row(doc_id="d7"), row(doc_id="d6")]
    d = make(env, rows, scripts={"gemini": [bad400()], LOCAL: [answer(GOOD)]})
    d.retry_failed = True
    assert d.start() == "3 failures in a row from gemini"
    assert env.fakes["gemini"].calls == 3


def test_a_401_stops_the_provider_at_once_and_logs_auth_error(env, capsys):
    from eval.silver.providers import ProviderError

    rows = [row(doc_id="d9"), row(doc_id="d8")]
    make(env, rows, scripts={"gemini": [bad400()], LOCAL: [answer(GOOD)]}).start()
    d = make(env, rows, scripts={"gemini": [ProviderError("auth", "x", code=401)], LOCAL: [answer(GOOD)]})  # fmt: skip
    d.retry_failed = True
    reason = d.start()
    assert env.fakes["gemini"].calls == 1  # not three tries, and d8 was not tried
    assert "auth_error" in events(env)
    assert gemini_entries(env)[-1]["outcome"] == "http_401"
    assert reason == "stalled: gemini stopped by an authorization error"
    assert "authorization error (http_401)" in capsys.readouterr().out


def test_a_retry_never_sends_a_document_that_is_not_open_to_a_cloud_provider(env):
    d = make(env, [row(doc_id="d9", license_class="restricted")])
    d.retry_failed = True
    d.start()
    assert total_calls(env) == 0 and "refused" in events(env)


def test_plan_lists_the_failed_parts_with_and_without_the_flag(
    env, monkeypatch, capsys
):
    r = row(doc_id="d9")
    make(env, [r], scripts={"gemini": [bad400()], LOCAL: [answer(GOOD)]}).start()
    monkeypatch.setattr(run, "read_rows", lambda: [r])
    gs = env.tmp / "gold_set.json"
    gs.write_text(json.dumps({"waves": [{"wave": 1, "docs": [{"doc_id": "d9"}]}]}))
    monkeypatch.setattr(daemon, "GOLD_SET", gs)
    monkeypatch.setattr(pipeline.Pipeline, "label", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a request was made")))  # fmt: skip
    assert cli.main(["daemon", "--gold", "--wave", "1", "--plan"]) == 0
    out = capsys.readouterr().out
    assert "NOTE 1 failed parts are being skipped (gemini 1)" in out and "--retry-failed" in out  # fmt: skip
    assert (
        "d9 gemini: failed parts 1\n" in out
        and "gemini" in out
        and "1 failed parts skipped" in out
    )
    assert (
        cli.main(["daemon", "--gold", "--wave", "1", "--plan", "--retry-failed"]) == 0
    )
    out = capsys.readouterr().out
    assert "--retry-failed: 1 failed parts" in out and "d9 gemini: failed parts 1 -> 1 request(s)" in out  # fmt: skip
    assert "1 requests for 1 documents" in out


def test_gold_sample_is_seeded_and_about_a_fifth():
    pick = [daemon.gold_sample(f"doc{i}", f) for i in range(200) for f in ("title", "contact")]  # fmt: skip
    assert pick == [daemon.gold_sample(f"doc{i}", f) for i in range(200) for f in ("title", "contact")]  # fmt: skip
    assert 0.12 < sum(pick) / len(pick) < 0.28


def test_a_wave_export_leaves_the_plain_batches_alone(env):
    out = config.CACHE / "export"
    out.mkdir(parents=True)
    (out / "batch-01.md").write_text("plain")
    (out / "batch-w1-09.md").write_text("old wave")
    review.export("dev", True, lambda s, o: [], 1)
    assert (out / "batch-01.md").exists() and not (out / "batch-w1-09.md").exists()


@pytest.fixture(autouse=True)
def _no_real_battery(monkeypatch):
    monkeypatch.setattr(daemon, "on_battery", NO_BATTERY)
