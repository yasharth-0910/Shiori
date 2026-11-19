"""app/ must not make or reference any network URL (CLAUDE.md hard rule, docs/privacy.md).

Scans the app's own source (not node_modules, build output, the gitignored fixture
or the lockfile, which names npm registry URLs for dev-time installs). Flags:
  - http(s)://, ws(s)://, ftp:// URLs, protocol-relative //host URLs in src= / href=
  - fetch/XMLHttpRequest/WebSocket/EventSource/sendBeacon calls whose target is not a
    relative path or a shiori:// URL
  - import of electron's net, https, http, or the 'autoUpdater'
  - a CSP that is missing or allows a remote source (index.html)
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
SKIP_DIRS = {"node_modules", "dist", "dist-electron", "public"}
SKIP_FILES = {"package-lock.json"}
SUFFIXES = {".ts", ".tsx", ".mts", ".js", ".mjs", ".cjs", ".json", ".html", ".css"}

URL = re.compile(r"""(?:https?|wss?|ftp)://[^\s"'`)<>]+""", re.I)
PROTO_REL = re.compile(r"""(?:src|href)\s*=\s*["']//""", re.I)
NET_API = re.compile(r"\b(?:XMLHttpRequest|WebSocket|EventSource|sendBeacon|autoUpdater)\b")
NET_IMPORT = re.compile(r"""(?:from|require\()\s*["'](?:node:)?(?:https?|net|dgram|tls)["']|\bnet\s*[,}]\s*[^;]*from\s*["']electron["']""")
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
        if not re.match(r"""["'`]\./|["'`]/[^/]|["']shiori://""", target) and "url" not in target.lower():
            out.append(f"fetch target {target}")
    return out


def test_app_has_sources_to_scan() -> None:
    names = {p.name for p in app_files()}
    assert {"main.ts", "App.tsx", "index.html"} <= names


SIDECAR = "electron/sidecar.ts"  # the one file that may name a URL: the sidecar's loopback port (D-83)


def sidecar_problems(text: str) -> list[str]:
    """In electron/sidecar.ts a URL must start with the HOST constant, which must be 127.0.0.1."""
    out = [p for p in problems(text) if not p.startswith(("URL http://${HOST}:", "fetch target"))]
    if 'const HOST = "127.0.0.1";' not in text:
        out.append("HOST is not the 127.0.0.1 constant")
    out += [f"fetch target {m.group(1)}" for m in FETCH.finditer(text) if not m.group(1).strip().startswith("`http://${HOST}:")]  # fmt: skip
    return out


def test_app_makes_no_network_reference() -> None:
    found = {
        str(p.relative_to(APP)): (sidecar_problems if p.relative_to(APP).as_posix() == SIDECAR else problems)(p.read_text())
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
    csp = re.search(r'Content-Security-Policy"\s+content="([^"]+)"', (APP / "index.html").read_text())
    assert csp
    assert re.search(r"connect-src 'self'(;|$)", csp.group(1))
    for p in [*(APP / "src").rglob("*"), APP / "index.html"]:
        if p.is_file():
            text = p.read_text().lower()
            for word in ("127.0.0.1", "localhost", "token", "authorization", "child_process", "ipcrenderer"):
                assert word not in text, f"{p.name} mentions {word}"
    fetchers = {p.relative_to(APP).as_posix() for p in app_files() if "fetch(" in p.read_text()}
    assert fetchers <= {SIDECAR, "src/App.tsx"}, fetchers  # App.tsx: ./fixture.json (relative, shiori://)


def test_sidecar_checker_catches_a_remote_host() -> None:
    assert sidecar_problems('const HOST = "127.0.0.1"; fetch(`http://example.com/${x}`)')
    assert sidecar_problems('const HOST = "0.0.0.0"; fetch(`http://${HOST}:${port}/x`)')
    assert not sidecar_problems('const HOST = "127.0.0.1"; fetch(`http://${HOST}:${port}/x`)')


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
