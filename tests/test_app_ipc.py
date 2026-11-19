# ruff: noqa: E501
"""The renderer's whole bridge to the main process is five functions (D-83, D-85, D-90)."""

import re
from pathlib import Path

ELECTRON = Path(__file__).resolve().parent.parent / "app" / "electron"
FIVE = {"startProcessing", "getStatus", "getFields", "translate", "cancel"}  # translate: D-85, cancel: D-90


def test_preload_exposes_exactly_five_functions() -> None:
    src = (ELECTRON / "preload.ts").read_text()
    exposed = re.findall(r"exposeInMainWorld\(\s*\"(\w+)\"", src)
    assert exposed == ["shiori"]  # one object, once
    body = src[src.index("exposeInMainWorld") :]
    assert set(re.findall(r"^\s+(\w+):\s*\(", body, re.M)) == FIVE
    assert len(re.findall(r"ipcRenderer\.invoke\(", src)) == 5


def test_preload_gives_no_raw_ipc_or_node() -> None:
    src = (ELECTRON / "preload.ts").read_text()
    assert re.findall(r"""(?:from|require\()\s*["']([^"']+)["']""", src) == ["electron"]
    assert not re.search(
        r"exposeInMainWorld\([^)]*ipcRenderer\s*[,}]", src
    )  # the module itself is not exposed


def test_main_handles_exactly_those_five_channels() -> None:
    main = (ELECTRON / "main.ts").read_text()
    assert re.findall(r'ipcMain\.handle\("([^"]+)"', main) == [
        "shiori:start",
        "shiori:status",
        "shiori:cancel",
        "shiori:translate",
        "shiori:fields",
    ]
    assert set(re.findall(r'ipcRenderer\.invoke\("([^"]+)"', (ELECTRON / "preload.ts").read_text())) == {
        "shiori:start", "shiori:status", "shiori:fields", "shiori:translate", "shiori:cancel"
    }  # fmt: skip


def test_ipc_handlers_check_sender_and_ids() -> None:
    main = (ELECTRON / "main.ts").read_text()
    assert main.count("own(e);") == 5
    assert "docId(id)" in main
