"""API keys from the environment or .env, and redaction. A key is never printed, logged,
cached, exported or written to a report: every string that may reach a file goes through
`redact`."""

import os
import re
from pathlib import Path

ENV_NAMES = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY"}


def _dotenv(path: Path = Path(".env")) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip().upper()] = v.strip().strip("\"'")
    return out


def get_key(provider: str) -> str | None:
    name = ENV_NAMES[provider]
    return os.environ.get(name) or _dotenv().get(name) or None


def _secrets() -> list[str]:
    env = _dotenv()
    vals = [os.environ.get(n) or env.get(n) for n in ENV_NAMES.values()]
    return [v for v in vals if v and len(v) >= 8]


def redact(text: str) -> str:
    for s in _secrets():
        text = text.replace(s, "<key>")
    # anything key-shaped that a server might echo back
    return re.sub(r"(gsk_|AIza)[A-Za-z0-9_\-]{10,}", "<key>", text)
