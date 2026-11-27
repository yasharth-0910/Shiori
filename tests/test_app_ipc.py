# ruff: noqa: E501
"""The renderer's whole bridge to the main process is twenty functions (D-83, D-85, D-90, D-98, D-99, D-100, D-115, D-121)."""

import re
from pathlib import Path

ELECTRON = Path(__file__).resolve().parent.parent / "app" / "electron"
TWENTY = {
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
    "scanModels",
    "scanStatus",
    "scanCancel",
    "useScanned",
    "listDocuments",
    "getStorage",
    "setKeepDocuments",
    "deleteDocument",
    "deleteAllDocuments",
}  # translate: D-85, cancel: D-90, saveExport: D-98, listModels: D-99, openCalendar: D-98, downloadModel, downloadStatus, chooseModelFile: D-100, scanModels to useScanned: D-115, the last five: D-121


def test_preload_exposes_exactly_twenty_functions() -> None:
    src = (ELECTRON / "preload.ts").read_text()
    exposed = re.findall(r"exposeInMainWorld\(\s*\"(\w+)\"", src)
    assert exposed == ["shiori"]  # one object, once
    body = src[src.index("exposeInMainWorld") :]
    assert set(re.findall(r"^\s+(\w+):\s*\(", body, re.M)) == TWENTY
    assert len(re.findall(r"ipcRenderer\.invoke\(", src)) == 20


def test_preload_gives_no_raw_ipc_or_node() -> None:
    src = (ELECTRON / "preload.ts").read_text()
    assert re.findall(r"""(?:from|require\()\s*["']([^"']+)["']""", src) == ["electron"]
    assert not re.search(
        r"exposeInMainWorld\([^)]*ipcRenderer\s*[,}]", src
    )  # the module itself is not exposed


def test_main_handles_exactly_those_twenty_channels() -> None:
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
        "shiori:scan",
        "shiori:scan-status",
        "shiori:scan-cancel",
        "shiori:scan-use",
        "shiori:fields",
        "shiori:documents",
        "shiori:storage",
        "shiori:set-keep",
        "shiori:delete",
        "shiori:delete-all",
    ]
    assert set(re.findall(r'ipcRenderer\.invoke\("([^"]+)"', (ELECTRON / "preload.ts").read_text())) == {
        "shiori:start", "shiori:status", "shiori:fields", "shiori:translate", "shiori:cancel", "shiori:save", "shiori:open-calendar", "shiori:models", "shiori:download", "shiori:download-status", "shiori:import-model", "shiori:scan", "shiori:scan-status", "shiori:scan-cancel", "shiori:scan-use", "shiori:documents", "shiori:storage", "shiori:set-keep", "shiori:delete", "shiori:delete-all"
    }  # fmt: skip


def test_ipc_handlers_check_sender_and_ids() -> None:
    main = (ELECTRON / "main.ts").read_text()
    assert main.count("own(e);") == 20
    assert "docId(id)" in main


def test_storage_channels_go_to_the_service() -> None:
    """Each storage channel checks the sender, then hands its raw argument to the
    service, which validates it (app/test/storage.test.ts)."""
    main = (ELECTRON / "main.ts").read_text()
    for channel, params, call in (
        ("documents", "", "listDocuments()"),
        ("storage", "", "getStorage()"),
        ("set-keep", ", keep: unknown", "setKeepDocuments(keep)"),
        ("delete", ", id: unknown", "deleteDocument(id)"),
        ("delete-all", "", "deleteAllDocuments()"),
    ):
        handler = (
            f'ipcMain.handle("shiori:{channel}", (e{params}) => {{\n'
            f"    own(e);\n    return storage.{call};\n  }});"
        )
        assert handler in main, channel
    assert "return storage.translate(doc, ids, modelId, live);" in main
    assert "return storage.fields(doc, info, " in main


def test_only_the_service_reaches_the_store() -> None:
    """storage.ts is the one value import of the store and the keeper (D-121)."""
    users = {
        p.name
        for p in ELECTRON.glob("*.ts")
        if re.search(
            r"""^import (?!type ).*["']\./(?:store|keeper)(?:\.ts)?["']""",
            p.read_text(),
            re.M,
        )
    }
    assert users == {"storage.ts"}
