# ruff: noqa: E501
"""The renderer's whole bridge to the main process is eleven functions (D-83, D-85, D-90, D-98, D-99, D-100)."""

import re
from pathlib import Path

ELECTRON = Path(__file__).resolve().parent.parent / "app" / "electron"
ELEVEN = {
    "startProcessing",
    "getStatus",
    "getFields",
    "translate",
    "cancel",
    "saveExport",
    "listModels",
    "openCalendar",
    "downloadModel",
    "downloadStatus",
    "chooseModelFile",
}  # translate: D-85, cancel: D-90, saveExport: D-98, listModels: D-99, openCalendar: D-98, the last three: D-100


def test_preload_exposes_exactly_eleven_functions() -> None:
    src = (ELECTRON / "preload.ts").read_text()
    exposed = re.findall(r"exposeInMainWorld\(\s*\"(\w+)\"", src)
    assert exposed == ["shiori"]  # one object, once
    body = src[src.index("exposeInMainWorld") :]
    assert set(re.findall(r"^\s+(\w+):\s*\(", body, re.M)) == ELEVEN
    assert len(re.findall(r"ipcRenderer\.invoke\(", src)) == 11


def test_preload_gives_no_raw_ipc_or_node() -> None:
    src = (ELECTRON / "preload.ts").read_text()
    assert re.findall(r"""(?:from|require\()\s*["']([^"']+)["']""", src) == ["electron"]
    assert not re.search(
        r"exposeInMainWorld\([^)]*ipcRenderer\s*[,}]", src
    )  # the module itself is not exposed


def test_main_handles_exactly_those_eleven_channels() -> None:
    main = (ELECTRON / "main.ts").read_text()
    assert re.findall(r'ipcMain\.handle\("([^"]+)"', main) == [
        "shiori:start",
        "shiori:status",
        "shiori:cancel",
        "shiori:translate",
        "shiori:save",
        "shiori:open-calendar",
        "shiori:models",
        "shiori:download",
        "shiori:download-status",
        "shiori:import-model",
        "shiori:fields",
    ]
    assert set(re.findall(r'ipcRenderer\.invoke\("([^"]+)"', (ELECTRON / "preload.ts").read_text())) == {
        "shiori:start", "shiori:status", "shiori:fields", "shiori:translate", "shiori:cancel", "shiori:save", "shiori:open-calendar", "shiori:models", "shiori:download", "shiori:download-status", "shiori:import-model"
    }  # fmt: skip


def test_ipc_handlers_check_sender_and_ids() -> None:
    main = (ELECTRON / "main.ts").read_text()
    assert main.count("own(e);") == 11
    assert "docId(id)" in main
