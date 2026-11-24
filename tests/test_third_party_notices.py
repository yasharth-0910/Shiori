"""packaging/third_party_notices.py finds the core packages (D-113).

Needs `uv sync` and app/node_modules.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "packaging" / "third_party_notices.py"


def test_notices_cover_core_packages():
    if not (SCRIPT.parent.parent / "app" / "node_modules").is_dir():
        pytest.skip("app/node_modules missing")
    spec = importlib.util.spec_from_file_location("tpn", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text, _ = mod.build()
    for name in ("pymupdf", "fastapi", "pydantic", "react", "electron", "pdfjs-dist"):
        assert name in text
    assert (
        "pytest" not in mod.runtime_python_packages()
    )  # dev-only tools are not shipped
