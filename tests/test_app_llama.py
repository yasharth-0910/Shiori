# ruff: noqa: E501
"""Static checks on how the app starts llama-server and the sidecar (D-84)."""

import re
from pathlib import Path

ELECTRON = Path(__file__).resolve().parent.parent / "app" / "electron"


def read(name: str) -> str:
    return (ELECTRON / name).read_text()


def test_shiori_pick_only_works_when_not_packaged() -> None:
    """SHIORI_PICK is read once, in a constant gated on app.isPackaged; the SHIORI_SHOT dev block is gated too."""
    for name in ("main.ts", "sidecar.ts", "llama.ts", "preload.ts"):
        for line in read(name).splitlines():
            if "process.env.SHIORI_PICK" in line:
                assert "app.isPackaged ?" in line, f"{name}: {line.strip()}"
    main = read("main.ts")
    assert "const PICK = app.isPackaged ? undefined : process.env.SHIORI_PICK" in main
    assert "const shot = app.isPackaged ? undefined : process.env.SHIORI_SHOT" in main


def test_shot_stage_and_shot_open_only_work_when_not_packaged() -> None:
    """The two screenshot dev options are read once each, in constants gated on app.isPackaged."""
    main = read("main.ts")
    assert (
        "const shotStage = app.isPackaged ? undefined : process.env.SHIORI_SHOT_STAGE"
        in main
    )
    assert (
        "const shotOpen = app.isPackaged ? undefined : process.env.SHIORI_SHOT_OPEN"
        in main
    )
    for name in ("main.ts", "sidecar.ts", "llama.ts", "preload.ts"):
        for line in read(name).splitlines():
            if "process.env.SHIORI_SHOT_" in line:
                assert "app.isPackaged ?" in line, f"{name}: {line.strip()}"


def test_highlight_check_hook_only_works_when_not_packaged() -> None:
    main = read("main.ts")
    assert (
        "const HLCHECK = app.isPackaged ? undefined : process.env.SHIORI_HLCHECK"
        in main
    )
    assert main.count("process.env.SHIORI_HLCHECK") == 1


def test_the_api_key_travels_in_the_environment_not_argv() -> None:
    llama, sidecar = read("llama.ts"), read("sidecar.ts")
    assert "LLAMA_API_KEY: key" in llama and "SHIORI_LLAMA_KEY: llama.key" in sidecar
    for text in (llama, sidecar):
        for args in re.findall(r"(?:const args = |spawn\([^,]+, )(\[[^\]]*\])", text):
            assert "key" not in args.lower().replace("--api-key", "X"), args
            assert "--api-key" not in args
    assert "--api-key" not in llama


def test_llama_server_is_loopback_one_at_a_time_and_stopped() -> None:
    llama, main = read("llama.ts"), read("main.ts")
    assert 'const HOST = "127.0.0.1";' in llama and '"--host", HOST' in llama
    assert "listen(0, HOST" in llama  # a random free port
    # one server at a time is the module's own `proc`; it never looks for other processes by name (D-112)
    assert "llama_already_started" in llama
    code = "\n".join(x for x in llama.splitlines() if not x.lstrip().startswith("//"))
    assert not re.search(r"pgrep|execFileSync|\"ps\"", code)
    assert (
        'stdio: "ignore"' in llama
    )  # its output (which could hold prompts) is discarded
    assert (
        "llama.stop()" in main
        and 'process.on("exit", stopAll)' in main
        and 'app.on("will-quit", stopAll)' in main
    )
    assert "sidecar.onDeath(" in main and "process.on(sig, () => app.quit())" in main


def test_renderer_never_gets_the_llama_port_or_key() -> None:
    for p in (ELECTRON.parent / "src").rglob("*"):
        if p.is_file():
            text = p.read_text().lower()
            assert "llama_api_key" not in text and "shiori_llama" not in text
