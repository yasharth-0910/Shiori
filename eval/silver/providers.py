# ruff: noqa: E501
"""Labeler providers: gemini, groq (plain HTTP, standard library) and local.

All three take a system prompt, a user prompt and a JSON schema (None: plain JSON mode,
the shape is in the prompt) and return the model's JSON text, token counts and whether
the output cap cut the answer off. A repair request (D-49) adds the previous answer and
a message listing its problems. Errors become `ProviderError` with a `kind` the pipeline
acts on. Keys go only into request headers; nothing here prints or stores them.
"""

import json
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from eval.silver.config import LOCAL_CTX, PROVIDERS
from eval.silver.keys import redact

# kind: rate_limit (wait and retry), daily_quota (stop for the day), auth, bad_request,
# server, network
Kind = str


class ProviderError(Exception):
    def __init__(
        self,
        kind: Kind,
        message: str = "",
        retry_after: float | None = None,
        code: int | None = None,
    ):
        super().__init__(f"{kind}: {redact(message)[:200]}")
        self.kind = kind
        self.retry_after = retry_after
        self.code = code

    @property
    def outcome(self) -> str:
        """The ledger's name for this failure: http_503, http_429, network, ..."""
        return f"http_{self.code}" if self.code else self.kind


@dataclass
class Completion:
    text: str
    tokens_in: int
    tokens_out: int
    truncated: bool = (
        False  # stopped by the output cap (finish reason length / MAX_TOKENS)
    )
    # llama-server's timings (cache_n, prompt_n, prompt_ms, predicted_n, predicted_ms)
    timings: dict | None = None


# (previous answer, message with its problems) for a repair request
Repair = tuple[str, str] | None


class Provider:
    name: str
    model: str
    local: bool = False

    def complete(
        self,
        system: str,
        user: str,
        schema: dict | None,
        max_out: int,
        repair: Repair = None,
    ) -> Completion:
        raise NotImplementedError


def chat_messages(system: str, user: str, repair: Repair) -> list[dict]:
    """OpenAI-style messages, with the repair turn when there is one."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if repair:
        msgs += [{"role": "assistant", "content": repair[0]},
                 {"role": "user", "content": repair[1]}]  # fmt: skip
    return msgs


def json_format(schema: dict | None) -> dict:
    if schema is None:
        return {"type": "json_object"}
    return {"type": "json_schema",
            "json_schema": {"name": "labels", "strict": True, "schema": schema}}  # fmt: skip


Post = Callable[[str, dict, dict], dict]


def http_post(url: str, headers: dict, body: dict, timeout: float = 300) -> dict:
    req = urllib.request.Request(
        url,
        json.dumps(body).encode(),
        {"Content-Type": "application/json", "User-Agent": "shiori-dev/0.1", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        retry = e.headers.get("retry-after")
        raise _classify(e.code, raw, float(retry) if retry else None) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderError("network", type(e).__name__) from None


def _classify(code: int, raw: str, retry_after: float | None) -> ProviderError:
    low = raw.lower()
    if code == 429:
        daily = any(k in low for k in ("perday", "per day", "tpd", "rpd"))
        return ProviderError("daily_quota" if daily else "rate_limit", f"HTTP {code}", retry_after, code)  # fmt: skip
    if code in (401, 403):
        return ProviderError("auth", f"HTTP {code}", code=code)
    if code == 413:
        return ProviderError("bad_request", "HTTP 413 request too large", code=code)
    if 400 <= code < 500:
        return ProviderError(
            "bad_request", f"HTTP {code} {_err_status(raw)}", code=code
        )
    return ProviderError("server", f"HTTP {code}", retry_after, code)


def _err_status(raw: str) -> str:
    try:
        e = json.loads(raw).get("error", {})
        status = str(e.get("status") or e.get("code") or e.get("type") or "")
        # the message says why (a schema with too many states, ...); ProviderError
        # redacts it and keeps 200 characters
        return f"{status}: {e['message']}" if e.get("message") else status
    except (ValueError, AttributeError):
        return ""


def openai_completion(r: dict) -> Completion:
    """Groq and llama-server answer in the OpenAI chat format."""
    ch = r["choices"][0]
    u = r.get("usage", {})
    return Completion(
        ch["message"].get("content") or "",
        u.get("prompt_tokens", 0),
        u.get("completion_tokens", 0),
        ch.get("finish_reason") == "length",
        r.get("timings"),
    )


class Gemini(Provider):
    name = "gemini"

    def __init__(self, key: str, model: str | None = None, post: Post = http_post):
        self.model = model or PROVIDERS["gemini"].model
        self._key, self._post = key, post

    def complete(
        self,
        system: str,
        user: str,
        schema: dict | None,
        max_out: int,
        repair: Repair = None,
    ) -> Completion:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        contents = [{"role": "user", "parts": [{"text": user}]}]
        if repair:
            contents += [{"role": "model", "parts": [{"text": repair[0]}]},
                         {"role": "user", "parts": [{"text": repair[1]}]}]  # fmt: skip
        gen: dict = {
            "temperature": 0,
            "maxOutputTokens": max_out,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": "low"},
        }
        if schema is not None:
            gen["responseJsonSchema"] = schema
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": gen,
        }
        r = self._post(url, {"x-goog-api-key": self._key}, body)
        cands = r.get("candidates") or []
        if not cands:
            raise ProviderError(
                "bad_request", f"no candidate: {r.get('promptFeedback')}"
            )
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        u = r.get("usageMetadata", {})
        out = u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
        cut = cands[0].get("finishReason") == "MAX_TOKENS"
        return Completion(text, u.get("promptTokenCount", 0), out, cut)


class Groq(Provider):
    name = "groq"

    def __init__(self, key: str, model: str | None = None, post: Post = http_post):
        self.model = model or PROVIDERS["groq"].model
        self._key, self._post = key, post

    def complete(
        self,
        system: str,
        user: str,
        schema: dict | None,
        max_out: int,
        repair: Repair = None,
    ) -> Completion:
        body = {
            "model": self.model,
            "messages": chat_messages(system, user, repair),
            "temperature": 0,
            "max_completion_tokens": max_out,
            "reasoning_effort": "low",
            "response_format": json_format(schema),
        }
        r = self._post(
            "https://api.groq.com/openai/v1/chat/completions",
            {"Authorization": f"Bearer {self._key}"},
            body,
        )
        return openai_completion(r)


class Local(Provider):
    """llama-server on 127.0.0.1 with JSON-schema output; nothing leaves the machine.
    Launch settings come from eval/model_feasibility.py (D-34)."""

    name = "local"
    local = True
    PORT = 8792
    TIMEOUT: float = 3600  # seconds per request; eval/bakeoff.py sets a lower one

    def __init__(self, gguf: str) -> None:
        self.model = Path(gguf).stem
        self._gguf = gguf
        self._proc: subprocess.Popen | None = None

    def _start(self) -> None:
        from eval.model_feasibility import EXTRA_ARGS, MODELS

        path = MODELS / self._gguf
        log = open(MODELS / f"{path.stem}.silver.log", "w")
        cmd = [
            "llama-server", "-m", str(path), "--port", str(self.PORT),
            "--host", "127.0.0.1", "-c", str(LOCAL_CTX), "-np", "1",
            "--reasoning", "off", "--no-webui", "-ngl", "99",
            *next((a for k, a in EXTRA_ARGS.items() if k in path.name), []),
        ]  # fmt: skip
        self._proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        t0 = time.time()
        while time.time() - t0 < 600:
            if self._proc.poll() is not None:
                raise ProviderError("server", "llama-server exited")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.PORT}/health", timeout=2
                ) as r:
                    if r.status == 200:
                        return
            except OSError:
                time.sleep(0.5)
        raise ProviderError("server", "llama-server not ready")

    def complete(
        self,
        system: str,
        user: str,
        schema: dict | None,
        max_out: int,
        repair: Repair = None,
    ) -> Completion:
        if self._proc is None:
            self._start()
        body = {
            "messages": chat_messages(system, user, repair),
            "temperature": 0,
            "max_tokens": max_out,
            # sv3-l1 (D-53): reuse the processed document across one document's calls
            "cache_prompt": True,
            "response_format": json_format(schema),
        }
        # a 9B model writes about 6 tokens/s on this Mac: 8,192 output tokens take ~22 min
        r = http_post(
            f"http://127.0.0.1:{self.PORT}/v1/chat/completions",
            {},
            body,
            timeout=self.TIMEOUT,
        )
        return openai_completion(r)

    def close(self) -> None:
        if self._proc:
            self._proc.terminate()
            self._proc.wait(timeout=30)
            self._proc = None
