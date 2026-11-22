"""A page in a real Electron session cannot reach an outside host (D-100).

Runs the app's own netfilter.js (built by `npm run build` in app/) inside
electron, no window shown. A local server on 127.0.0.1 stands in for an outside
host; it must see no request. Skipped when electron or the build is missing.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"
ELECTRON = APP / "node_modules" / ".bin" / "electron"
BUILT = APP / "dist-electron" / "netfilter.js"


@pytest.mark.skipif(
    not (ELECTRON.exists() and BUILT.exists()),
    reason="needs app/node_modules (electron) and `npm run build` in app/",
)
def test_renderer_fetch_to_an_outside_host_is_cancelled() -> None:
    r = subprocess.run(
        [str(ELECTRON), str(Path(__file__).parent / "electron_filter" / "main.cjs")],
        env={**os.environ, "APP_DIR": str(APP)},
        capture_output=True,
        text=True,
        timeout=90,
    )
    line = next((x for x in r.stdout.splitlines() if x.startswith("RESULT ")), None)
    assert line, (r.stdout[-500:], r.stderr[-500:])
    out = json.loads(line[len("RESULT ") :])
    assert out["outside"] == "cancelled"
    # the renderer never needs loopback; main talks to the sidecar
    assert out["loopback"] == "cancelled"
    assert out["hits"] == 0, "the server stand-in saw a request"
    assert out["blocked"] == 2  # counted, not listed
