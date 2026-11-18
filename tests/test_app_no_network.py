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


def test_app_makes_no_network_reference() -> None:
    found = {str(p.relative_to(APP)): problems(p.read_text()) for p in app_files()}
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


def test_window_flags() -> None:
    main = (APP / "electron" / "main.ts").read_text()
    assert "contextIsolation: true" in main
    assert "nodeIntegration: false" in main


def test_detector_catches_bad_code() -> None:
    assert problems('fetch("https://example.com/x")')
    assert problems("new WebSocket(u)")
    assert problems('import https from "node:https"')
    assert problems('fetch(remote + "/a")')
    assert not problems('fetch("./fixture.json")')
