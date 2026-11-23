# ruff: noqa: E501
"""Selecting documents, the quota guard (`plan`), `run` and `status`.

Nothing here calls a provider unless `run` is given both --yes and --max-calls N. `run`
prices the remaining work with the same code `plan` uses and says what today's budgets
allow; it never aborts for that. A provider whose daily budget runs out stops for the
day and the others go on; --max-calls stops the run (D-56).

Each slot works through its own queue of documents: side A (Gemini for open documents,
Groq for the rest) first, then side B (the local model), so one provider's outage,
daily cap or failures never stop the other, and a document is resolved once both have
answered. A document that already has labels made with an earlier prompt version is
never resolved again: it runs in comparison mode, which writes only the raw answer
cache, the usage ledger and eval/reports/silver_pilot_<prompt>.md. A re-run with the
same prompt version resolves as before (reviewed lines are never replaced)."""

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from shiori_core.models import Sentence

from collector.manifest import ManifestRow, read_rows
from eval.documents import load_sentences
from eval.silver import config
from eval.silver.config import PROMPT_VERSION, PROVIDERS, SLOTS
from eval.silver.limiter import DailyCap, Ledger, _day, effective_cfg
from eval.silver.pipeline import (
    OutOfCalls,
    Pipeline,
    Resolved,
    answers,
    assign,
    cfg_for,
    labeled_by_earlier_prompt,
    load_raw,
    plan_parts,
    prompt_for,
    raw_path,
    raw_state,
    read_resolved,
    resolve,
    store_resolution,
)  # fmt: skip
from eval.silver.prompt import applicable_fields, est_output

LABEL_SET = Path("data/eval/label_set.json")
SPLITS = Path("data/eval/splits.json")


def select(
    split: str | None = None,
    open_only: bool = False,
    doc_ids: list[str] | None = None,
    groups: list[str] | None = None,
) -> list[ManifestRow]:
    rows = {r.doc_id: r for r in read_rows()}
    ls = json.loads(LABEL_SET.read_text())
    entries = [e for s in ("dev", "test") for e in ls[s] if split in (None, s)]
    if doc_ids:
        entries = [
            e for e in entries if any(e["doc_id"].startswith(d) for d in doc_ids)
        ]
    if groups:
        entries = [e for e in entries if e["group"] in groups]
    if open_only:
        entries = [e for e in entries if e["license_class"] == "open"]
    return [rows[e["doc_id"]] for e in entries]


def ja_sentences(row: ManifestRow) -> list[Sentence]:
    return [s for s in load_sentences(row) if s.language == "ja"]


def model_of(key: str) -> str:
    return PROVIDERS[key].model if key in PROVIDERS else key[6:].removesuffix(".gguf")


def raw_for(row: ManifestRow, key: str) -> dict:
    return load_raw(raw_path(row.doc_id, "local" if key.startswith("local:") else key, model_of(key)))  # fmt: skip


@dataclass
class Tally:
    docs: int = 0
    calls: int = 0
    cached_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    split_docs: int = 0
    notes: list[str] = field(default_factory=list)


def price(rows: list[ManifestRow]) -> tuple[dict[str, Tally], list[tuple[str, str]]]:
    """Per labeler key (gemini, groq, local:<gguf>): documents, calls still to make
    (cached chunks are free), estimated tokens, documents that need splitting. Also the
    documents that cannot be labeled at all, with the reason."""
    tallies: dict[str, Tally] = {}
    skipped: list[tuple[str, str]] = []
    for row in rows:
        a = assign(row)
        if isinstance(a, str):
            skipped.append((row.doc_id, a))
            continue
        ja = ja_sentences(row)
        for key in a.keys.values():
            t = tallies.setdefault(key, Tally())
            parts = plan_parts(row, ja, cfg_for(key))
            raw = raw_for(row, key)
            t.docs += 1
            t.split_docs += len(parts) > 1
            for i, part in enumerate(parts):
                if raw["chunks"].get(str(i), {}).get("status") == "ok":
                    t.cached_calls += 1
                    continue
                t.calls += 1
                t.tokens_in += part.est_in()
                t.tokens_out += est_output(len(part.field_ids))
    return tallies, skipped


def days_needed(key: str, t: Tally) -> int | None:
    if key.startswith("local:"):
        return None
    c = effective_cfg(PROVIDERS[key])
    d = math.ceil(t.calls / c.rpd) if t.calls else 0
    if c.tpd:
        d = max(d, math.ceil((t.tokens_in + t.tokens_out) / c.tpd))
    return d


def plan_text(title: str, rows: list[ManifestRow]) -> str:
    tallies, skipped = price(rows)
    out = [
        f"{title}: {len(rows)} documents ({sum(r.license_class == 'open' for r in rows)} open)"
    ]
    compare = [r for r in rows if labeled_by_earlier_prompt(r.doc_id)]
    if compare:
        out.append(
            f"  comparison mode (labels from an earlier prompt exist; report only, no label written): "
            f"{', '.join(r.doc_id[:12] for r in compare)}"
        )
    ledger, now = Ledger(), datetime.now(UTC).timestamp()
    for key, t in sorted(tallies.items()):
        local = key.startswith("local:")
        c = None if local else effective_cfg(PROVIDERS[key])
        d = days_needed(key, t)
        out.append(
            f"  {key:<28} docs {t.docs:>3}  calls {t.calls:>4} (+{t.cached_calls} cached)  "
            f"tokens in~{t.tokens_in:>9,} out~{t.tokens_out:>8,}  "
            f"multi-request docs {t.split_docs:>3}  "
            + (
                "no quota (runs on this machine)"
                if local
                else f"days of free quota at the daily cap: {d}"
            )
        )
        if c and not c.published:
            out.append(
                f"    ({key} limits are ASSUMED: rpm {c.rpm}, tpm {c.tpm:,}, rpd {c.rpd}; put your AI Studio numbers in {config.CACHE / 'limits.json'})"
            )
        elif c:
            out.append(
                f"    (limits: {c.rpm} req/min, {c.tpm:,} tokens/min, {c.rpd} req/day, "
                + (f"{c.tpd:,} tokens/day)" if c.tpd else "no tokens/day cap)")
            )
        if c:
            u = ledger.today(key, now, c.quota_tz)
            out.append(
                f"    today ({c.quota_tz} {_day(now, c.quota_tz)}): {u['requests']} of {c.rpd} requests used "
                f"({u['ok']} ok, {u['failed']} failed), {max(0, c.rpd - u['requests'])} left"
                + (
                    f"; tokens {u['tokens_in'] + u['tokens_out']:,} of {c.tpd:,}"
                    if c.tpd
                    else ""
                )
                + ("  [daily cap reached]" if u["blocked"] else "")
            )
    for d, why in skipped:
        out.append(f"  SKIPPED {d[:12]}: {why}")
    return "\n".join(out)


def run_notes(rows: list[ManifestRow], max_calls: int, now: float) -> list[str]:
    """What today's run can do, printed before it starts. Nothing here stops a run:
    a provider whose daily budget (requests or tokens, failures included) runs out
    is stopped for the day by the limiter (DailyCap) and the others go on; --max-calls
    stops the whole run. The next run picks up from the raw cache (D-56)."""
    tallies, _ = price(rows)
    ledger, out = Ledger(), []
    total = sum(t.calls for t in tallies.values())
    if total > max_calls:
        out.append(f"{total} calls left in this selection; --max-calls {max_calls} stops the run before the end")  # fmt: skip
    for key, t in sorted(tallies.items()):
        if key.startswith("local:"):
            continue
        c = effective_cfg(PROVIDERS[key])
        u = ledger.today(key, now, c.quota_tz)
        if u["blocked"] or u["requests"] >= c.rpd:
            out.append(f"{key}: daily cap already reached today, it sits this run out")
            continue
        if u["requests"] + t.calls > c.rpd:
            out.append(f"{key}: {t.calls} calls left, {c.rpd - u['requests']} requests left today: stops at the cap, the rest waits for the next run")  # fmt: skip
        if (
            c.tpd
            and u["tokens_in"] + u["tokens_out"] + t.tokens_in + t.tokens_out > c.tpd
        ):
            out.append(f"{key}: ~{t.tokens_in + t.tokens_out:,} tokens left, {c.tpd - u['tokens_in'] - u['tokens_out']:,} left today: stops at the cap, the rest waits for the next run")  # fmt: skip
    return out


def label_queue(
    pipe: Pipeline,
    slot: str,
    rows: list[ManifestRow],
    used: dict[str, dict[str, tuple[str, dict]]],
    retry_failed: bool,
) -> None:
    """One slot's queue. A daily cap or a backoff pause stops only that provider; an
    unavailable or failed document is skipped and the queue moves on. There is no
    fallback labeler since sv3: side B is already the local model, and a second local
    answer would be the same voice twice (D-50)."""
    for row in rows:
        a = assign(row)
        if isinstance(a, str):
            continue
        key = a.keys[slot]
        raw: dict = {"chunks": {}}
        if key not in pipe.down:
            try:
                raw = pipe.label(row, ja_sentences(row), key, retry_failed)
            except DailyCap:
                pipe.down.add(key)
                pipe.say(
                    f"{key}: daily cap reached, stopped for today (the other provider goes on)"
                )
        used.setdefault(row.doc_id, {})[slot] = (key, raw)


def decide(row: ManifestRow, raws: list[dict], overlap: bool) -> tuple[list[Resolved], list]:  # fmt: skip
    """Resolve one document from two complete raw answers (first = side A). Pure: writes
    nothing. Returns the decisions and the labelers for provenance."""
    sentences = load_sentences(row)
    by_id = {x.id: x for x in sentences}
    labelers = [(r["provider"], r["model"], max(c["date"] for c in r["chunks"].values()),
                 r.get("prompt_version") or prompt_for(r["provider"])) for r in raws]  # fmt: skip
    cands = [answers(r, f"{r['provider']}/{r['model']}", applicable_fields(row.doc_type), by_id) for r in raws]  # fmt: skip
    return resolve(row, sentences, cands, labelers, overlap), labelers


def run_docs(
    rows: list[ManifestRow],
    max_calls: int,
    retry_failed: bool = False,
    pipe: Pipeline | None = None,
) -> dict[str, int]:
    """Each slot labels every document in its own queue; then every document with two
    complete answers is resolved. Documents that already have labels are only compared
    (comparison mode, report in eval/reports/silver_pilot_<prompt>.md)."""
    pipe = pipe or Pipeline()
    pipe.calls_left = max_calls
    pipe.down = set()  # a pause lasts one run
    used: dict[str, dict[str, tuple[str, dict]]] = {}
    # ponytail: one queue after the other; a thread each if wall time matters
    try:
        for slot in SLOTS:
            label_queue(pipe, slot, rows, used, retry_failed)
    except OutOfCalls:
        pipe.say("--max-calls reached")
    finally:
        pipe.close()  # stop llama-server before resolving
    count = resolve_docs(rows, used, pipe.say)
    if count["compared"]:
        from eval.silver.compare import full_report

        pipe.say(f"comparison report: {full_report(rows)}")
    return count


def resolve_docs(rows: list[ManifestRow], used: dict[str, dict[str, tuple[str, dict]]], say, mark=None) -> dict[str, int]:  # fmt: skip
    """Resolve every document whose two slots have complete answers in `used`. `mark`
    (row, decisions) may set `Resolved.spot` / `reasons` before storing: the daemon's
    gold export policy (D-62) uses it; the default is the D-43 spot-check."""
    splits = json.loads(SPLITS.read_text())
    count = {"resolved": 0, "compared": 0, "pending": 0, "skipped": 0}
    for row in rows:
        got = used.get(row.doc_id, {})
        if isinstance(assign(row), str):
            count["skipped"] += 1
            continue
        raws = {s: got[s][1] for s in SLOTS if s in got}
        if len(raws) < 2 or not all(raw_state(r) == "complete" for r in raws.values()):
            count["pending"] += 1
            continue
        overlap = any(k.startswith("local:") for k, _ in got.values())
        res, labelers = decide(row, [raws[s] for s in SLOTS], overlap)
        if mark:
            mark(row, res)
        if labeled_by_earlier_prompt(row.doc_id):
            count["compared"] += 1
            continue
        path = store_resolution(row, res, labelers, splits)
        count["resolved"] += 1
        say(
            f"{row.doc_id[:12]}: accepted {sum(r.state == 'accepted' for r in res)}, "
            f"flagged {sum(r.state == 'flagged' for r in res)}"
            + (f", wrote {path}" if path else "")
        )
    return count


def resolve_cached(rows: list[ManifestRow]) -> dict[str, int]:
    """`resolve`: the same resolution from the raw cache alone; no provider is made, so
    no request can be sent (after `repair`, D-52)."""
    used = {}
    for row in rows:
        a = assign(row)
        if not isinstance(a, str):
            used[row.doc_id] = {s: (k, raw_for(row, k)) for s, k in a.keys.items()}
            web = load_raw(raw_path(row.doc_id, "web", "gemini-web", "sv4-web"))  # D-104
            if web["chunks"]:  # the web-chat answer is side A in place of the API provider's
                used[row.doc_id]["A"] = ("web", web)
    return resolve_docs(rows, used, print)


def status_text(split: str | None = None) -> str:
    now = datetime.now(UTC).timestamp()
    ledger = Ledger()
    out = []
    flagged: dict[tuple[str, str], int] = {}
    fp = config.CACHE / "flagged.jsonl"
    if fp.exists():
        for x in fp.read_text().splitlines():
            if x.strip():
                d = json.loads(x)
                if d["kind"] != "spot":
                    flagged[d["doc_id"], d["field"]] = 1
    ls = json.loads(LABEL_SET.read_text())
    for s in ("dev", "test"):
        if split and s != split:
            continue
        out.append(
            f"{s}: accepted | reviewed | rule-absent | flagged | failed chunks (prompt {PROMPT_VERSION})"
        )
        tot = [0, 0, 0, 0, 0]
        for e in ls[s]:
            d = e["doc_id"]
            lines = read_resolved(d)
            st = [x.get("provenance", {}).get("final_state") for x in lines.values()]
            acc = st.count("silver_consensus")
            rev = st.count("silver_model_reviewed")
            ra = sum(1 for x in lines.values() if x["provenance"]["pre_labelers"] == [])
            fl = sum(1 for (dd, _f) in flagged if dd == d)
            fails = 0
            for p in (
                (config.CACHE / "raw" / d).glob("*.json")
                if (config.CACHE / "raw" / d).exists()
                else []
            ):
                fails += sum(
                    c["status"] == "failed"
                    for c in json.loads(p.read_text())["chunks"].values()
                )
            if acc + rev + ra + fl + fails:
                out.append(
                    f"  {d[:12]} {e['license_class'][:4]:<5} {e['group']:<16} {acc:>3} {rev:>3} {ra:>3} {fl:>3} {fails:>3}"
                )
            for i, v in enumerate((acc, rev, ra, fl, fails)):
                tot[i] += v
        out.append(
            f"  total: {tot[0]} accepted, {tot[1]} reviewed, {tot[2]} rule-absent, {tot[3]} flagged, {tot[4]} failed chunks"
        )
    out.append(
        "provider progress (each labeler's own prompt version, label set, documents):"
    )
    for name in (*PROVIDERS, "local"):
        states: dict[str, int] = {}
        for s in ("dev", "test"):
            if split and s != split:
                continue
            for e in ls[s]:
                d = config.CACHE / "raw" / e["doc_id"]
                for p in (
                    d.glob(f"{name}__*__{prompt_for(name)}__*.json")
                    if d.exists()
                    else []
                ):
                    st = raw_state(load_raw(p))
                    states[st] = states.get(st, 0) + 1
        out.append(f"  {name:<7} " + (", ".join(f"{v} {k}" for k, v in sorted(states.items())) or "nothing yet"))  # fmt: skip
    out.append(
        "today's usage (each provider's quota day: Gemini Pacific, Groq UTC; every request, failures included):"
    )
    for name in PROVIDERS:
        c = effective_cfg(PROVIDERS[name])
        u = ledger.today(name, now, c.quota_tz)
        fails = ", ".join(
            f"{k} {v}" for k, v in sorted(u["outcomes"].items()) if k != "ok"
        )
        kinds = ", ".join(f"{k} {v}" for k, v in sorted(u["kinds"].items()))
        out.append(
            f"  {name:<7} requests {u['requests']} of {c.rpd} ({u['ok']} ok, {u['failed']} failed"
            + (f": {fails}" if fails else "")
            + ")"
            + (f" [{kinds}]" if kinds else "")
            + f", tokens in {u['tokens_in']:,}, out {u['tokens_out']:,}"
            + (f" of {c.tpd:,}/day" if c.tpd else "")
            + ("  [daily cap reached]" if u["blocked"] else "")
        )
    sp = config.CACHE / "spotcheck.jsonl"
    if sp.exists():
        rs = [json.loads(x) for x in sp.read_text().splitlines() if x.strip()]
        ch = sum(r["changed"] for r in rs)
        out.append(
            f"consensus spot-check: {len(rs)} reviewed, {ch} changed ({100 * ch / len(rs):.0f}% silver error estimate, n={len(rs)})"
        )
    return "\n".join(out)
