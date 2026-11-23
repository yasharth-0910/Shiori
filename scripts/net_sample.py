# ruff: noqa: E501
"""Dev-only network sample: one extraction of a public document with the app running, sockets listed every 2 s.

Starts the app like the highlight check does (SHIORI_PICK, SHIORI_SHOT with SHIORI_SHOT_OPEN, so it quits when the
extraction and the English queue are done), then every 2 seconds runs lsof on the Electron process tree (Electron,
the sidecar, llama-server) and keeps the distinct remote endpoints. Writes a short result into docs/privacy.md.
It is a sample, not a packet capture: a connection shorter than 2 s can be missed. It logs counts and addresses only,
never document text. Run: uv run python scripts/net_sample.py
"""

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = (
    ROOT
    / "data/raw/_samples/wakayama_pref/2f2f5bd332965253eed43d739e56e7859b149afa0d157ea3c89dfdd7d0d8b419.pdf"
)
MODEL = ROOT / "models" / "Qwen3.5-9B-Q4_K_M.gguf"
PRIVACY = ROOT / "docs" / "privacy.md"
START, END = "<!-- net_sample:start -->", "<!-- net_sample:end -->"
LOOP = ("127.0.0.1", "[::1]", "localhost")


def tree(root: int) -> list[int]:
    out = subprocess.run(
        ["ps", "-axo", "pid=,ppid="], capture_output=True, text=True
    ).stdout
    kids: dict[int, list[int]] = {}
    for line in out.splitlines():
        p, pp = (int(x) for x in line.split())
        kids.setdefault(pp, []).append(p)
    found, todo = [], [root]
    while todo:
        p = todo.pop()
        found.append(p)
        todo += kids.get(p, [])
    return found


def sockets(pids: list[int]) -> list[tuple[str, str]]:
    """(protocol, name) for every internet socket of the pids. lsof -F: P = protocol, n = name."""
    out = subprocess.run(
        ["lsof", "-nP", "-i", "-a", "-p", ",".join(map(str, pids)), "-FPn"],
        capture_output=True,
        text=True,
    ).stdout
    res, proto = [], ""
    for line in out.splitlines():
        if line.startswith("P"):
            proto = line[1:]
        elif line.startswith("n"):
            res.append((proto, line[1:]))
    return res


def host_of(addr: str) -> str:
    return addr.rsplit(":", 1)[0]


def main() -> int:
    llama = shutil.which("llama-server")
    if not llama or not MODEL.exists() or not DOC.exists():
        print("need llama-server on PATH,", MODEL, "and", DOC)
        return 2
    app = ROOT / "app"
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "SHIORI_PICK": str(DOC), "SHIORI_LLAMA_SERVER": llama, "SHIORI_MODEL": str(MODEL),
               "SHIORI_SHOT": str(Path(tmp) / "s.png"), "SHIORI_CHIP": "999", "SHIORI_SHOT_OPEN": "Title"}  # fmt: skip
        p = subprocess.Popen([str(app / "node_modules/.bin/electron"), "."], cwd=app, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)  # fmt: skip
        blocked: list[str] = []

        def read() -> None:  # keep only the quit line; other output may carry titles
            for line in p.stdout or []:
                if "renderer requests blocked" in line:
                    blocked.append(line.strip())

        threading.Thread(target=read, daemon=True).start()
        samples, remote_loop, remote_out, listeners = 0, set(), set(), set()
        t_end = time.time() + 1800
        while p.poll() is None and time.time() < t_end:
            pids = tree(p.pid)
            for proto, name in sockets(pids):
                if "->" in name:
                    remote = name.split("->", 1)[1].split(" ")[0]
                    (remote_loop if host_of(remote) in LOOP else remote_out).add(
                        f"{proto} {remote}"
                    )
                else:
                    listeners.add(f"{proto} {host_of(name)}")
            samples += 1
            time.sleep(2)
        if p.poll() is None:
            p.kill()
            print("timed out")
            return 1
    line = blocked[-1] if blocked else "renderer requests blocked: (line not seen)"
    out_txt = ", ".join(sorted(remote_out)) if remote_out else "none"
    non_loop = sorted(x for x in listeners if host_of(x.split(" ", 1)[1]) not in LOOP)
    listen_txt = ", ".join(non_loop) if non_loop else "none"
    sec = f"""{START}
Network sample ({date.today().isoformat()}, `scripts/net_sample.py`): one full extraction of the open Wakayama notice 2f2f5bd3
(Qwen3.5-9B, English queue included) on the dev Mac. Every 2 seconds `lsof` listed the internet sockets of the Electron
process tree (Electron, the sidecar, llama-server). {samples} samples. Distinct remote endpoints that were not loopback:
{out_txt}. Distinct loopback endpoints seen: {len(remote_loop)}. Sockets listening on a non-loopback address: {listen_txt}.
The app's own quit line was "{line}". Sampled, not a packet capture: a connection shorter than 2 seconds can be missed,
and it does not cover other processes on the machine.
{END}"""
    text = PRIVACY.read_text()
    if START in text:
        text = re.sub(
            re.escape(START) + r".*?" + re.escape(END), lambda _: sec, text, flags=re.S
        )
    else:
        text = text.replace(
            "## Checklist", "## Measured so far\n\n" + sec + "\n\n## Checklist", 1
        )
    PRIVACY.write_text(text)
    print(f"samples {samples}")
    print("non-loopback remote endpoints:", out_txt)
    print("loopback remote endpoints:", len(remote_loop))
    print("non-loopback listeners:", listen_txt)
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
