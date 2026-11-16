# ruff: noqa: E501
"""Usage ledger and rate limiter. The ledger (data/cache/labeling/usage.jsonl) holds one
line per request of any kind: labeling calls and their retries (`label`), diagnostic
probes (`probe`) and key checks (`keys`), with time, provider, model, tokens and the
outcome (`ok`, `http_503`, `http_429`, `network`, ...). No document text, no ids.

Failed requests count against the daily request budget: Google does not say whether a
503 counts against its cap, so the guard assumes it does. The limiter waits for the
per-minute window, and raises `DailyCap` when the day's request or token budget is
spent; the next run resumes from the cache.
"""

import json
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from eval.silver import config
from eval.silver.config import ProviderCfg


class DailyCap(Exception):
    pass


def effective_cfg(cfg: ProviderCfg) -> ProviderCfg:
    """Published defaults, overridden by data/cache/labeling/limits.json
    ({"gemini": {"rpm": 15, "tpm": 1000000, "rpd": 1500}}) once you have read your own."""
    p = config.CACHE / "limits.json"
    if p.exists():
        over = json.loads(p.read_text()).get(cfg.name, {})
        cfg = replace(cfg, published=True, **over)
    return cfg


def _day(ts: float, tz: str = "UTC") -> str:
    """The provider's quota day of a timestamp (ProviderCfg.quota_tz, D-57)."""
    return datetime.fromtimestamp(ts, UTC).astimezone(ZoneInfo(tz)).date().isoformat()


class Ledger:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config.CACHE / "usage.jsonl"

    def append(self, **entry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def entries(self, provider: str) -> list[dict]:
        if not self.path.exists():
            return []
        rows = [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()]
        return [r for r in rows if r["provider"] == provider]

    def today(self, provider: str, now: float, tz: str = "UTC") -> dict:
        """requests = every attempt (successes and failures) on the provider's current
        quota day (`tz`, D-57); `outcomes` splits them."""
        rows = [r for r in self.entries(provider) if _day(r["ts"], tz) == _day(now, tz)]
        reqs = [r for r in rows if r.get("kind") != "daily_block"]
        outcomes: dict[str, int] = {}
        kinds: dict[str, int] = {}
        for r in reqs:
            o = outcome_of(r)
            outcomes[o] = outcomes.get(o, 0) + 1
            kinds[r.get("kind", "label")] = kinds.get(r.get("kind", "label"), 0) + 1
        return {
            "requests": len(reqs),
            "ok": outcomes.get("ok", 0),
            "failed": len(reqs) - outcomes.get("ok", 0),
            "outcomes": outcomes,
            "kinds": kinds,
            "tokens_in": sum(r.get("tokens_in", 0) for r in reqs),
            "tokens_out": sum(r.get("tokens_out", 0) for r in reqs),
            "blocked": any(r.get("kind") == "daily_block" for r in rows),
        }


def outcome_of(r: dict) -> str:
    """Entries before sv2 have only `ok`; their failures are `failed_unrecorded`."""
    if "outcome" in r:
        return r["outcome"]
    return "ok" if r.get("ok") else "failed_unrecorded"


class Limiter:
    def __init__(
        self,
        cfg: ProviderCfg,
        ledger: Ledger,
        now: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cfg, self.ledger, self.now, self.sleep = (
            effective_cfg(cfg),
            ledger,
            now,
            sleep,
        )

    def _window(self) -> list[dict]:
        t = self.now()
        return [r for r in self.ledger.entries(self.cfg.name)
                if t - r["ts"] < 60 and r.get("kind") != "daily_block"]  # fmt: skip

    def before(self, est_tokens: int) -> None:
        c = self.cfg
        if est_tokens > c.tpm:
            raise ValueError(
                f"request of ~{est_tokens} tokens can never fit {c.tpm}/min"
            )
        u = self.ledger.today(c.name, self.now(), c.quota_tz)
        used = u["tokens_in"] + u["tokens_out"]
        if (
            u["blocked"]
            or u["requests"] >= c.rpd
            or (c.tpd and used + est_tokens > c.tpd)
        ):
            raise DailyCap(c.name)
        while True:
            win = self._window()
            toks = sum(r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in win)
            if len(win) < c.rpm and toks + est_tokens <= c.tpm:
                return
            oldest = min(r["ts"] for r in win)
            self.sleep(max(0.5, 60 - (self.now() - oldest) + 0.5))

    def record(
        self, provider_model: str, tokens_in: int, tokens_out: int, outcome: str,
        kind: str = "label",
    ) -> None:  # fmt: skip
        self.ledger.append(ts=self.now(), provider=self.cfg.name, model=provider_model,
                           kind=kind, outcome=outcome, ok=outcome == "ok",
                           tokens_in=tokens_in, tokens_out=tokens_out)  # fmt: skip

    def block_today(self) -> None:
        self.ledger.append(ts=self.now(), provider=self.cfg.name, kind="daily_block")
