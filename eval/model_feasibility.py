# ruff: noqa: E501  (long hashed paths, Japanese prompt text and table rows)
"""Model feasibility bench: can a candidate GGUF run here, and how fast? (D-34)

Dev-time only. Starts one llama-server per model, sends one fixed "find the submission
deadline" prompt per document with JSON-schema constrained output, and records load
time, prompt and generation speed, peak memory and whether the JSON was valid.
Correctness is not scored; raw answers go to models/feasibility_raw.jsonl (gitignored)
so they can be read by eye for obvious nonsense.

    uv run python -m eval.model_feasibility run [--cpu] [model_stem ...]
    uv run python -m eval.model_feasibility mem [model_stem ...]
    uv run python -m eval.model_feasibility report

Only talks to 127.0.0.1. Document text never leaves the machine.
"""

import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from shiori_core.ingest import load_document

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
RAW = MODELS / "feasibility_raw.jsonl"
MEM = MODELS / "feasibility_mem.jsonl"
REPORT = ROOT / "eval" / "reports" / "model_feasibility.md"
PORT = 8791
CTX = 16384

# doc id -> (role, path). All three have an open licence (documents.jsonl).
DOCS = {
    "notice": "data/raw/hokkaido/737f48e78112b5e581fc18785d88a666403f5b4f1f77ad11775453975ab9ff69.pdf",
    "spec": "data/raw/wakayama_pref/12f50d0602ce35d34a27055226991593730b4b9ebb11c7ad721ea8dd9572cad2.pdf",
    "wto_notice": "data/raw/p-portal/70e1f40de5ceb2ca3cefe09a13f9c4791c511cea34784402c12574844a208a8c.html",
    # 27-page IT spec cut to its first LONG_CHARS characters: a speed test on a long prompt
    "long_spec": "data/raw/digital/e74184761fa329e4c4ec9937fe22583c61ff626be65b582571cb2630b6170f16.pdf",
}
LONG_CHARS = 9000

SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "deadline_text": {"type": "string"},
        "sentence_ids": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
    },
    "required": ["found", "deadline_text", "sentence_ids"],
    "additionalProperties": False,
}
SYSTEM = "You read Japanese public tender documents. Reply with JSON only."
QUESTION = (
    "What is the deadline for submitting bids or applications (入札書・申込書等の提出期限)? "
    "Copy the date and time exactly as written in the document and list the IDs of the "
    "sentences it comes from. If the document states no such deadline, set found to false, "
    "deadline_text to an empty string and sentence_ids to an empty list."
)


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self.skip += tag in ("script", "style")
        if tag in ("br", "tr", "p", "div", "li", "h1", "h2", "h3", "dt", "dd"):
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        self.skip -= tag in ("script", "style")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(data)


def html_sentences(path: Path) -> list[tuple[str, str]]:
    """p-portal notice body as (id, text). The page is hard-wrapped at about 20
    characters, so wrapped lines are joined; a new item starts at `(1)`, `１ ` etc.
    The English Summary is left out (its wrapping breaks words).
    ponytail: stand-in for a real HTML ingest step; core has none yet."""
    p = _Text()
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    lines = [re.sub(r"\s+", " ", x).strip() for x in "".join(p.out).split("\n")]
    lines = [x for x in lines if x]
    start = next(i for i, x in enumerate(lines) if x == "公告内容")
    end = next(i for i, x in enumerate(lines) if x.endswith("Summary"))
    items: list[str] = []
    for line in lines[start + 1 : end]:
        new_item = re.match(r"(\(\d+\)|[０-９]+ |◎|○)", line) or not items
        if new_item or items[-1].endswith("。"):
            items.append(line)
        else:
            items[-1] += line
    return [(f"h_s{i}", t) for i, t in enumerate(items, 1)]


def doc_sentences(role: str) -> list[tuple[str, str]]:
    path = ROOT / DOCS[role]
    if path.suffix == ".html":
        return html_sentences(path)
    out, n = [], 0
    for s in load_document(path).sentences:
        n += len(s.text_orig)
        if role == "long_spec" and n > LONG_CHARS:
            break
        out.append((s.id, s.text_orig))
    return out


def build_messages(sentences: list[tuple[str, str]]) -> list[dict]:
    body = "\n".join(f"[{i}] {t}" for i, t in sentences)
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"{body}\n\n{QUESTION}"},
    ]


def _post(path: str, payload: dict, timeout: int = 1800) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}",
        json.dumps(payload).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _gpu_inuse_mb() -> float:
    """GPU-visible system memory in use, MB (IOAccelerator). On Apple Silicon this
    includes Metal buffers, which a process's RSS under-reports (Qwen3.5-9B: 6.2 GB
    RSS vs 7.1 GB here, for a 5.7 GB file)."""
    out = subprocess.run(
        ["ioreg", "-r", "-d", "1", "-w0", "-c", "IOAccelerator"],
        capture_output=True,
        text=True,
    ).stdout
    m = re.search(r'"In use system memory"=(\d+)', out)
    return int(m.group(1)) / 1e6 if m else 0.0


def _rss_mb(pid: int) -> float:
    out = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True
    ).stdout
    return int(out.strip() or 0) / 1024


# LFM2.5-8B-A1B ignores `--reasoning off` (its template always thinks, and the trace
# used all 300 tokens, leaving the answer empty); a zero thinking budget works.
EXTRA_ARGS = {"LFM2.5-8B": ["--reasoning-budget", "0"]}


class Server:
    def __init__(self, gguf: Path, cpu: bool) -> None:
        log = open(MODELS / f"{gguf.stem}.{'cpu' if cpu else 'gpu'}.log", "w")
        cmd = [
            "llama-server", "-m", str(gguf), "--port", str(PORT), "--host", "127.0.0.1",
            "-c", str(CTX), "-np", "1", "--reasoning", "off", "--no-webui",
            "-ngl", "0" if cpu else "99",
            *next((a for k, a in EXTRA_ARGS.items() if k in gguf.name), []),
        ]  # fmt: skip
        self.proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        self.gpu_base = _gpu_inuse_mb()  # before launch, so the model is not in it
        self.peak = [0.0, 0.0]  # [RSS MB, GPU in-use delta MB]
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.is_set():
            gpu = _gpu_inuse_mb() - self.gpu_base
            rss = _rss_mb(self.proc.pid)
            self.peak = [max(self.peak[0], rss), max(self.peak[1], gpu)]
            time.sleep(0.5)

    def wait_ready(self) -> float:
        t0 = time.time()
        self._t.start()
        while time.time() - t0 < 600:
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server exited (see models/*.log)")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/health", timeout=2
                ) as r:
                    if r.status == 200:
                        return time.time() - t0
            except OSError:
                time.sleep(0.3)
        raise TimeoutError("llama-server not ready")

    def close(self) -> None:
        self._stop.set()
        self.proc.terminate()
        self.proc.wait(timeout=30)


def ask(sentences: list[tuple[str, str]], max_tokens: int = 300) -> dict:
    """Chat endpoint with a JSON schema. Falls back to /completion with the chat
    template applied by hand when llama-server's chat parser rejects the output
    (Sarashina2.2: its GGUF emits a literal </s>). The reply has the chat shape plus
    `endpoint` so the report can say which route was used."""
    messages = build_messages(sentences)
    try:
        r = _post(
            "/v1/chat/completions",
            {
                "messages": messages,
                "temperature": 0,
                "max_tokens": max_tokens,
                "cache_prompt": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "deadline",
                        "strict": True,
                        "schema": SCHEMA,
                    },
                },
            },
        )
        r["endpoint"] = "chat"
        return r
    except urllib.error.HTTPError as e:
        if e.code != 500:
            raise
    prompt = _post("/apply-template", {"messages": messages})["prompt"]
    c = _post(
        "/completion",
        {
            "prompt": prompt,
            "temperature": 0,
            "n_predict": max_tokens,
            "cache_prompt": False,
            "json_schema": SCHEMA,
        },
    )
    return {
        "choices": [
            {
                "message": {"content": c["content"]},
                "finish_reason": "stop" if c["stop_type"] != "limit" else "length",
            }
        ],
        "timings": c["timings"],
        "endpoint": "completion",
    }


def check_json(text: str, known_ids: set[str]) -> tuple[bool, bool]:
    """(valid against the schema, every cited id exists in the document)."""
    try:
        d = json.loads(text)
        ok = (
            isinstance(d["found"], bool)
            and isinstance(d["deadline_text"], str)
            and isinstance(d["sentence_ids"], list)
        )
        return ok, ok and all(i in known_ids for i in d["sentence_ids"])
    except (ValueError, KeyError, TypeError):
        return False, False


def run(stems: list[str], cpu: bool) -> None:
    docs = {role: doc_sentences(role) for role in DOCS}
    for gguf in sorted(MODELS.glob("*.gguf")):
        if stems and not any(s in gguf.name for s in stems):
            continue
        srv = Server(gguf, cpu)
        try:
            load_s = srv.wait_ready()
            t0 = time.time()
            ask(
                [("x", "テスト")], max_tokens=8
            )  # first request pays one-off setup costs
            warm_s = time.time() - t0
            for role, sents in docs.items():
                if cpu and role == "long_spec" and gguf.stat().st_size > 3e9:
                    continue  # ponytail: ~15 min per big model on CPU; skipped
                t0 = time.time()
                try:
                    r = ask(sents)
                except urllib.error.HTTPError as e:
                    # e.g. prompt longer than the model's context (Sarashina: 8192)
                    err = {
                        "model": gguf.name,
                        "mode": "cpu" if cpu else "gpu",
                        "doc": role,
                        "error": f"HTTP {e.code}",
                    }
                    with RAW.open("a") as f:
                        f.write(json.dumps(err) + "\n")
                    print(role, gguf.name, err["error"], flush=True)
                    continue
                wall = time.time() - t0
                msg = r["choices"][0]["message"]["content"] or ""
                valid, ids_ok = check_json(msg, {i for i, _ in sents})
                tm = r["timings"]
                row = {
                    "model": gguf.name, "mode": "cpu" if cpu else "gpu", "doc": role,
                    "size_gb": round(gguf.stat().st_size / 1e9, 2),
                    "load_s": round(load_s, 1), "warmup_s": round(warm_s, 1),
                    "prompt_tokens": tm["prompt_n"], "gen_tokens": tm["predicted_n"],
                    "prompt_tps": round(tm["prompt_per_second"], 1),
                    "gen_tps": round(tm["predicted_per_second"], 1),
                    "wall_s": round(wall, 1), "finish": r["choices"][0]["finish_reason"],
                    "endpoint": r["endpoint"], "json_valid": valid, "ids_exist": ids_ok, "answer": msg,
                    "peak_rss_mb": round(srv.peak[0]), "peak_gpu_mb": round(srv.peak[1]),
                }  # fmt: skip
                with RAW.open("a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(
                    role,
                    gguf.name,
                    row["mode"],
                    row["prompt_tps"],
                    row["gen_tps"],
                    valid,
                    flush=True,
                )
        finally:
            srv.close()


def mem(stems: list[str]) -> None:
    """One short GPU request per model, to record memory (weights, KV for CTX, buffers)."""
    sents = doc_sentences("spec")
    for gguf in sorted(MODELS.glob("*.gguf")):
        if stems and not any(s in gguf.name for s in stems):
            continue
        srv = Server(gguf, cpu=False)
        try:
            srv.wait_ready()
            ask(sents, max_tokens=8)
            row = {
                "model": gguf.name,
                "size_gb": round(gguf.stat().st_size / 1e9, 2),
                "gpu_mb": round(srv.peak[1]),
                "rss_gpu_mode_mb": round(srv.peak[0]),
            }
            with MEM.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(row, flush=True)
        finally:
            srv.close()


def _name(model: str) -> str:
    return model.removesuffix(".gguf")


def report() -> None:
    rows = [json.loads(x) for x in RAW.read_text().splitlines()]
    out = [
        "# Model feasibility (D-34)",
        "",
        "Q4_K_M GGUFs on a MacBook Air M4, 24 GB. One fixed deadline prompt per document, "
        "JSON-schema constrained output, thinking off, temperature 0, context 16384. "
        "Not an accuracy test. `ids exist` only checks that cited sentence IDs are in the document.",
        "",
        "## Speed",
        "",
        "| model | mode | file GB | load s | doc | prompt tok | prompt tok/s | gen tok/s | wall s | JSON valid | ids exist | route |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            out.append(
                f"| {_name(r['model'])} | {r['mode']} | | | {r['doc']} | | | | | {r['error']} | | |"
            )
            continue
        out.append(
            f"| {_name(r['model'])} | {r['mode']} | {r['size_gb']} | {r['load_s']} "
            f"| {r['doc']} | {r['prompt_tokens']} | {r['prompt_tps']} | {r['gen_tps']} "
            f"| {r['wall_s']} | {r['json_valid']} | {r['ids_exist']} | {r.get('endpoint', 'chat')} |"
        )
    if MEM.exists():
        cpu_rss: dict[str, int] = {}
        for r in rows:
            if r["mode"] == "cpu" and "error" not in r:
                cpu_rss[r["model"]] = max(cpu_rss.get(r["model"], 0), r["peak_rss_mb"])
        out += [
            "",
            "## Memory",
            "",
            "GPU column: growth of the GPU's in-use system memory (ioreg IOAccelerator) "
            "while the server runs, which includes Metal buffers. CPU column: peak "
            "resident set size with `-ngl 0`, where all weights live in the process. "
            "Both include the KV cache for a 16384-token context, allocated up front.",
            "",
            "| model | file GB | GPU mode MB | GPU-mode RSS MB (under-reports) | CPU mode peak RSS MB |",
            "|---|---|---|---|---|",
        ]
        for line in MEM.read_text().splitlines():
            m = json.loads(line)
            out.append(
                f"| {_name(m['model'])} | {m['size_gb']} | {m['gpu_mb']} "
                f"| {m['rss_gpu_mode_mb']} | {cpu_rss.get(m['model'], 'n/a')} |"
            )
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(out) + "\n")
    print("wrote", REPORT)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["report"]:
        report()
    elif args[:1] == ["mem"]:
        mem(args[1:])
    else:
        run([a for a in args[1:] if a != "--cpu"], "--cpu" in args)
