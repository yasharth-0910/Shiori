"""app/ must not make or reference any network URL (CLAUDE.md hard rule, docs/privacy.md).

Scans the app's own source (not node_modules, build output, the gitignored fixture
or the lockfile, which names npm registry URLs for dev-time installs). Flags:
  - http(s)://, ws(s)://, ftp:// URLs, protocol-relative //host URLs in src= / href=
  - fetch/XMLHttpRequest/WebSocket/EventSource/sendBeacon calls whose target is not a
    relative path or a shiori:// URL
  - import of electron's net, https, http, or the 'autoUpdater'
  - a CSP that is missing or allows a remote source (index.html)

The one exception is the model download (D-100, CLAUDE.md): exactly
electron/download.ts may import node:https and node:http, and
electron/registry.ts may hold the pinned https://huggingface.co/ URLs it
downloads. Both are named below with their reason; nothing else may.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
# test/ holds the dev-only node tests: never built or packaged (the two tsconfig
# files include src and electron only). They name example hosts and run a loopback
# server on purpose.
SKIP_DIRS = {"node_modules", "dist", "dist-electron", "public", "test"}
SKIP_FILES = {"package-lock.json"}
SUFFIXES = {".ts", ".tsx", ".mts", ".js", ".mjs", ".cjs", ".json", ".html", ".css"}

URL = re.compile(r"""(?:https?|wss?|ftp)://[^\s"'`)<>]+""", re.I)
PROTO_REL = re.compile(r"""(?:src|href)\s*=\s*["']//""", re.I)
NET_API = re.compile(
    r"\b(?:XMLHttpRequest|WebSocket|EventSource|sendBeacon|autoUpdater)\b"
)
NET_IMPORT = re.compile(
    r"""(?:from|require\()\s*["'](?:node:)?(?:https?|net|dgram|tls)["']|\bnet\s*[,}]\s*[^;]*from\s*["']electron["']"""
)
FETCH = re.compile(r"""\bfetch\(\s*([^)]*)\)""")


def app_files() -> list[Path]:
    return [
        p
        for p in APP.rglob("*")
        if p.is_file()
        and p.suffix in SUFFIXES
        and p.name not in SKIP_FILES
        and not (set(p.relative_to(APP).parts) & SKIP_DIRS)
    ]


def problems(text: str) -> list[str]:
    out = [f"URL {m.group(0)}" for m in URL.finditer(text)]
    out += ["protocol-relative src/href" for _ in PROTO_REL.finditer(text)]
    out += [f"network API {m.group(0)}" for m in NET_API.finditer(text)]
    out += [f"network import {m.group(0)}" for m in NET_IMPORT.finditer(text)]
    for m in FETCH.finditer(text):
        target = m.group(1).strip()
        if (
            not re.match(r"""["'`]\./|["'`]/[^/]|["']shiori://""", target)
            and "url" not in target.lower()
        ):
            out.append(f"fetch target {target}")
    return out


def test_app_has_sources_to_scan() -> None:
    names = {p.name for p in app_files()}
    assert {"main.ts", "App.tsx", "index.html"} <= names


SIDECAR = "electron/sidecar.ts"  # may name a URL: the sidecar's loopback port (D-83)
LLAMA = "electron/llama.ts"  # may name a URL (llama-server's loopback port, health check) and import net for a free port (D-84)
LOOPBACK_FILES = {SIDECAR, LLAMA}
# The model download exception (D-100): the ONLY file that may import a network
# module. It takes a registry id, never a URL from the renderer, requires https,
# and moves a file into place only if its SHA-256 matches the registry.
DOWNLOAD = "electron/download.ts"
# The registry holds the pinned download URLs as data (D-100): this host only.
REGISTRY_FILE = "electron/registry.ts"
PINNED_HOST = "URL https://huggingface.co/"


def download_problems(text: str) -> list[str]:
    """download.ts: node:https and node:http imports are its point; the rest is not."""
    return [
        p
        for p in problems(text)
        if not (
            p.startswith("network import")
            and re.search(r"""["']node:https?["']""", p + text) is not None
            and "node:net" not in p
            and "tls" not in p
            and "dgram" not in p
        )
    ]


def registry_problems(text: str) -> list[str]:
    return [p for p in problems(text) if not p.startswith(PINNED_HOST)]


def sidecar_problems(text: str) -> list[str]:
    """In electron/sidecar.ts a URL must start with the HOST constant, which must be 127.0.0.1."""
    out = [
        p
        for p in problems(text)
        if not p.startswith(("URL http://${HOST}:", "fetch target", "network import"))
    ]
    if "node:net" in text.replace('"node:net"', "", 1):
        out.append("net imported twice or used for more")
    if 'const HOST = "127.0.0.1";' not in text:
        out.append("HOST is not the 127.0.0.1 constant")
    out += [f"fetch target {m.group(1)}" for m in FETCH.finditer(text) if not m.group(1).strip().startswith("`http://${HOST}:")]  # fmt: skip
    return out


def test_app_makes_no_network_reference() -> None:
    found = {
        str(p.relative_to(APP)): (
            sidecar_problems
            if p.relative_to(APP).as_posix() in LOOPBACK_FILES
            else download_problems
            if p.relative_to(APP).as_posix() == DOWNLOAD
            else registry_problems
            if p.relative_to(APP).as_posix() == REGISTRY_FILE
            else problems
        )(p.read_text())
        for p in app_files()
    }
    found = {k: v for k, v in found.items() if v}
    assert not found, found


def test_csp_present_and_local_only() -> None:
    html = (APP / "index.html").read_text()
    m = re.search(r'Content-Security-Policy"\s+content="([^"]+)"', html)
    assert m, "index.html has no CSP meta tag"
    csp = m.group(1)
    assert "default-src 'none'" in csp
    for bad in ("*", "http:", "https:", "ws:", "wss:", "'unsafe-eval'"):
        assert bad not in csp.split(), f"CSP allows {bad}"


def test_renderer_cannot_reach_any_host() -> None:
    """The renderer (app/src, index.html) names no host and holds no token; the CSP lets it
    talk to itself only (shiori://); the only other fetch in the app is the main process's call
    to the sidecar. A page that can only reach 'self' cannot reach 127.0.0.1 either."""
    csp = re.search(
        r'Content-Security-Policy"\s+content="([^"]+)"',
        (APP / "index.html").read_text(),
    )
    assert csp
    assert re.search(r"connect-src 'self'(;|$)", csp.group(1))
    for p in [*(APP / "src").rglob("*"), APP / "index.html"]:
        if p.is_file():
            text = p.read_text().lower()
            for word in (
                "127.0.0.1",
                "localhost",
                "token",
                "authorization",
                "child_process",
                "ipcrenderer",
            ):
                assert word not in text, f"{p.name} mentions {word}"
    fetchers = {
        p.relative_to(APP).as_posix() for p in app_files() if "fetch(" in p.read_text()
    }
    assert fetchers <= {SIDECAR, LLAMA, "src/App.tsx"}, (
        fetchers
    )  # App.tsx: ./fixture.json (relative, shiori://)


def test_sidecar_checker_catches_a_remote_host() -> None:
    assert sidecar_problems(
        'const HOST = "127.0.0.1"; fetch(`http://example.com/${x}`)'
    )
    assert sidecar_problems('const HOST = "0.0.0.0"; fetch(`http://${HOST}:${port}/x`)')
    assert not sidecar_problems(
        'const HOST = "127.0.0.1"; fetch(`http://${HOST}:${port}/x`)'
    )


def test_window_flags() -> None:
    main = (APP / "electron" / "main.ts").read_text()
    assert "contextIsolation: true" in main
    assert "nodeIntegration: false" in main
    assert "sandbox: true" in main


def test_detector_catches_bad_code() -> None:
    assert problems('fetch("https://example.com/x")')
    assert problems("new WebSocket(u)")
    assert problems('import https from "node:https"')
    assert problems('fetch(remote + "/a")')
    assert not problems('fetch("./fixture.json")')


def _own_files() -> list[Path]:
    """Every .ts/.tsx under electron/, src/ and the dev tests."""
    return [
        p
        for d in ("electron", "src", "test")
        for p in (APP / d).rglob("*")
        if p.suffix in {".ts", ".tsx", ".mts"}
    ]


def test_network_import_is_only_in_download_ts() -> None:
    """Exactly one shipped file imports node:https or node:http (not the dev tests)."""
    imp = re.compile(r"""(?:from|require\()\s*["'](?:node:)?(?:https?)["']""")
    shipped = {
        p.relative_to(APP).as_posix()
        for p in _own_files()
        if p.relative_to(APP).parts[0] != "test" and imp.search(p.read_text())
    }
    assert shipped == {DOWNLOAD}, shipped
    assert "node:https" in (APP / DOWNLOAD).read_text()


def test_download_checker_catches_other_network_use() -> None:
    assert not download_problems('import * as https from "node:https";')
    assert not download_problems('import * as http from "node:http";')
    assert download_problems('import * as net from "node:net";')
    assert download_problems('fetch("https://example.com/x")')
    assert download_problems('const u = "https://example.com/x";')
    assert download_problems("new WebSocket(u)")
    assert not registry_problems('url: "https://huggingface.co/a/b/resolve/x/y.gguf",')
    assert registry_problems('url: "https://example.com/a.gguf",')
    assert registry_problems('url: "http://huggingface.co/a.gguf",')


def test_download_ts_holds_no_url_and_takes_no_url_from_the_renderer() -> None:
    src = (APP / DOWNLOAD).read_text()
    code = re.sub(r"//.*", "", src)
    assert not re.search(r"""(?:https?|wss?|ftp)://""", code), "names a URL"
    assert "fetch(" not in src
    main = (APP / "electron" / "main.ts").read_text()
    # the handler passes the id to start() and nothing else
    handler = (
        r'"shiori:download", \(e, id: unknown\) => \{'
        r"\s*own\(e\);\s*void dl\(\)\.start\(id\);"
    )
    assert re.search(handler, main)
    assert "allowLoopbackHttp" not in main


def test_main_uses_the_counting_request_filter() -> None:
    main = (APP / "electron" / "main.ts").read_text()
    assert "webRequest.onBeforeRequest(filter.onBeforeRequest)" in main
    assert main.count("webRequest.onBeforeRequest") == 1
    nf = (APP / "electron" / "netfilter.ts").read_text()
    assert "^(shiori|devtools|data|blob):" in nf
    code = re.sub(r"//.*", "", nf)
    assert not re.search(r"""https?://|127\.0\.0\.1|localhost""", code)
