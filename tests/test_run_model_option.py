# ruff: noqa: E501
"""eval.run --model sets hybrid.MODEL before the extractor starts (no model, no corpus)."""

from pathlib import Path

from eval import hybrid, run


def test_model_option_sets_hybrid_model(monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(run, "label_dirs", lambda s: [])
    monkeypatch.setattr("eval.silver.run.select", lambda s, doc_ids=None: seen.setdefault("m", hybrid.MODEL) and [])
    monkeypatch.setattr(hybrid, "MODEL", Path("models/default.gguf"))
    monkeypatch.setattr(hybrid, "stop", lambda: None)
    monkeypatch.setattr(hybrid, "write_report", lambda *a: Path("x"))
    monkeypatch.setattr(hybrid, "show", lambda *a: None)
    monkeypatch.setattr(run, "write", lambda rep: (Path("j"), Path("m")))
    run.main(["--extractor", "hybrid", "--model", "models/other.gguf"])
    assert seen["m"] == Path("models/other.gguf")
