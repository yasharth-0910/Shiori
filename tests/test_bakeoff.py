# ruff: noqa: E501, E731, F811
"""eval/bakeoff.py with a fake llama-server (scripted Fake providers), invented documents
and invented labels. No network, no llama-server, no real model file."""

import json
import os

import pytest

from eval import bakeoff
from eval.silver import config, pipeline, run
from eval.silver.prompt import applicable_fields
from eval.silver.providers import ProviderError
from tests.test_silver import (  # noqa: F401  (env is a fixture)
    GOOD,
    Fake,
    answer,
    env,
    row,
)

REPORT_TEXT = """| model | size GB | loaded | load s | tok/s | notes |
|---|---|---|---|---|---|
| NVIDIA-Nemotron-9B.gguf | 6.5 | yes | 5.0 | 11.7 | ok |
| Qwen3.5-9B-Q4_K_M.gguf | 5.7 | yes | 4.5 | 15.8 | ok |
| LFM-small.gguf | 0.7 | yes | 1.0 | 86.2 | ok |
| sarashina2.2-3b.gguf | 2.1 | yes | 2.0 | 35.3 | ok |
| broken.gguf | 3.4 | no | - | - | exited |
| gone.gguf | 1.0 | yes | 1.0 | 50.0 | ok |
"""
NO_BATTERY = lambda: False  # noqa: E731
NOT_BUSY = lambda: False  # noqa: E731


@pytest.fixture
def bo(env, monkeypatch):
    """Report, model files, one open dev document with a label file (GOOD answers)."""
    models = env.tmp / "models"
    models.mkdir()
    for n in (
        "NVIDIA-Nemotron-9B",
        "Qwen3.5-9B-Q4_K_M",
        "LFM-small",
        "sarashina2.2-3b",
    ):
        (models / f"{n}.gguf").write_bytes(b"GGUF")
    rep = env.tmp / "loadcheck.md"
    rep.write_text(REPORT_TEXT)
    monkeypatch.setattr(bakeoff, "LOADCHECK", rep)
    monkeypatch.setattr(bakeoff, "MODELS_DIR", models)
    monkeypatch.setattr(bakeoff, "REPORT", env.tmp / "bakeoff.md")
    monkeypatch.setattr(config, "PILOT", ("d1",))
    r = row()
    lines = []
    for f in applicable_fields("notice"):
        g = GOOD.get(f, {})
        lines.append({"doc_id": "d1", "field": f, "status": g.get("status", "absent"),
                      "value_ja": g.get("value_ja"), "value_en": None,
                      "normalized": g.get("normalized"), "citations": g.get("citations", []),
                      "provenance": {"reviewed_by": "claude_chat" if f in GOOD else None}})  # fmt: skip
    p = pipeline.label_file(r, json.loads(run.SPLITS.read_text()))
    p.parent.mkdir(parents=True)
    p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
    return env


def fakes_for(scripts: dict[str, list], cls=Fake) -> dict[str, Fake]:
    return {f"local:{g}": cls("local", g.removesuffix(".gguf"), sc, True) for g, sc in scripts.items()}  # fmt: skip


def start(bo, fakes, max_calls=50, battery=NO_BATTERY, rows=None):
    models, _ = bakeoff.pool()
    b = bakeoff.Bakeoff(models, rows or [row()], max_calls, fakes.__getitem__, bo.clock.now,
                        bo.clock.sleep, battery, NOT_BUSY, lambda s: None)  # fmt: skip
    return b, b.start()


def calls(fakes) -> int:
    return sum(f.calls for f in fakes.values())


def test_pool_reads_the_report_orders_by_speed_and_leaves_out_sarashina(bo):
    models, notes = bakeoff.pool()
    assert [m.gguf for m in models] == ["LFM-small.gguf", "Qwen3.5-9B-Q4_K_M.gguf", "NVIDIA-Nemotron-9B.gguf"]  # fmt: skip
    assert [m.overlap for m in models] == [False, True, False]
    text = " ".join(notes)
    assert "sarashina" in text and "broken.gguf" in text and "gone.gguf" in text


def test_scoring_matches_the_expected_counts_and_overlap_is_marked(bo):
    wrong = {**GOOD, "bid_bond": dict(status="present", citations=["p1_s4"], normalized={"status": "required"})}  # fmt: skip
    fakes = fakes_for({"LFM-small.gguf": [answer(GOOD)], "Qwen3.5-9B-Q4_K_M.gguf": [answer(wrong)],
                       "NVIDIA-Nemotron-9B.gguf": [answer(GOOD)]})  # fmt: skip
    _, reason = start(bo, fakes)
    assert reason == "all models done"
    n = len(applicable_fields("notice"))
    t1 = len([f for f in applicable_fields("notice") if f in config.TIER1])
    models, _ = bakeoff.pool()
    per = {m.gguf: bakeoff.summarize([bakeoff.measure(row(), bakeoff.model_raw(m, row()), bakeoff.read_gold(row()))]) for m in models}  # fmt: skip
    assert per["LFM-small.gguf"]["all"] == (n, n) and per["LFM-small.gguf"]["t1"] == (
        t1,
        t1,
    )
    q = per["Qwen3.5-9B-Q4_K_M.gguf"]
    assert q["all"] == (n - 1, n) and q["t1"] == (t1 - 1, t1)  # bid_bond is tier 1
    assert q["valid"] == (1, 1) and q["repair"] == (0, 1)
    assert q["cite"][1] > 0 and q["cite"][0] == q["cite"][1]  # every present answer cites a real sentence  # fmt: skip
    text = bakeoff.REPORT.read_text()
    qline = next(x for x in text.splitlines() if x.startswith("| Qwen3.5-9B"))
    other = next(x for x in text.splitlines() if x.startswith("| LFM-small"))
    assert "labeler_overlap" in qline and "labeler_overlap" not in other
    assert f"{t1 - 1}/{t1}" in qline and "does not tell you" in text
    assert "庁舎" not in text  # no document text in the report


def test_a_restart_repeats_no_request(bo):
    fakes = fakes_for({"LFM-small.gguf": [answer(GOOD)], "Qwen3.5-9B-Q4_K_M.gguf": [answer(GOOD)],
                       "NVIDIA-Nemotron-9B.gguf": [answer(GOOD)]})  # fmt: skip
    _, reason = start(bo, fakes, max_calls=2)
    assert reason == "--max-calls 2 reached" and calls(fakes) == 2
    assert not bakeoff.paths()[0].exists()  # pid file removed
    _, reason = start(bo, fakes)
    assert reason == "all models done" and calls(fakes) == 3  # one per model in all
    _, _ = start(bo, fakes)
    assert calls(fakes) == 3


def test_the_stop_file_ends_the_run_before_the_next_request(bo):
    class StopAfterFirst(Fake):
        def complete(self, *a, **k):
            c = super().complete(*a, **k)
            bakeoff.paths()[1].parent.mkdir(parents=True, exist_ok=True)
            bakeoff.paths()[1].write_text("")
            return c

    fakes = fakes_for({"LFM-small.gguf": [answer(GOOD)], "Qwen3.5-9B-Q4_K_M.gguf": [answer(GOOD)],
                       "NVIDIA-Nemotron-9B.gguf": [answer(GOOD)]}, StopAfterFirst)  # fmt: skip
    _, reason = start(bo, fakes)
    assert reason == "stopped: stop file" and calls(fakes) == 1
    _, reason = start(bo, fakes)  # a start with the file present is refused
    assert reason.startswith("refused") and calls(fakes) == 1


def test_a_live_pid_file_refuses_a_start(bo):
    bakeoff.paths()[0].parent.mkdir(parents=True, exist_ok=True)
    bakeoff.paths()[0].write_text(f"{os.getpid()}\n")
    fakes = fakes_for({"LFM-small.gguf": [answer(GOOD)]})
    _, reason = start(bo, fakes)
    assert reason.startswith("refused") and calls(fakes) == 0


def test_a_failed_request_is_not_retried_and_scores_as_all_wrong(bo):
    boom = ProviderError("network", "TimeoutError")
    fakes = fakes_for({"LFM-small.gguf": [boom], "Qwen3.5-9B-Q4_K_M.gguf": [answer(GOOD)],
                       "NVIDIA-Nemotron-9B.gguf": [answer(GOOD)]})  # fmt: skip
    docs = [row(doc_id="d1")]
    b, reason = start(bo, fakes, rows=docs)
    # one request, no retry, the failed answer is a miss for every field
    assert fakes["local:LFM-small.gguf"].calls == 1 and reason == "all models done"
    assert fakes["local:Qwen3.5-9B-Q4_K_M.gguf"].calls == 1
    m = bakeoff.pool()[0][0]
    d = bakeoff.measure(row(), bakeoff.model_raw(m, row()), bakeoff.read_gold(row()))
    assert (
        d.state == "failed" and d.valid_first == 0 and not any(ok for _, ok in d.scored)
    )


def test_no_cloud_labeler_can_be_made():
    with pytest.raises(ProviderError):
        bakeoff.make_provider("gemini")
    assert bakeoff.make_provider("local:x.gguf").TIMEOUT == bakeoff.REQUEST_TIMEOUT  # type: ignore[attr-defined]


def test_plan_makes_no_request_and_a_bare_run_is_a_plan(bo, capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a request was made")

    monkeypatch.setattr(bakeoff, "make_provider", boom)
    monkeypatch.setattr(bakeoff.Local, "complete", boom)
    for argv in (["--plan"], [], ["--max-calls", "5"]):
        assert bakeoff.main(argv) == 0
    out = capsys.readouterr().out
    assert (
        "LFM-small.gguf" in out
        and "est hours" in out
        and "no request has been made" in out
    )
    assert "sarashina" in out and "labeler_overlap" in out
    assert bakeoff.main(["--yes"]) == 2  # --yes needs --max-calls
    assert not bakeoff.paths()[0].exists() and not bakeoff.REPORT.exists()
