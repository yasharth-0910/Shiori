"""Checks for eval/model_loadcheck.py. Invented data; no test starts a server."""

import json
from pathlib import Path

import pytest

from eval.model_loadcheck import is_gguf, manifest_model_digest, ollama_blob, table


def test_manifest_picks_the_model_layer() -> None:
    m = {"layers": [
        {"mediaType": "application/vnd.ollama.image.license", "digest": "sha256:aaa"},
        {"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:bbb"},
    ]}  # fmt: skip
    assert manifest_model_digest(m) == "sha256:bbb"
    with pytest.raises(ValueError):
        manifest_model_digest({"layers": []})


def test_ollama_blob_path(tmp_path: Path) -> None:
    d = tmp_path / "manifests" / "registry.ollama.ai" / "library" / "toy"
    d.mkdir(parents=True)
    layer = {"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:abc"}
    (d / "1b").write_text(json.dumps({"layers": [layer]}))
    assert ollama_blob("toy:1b", tmp_path) == tmp_path / "blobs" / "sha256-abc"


def test_gguf_magic(tmp_path: Path) -> None:
    good, bad = tmp_path / "g", tmp_path / "b"
    good.write_bytes(b"GGUF\x03\x00\x00\x00")
    bad.write_bytes(b"PK\x03\x04")
    assert is_gguf(good) and not is_gguf(bad)


def test_table_row() -> None:
    row = {
        "model": "m.gguf",
        "gb": 2.0,
        "loaded": False,
        "load_s": None,
        "tok_s": None,
        "note": "a|b",
    }
    assert "| m.gguf | 2.0 | no | - | - | a/b |" in table([row])


def test_report_text_never_carries_the_home_directory() -> None:
    from pathlib import Path

    from eval.model_loadcheck import home_to_tilde

    home = Path("/home/someone")  # invented
    text = "loading model '/home/someone/Coding/x/models/a.gguf'"
    assert home_to_tilde(text, home) == "loading model '~/Coding/x/models/a.gguf'"
    assert home_to_tilde(f"{Path.home()}/x") == "~/x"  # default: the real home
