# ruff: noqa: E501
"""Local labeler bake-off (D-63): which local models can label tender documents, scored
against the reviewed pilot labels.

Dev-time only, never imported by core/, sidecar/ or app/. It is a loop around the
existing pieces, not a new labeler: `Pipeline.label` (the `shadow` command: same sv4
prompt, per-model raw cache), `Pipeline.repair_cached` (the local shape repair, D-52),
`compare.score` (the consensus agreement rule) and the checks in `eval.silver.checks`.

    uv run python -m eval.bakeoff --plan                    # no request at all
    uv run python -m eval.bakeoff --yes --max-calls N       # a real run

One model at a time (one llama-server on 127.0.0.1:8792), a hard timeout per request,
`data/cache/labeling/STOP` checked before every request, a pid file, a pause on battery,
and a restart repeats nothing (every answered part is in the cache). No cloud call: a
labeler key that is not `local:<gguf>` is refused. The report holds counts, field names
and document id prefixes, never document text."""

import argparse
import json
import os
import sys
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from shiori_core.fields import BY_ID

from collector.manifest import ManifestRow
from eval.model_feasibility import MODELS as MODELS_DIR
from eval.silver import compare, config, pipeline, run
from eval.silver.checks import citations_exist, value_in_citation
from eval.silver.config import TIER1
from eval.silver.daemon import POLL, Stop, alive, on_battery
from eval.silver.limiter import Ledger
from eval.silver.pipeline import (
    LOCAL_CFG,
    OutOfCalls,
    Pipeline,
    load_raw,
    plan_parts,
    raw_path,
    raw_state,
    valid_answer,
)
from eval.silver.prompt import applicable_fields, est_output
from eval.silver.providers import Local, Provider, ProviderError

LOADCHECK = Path("eval/reports/model_loadcheck.md")
REPORT = Path("eval/reports/local_labeler_bakeoff.md")
EXCLUDED = (("sarashina", "8k context, cannot read a long section (D-34)"),)
OVERLAP = ("Qwen3.5-9B",)  # its answers fed the review candidates (D-45, D-50)
LAST = "nemotron"  # slowest, so it runs last
REQUEST_TIMEOUT = 1800  # seconds; Nemotron's 8,192-token cap at 11.7 tok/s is ~700 s
MAX_FAILURES = 3  # failed requests in a row: the model is given up, the next one starts
# ponytail: prompt speed is not in model_loadcheck.md (only generation tok/s). D-34 measured
# prompt/generation ratios of 8.7 to 11.8 on this Mac; 8 is the cautious end.
PROMPT_RATIO = 8


# --- the model pool --------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    gguf: str
    tok_s: float

    @property
    def key(self) -> str:
        return "local:" + self.gguf

    @property
    def overlap(self) -> bool:
        return any(o in self.gguf for o in OVERLAP)


def pool(report: Path | None = None, models: Path | None = None) -> tuple[list[Entry], list[str]]:  # fmt: skip
    """(models to run, notes on what was left out), read from the load-check report:
    rows that loaded, minus EXCLUDED, minus files missing from models/. Fastest first,
    Nemotron last."""
    report = LOADCHECK if report is None else report
    report = LOADCHECK if report is None else report
    models = MODELS_DIR if models is None else models
    use: list[Entry] = []
    notes: list[str] = []
    for ln in report.read_text().splitlines():
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) < 6 or not c[0].endswith(".gguf"):
            continue
        if c[2] != "yes":
            notes.append(f"{c[0]}: did not load in the load check")
        elif why := next((w for k, w in EXCLUDED if k in c[0].lower()), None):
            notes.append(f"{c[0]}: left out, {why}")
        elif not (models / c[0]).exists():
            notes.append(f"{c[0]}: loaded in the load check but is not in models/ now")
        else:
            use.append(Entry(c[0], float(c[4])))
    use.sort(key=lambda e: (LAST in e.gguf.lower(), -e.tok_s))
    return use, notes


# --- documents and gold ----------------------------------------------------------------


def pilot_rows() -> tuple[list[ManifestRow], list[str]]:
    """The pilot documents that can be scored: open, in the dev split, with a label
    file. Any other is refused with the reason."""
    splits = json.loads(run.SPLITS.read_text())
    rows, refused = [], []
    for r in run.select(None, True, list(config.PILOT)):
        if r.license_class != "open":
            refused.append(
                f"{r.doc_id[:12]}: license_class is {r.license_class}, not open"
            )
        elif splits.get(r.issuer_org) != "dev":
            refused.append(f"{r.doc_id[:12]}: not in the dev split")
        elif not gold_path(r).exists():
            refused.append(f"{r.doc_id[:12]}: no label file")
        else:
            rows.append(r)
    return rows, refused


def gold_path(row: ManifestRow) -> Path:
    return pipeline.label_file(row, json.loads(run.SPLITS.read_text()))


def read_gold(row: ManifestRow) -> dict[str, dict]:
    lines = (
        json.loads(x) for x in gold_path(row).read_text().splitlines() if x.strip()
    )
    return {ln["field"]: ln for ln in lines}


# --- plan ------------------------------------------------------------------------------


def paths() -> tuple[Path, Path, Path]:
    return (
        config.CACHE / "bakeoff.pid",
        config.CACHE / "STOP",
        config.CACHE / "bakeoff.log",
    )


def estimate(m: Entry, rows: list[ManifestRow]) -> dict:
    """Requests still to make for one model (answered parts are free) and an estimate
    of the time: output at the load-check speed, input at PROMPT_RATIO times faster.
    Repair requests and answers longer than estimated are not counted."""
    calls = cached = t_in = t_out = 0
    for r in rows:
        raw = run.raw_for(r, m.key)
        for i, p in enumerate(plan_parts(r, run.ja_sentences(r), LOCAL_CFG)):
            if raw["chunks"].get(str(i), {}).get("status") == "ok":
                cached += 1
                continue
            calls += 1
            t_in += p.est_in()
            t_out += est_output(len(p.field_ids))
    hours = (t_in / (m.tok_s * PROMPT_RATIO) + t_out / m.tok_s) / 3600
    return {
        "calls": calls,
        "cached": cached,
        "t_in": t_in,
        "t_out": t_out,
        "hours": hours,
    }


def pid_state() -> str:
    pid_p = paths()[0]
    others = [pid_p, config.CACHE / "daemon.pid"]
    for p in others:
        if p.exists():
            first = p.read_text().split()[:1]
            if first and first[0].isdigit() and alive(int(first[0])):
                return f"{p.name}: process {first[0]} ALIVE, a start would be refused"
    return "none alive"


def plan_text(max_calls: int | None = None) -> str:
    """What a real run would do. Reads files only: no request, no file written."""
    models, notes = pool()
    rows, refused = pilot_rows()
    out = [f"bakeoff plan: {len(models)} local models x {len(rows)} pilot documents, prompt {config.PROMPT_VERSION}, no cloud call"]  # fmt: skip
    out.append(f"models (from {LOADCHECK}, fastest first, Nemotron last):")
    out += [f"  {i + 1}. {m.gguf}  {m.tok_s} tok/s" + ("  [labeler_overlap]" if m.overlap else "") for i, m in enumerate(models)]  # fmt: skip
    out += [f"  not run: {n}" for n in notes]
    out.append(f"documents ({len(rows)}):")
    out += [f"  {r.doc_id[:12]} {r.doc_type:<17} {r.issuer_org}" for r in rows]
    out += [f"  REFUSED {n}" for n in refused]
    out.append("requests still to make (answered parts are cached and free; a repair costs one more request each):")  # fmt: skip
    out.append(f"  {'model':<52}{'requests':>9}{'cached':>8}{'est tokens in/out':>20}{'est hours':>11}")  # fmt: skip
    tot = {"calls": 0, "hours": 0.0}
    for m in models:
        e = estimate(m, rows)
        tot["calls"] += e["calls"]
        tot["hours"] += e["hours"]
        out.append(f"  {m.gguf:<52}{e['calls']:>9}{e['cached']:>8}{f'{e['t_in']:,} / {e['t_out']:,}':>20}{e['hours']:>11.1f}")  # fmt: skip
    out.append(
        f"  {'all models':<52}{tot['calls']:>9}{'':>8}{'':>20}{tot['hours']:>11.1f}"
    )
    out.append(f"hours = output tokens / tok/s from the load check + input tokens / ({PROMPT_RATIO} x tok/s); model load time, repairs and longer answers not counted, so read it as a floor.")  # fmt: skip
    out.append(f"hard stops: --max-calls {max_calls if max_calls else 'N (required with --yes)'} (retries and repairs count), "
               f"{REQUEST_TIMEOUT} s per request, {MAX_FAILURES} failures in a row end a model, "
               f"laptop on battery (pauses; now: {'battery' if on_battery() else 'AC'}), stop file {paths()[1]}"
               + (" (PRESENT: a start would be refused)" if paths()[1].exists() else ""))  # fmt: skip
    out.append(f"pid files: {pid_state()}")
    out.append("no request has been made (plan only).")
    return "\n".join(out)


# --- the run ---------------------------------------------------------------------------


def make_provider(key: str) -> Provider:
    """The only way a labeler is made here: a local llama-server with a hard timeout."""
    if not key.startswith("local:"):
        raise ProviderError("auth", f"the bake-off makes no cloud call ({key})")
    p = Local(key[6:])
    p.TIMEOUT = REQUEST_TIMEOUT
    return p


def server_up() -> bool:
    """Something already answers on the llama-server port (a stale server would be
    mistaken for the model we start)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{Local.PORT}/health", timeout=2):
            return True
    except OSError:
        return False


class Skip(Exception):
    """This model failed MAX_FAILURES requests in a row."""


@dataclass
class Bakeoff:
    models: list[Entry]
    rows: list[ManifestRow]
    max_calls: int
    factory: Callable[[str], Provider] = field(default=lambda k: make_provider(k))
    now: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    battery: Callable[[], bool] = on_battery
    busy: Callable[[], bool] = server_up
    say: Callable[[str], None] = print
    calls_left: int = 0
    streak: int = 0
    abandoned: list[str] = field(default_factory=list)
    pipe: Pipeline | None = None
    prov: Provider | None = None

    def log(self, event: str, model: str = "-", doc: str | None = None, count: int | None = None) -> None:  # fmt: skip
        """One line per event: no document text, no error messages."""
        lp = paths()[2]
        lp.parent.mkdir(parents=True, exist_ok=True)
        f = [time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.now())), event, f"model={model}"]  # fmt: skip
        if doc:
            f.append(f"doc={doc[:12]}")
        if count is not None:
            f.append(f"count={count}")
        with lp.open("a") as fh:
            fh.write(" ".join(f) + "\n")

    def write_pid(self) -> None:
        proc = getattr(self.prov, "_proc", None)
        lines = [str(os.getpid())] + ([f"llama-server {proc.pid}"] if proc else [])
        paths()[0].write_text("\n".join(lines) + "\n")

    def gate(self) -> None:
        """Checked before every request."""
        if paths()[1].exists():
            raise Stop("stop file")
        if self.streak >= MAX_FAILURES:
            raise Skip
        paused = False
        while self.battery():
            if not paused:
                self.log("paused_battery")
                paused = True
            if paths()[1].exists():
                raise Stop("stop file")
            self.sleep(POLL)
        if paused:
            self.log("resumed_ac")

    def guarded(self, key: str) -> Provider:
        prov = self.prov = self.factory(key)
        inner = prov.complete

        def complete(*a, **k):
            try:
                self.gate()
            except (Stop, Skip):
                assert self.pipe
                self.pipe.calls_left += 1  # the request was counted but never sent
                raise
            try:
                c = inner(*a, **k)
            except ProviderError as e:
                # a timeout, a crash or a server that will not start: never retried at
                # the same spot; the server is stopped and the next request starts fresh
                self.streak += 1
                if close := getattr(prov, "close", None):
                    close()
                raise ProviderError("local_failure", e.kind) from None
            self.streak = 0
            self.write_pid()
            return c

        prov.complete = complete  # type: ignore[method-assign]
        return prov

    def one_model(self, m: Entry) -> None:
        self.streak = 0
        pipe = self.pipe = Pipeline(
            self.guarded, Ledger(), self.now, self.sleep, self.say
        )
        pipe.calls_left = self.calls_left
        self.log("model_start", m.gguf)
        try:
            for row in self.rows:
                self.gate()
                ja = run.ja_sentences(row)
                pipe.label(row, ja, m.key)  # the `shadow` command's loop body
                pipe.repair_cached(row, ja, m.key)  # the `repair` command's
                self.log("doc_done", m.gguf, row.doc_id)
        finally:
            self.calls_left = pipe.calls_left
            pipe.close()
            self.log("model_end", m.gguf)

    def start(self) -> str:
        pid_p, stop_p, _ = paths()
        if stop_p.exists():
            return f"refused: stop file {stop_p} exists"
        if (s := pid_state()) != "none alive":
            return f"refused: {s}"
        if self.busy():
            return f"refused: something already answers on 127.0.0.1:{Local.PORT}"
        pid_p.parent.mkdir(parents=True, exist_ok=True)
        pid_p.write_text(f"{os.getpid()}\n")
        self.calls_left = self.max_calls
        reason = "all models done"
        self.log("start", count=self.max_calls)
        try:
            for m in self.models:
                try:
                    self.one_model(m)
                except Skip:
                    self.abandoned.append(m.gguf)
                    self.log("model_abandoned", m.gguf)
        except Stop as e:
            reason = f"stopped: {e}"
        except OutOfCalls:
            reason = f"--max-calls {self.max_calls} reached"
        finally:
            pid_p.unlink(missing_ok=True)
            self.log("end")
            write_report(self.models, self.rows, reason, self.abandoned)
        return reason


# --- scoring ---------------------------------------------------------------------------


@dataclass
class DocResult:
    doc: str
    state: str  # complete | failed | pending | unavailable
    seconds: float | None = None
    parts: int = 0
    valid_first: int = 0  # parts whose first answer was a usable answer
    repaired: int = 0  # parts that got a repair request
    scored: list[tuple[str, bool]] = field(default_factory=list)
    cite_exists: list[bool] = field(default_factory=list)
    value_in: list[bool] = field(default_factory=list)
    gen_n: int = 0
    gen_ms: float = 0.0


def first_answer(chunk: dict) -> str | None:
    rep = chunk.get("repair") or {}
    return rep.get("first_response") or chunk.get("response")


def measure(row: ManifestRow, raw: dict, gold: dict[str, dict]) -> DocResult:
    """One labeler's cached answers to one document against its label file. A document
    whose answers failed counts every field as wrong; one not run yet is not counted."""
    state = raw_state(raw)
    r = DocResult(row.doc_id[:12], state)
    if state in ("pending", "unavailable") and not raw.get("chunks"):
        return r
    chunks = list(raw["chunks"].values())
    r.parts = raw.get("n_chunks", len(chunks))
    r.valid_first = sum(valid_answer(first_answer(c) or "") is not None for c in chunks)
    r.repaired = sum(bool(c.get("repair")) for c in chunks)
    secs = [c.get("seconds") for c in chunks]
    r.seconds = sum(secs) if secs and None not in secs else None  # type: ignore[arg-type]
    for t in (t for c in chunks for t in c.get("timings", [])):
        r.gen_n += t.get("predicted_n") or 0
        r.gen_ms += t.get("predicted_ms") or 0
    if state == "failed":
        r.scored = [(f, False) for f in applicable_fields(row.doc_type) if f in gold]
        return r
    if state != "complete":
        r.state = "pending"
        return r
    cands = compare.candidates(row, raw)
    r.scored = compare.score(row, cands, gold)
    by_id = {s.id: s for s in run.load_sentences(row)}
    for c in cands.values():
        if (e := citations_exist(c, by_id)) is not None:
            r.cite_exists.append(e)
        if (v := value_in_citation(c, by_id)) is not None:
            r.value_in.append(v)
    return r


def rate(n: int, m: int) -> str:
    return f"{n}/{m} ({100 * n / m:.0f}%)" if m else "-"


def summarize(results: list[DocResult]) -> dict:
    """Counts over the documents that were run."""
    run_ = [d for d in results if d.state != "pending"]
    sc = [x for d in run_ for x in d.scored]
    t1 = [ok for f, ok in sc if f in TIER1]
    ls = [ok for f, ok in sc if BY_ID[f].kind == "list"]
    ms = sum(d.gen_ms for d in run_)
    secs = [d.seconds for d in run_ if d.seconds is not None]
    return {
        "docs": len(run_), "complete": sum(d.state == "complete" for d in run_),
        "t1": (sum(t1), len(t1)), "all": (sum(ok for _, ok in sc), len(sc)),
        "list": (sum(ls), len(ls)),
        "valid": (sum(d.valid_first for d in run_), sum(d.parts for d in run_)),
        "repair": (sum(d.repaired for d in run_), sum(d.parts for d in run_)),
        "cite": (sum(x for d in run_ for x in d.cite_exists), sum(len(d.cite_exists) for d in run_)),
        "value": (sum(x for d in run_ for x in d.value_in), sum(len(d.value_in) for d in run_)),
        "tok_s": sum(d.gen_n for d in run_) / (ms / 1000) if ms else None,
        "s_doc": sum(secs) / len(secs) if secs else None,
    }  # fmt: skip


def results_for(rows: list[ManifestRow], raw_of: Callable[[ManifestRow], dict]) -> list[DocResult]:  # fmt: skip
    return [measure(r, raw_of(r), read_gold(r)) for r in rows]


def model_raw(m: Entry, row: ManifestRow) -> dict:
    return load_raw(raw_path(row.doc_id, "local", m.gguf.removesuffix(".gguf")))


# --- report ----------------------------------------------------------------------------

HEAD = ("| model | note | documents run (complete) | tier 1 fields | all fields | list fields | valid JSON before repair (parts) | repair request (parts) | citation exists | value in citation | tok/s | s per document |")  # fmt: skip


def table_row(name: str, note: str, s: dict) -> str:
    fmt = lambda k: rate(*s[k])  # noqa: E731
    return (f"| {name} | {note} | {s['docs']} ({s['complete']}) | {fmt('t1')} | {fmt('all')} | {fmt('list')} | "
            f"{fmt('valid')} | {fmt('repair')} | {fmt('cite')} | {fmt('value')} | "
            f"{f'{s['tok_s']:.1f}' if s['tok_s'] else '-'} | {f'{s['s_doc']:.0f}' if s['s_doc'] else '-'} |")  # fmt: skip


def report_text(models: list[Entry], rows: list[ManifestRow], reason: str, abandoned: list[str]) -> str:  # fmt: skip
    per = {m.gguf: results_for(rows, lambda r, m=m: model_raw(m, r)) for m in models}
    gem = results_for(rows, lambda r: compare.cached(r).get("gemini") or {"chunks": {}})
    out = [
        "# Local labeler bake-off",
        "",
        f"Prompt {config.PROMPT_VERSION} (frozen), local llama-server, no cloud call. Scored against the label files of the pilot documents with the consensus agreement rule (`compare.score`), on the answers after the local shape repair. Run ended: {reason}."
        + (f" Given up after {MAX_FAILURES} failed requests in a row: {', '.join(abandoned)}." if abandoned else ""),
        "",
        "Every rate has its counts next to it, because n is small. `labeler_overlap`: that model's answers fed the review candidates, so its score is optimistic.",
        "",
        HEAD,
        "|" + " --- |" * 12,
    ]  # fmt: skip
    for m in models:
        out.append(
            table_row(
                m.gguf, "labeler_overlap" if m.overlap else "", summarize(per[m.gguf])
            )
        )
    if any(d.state != "pending" for d in gem):
        s = summarize(gem)
        out.append(table_row("gemini sv4 (reference, not ground truth)", "labeler_overlap: it also fed the review candidates", {**s, "valid": (0, 0), "repair": (0, 0), "tok_s": None, "s_doc": None}))  # fmt: skip
    out += ["", "## Per document", ""]
    for row in rows:
        g = read_gold(row)
        rev = sum(bool(x["provenance"].get("reviewed_by")) for x in g.values())
        out.append(f"- {row.doc_id[:12]} ({row.doc_type}, {row.issuer_org}): {len(g)} label lines, {rev} reviewed by a person, {len(g) - rev} accepted by agreement of two labelers.")  # fmt: skip
        for m in models:
            d = next(x for x in per[m.gguf] if x.doc == row.doc_id[:12])
            if d.state == "pending":
                out.append(f"  - {m.gguf}: not run")
                continue
            miss = [f for f, ok in d.scored if not ok]
            out.append(f"  - {m.gguf}: {d.state}, {len(d.scored) - len(miss)}/{len(d.scored)} fields, {d.seconds:.0f} s" if d.seconds is not None else f"  - {m.gguf}: {d.state}, {len(d.scored) - len(miss)}/{len(d.scored)} fields")  # fmt: skip
            if miss:
                out.append(f"    wrong or missing: {', '.join(miss)}")
    out += [
        "",
        "## What this does not tell you",
        "",
        "- Five documents. One more or fewer correct field moves a rate by a few points, and tier 1 has about 10 fields per document, so the tier 1 counts are small.",
        "- Three of the five documents are from one Wakayama template family, so a model that learned that template looks better than it would on other issuers.",
        "- The labels are not independent of the labelers: Gemini and Qwen3.5-9B supplied the candidates the reviewer chose from, and some lines were accepted without a person reading them (the per-document counts above). Qwen3.5-9B's score is the most optimistic.",
        "- Speed is from a MacBook Air M4 with Metal. It is not the 16 GB Windows laptop without a GPU that the app targets; on CPU the ranking by speed can change (D-34: Nemotron generates 0.6 tok/s there).",
        "- Seconds per document are the cached run times, and exclude the model load. Time and tok/s only exist for answers made with a build that recorded llama-server's timings.",
        "- It scores field values and citations against the labels. It does not say whether an answer is useful to a bidder, and nobody here checked the Japanese meaning.",
        "",
    ]  # fmt: skip
    return "\n".join(out)


def write_report(models: list[Entry], rows: list[ManifestRow], reason: str, abandoned: list[str]) -> None:  # fmt: skip
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report_text(models, rows, reason, abandoned), encoding="utf-8")


# --- command line ----------------------------------------------------------------------


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m eval.bakeoff", description=__doc__)
    ap.add_argument(
        "--plan", action="store_true", help="print the plan, make no request"
    )
    ap.add_argument("--yes", action="store_true", help="really run (needs --max-calls)")
    ap.add_argument("--max-calls", type=int, help="most requests this run may make (retries and repairs count)")  # fmt: skip
    a = ap.parse_args(argv)
    if a.plan or not a.yes:
        print(plan_text(a.max_calls))
        return 0
    if not a.max_calls or a.max_calls < 1:
        print("--yes needs --max-calls N (N >= 1)")
        return 2
    models, _ = pool()
    rows, refused = pilot_rows()
    for n in refused:
        print(f"REFUSED {n}")
    reason = Bakeoff(models, rows, a.max_calls).start()
    print(reason)
    print(f"report: {REPORT}")
    return 1 if reason.startswith("refused") else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
