"""Does llama-server load this GGUF and answer one short request?

Dev-time only, never imported by core/, sidecar/ or app/. One server at a time, on a
free port bound to 127.0.0.1. Writes eval/reports/model_loadcheck.md (no document text;
the only prompt is the fixed one below).

    uv run python -m eval.model_loadcheck --link qwen3.5:4b gemma4:e4b  # Ollama blobs
    uv run python -m eval.model_loadcheck                  # every models/*.gguf
    uv run python -m eval.model_loadcheck models/x.gguf    # just these
"""

import argparse
import json
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from eval.model_feasibility import EXTRA_ARGS

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
REPORT = ROOT / "eval" / "reports" / "model_loadcheck.md"
OLLAMA = Path.home() / ".ollama" / "models"
CTX = 4096
LOAD_TIMEOUT = 600  # seconds to reach /health
REQUEST_TIMEOUT = 300
# Fixed test prompt (invented sentence). Expected answer contains "13".
PROMPT = (
    "入札書の受領期限は令和8年10月13日17時00分です。"
    "受領期限は何日ですか。日付だけ答えてください。"
)
EXPECTED = "13"


def manifest_model_digest(manifest: dict) -> str:
    """Digest of the layer holding the GGUF, e.g. 'sha256:abcd...'."""
    for layer in manifest.get("layers", []):
        if layer.get("mediaType") == "application/vnd.ollama.image.model":
            return layer["digest"]
    raise ValueError("manifest has no application/vnd.ollama.image.model layer")


def ollama_blob(model: str, root: Path = OLLAMA) -> Path:
    """'qwen3.5:4b' -> blob path under root/blobs. Read only."""
    name, _, tag = model.partition(":")
    manifest = (
        root / "manifests" / "registry.ollama.ai" / "library" / name / (tag or "latest")
    )
    digest = manifest_model_digest(json.loads(manifest.read_text()))
    return root / "blobs" / digest.replace(":", "-")


def is_gguf(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(4) == b"GGUF"


def link_ollama(model: str) -> Path:
    blob = ollama_blob(model)
    if not is_gguf(blob):
        raise ValueError(f"{blob.name} does not start with the GGUF magic bytes")
    link = MODELS / f"{model.replace(':', '-')}-ollama.gguf"
    if not link.is_symlink():
        link.symlink_to(blob)
    return link


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def tail(f, n: int = 10) -> str:
    f.seek(0)
    return "\n".join(f.read().decode(errors="replace").splitlines()[-n:])


def check(gguf: Path) -> dict:
    """Load one model, ask once, stop the server by pid. Never raises."""
    row = {"model": gguf.name, "gb": gguf.stat().st_size / 1e9, "loaded": False,
           "load_s": None, "tok_s": None, "note": ""}  # fmt: skip
    port = free_port()
    cmd = ["llama-server", "-m", str(gguf), "--host", "127.0.0.1", "--port", str(port),
           "-c", str(CTX), "-np", "1", "--reasoning", "off", "--no-webui",
           *next((a for k, a in EXTRA_ARGS.items() if k in gguf.name), [])]  # fmt: skip
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err)
        try:
            t0 = time.time()
            while True:
                if proc.poll() is not None:
                    row["note"] = "exited: " + tail(err).replace("\n", " / ")
                    return row
                if time.time() - t0 > LOAD_TIMEOUT:
                    row["note"] = f"not healthy after {LOAD_TIMEOUT}s"
                    return row
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/health", timeout=2
                    ) as r:
                        if r.status == 200:
                            break
                except OSError:
                    time.sleep(0.5)
            row["loaded"], row["load_s"] = True, time.time() - t0
            msgs = [{"role": "user", "content": PROMPT}]
            body = json.dumps(
                {"messages": msgs, "max_tokens": 64, "temperature": 0}
            ).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/chat/completions", body,
                {"Content-Type": "application/json"},
            )  # fmt: skip
            t1 = time.time()
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                out = json.load(r)
            text = (out["choices"][0]["message"].get("content") or "").strip()
            n = out.get("usage", {}).get("completion_tokens", 0)
            row["tok_s"] = out.get("timings", {}).get("predicted_per_second") or (
                n / (time.time() - t1) if n else None
            )
            row["note"] = ("reply ok" if text else "reply EMPTY") + (
                f", has {EXPECTED}" if EXPECTED in text else f", no {EXPECTED}"
            )
        except Exception as e:  # report it, keep going with the next model
            row["note"] = (
                f"{row['note']} request failed: {type(e).__name__}: {e}".strip()
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    if "unknown model architecture" in row["note"]:
        row["note"] = "unknown architecture: " + row["note"]
    return row


def home_to_tilde(text: str, home: Path | None = None) -> str:
    """Report text must not carry the home directory (it holds the user name)."""
    return text.replace(str(home or Path.home()), "~")


def table(rows: list[dict]) -> str:
    out = [
        "| model | size GB | loaded | load s | tok/s | notes |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        f = lambda v: "-" if v is None else f"{v:.1f}"  # noqa: E731
        note = home_to_tilde(r["note"]).replace("|", "/")
        out.append(f"| {r['model']} | {r['gb']:.1f} | {'yes' if r['loaded'] else 'no'} "
                   f"| {f(r['load_s'])} | {f(r['tok_s'])} | {note} |")  # fmt: skip
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ggufs", nargs="*", type=Path)
    ap.add_argument("--link", nargs="*", default=[], metavar="OLLAMA_MODEL")
    a = ap.parse_args()
    for m in a.link:
        print("linked", link_ollama(m))
    paths = a.ggufs or sorted(MODELS.glob("*.gguf"))
    version = subprocess.run(
        ["llama-server", "--version"], capture_output=True, text=True
    )
    ver = (version.stdout + version.stderr).strip()
    print(ver)
    rows = []
    for p in paths:
        print("checking", p.name, flush=True)
        rows.append(check(p))
    t = table(rows)
    print(t)
    REPORT.write_text(
        "# Model load check\n\n"
        f"`uv run python -m eval.model_loadcheck`, context {CTX}, one server at a "
        "time, `--reasoning off`. Fixed test prompt: one invented Japanese sentence "
        "asking for the "
        f"day of a deadline (expected answer contains {EXPECTED}).\n\n"
        f"llama-server version:\n\n```\n{home_to_tilde(ver)}\n```\n\n{t}\n"
    )


if __name__ == "__main__":
    main()
