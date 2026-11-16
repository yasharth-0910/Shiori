# ruff: noqa: E501
"""`daemon --gold --wave N`: a loop around run/resolve/export for one gold wave (D-62).

It is not a second pipeline. It asks `Pipeline.label` for the missing parts (every
answered part is cached, so a restart repeats nothing), resolves with `run.resolve_docs`
(with the gold export policy as its `mark` hook) and exports with `review.export`.
Gold documents are open-license: Gemini and the local model label them, Groq is never
used, and no document that is not `open` reaches a cloud provider.

Nothing is sent without --yes and --max-calls. Without --yes the command prints the plan
and makes no request at all (cloud or local). Imports are never done here."""

import hashlib
import json
import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from shiori_core.fields import FIELD_IDS

from collector.manifest import ManifestRow
from eval.silver import config, review, run
from eval.silver.config import PROVIDERS, SLOTS, TIER1
from eval.silver.limiter import DailyCap, Ledger, _day, effective_cfg
from eval.silver.pipeline import (
    OutOfCalls,
    Pipeline,
    _default_factory,
    assign,
    decisions_path,
    raw_state,
    read_resolved,
)
from eval.silver.prompt import applicable_fields
from eval.silver.providers import Provider, ProviderError

GOLD_SET = Path("data/eval/gold_set.json")
GOLD_SPOT_SEED = 20261016  # the gold set's own seed (D-61)
GOLD_SPOT_PERCENT = 20
MAX_FAILURES = 3  # consecutive failures from one provider
POLL = 60  # seconds between checks while sleeping or paused
RESET_MARGIN = 5  # seconds after a provider's midnight before asking again

# The tier 1 concepts of D-61/D-62 and the field ids of schema 1.0.0 (docs/field_schema.md).
CONCEPTS = {
    "submission deadline(s)": "deadlines",
    "submission method(s)": "submission_modes",
    "bid bond": "bid_bond",
    "performance bond": "performance_bond",
    "eligibility": "eligibility",
    "unified qualification": "unified_qualification",
    "tax basis": "tax_basis",
    "spec access": "spec_access",
    "procurement type": "procurement_type",
    "award method": "award_method",
}


def tier1_problems() -> list[str]:
    """A concept without a real field id, a field id used twice, or a mapping that
    differs from config.TIER1: listed, never guessed."""
    out = [f"concept '{c}': field id '{f}' is not in schema 1.0.0" for c, f in CONCEPTS.items() if f not in FIELD_IDS]  # fmt: skip
    ids = list(CONCEPTS.values())
    out += [f"field id '{f}' answers more than one concept" for f in sorted(set(ids)) if ids.count(f) > 1]  # fmt: skip
    if set(ids) != set(TIER1):
        out.append(f"mapping {sorted(set(ids) ^ set(TIER1))} differs from config.TIER1")
    return out


def gold_sample(doc_id: str, field: str) -> bool:
    """The seeded 20% spot-check of accepted non-tier-1 fields: a hash, so two runs
    pick the same ones."""
    h = hashlib.sha256(f"{GOLD_SPOT_SEED}:{doc_id}:{field}".encode()).digest()
    return h[0] * 256 + h[1] < 65536 * GOLD_SPOT_PERCENT / 100


def gold_mark(row: ManifestRow, res: list) -> None:
    """Export policy (D-62): flagged fields go to review (as always); an accepted tier 1
    field always does; an accepted other field when gold_sample picks it."""
    for r in res:
        if r.state != "accepted":
            continue
        if r.field in TIER1:
            r.spot, r.reasons = True, ["gold: tier 1 field, always reviewed"]
        elif gold_sample(row.doc_id, r.field):
            r.spot, r.reasons = True, [f"gold: {GOLD_SPOT_PERCENT}% spot-check"]
        else:
            r.spot = False  # the D-43 5% check does not apply to gold documents


# --- the wave --------------------------------------------------------------------------


def gold_rows(wave: int) -> tuple[list[ManifestRow], list[tuple[str, str]]]:
    """(rows to label, refused with reason). A document that is not `open` in the
    manifest, or whose organization is not in the dev split of splits.json, is refused
    even when gold_set.json lists it. (The gold set is drawn from the dev split, not
    from label_set.json, which is a smaller sample of it.)"""
    g = json.loads(GOLD_SET.read_text())
    docs = next((w["docs"] for w in g["waves"] if w["wave"] == wave), None)
    if docs is None:
        raise SystemExit(f"gold_set.json has no wave {wave}")
    by_id = {r.doc_id: r for r in run.read_rows()}
    splits = json.loads(run.SPLITS.read_text())
    rows, refused = [], []
    for d in docs:
        r = by_id.get(d["doc_id"])
        if r is None:
            refused.append((d["doc_id"], "not in the manifest"))
        elif r.license_class != "open":
            refused.append((d["doc_id"], f"license_class is {r.license_class}, not open: never sent to a cloud provider"))  # fmt: skip
        elif splits.get(r.issuer_org) != "dev":
            refused.append((d["doc_id"], f"organization is in split {splits.get(r.issuer_org)}, not dev"))  # fmt: skip
        else:
            rows.append(r)
    return rows, refused


def tier1_not_in_review(row: ManifestRow) -> list[str]:
    """For a document resolved before the gold policy: its tier 1 fields that are neither
    reviewed nor waiting as a review item."""
    have = read_resolved(row.doc_id)
    p = decisions_path(row.doc_id)
    items = {i["field"] for i in json.loads(p.read_text())["items"]} if p.exists() else set()  # fmt: skip
    return [
        f for f in TIER1
        if f in applicable_fields(row.doc_type)
        and f not in items
        and not have.get(f, {}).get("provenance", {}).get("reviewed_by")
    ]  # fmt: skip


def is_done(row: ManifestRow) -> bool:
    """Resolved by the pipeline already (accepted labels or review items exist)."""
    return decisions_path(row.doc_id).exists() or bool(read_resolved(row.doc_id))


def next_reset(key: str, now: float) -> float:
    """The provider's next midnight in its quota time zone (D-57)."""
    tz = ZoneInfo(effective_cfg(PROVIDERS[key]).quota_tz)
    local = datetime.fromtimestamp(now, UTC).astimezone(tz)
    return (datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), tz)).timestamp()  # fmt: skip


def left_today(key: str, now: float) -> tuple[int, bool]:
    """(requests left on the provider's quota day, blocked by a daily 429)."""
    c = effective_cfg(PROVIDERS[key])
    u = Ledger().today(key, now, c.quota_tz)
    return max(0, c.rpd - u["requests"]), u["blocked"]


def on_battery() -> bool:
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=10).stdout  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return False  # no pmset: not a Mac laptop, nothing to pause for
    return "Battery Power" in out


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def failed_parts(row: ManifestRow) -> dict[str, list[int]]:
    """labeler key -> indexes of the parts that are `failed` in the raw cache. Without
    --retry-failed they are skipped; `provider_unavailable` parts are always asked again."""
    a = assign(row)
    if isinstance(a, str):
        return {}
    out = {}
    for k in a.keys.values():
        bad = [int(i) for i, c in run.raw_for(row, k)["chunks"].items() if c["status"] == "failed"]  # fmt: skip
        if bad:
            out[k] = sorted(bad)
    return out


def retry_hint(wave: int) -> str:
    return f"daemon --gold --wave {wave} --retry-failed --yes --max-calls N"


def paths() -> tuple[Path, Path, Path]:
    return (
        config.CACHE / "daemon.pid",
        config.CACHE / "STOP",
        config.CACHE / "daemon.log",
    )


# --- plan ------------------------------------------------------------------------------


def plan_text(wave: int, now: float, max_calls: int | None = None, retry: bool = False) -> str:  # fmt: skip
    """What a real run would do. Reads files only: no request, no file written."""
    pid_p, stop_p, _ = paths()
    probs = tier1_problems()
    out = [
        f"daemon plan: gold wave {wave} (data/eval/gold_set.json), labelers gemini + local, groq not used"
    ]
    out.append("tier 1 fields (concept -> field id, always exported for review):")
    out += [f"  {c:<24} -> {f}" for c, f in CONCEPTS.items()]
    if probs:
        return "\n".join(
            out + ["TIER 1 MAPPING PROBLEMS, stopping:"] + [f"  {p}" for p in probs]
        )
    rows, refused = gold_rows(wave)
    pending = [r for r in rows if not is_done(r)]
    out.append(f"documents: {len(rows) + len(refused)} in wave {wave}, {len(pending)} without labels yet, {len(rows) - len(pending)} already resolved, {len(refused)} refused")  # fmt: skip
    for r in pending:
        out.append(
            f"  {r.doc_id[:12]} {r.doc_type:<17} {r.issuer_org} (license {r.license_class})"
        )
    for d, why in refused:
        out.append(f"  REFUSED {d[:12]}: {why}")
    for r in rows:
        if is_done(r):
            miss = tier1_not_in_review(r)
            out.append(f"  NOTE {r.doc_id[:12]} was resolved before the gold policy; a real start re-resolves it from the raw cache (no request); {len(miss)} of its tier 1 fields are not in review now" + (f": {', '.join(miss)}" if miss else ""))  # fmt: skip
    tallies, _ = run.price(pending)
    failed = {r.doc_id: failed_parts(r) for r in pending}
    n_failed: dict[str, int] = {}
    for per_doc in failed.values():
        for k, idx in per_doc.items():
            n_failed[k] = n_failed.get(k, 0) + len(idx)
    if retry:
        out.append(f"--retry-failed: {sum(n_failed.values())} failed parts in the cache would be asked again (one request each at least; a repair or split costs more):")  # fmt: skip
        for r in pending:
            for k, idx in failed[r.doc_id].items():
                out.append(f"  {r.doc_id[:12]} {k.split(':')[0]}: failed parts {', '.join(str(i + 1) for i in idx)} -> {len(idx)} request(s)")  # fmt: skip
    elif n_failed:
        who = ", ".join(f"{k.split(':')[0]} {n}" for k, n in sorted(n_failed.items()))
        out.append(f"NOTE {sum(n_failed.values())} failed parts are being skipped ({who}); retry them with: uv run python -m eval.silver {retry_hint(wave)}")  # fmt: skip
        for r in pending:
            for k, idx in failed[r.doc_id].items():
                out.append(f"  {r.doc_id[:12]} {k.split(':')[0]}: failed parts {', '.join(str(i + 1) for i in idx)}")  # fmt: skip
    out.append("requests still to make (cached parts are free; a retry or repair costs more, and a failed request counts against Gemini's cap):")  # fmt: skip
    for key, t in sorted(tallies.items()):
        skipped = (
            0 if retry else n_failed.get(key, 0)
        )  # failed parts are not asked without the flag
        out.append(f"  {key:<30} {t.calls - skipped:>3} requests for {t.docs} documents (+{t.cached_calls} cached)" + (f", {skipped} failed parts skipped" if skipped else ""))  # fmt: skip
    if not tallies:
        out.append("  none")
    out.append("providers today:")
    for key in sorted(k for k in tallies if not k.startswith("local:")):
        c = effective_cfg(PROVIDERS[key])
        left, blocked = left_today(key, now)
        r_ts = next_reset(key, now)
        out.append(
            f"  {key}: {0 if blocked else left} of {c.rpd} requests left on {c.quota_tz} {_day(now, c.quota_tz)}"
            f"{' (blocked by a daily 429)' if blocked else ''}; next reset {datetime.fromtimestamp(r_ts, UTC):%Y-%m-%d %H:%M} UTC, in {(r_ts - now) / 3600:.1f} h"  # fmt: skip
        )
    out.append("  local: no cap")
    t1 = sum(
        len([f for f in TIER1 if f in applicable_fields(r.doc_type)]) for r in pending
    )
    sample = sum(len([f for f in applicable_fields(r.doc_type) if f not in TIER1 and gold_sample(r.doc_id, f)]) for r in pending)  # fmt: skip
    out.append(f"export (wave-tagged, data/cache/labeling/export/batch-w{wave}-NN.md, written when the daemon ends; nothing is imported):")  # fmt: skip
    out.append(f"  tier 1 items: {t1} (always); spot-check sample ({GOLD_SPOT_PERCENT}%, seed {GOLD_SPOT_SEED}): up to {sample} (the fields that end up accepted); flagged: unknown until the documents are labeled")  # fmt: skip
    out.append(f"  batches: at least {-(-(t1 + sample) // review.MAX_ITEMS)} of up to {review.MAX_ITEMS} items each, plus the flagged items")  # fmt: skip
    out.append(
        f"hard stops: --max-calls {max_calls if max_calls else 'N (required with --yes)'}, {MAX_FAILURES} failures in a row from one provider, "
        f"laptop on battery (pauses; now: {'battery' if on_battery() else 'AC'}), stop file {stop_p}"
    )
    out.append(f"pid file {pid_p}: " + (f"process {pid_p.read_text().strip()} {'ALIVE: a start would be refused' if pid_p.read_text().strip().isdigit() and alive(int(pid_p.read_text().strip())) else 'stale'}" if pid_p.exists() else "none"))  # fmt: skip
    out.append(f"stop file: {'PRESENT: a start would be refused until it is removed' if stop_p.exists() else 'none'}")  # fmt: skip
    out.append("no request has been made (plan only).")
    return "\n".join(out)


# --- the loop --------------------------------------------------------------------------


class Stop(Exception):
    pass


@dataclass
class Daemon:
    wave: int
    rows: list[ManifestRow]
    max_calls: int
    factory: Callable[[str], Provider] = _default_factory
    now: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    battery: Callable[[], bool] = on_battery
    retry_failed: bool = False

    def log(self, event: str, provider: str = "-", count: int | None = None, secs: float | None = None, doc: str | None = None) -> None:  # fmt: skip
        """One line per event: no document text, no keys, no error messages."""
        _, _, lp = paths()
        lp.parent.mkdir(parents=True, exist_ok=True)
        f = [datetime.fromtimestamp(self.now(), UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), event, f"provider={provider}"]  # fmt: skip
        if count is not None:
            f.append(f"count={count}")
        if secs is not None:
            f.append(f"secs={secs:.0f}")
        if doc:
            f.append(f"doc={doc[:12]}")
        with lp.open("a") as fh:
            fh.write(" ".join(f) + "\n")

    # -- gates, checked before every request --
    def check_stop(self) -> None:
        if paths()[1].exists():
            raise Stop("stop file")

    def nap(self, secs: float) -> None:
        end = self.now() + secs
        while self.now() < end:
            self.check_stop()
            self.sleep(min(POLL, end - self.now()))

    def gate(self, key: str) -> None:
        self.check_stop()
        if self.streak.get(key, 0) >= MAX_FAILURES:
            raise Stop(f"{MAX_FAILURES} failures in a row from {key}")
        paused = False
        while self.battery():
            if not paused:
                self.log("paused_battery")
                paused = True
            self.nap(POLL)
        if paused:
            self.log("resumed_ac")

    def guarded_factory(self, key: str) -> Provider:
        prov = self.factory(key)
        inner = prov.complete

        def complete(*a, **k):
            try:
                self.gate(key)
            except Stop:
                self.pipe.calls_left += 1  # the request was counted but never sent
                raise
            try:
                c = inner(*a, **k)
            except ProviderError as e:
                self.streak[key] = self.streak.get(key, 0) + 1
                if e.kind == "auth":  # a bad key stays bad: no point in a second try
                    self.dead.add(key)
                    self.log("auth_error", key)
                    print(f"{key}: authorization error ({e.outcome}); provider stopped for this run, check its key")  # fmt: skip
                raise
            self.streak[key] = 0
            return c

        prov.complete = complete  # type: ignore[method-assign]
        return prov

    def guard(self, row: ManifestRow, key: str) -> str | None:
        """Why this labeler must not see this document, else None."""
        if key in PROVIDERS and (row.license_class != "open" or key != "gemini"):
            return f"{key} is not allowed for a {row.license_class} document (gold uses open documents, gemini and local only)"  # fmt: skip
        return None

    # -- one pass --
    def label_pass(self, pending: list[ManifestRow]) -> None:
        for row in pending:
            self.check_stop()
            a = assign(row)
            if isinstance(a, str):
                self.log("refused", doc=row.doc_id)
                continue
            for slot in SLOTS:
                key = a.keys[slot]
                if self.guard(row, key):
                    self.log("refused", key, doc=row.doc_id)
                    break
                if raw_state(run.raw_for(row, key)) == "complete":
                    continue  # nothing left to ask, and no provider is built for it
                if key in self.dead:
                    continue
                if key in PROVIDERS:
                    if key in self.capped and self.now() < self.capped[key]:
                        continue
                    left, blocked = left_today(key, self.now())
                    if blocked or left <= 0:
                        self.capped[key] = next_reset(key, self.now())
                        self.log("cap", key, doc=row.doc_id)
                        continue
                spent, t0 = self.pipe.calls_left, time.monotonic()
                retry = self.retry_failed and (row.doc_id, key) not in self.retried
                try:
                    self.pipe.label(row, run.ja_sentences(row), key, retry)
                    self.retried.add(
                        (row.doc_id, key)
                    )  # a part that fails again waits for the next start
                except DailyCap:
                    self.capped[key] = next_reset(key, self.now())
                    self.streak[key] = 0
                    self.log("cap", key, spent - self.pipe.calls_left, doc=row.doc_id)
                    continue
                finally:
                    self.pipe.down.discard(key)
                self.log("labeled", key.split(":")[0], spent - self.pipe.calls_left, time.monotonic() - t0, row.doc_id)  # fmt: skip

    def ok_parts(self) -> int:
        n = 0
        for r in self.rows:
            a = assign(r)
            if not isinstance(a, str):
                for k in a.keys.values():
                    n += sum(c["status"] == "ok" for c in run.raw_for(r, k)["chunks"].values())  # fmt: skip
        return n

    def resolve(self, rows: list[ManifestRow], event: str = "resolved") -> int:
        used = {}
        for r in rows:
            a = assign(r)
            if not isinstance(a, str):
                used[r.doc_id] = {s: (k, run.raw_for(r, k)) for s, k in a.keys.items()}
        n = run.resolve_docs(rows, used, lambda s: None, gold_mark)["resolved"]
        for r in rows:
            if is_done(r):
                self.log(event, doc=r.doc_id)
        return n

    def regold(self) -> None:
        """Documents resolved before the gold policy (D-62): resolve them again from
        the raw cache, no request. A reviewed line is never replaced; the same hash
        picks the same sample, so doing it on every start changes nothing."""
        self.resolve([r for r in self.rows if is_done(r)], "regold")

    def loop(self) -> str:
        while True:
            pending = [r for r in self.rows if not is_done(r)]
            if not pending:
                return "wave resolved"
            before = self.ok_parts()
            self.label_pass(pending)
            resolved = self.resolve(pending)
            if not [r for r in self.rows if not is_done(r)]:
                continue
            if self.capped:
                key, ts = min(self.capped.items(), key=lambda kv: kv[1])
                secs = max(0.0, ts - self.now()) + RESET_MARGIN
                self.log("sleep", key, secs=secs)
                self.nap(secs)
                self.capped = {k: t for k, t in self.capped.items() if t > self.now()}
                self.log("woke", key)
            elif not resolved and self.ok_parts() == before:
                if self.dead:
                    return f"stalled: {', '.join(sorted(self.dead))} stopped by an authorization error"  # fmt: skip
                if self.retry_failed:
                    return "stalled: the failed parts failed again (see the ledger outcomes); nothing more can be asked"  # fmt: skip
                return f"stalled: nothing more can be asked; failed parts of a gold document need `{retry_hint(self.wave)}`, not `run`"  # fmt: skip

    def export(self) -> None:
        done = [r for r in self.rows if is_done(r)]
        if not done:
            return
        paths_ = review.export("dev", True, lambda s, o: done, self.wave)
        self.log("export", count=len(paths_))

    def start(self) -> str:
        pid_p, stop_p, _ = paths()
        if pid_p.exists():
            txt = pid_p.read_text().strip()
            if txt.isdigit() and alive(int(txt)):
                self.log("refused_start_pid_alive")
                return f"refused: process {txt} is running (pid file {pid_p})"
        if stop_p.exists():
            self.log("refused_start_stop_file")
            return f"refused: stop file {stop_p} exists, remove it first"
        pid_p.parent.mkdir(parents=True, exist_ok=True)
        pid_p.write_text(str(os.getpid()))
        self.streak: dict[str, int] = {}
        self.capped: dict[str, float] = {}
        self.dead: set[str] = set()  # providers stopped by an authorization error
        self.retried: set[tuple[str, str]] = set()
        self.pipe = Pipeline(
            self.guarded_factory, Ledger(), self.now, self.sleep, print
        )
        self.pipe.calls_left, self.pipe.down = self.max_calls, set()
        self.log("start", count=self.max_calls)
        try:
            self.regold()
            reason = self.loop()
        except Stop as e:
            reason = str(e)
        except OutOfCalls:
            reason = f"--max-calls {self.max_calls} reached"
        finally:
            self.pipe.close()
            pid_p.unlink(missing_ok=True)
        self.export()
        slug = reason.split(":")[0].replace(" ", "_")
        self.log(f"stop_{slug}", count=self.max_calls - self.pipe.calls_left)
        return reason
