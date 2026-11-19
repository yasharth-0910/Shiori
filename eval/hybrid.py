# ruff: noqa: E501
"""The hybrid extractor for eval.run: rules for everything they answer, the local model
(core/shiori_core/extract/llm.py) for eligibility, deadlines and required_documents.

    uv run python -m eval.run --split dev --extractor hybrid [--docs f19cddbd 136dfba9]
    uv run python -m eval.hybrid --unlabeled 5     # first 3 items of each list, on stdout only

Starts one llama-server on 127.0.0.1 (Qwen3.5-9B Q4_K_M, the path of
eval/reports/model_loadcheck.md) on first use and stops it when the run ends. It refuses to
start when any llama-server runs or the port is taken: one local model at a time.

Dev-time only. No cloud call. Reports hold counts and seconds, never document text.
"""

import argparse
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from shiori_core.extract import llm
from shiori_core.extract.rules import extract as rules_extract
from shiori_core.fields import BY_ID
from shiori_core.models import Sentence

from collector.manifest import ManifestRow
from eval.silver.model import Candidate

MODEL = Path("models/Qwen3.5-9B-Q4_K_M.gguf")
PORT = 8792
CTX = 16384
LOG = Path("data/cache/hybrid/server.log")
REPORTS = Path("eval/reports")

# Said next to every number (the user's overfitting guard).
GUARD = (
    "**Not a generalization number.** The prompts, the retrieval window and the examples were tuned "
    "on the same dev documents this is scored on (the prompt examples now come from unlabeled dev "
    "documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one "
    "of the two labelers that made the candidates they were reviewed from (D-50), so every score here "
    "is optimistic."
)


class Server:
    def __init__(self) -> None:
        busy = subprocess.run(
            ["pgrep", "-x", "llama-server"], capture_output=True, text=True
        )
        if busy.stdout.strip():
            raise RuntimeError(
                f"a llama-server is already running (pid {busy.stdout.split()[0]})"
            )
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", PORT)) == 0:
                raise RuntimeError(f"port {PORT} is in use")
        from eval.model_feasibility import EXTRA_ARGS

        LOG.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "llama-server", "-m", str(MODEL), "--host", "127.0.0.1", "--port", str(PORT),
            "-c", str(CTX), "-np", "1", "--reasoning", "off", "--no-webui", "-ngl", "99",
            *next((a for k, a in EXTRA_ARGS.items() if k in MODEL.name), []),
        ]  # fmt: skip
        self.proc = subprocess.Popen(
            cmd, stdout=open(LOG, "w"), stderr=subprocess.STDOUT
        )
        print(f"llama-server pid {self.proc.pid} on 127.0.0.1:{PORT}", flush=True)
        t0 = time.time()
        while time.time() - t0 < 600:
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server exited while loading")
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", PORT)) == 0:
                    try:
                        import urllib.request

                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{PORT}/health", timeout=2
                        ) as r:
                            if r.status == 200:
                                return
                    except OSError:
                        pass
            time.sleep(1)
        self.stop()
        raise RuntimeError("llama-server not ready in 600 s")

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        print(f"llama-server pid {self.proc.pid} stopped", flush=True)


class State:
    server: Server | None = None
    client: llm.Client | None = None
    stats: list[tuple[str, llm.CallStat]] = []  # (doc id prefix, call)
    doc_seconds: dict[str, float] = {}  # doc id prefix -> seconds of the model calls
    outputs: dict[str, dict[str, Candidate]] = {}  # doc id -> field -> answer


def extract(row: ManifestRow, sentences: list[Sentence]) -> dict[str, Candidate]:
    """eval.run Extractor: rules first, the model for the three list fields."""
    if State.server is None:
        State.server = Server()
        State.client = llm.Client(PORT)
    assert State.client is not None
    stats: list[llm.CallStat] = []
    found = {**rules_extract(row.doc_type, sentences), **llm.extract_lists(row.doc_type, sentences, State.client.complete, stats)}  # fmt: skip
    out = {f: Candidate(f, x.status, x.value_ja, None, x.normalized or None, x.citations) for f, x in found.items()}  # fmt: skip
    State.stats += [(row.doc_id[:12], s) for s in stats]
    State.doc_seconds[row.doc_id[:12]] = sum(s.seconds for s in stats)
    State.outputs[row.doc_id] = out
    return out


def stop() -> None:
    if State.server is not None:
        State.server.stop()
        State.server = None


# --- the report ---------------------------------------------------------------------------------


def pct(n: int, m: int) -> str:
    return f"{n} of {m} ({100 * n / m:.0f}%)" if m else "- (0 of 0)"


def item_totals(rows: list[ManifestRow], dirs: list[Path], outputs: dict[str, dict[str, Candidate]]) -> dict[str, list[int]]:  # fmt: skip
    """field -> [answer items paired with a label item, label items, answer items], summed
    over the documents, pairing as eval.silver.compare.item_pairs does."""
    from eval.run import read_labels
    from eval.silver import compare

    tot = {f: [0, 0, 0] for f in llm.LIST_FIELDS}
    for r in rows:
        gold = read_labels(r.doc_id, dirs) or {}
        for f in llm.LIST_FIELDS:
            if f in gold and r.doc_type in BY_ID[f].applies_to:
                c = outputs.get(r.doc_id, {}).get(f) or Candidate(f)
                for k, v in enumerate(
                    compare.item_pairs(f, c, compare.gold_of(gold[f]))
                ):
                    tot[f][k] += v
    return tot


def whole_field(recs: list[dict]) -> dict[str, list[int]]:
    """field -> [value correct, verified, asked]."""
    out = {f: [0, 0, 0] for f in llm.LIST_FIELDS}
    for r in recs:
        if r["field"] in out:
            out[r["field"]][0] += r["value_ok"]
            out[r["field"]][1] += r["verified_ok"]
            out[r["field"]][2] += 1
    return out


def write_report(rep: dict, rows: list[ManifestRow], dirs: list[Path]) -> Path:
    from eval.documents import load_sentences
    from eval.run import evaluate, rules_extractor

    scored = [r for r in rows if r.doc_id[:12] in rep["documents"]]
    mine = item_totals(scored, dirs, State.outputs)
    rrecs, _ = evaluate(scored, dirs, rules_extractor, load_sentences)
    rules_items = item_totals(scored, dirs, {})
    wf_h, wf_r = whole_field(rep["records"]), whole_field(rrecs)

    def sums(d: dict[str, list[int]]) -> list[int]:
        return [sum(v[k] for v in d.values()) for k in range(3)]

    (hp, hg, ha), (_, rg, _) = sums(mine), sums(rules_items)
    wh, wr = sums(wf_h), sums(wf_r)
    proposed = sum(s.proposed for _, s in State.stats)
    kept = sum(s.kept for _, s in State.stats)
    reasons: dict[str, int] = {}
    for _, s in State.stats:
        for k, v in s.dropped.items():
            reasons[k] = reasons.get(k, 0) + v
    failed = [s for _, s in State.stats if s.call_failed]
    calls = [
        (d, s) for d, s in State.stats if s.sentences_sent
    ]  # a field with nothing retrieved makes no call
    secs = [s.seconds for _, s in calls]
    docs = max(len(rep["documents"]), 1)
    model_time = sum(State.doc_seconds.values())

    L = [
        f"# Hybrid extractor: list fields ({rep['name']})", "",
        f"Rules for everything they answer, `{MODEL.name}` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `{rep['split']}`, {len(rep['documents'])} documents scored, extractor version {rep['extractor_version']}, schema {rep['schema_version']}, {rep['date']}. Retrieval: sections whose heading holds a field cue plus {llm.WINDOW} sentences each side, at most {llm.BUDGET} characters; one call per field; JSON-schema output; every item checked against its cited sentences.",  # fmt: skip
        "", GUARD, "",
        "## The three list fields, hybrid against the rules extractor and the grouped bake-off", "",
        GUARD, "",
        "| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |",  # fmt: skip
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        f"| hybrid (rules + model) | {pct(hp, ha)} | {pct(hp, hg)} | {pct(wh[0], wh[2])} | {pct(wh[1], wh[2])} | {pct(proposed - kept, proposed)} | {model_time / docs:.0f} (model calls only) | {sum(secs) / len(secs) if secs else 0:.0f} |",  # fmt: skip
        f"| rules only (0 items by design) | - (0 items given) | {pct(0, rg)} | {pct(wr[0], wr[2])} | {pct(wr[1], wr[2])} | - | 0 | - |",
        "| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |",  # fmt: skip
        "",
        f"Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator ({wh[2]} fields here).",  # fmt: skip
        "",
        f"Calls: {len(calls)} calls ({sum(s.retries for _, s in calls)} retried), {len(failed)} not found after the retry ({', '.join(sorted({s.call_failed or '' for s in failed})) or 'none'}). Items proposed {proposed}, kept {kept}; dropped by reason: " + (", ".join(f"{k} {v}" for k, v in sorted(reasons.items())) or "none") + ".",  # fmt: skip
        "",
        "## By field", "", GUARD, "",
        "| field | item precision | item recall | whole-field (value correct) | whole-field verified |", "| --- | --- | --- | --- | --- |",  # fmt: skip
    ]  # fmt: skip
    for f in llm.LIST_FIELDS:
        p, g, a = mine[f]
        L.append(f"| {f} | {pct(p, a)} | {pct(p, g)} | {pct(wf_h[f][0], wf_h[f][2])} | {pct(wf_h[f][1], wf_h[f][2])} |")  # fmt: skip
    L += ["", "## By document", "", GUARD, "", "| document | type | model seconds | items paired / label items / answer items | dropped items |", "| --- | --- | --- | --- | --- |"]  # fmt: skip
    for r in scored:
        d = r.doc_id[:12]
        one = item_totals([r], dirs, State.outputs)
        dr = sum(sum(s.dropped.values()) for k, s in State.stats if k == d)
        L.append(f"| {d} | {r.doc_type} | {State.doc_seconds.get(d, 0):.0f} | {sum(v[0] for v in one.values())} / {sum(v[1] for v in one.values())} / {sum(v[2] for v in one.values())} | {dr} |")  # fmt: skip
    L += ["", "## Calls", "", "| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for d, s in calls:
        L.append(f"| {d} | {s.field} | {s.sentences_sent} | {s.seconds:.0f} | {s.retries} | {s.proposed} | {s.kept} | {', '.join(f'{k} {v}' for k, v in s.dropped.items()) or s.call_failed or '-'} |")  # fmt: skip
    L += ["", "## What this does not tell you", "",
          "- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).",  # fmt: skip
          "- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.",
          "- Documents that are not notice-like (specs) have no list fields and are not counted.", ""]  # fmt: skip
    p = REPORTS / f"hybrid_{rep['name']}.md"
    p.write_text("\n".join(L))
    save_trace(rep["name"])
    print(f"wrote {write_diagnostic(rep, scored, dirs)}")
    return p


TRACES = Path("data/cache/hybrid")  # gitignored; holds the model's items, so local only


def save_trace(name: str) -> Path:
    """The calls of this run (ids, verdicts and the model's items) for `--diagnose`."""
    import dataclasses
    import json

    TRACES.mkdir(parents=True, exist_ok=True)
    p = TRACES / f"trace_{name}.json"
    p.write_text(
        json.dumps(
            [[d, dataclasses.asdict(s)] for d, s in State.stats], ensure_ascii=False
        )
    )
    return p


def load_trace(name: str) -> None:
    import json

    State.stats = [(d, llm.CallStat(**{**s, "trace": [tuple(t) for t in s["trace"]]})) for d, s in json.loads((TRACES / f"trace_{name}.json").read_text())]  # fmt: skip


def traced_rows(rows: list[ManifestRow]) -> list[ManifestRow]:
    """Only the documents the loaded trace has calls for: `--diagnose` on a run of a
    subset must not count the other labeled documents as category a (no window sent)."""
    seen = {d for d, _ in State.stats}
    return [r for r in rows if r.doc_id[:12] in seen]


# --- diagnostic: why was each label item missed or wrong (measurement only) ------------------------

CATEGORIES = {
    "hit": "paired with a kept answer item (not missed)",
    "a": "its sentence was not in the retrieved window",
    "b": "in the window, but the model did not produce it",
    "c": "produced, then dropped by a verification check",
    "d": "produced (kept or dropped) but the value or kind is wrong",
}


SUBCAUSES = {
    "d1": "same sentence, different kind",
    "d2": "same sentence, different polarity",
    "d3": "different split of the same text",
    "d4": "wrong sentence (the answer item is built on another sentence)",
    "d5": "wrong value (datetime, flags or name)",
}


def subcause(field: str, g: dict, cands: list[dict]) -> tuple[str, str]:
    """(sub-cause, "convention" or "real") for a label item and the answer items that share
    a cited sentence with it, read side by side. Convention = the two readings are both
    defensible or the label predates the written guide rule; real = the answer breaks a
    written rule or misses the evidence."""
    from eval.silver.agree import _NEGATION_END, _n, similar
    from eval.silver.config import FUZZY_LONG, FUZZY_SHORT

    key = llm.TEXT_KEY.get(field)
    if key:
        tg = _n(g.get(key))
        thr = FUZZY_LONG if field == "eligibility" else FUZZY_SHORT
        parts = [p for p in cands if _n(p.get(key)) and _n(p[key]) != tg and (_n(p[key]) in tg or tg in _n(p[key]))]  # fmt: skip
        if (
            parts
        ):  # the same text cut differently: a part of it, or it inside a longer one
            return "d3", "real"
        same = next((p for p in cands if similar(p.get(key), g.get(key), thr)), None)
        if same is None:
            return "d4", "real"
        if same.get("kind") != g.get("kind"):
            return (
                "d1",
                "convention",
            )  # legal or other, the guide does not draw the line
        if same.get("polarity") != g.get("polarity"):
            kept = _NEGATION_END.search(re.sub(r"[。．.]+$", "", _n(same.get(key))))
            return (
                "d2",
                "convention" if kept else "real",
            )  # sv4: a kept negation is a requirement
        return "d5", "real"
    p = max(
        cands,
        key=lambda p: len(set(p.get("citations", [])) & set(g.get("citations", []))),
    )
    if p.get("datetime") != g.get("datetime") or p.get("relative_text") != g.get(
        "relative_text"
    ):
        return "d5", "real"
    if p.get("kind") != g.get("kind"):
        return "d1", "convention" if g.get(
            "kind"
        ) == "other" else "real"  # a label of other predates the electronic rule
    return "d5", "real"  # flags: the 必着 sentence was not cited


def classify(
    field: str, gold_items: list[dict], stat: llm.CallStat | None
) -> list[tuple[str, str]]:
    """(category, detail) for each label item, in order. Kept answer items are paired with
    label items first, as compare.item_pairs does; for what is left: a proposal that would
    pair but was dropped is c (detail: the check); one that shares a cited sentence but does
    not pair is d (detail: which parts differ); else a when no cited sentence was sent, b when
    one was."""
    from eval.silver.agree import ACTIVE, item_same

    props = list(stat.trace) if stat else []
    sent = set(stat.retrieved) if stat else set()
    free = list(range(len(gold_items)))
    used: set[int] = set()
    out: dict[int, tuple[str, str]] = {}

    def same(p: dict, g: dict) -> bool:
        try:
            return bool(item_same(field, p, g, ACTIVE))
        except (AttributeError, TypeError, KeyError):
            return False

    for k, (p, v) in enumerate(props):
        if (
            v == "kept"
            and (g := next((i for i in free if same(p, gold_items[i])), None))
            is not None
        ):
            free.remove(g)
            used.add(k)
            out[g] = ("hit", "")
    for g in free:
        gi = gold_items[g]
        cites = set(gi.get("citations", []))
        c = next(
            (
                v
                for k, (p, v) in enumerate(props)
                if k not in used and v != "kept" and same(p, gi)
            ),
            None,
        )
        if c is not None:
            out[g] = ("c", c)
            continue
        near = [p for k, (p, v) in enumerate(props) if k not in used and cites & set(p.get("citations", []))]  # fmt: skip
        if near:
            sub, kind = subcause(field, gi, near)
            out[g] = ("d", f"{sub} {kind}")
            continue
        out[g] = ("a", "") if not cites & sent else ("b", "")
    return [out[i] for i in range(len(gold_items))]


def write_diagnostic(rep: dict, rows: list[ManifestRow], dirs: list[Path]) -> Path:
    from eval.run import read_labels

    cat = {
        f: {k: [] for k in CATEGORIES} for f in llm.LIST_FIELDS
    }  # field -> category -> [(item id, ids, detail)]
    extra = {f: 0 for f in llm.LIST_FIELDS}  # answer items that pair with no label item
    for r in rows:
        gold = read_labels(r.doc_id, dirs) or {}
        for f in llm.LIST_FIELDS:
            if f not in gold or r.doc_type not in BY_ID[f].applies_to:
                continue
            items = (
                (gold[f].get("normalized") or {}).get("items", [])
                if gold[f]["status"] == "present"
                else []
            )
            stat = next(
                (s for d, s in State.stats if d == r.doc_id[:12] and s.field == f), None
            )
            for n, (c, detail) in enumerate(classify(f, items, stat), 1):
                cat[f][c].append(
                    (
                        f"{r.doc_id[:12]}/{f}#{n}",
                        items[n - 1].get("citations", []),
                        detail,
                    )
                )
            if stat:
                extra[f] += stat.kept - sum(
                    c == "hit" for c, _ in classify(f, items, stat)
                )
    d = REPORTS / f"hybrid_diagnostic_{rep['name']}.md"
    total = {f: sum(len(v) for v in cat[f].values()) for f in llm.LIST_FIELDS}
    L = [f"# Hybrid extractor: why label items were missed ({rep['name']})", "", GUARD, "",
         "Measurement only: no prompt, retrieval window or check was changed for this table. One row per label item of the three list fields on the scored dev documents. Item ids are `<doc id prefix>/<field>#<n>`, n counting the label file's items from 1; only sentence ids are shown, no document text.", "",
         "Order of the tests: a kept answer item that pairs with the label item (hit); else a dropped one that would have paired (c); else an answer item citing a shared sentence that does not pair (d); else a if none of the label item's sentences was sent, b if one was.", "",
         "| field | label items | hit | a: not in window | b: not produced | c: dropped by a check | d: wrong value or kind | answer items with no label item |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for f in llm.LIST_FIELDS:
        L.append(
            f"| {f} | {total[f]} | "
            + " | ".join(str(len(cat[f][k])) for k in CATEGORIES)
            + f" | {extra[f]} |"
        )
    L.append("| all | " + str(sum(total.values())) + " | " + " | ".join(str(sum(len(cat[f][k]) for f in llm.LIST_FIELDS)) for k in CATEGORIES) + f" | {sum(extra.values())} |")  # fmt: skip
    L += ["", "## Category c by check", ""]
    for f in llm.LIST_FIELDS:
        by: dict[str, int] = {}
        for _, _, det in cat[f]["c"]:
            by[det] = by.get(det, 0) + 1
        L.append(
            f"- {f}: "
            + (", ".join(f"{k} {v}" for k, v in sorted(by.items())) or "none")
        )
    L += ["", "## Category d by sub-cause", "",
          "Read side by side: the label item and the answer items that share a cited sentence with it. Cells: count (convention / real).", "",
          "| sub-cause | " + " | ".join(llm.LIST_FIELDS) + " | all |", "| --- | --- | --- | --- | --- |"]  # fmt: skip
    for sc, name in SUBCAUSES.items():
        cells, tot = [], [0, 0, 0]
        for f in llm.LIST_FIELDS:
            hits = [x for x in cat[f]["d"] if x[2].startswith(sc)]
            n = [sum(x[2].endswith(w) for x in hits) for w in ("convention", "real")]
            tot = [tot[0] + len(hits), tot[1] + n[0], tot[2] + n[1]]
            cells.append(f"{len(hits)} ({n[0]} / {n[1]})")
        L.append(
            f"| {sc} {name} | "
            + " | ".join(cells)
            + f" | {tot[0]} ({tot[1]} / {tot[2]}) |"
        )
    for sc in SUBCAUSES:
        for f in llm.LIST_FIELDS:
            hits = [x for x in cat[f]["d"] if x[2].startswith(sc)][:3]
            if hits:
                L.append(f"- {sc} {f}: " + "; ".join(f"`{i}` sentences {', '.join(ids)} ({det.split()[1]})" for i, ids, det in hits))  # fmt: skip
    L += ["", "Convention or real error, with the reasoning:",
          "- d1 kind, eligibility: convention. Whether a rule about a stated officer qualification (予算決算及び会計令第73条) or a tax arrears rule is `legal` or `other` is not settled by the field table, and the labels disagree with each other. d1 kind, deadlines: convention only when the label says `other` (those labels predate the rule that a bid receipt on an electronic notice is `electronic`); otherwise real, because the answer cited one sentence and missed the one with 到着 or 質問.",  # fmt: skip
          "- d2 polarity: convention when the answer text keeps its negation (...ないこと): the guide says that is a requirement, and the older labels say disqualification. Real when the text names the bad state (暴力団... 者) under a header that says none of them may apply: the guide says disqualification.",  # fmt: skip
          "- d3 split: real against the written rule (the なお or ただし sentence stays inside the 第70条 item with both ids), although the reader loses little. The label side is consistent with the guide.",  # fmt: skip
          "- d4 wrong sentence: real. The label lists each item of an ア to ケ list with the header sentence and its own sentence; the answer made one item from the header only and none from the list items, so those label items are misses that share only the header sentence.",  # fmt: skip
          "- d5 wrong value: real. The label's 必着 comes from a second sentence the answer did not cite; flags are read from the cited sentences only.",  # fmt: skip
          "These readings are mine, not a native speaker's. The calls that need a Japanese reader are the legal-or-other split in d1 and the sentences behind d4.", ""]  # fmt: skip
    L += [
        "",
        "## Examples (first three per field and category, spread over documents)",
        "",
    ]
    for f in llm.LIST_FIELDS:
        for k in ("a", "b", "c", "d"):
            seen_docs: set[str] = set()
            pick = [x for x in cat[f][k] if not (x[0].split("/")[0] in seen_docs or seen_docs.add(x[0].split("/")[0]))][:3]  # fmt: skip
            pick += [x for x in cat[f][k] if x not in pick][: 3 - len(pick)]
            L.append(f"- {f}, {k} ({CATEGORIES[k]}): " + ("; ".join(f"`{i}` sentences {', '.join(ids)}" + (f" ({det})" if det else "") for i, ids, det in pick) or "none"))  # fmt: skip
    d.write_text("\n".join(L) + "\n")
    return d


# --- unlabeled sample (stdout only) ---------------------------------------------------------------


def show(rows: list[ManifestRow], sentences_of) -> None:
    """The first 3 items of each list field per document, to stdout only (never a file)."""
    for r in rows:
        if r.doc_id not in State.outputs:
            continue
        by_id = {s.id: s for s in sentences_of(r)}
        out = State.outputs[r.doc_id]
        print(f"\n=== {r.doc_id[:12]} ({r.doc_type})")
        for f in llm.LIST_FIELDS:
            items = (out[f].normalized or {}).get("items", []) if f in out else []
            print(f"-- {f}: {len(items)} items" if items else f"-- {f}: not found")
            for it in items[:3]:
                text = it.get("text_ja") or it.get("name_ja") or " / ".join(by_id[i].text_orig for i in it["citations"])  # fmt: skip
                extra = f" kind={it['kind']} when={it.get('datetime') or it.get('relative_text')} flags={it['flags']}" if f == "deadlines" else ""  # fmt: skip
                print(f"   {r.doc_id[:8]} {f} {it['citations']}{extra} | {text}")
        for d, s in State.stats:
            if d == r.doc_id[:12]:
                print(f"   call {s.field}: {s.seconds:.0f}s, sent {s.sentences_sent}, proposed {s.proposed}, kept {s.kept}, dropped {s.dropped}, failed {s.call_failed}")  # fmt: skip


def unlabeled(n: int) -> None:
    from eval.documents import load_sentences
    from eval.run import label_dirs, read_labels
    from eval.silver import run

    dirs = label_dirs("dev")
    rows = [r for r in run.select("dev", open_only=True) if r.doc_type in BY_ID["deadlines"].applies_to and read_labels(r.doc_id, dirs) is None][:n]  # fmt: skip
    try:
        for r in rows:
            extract(r, [s for s in load_sentences(r) if s.language == "ja"])
        show(rows, lambda r: [s for s in load_sentences(r) if s.language == "ja"])
    finally:
        stop()


# --- freeze: tie a later hold-out score to this exact version ---------------------------------------

FROZEN_FILES = (
    "core/shiori_core/extract/llm.py",
    "core/shiori_core/extract/rules.py",
    "core/shiori_core/fields.py",
    "core/shiori_core/value_normalize.py",
    "eval/hybrid.py",
)


def freeze(name: str) -> Path:
    """eval/reports/hybrid_freeze_<name>.md: git blob ids and SHA-256 of the files, a hash
    of every prompt as sent (with no sentences) and of every schema, the retrieval settings
    and the model file. `git hash-object` is the id git gives the file once it is committed,
    so the ids hold only while the files stay as they are."""
    import hashlib
    import json

    def sha(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()

    def blob(f: str) -> str:
        return subprocess.run(["git", "hash-object", f], capture_output=True, text=True, check=True).stdout.strip()  # fmt: skip

    h = hashlib.sha256()
    with open(MODEL, "rb") as m:
        while chunk := m.read(1 << 24):
            h.update(chunk)
    ver = subprocess.run(["llama-server", "--version"], capture_output=True, text=True)
    L = [f"# Frozen hybrid extractor ({name})", "", "A hold-out score is tied to this version only if every hash below still matches. " + GUARD, "",
         "## Files", "", "`eval/hybrid.py` is the harness (calls, diagnostic, this record); the extraction itself is llm.py, rules.py, fields.py and value_normalize.py. llm.py, rules.py and fields.py were not edited between the scored run and this record; hybrid.py gained this command after the run.", "", "| file | git blob id (`git hash-object`) | SHA-256 |", "| --- | --- | --- |"]  # fmt: skip
    L += [
        f"| `{f}` | `{blob(f)}` | `{sha(Path(f).read_bytes())}` |" for f in FROZEN_FILES
    ]
    L += ["", "## Prompts as sent (no sentences) and schemas", "", "| field | prompt SHA-256 | schema SHA-256 |", "| --- | --- | --- |"]  # fmt: skip
    L.append(f"| system message | `{sha(llm.SYSTEM.encode())}` | |")
    for f in llm.LIST_FIELDS:
        L.append(f"| {f} | `{sha(llm.prompt(f, []).encode())}` | `{sha(json.dumps(llm.schema_for(f), sort_keys=True).encode())}` |")  # fmt: skip
    L += ["", "## Settings", "",
          f"- retrieval: window {llm.WINDOW} sentences, budget {llm.BUDGET} characters, extra cues {llm.EXTRA_CUES}, heading cues {llm.HEADING_CUES}",  # fmt: skip
          f"- call: max {llm.MAX_OUT} tokens, timeout {llm.TIMEOUT:.0f} s, one retry, temperature 0, schema bounds {llm.MAX_ITEMS} items and {llm.MAX_CITES} citations",  # fmt: skip
          f"- model: `{MODEL.name}`, {MODEL.stat().st_size} bytes, SHA-256 `{h.hexdigest()}`; context {CTX}",
          f"- llama-server: {next((x for x in (ver.stdout + ver.stderr).splitlines() if x.startswith('version:')), 'unknown')}",  # fmt: skip
          f"- score this freeze belongs to: `eval/reports/hybrid_{name}.md` and `eval/reports/hybrid_diagnostic_{name}.md`", ""]  # fmt: skip
    p = REPORTS / f"hybrid_freeze_{name}.md"
    p.write_text("\n".join(L))
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval.hybrid")
    ap.add_argument("--unlabeled", type=int, help="dev documents with no label file")
    ap.add_argument(
        "--freeze", help="write the freeze record (hashes) for a finished run name"
    )
    ap.add_argument("--diagnose", help="rewrite the diagnostic of a finished run from its saved trace")  # fmt: skip
    a = ap.parse_args(argv)
    if a.diagnose:
        from eval.run import label_dirs
        from eval.silver import run

        load_trace(a.diagnose)
        print(f"wrote {write_diagnostic({'name': a.diagnose}, traced_rows(run.select('dev')), label_dirs('dev'))}")  # fmt: skip
    elif a.freeze:
        print(f"wrote {freeze(a.freeze)}")
    elif a.unlabeled:
        unlabeled(a.unlabeled)
    else:
        ap.error("give --unlabeled N, --diagnose NAME or --freeze NAME")
    return 0


if __name__ == "__main__":
    sys.exit(main())
