# ruff: noqa: E501
"""The pilot report for the current prompt version (eval/reports/silver_pilot_<prompt>.md),
rebuilt from the caches with no API call.

Comparison mode: documents that already have labels (made with an earlier prompt) are
never resolved again. Each labeler's answers to them are scored field by field against
those labels (score), which serve as pseudo-gold. Documents labeled for real in the
same run are reported without gold: agreement, flags, and what each labeler cost."""

import json
import math
from pathlib import Path

from shiori_core.fields import BY_ID

from collector.manifest import ManifestRow
from eval.silver import config
from eval.silver.agree import agree
from eval.silver.checks import BLOCKING, failed
from eval.silver.config import PROMPT_VERSION, PROVIDERS, SPOT_CHECK_PERCENT, TIER1
from eval.silver.model import Candidate, canonical
from eval.silver.pipeline import (
    Resolved,
    answers,
    labeled_by_earlier_prompt,
    load_raw,
    raw_state,
    read_resolved,
)
from eval.silver.prompt import applicable_fields, focused_fields

REPORT = Path(f"eval/reports/silver_pilot_{PROMPT_VERSION}.md")
KINDS = ("list", "structured", "text")
# Groq real / estimated tokens (input, output) measured in the sv2 pilot
# (eval/reports/silver_pilot_sv2.md, 15 requests), and its share of parts that came back
# json_validate_failed (4 of 19). sv3 makes no Groq call in its pilot.
GROQ_RATIO = (1.06, 0.75)
GROQ_FAIL_RATE = 4 / 19
SINGLE_SPOT_PERCENT = 10  # spot-check of fields the single-source rule would settle


def gold_of(line: dict) -> Candidate:
    return Candidate(line["field"], line["status"], line.get("value_ja"), line.get("value_en"),
                     line.get("normalized"), line.get("citations", []))  # fmt: skip


def cached(row: ManifestRow, prompt: str | None = None, first_sent: bool = False,
           local_prompt: str | None = None) -> dict[str, dict]:  # fmt: skip
    """Every raw answer cached for the document with this prompt version (default: the
    report's, PROMPT_VERSION), by labeler name (gemini, groq, or the local model's
    name). `local_prompt`: the local model's answers of another version (sv3-l1, D-53).
    `first_sent`: the local model's answers before their repair (D-52)."""
    from eval.silver import pipeline

    prompt = prompt or pipeline.PROMPT_VERSION
    d = config.CACHE / "raw" / row.doc_id
    out = {}
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        provider, _, version = p.name.split("__")[:3]
        if version != ((local_prompt or prompt) if provider == "local" else prompt):
            continue
        raw = load_raw(p)
        local = raw.get("provider") == "local"
        out[raw["model"] if local else raw["provider"]] = before_repair(raw) if local and first_sent else raw  # fmt: skip
    return out


def before_repair(raw: dict) -> dict:
    """The raw answer as first sent: each repaired part's first answer (D-52), and for
    a part repaired from the cache its time and tokens without the repair request."""

    def first(c: dict) -> dict:
        rep = c.get("repair") or {}
        if not rep.get("first_response"):
            return c
        out = {k: v for k, v in c.items() if k != "repair"}
        out["response"] = rep["first_response"]
        if "seconds" in rep:
            out.update(seconds=round(c["seconds"] - rep["seconds"], 1),
                       tokens_in=c["tokens_in"] - rep["tokens_in"],
                       tokens_out=c["tokens_out"] - rep["tokens_out"])  # fmt: skip
        return out

    return {**raw, "chunks": {i: first(c) for i, c in raw["chunks"].items()}}


def candidates(row: ManifestRow, raw: dict) -> dict[str, Candidate]:
    from eval.silver import run

    by_id = {s.id: s for s in run.load_sentences(row)}
    return answers(raw, f"{raw['provider']}/{raw['model']}", applicable_fields(row.doc_type), by_id)  # fmt: skip


def score(row: ManifestRow, cands: dict[str, Candidate], gold: dict[str, dict]) -> list[tuple[str, bool]]:  # fmt: skip
    """(field, matches) for every field asked of the document's type that has a label.
    Matches = the consensus agreement rule (agree.agree with the active relaxations):
    this answer would have been accepted beside the label. An answer that did not parse
    never matches."""
    out = []
    for f in applicable_fields(row.doc_type):
        if f in gold:
            c = cands.get(f)
            out.append((f, c is not None and not c.parse_error and agree(c, gold_of(gold[f]))[0]))  # fmt: skip
    return out


def item_ids() -> dict[tuple[str, str], str]:
    """(doc_id, field) -> review item id, from the export registry."""
    p = config.CACHE / "export" / "ids.json"
    reg = json.loads(p.read_text())["items"] if p.exists() else {}
    return {(m["doc_id"], m["field"]): i for i, m in sorted(reg.items())}


def seconds(raw: dict) -> float | None:
    s = [c.get("seconds") for c in raw["chunks"].values()]
    return sum(s) if s and all(v is not None for v in s) else None  # type: ignore[arg-type]


# --- sections --------------------------------------------------------------------------


def first_sent_and_sv1(row: ManifestRow) -> dict[str, dict]:
    """This prompt's answers (the local model's as first sent), plus Groq's sv1 answers
    as a reference row."""
    named = {k: v for k, v in cached(row, first_sent=True).items() if k != "groq"}
    if "groq" in (sv1 := cached(row, "sv1")):
        named["groq (sv1, reference)"] = sv1["groq"]
    return named


def local_before_after(row: ManifestRow) -> dict[str, dict]:
    """The local model's answers as first sent and after the repair (D-52)."""
    named = {}
    for k, raw in cached(row).items():
        if k not in PROVIDERS:
            named[f"{k}, as first sent"] = before_repair(raw)
            named[f"{k}, after repair"] = raw
    return named


def comparison_lines(rows: list[ManifestRow], labelers=first_sent_and_sv1) -> list[str]:
    """Each labeler (`labelers(row)`: name -> raw answer) against the labels of the
    documents in comparison mode."""
    ids = item_ids()
    tally: dict[str, dict] = {}
    for row in rows:
        gold = read_resolved(row.doc_id)
        reviewed = {f for f, g in gold.items() if g["provenance"].get("reviewed_by")}
        for name, raw in labelers(row).items():
            t = tally.setdefault(name, {k: [0, 0] for k in KINDS} | {"miss": [], "incomplete": []})  # fmt: skip
            if raw_state(raw) != "complete":
                t["incomplete"].append(row.doc_id[:12])
                continue
            for f, ok in score(row, candidates(row, raw), gold):
                cell = t[BY_ID[f].kind]
                cell[0] += ok
                cell[1] += 1
                if not ok:
                    src = (
                        ids.get((row.doc_id, f), "?") if f in reviewed else "consensus"
                    )
                    t["miss"].append(f"{row.doc_id[:6]} {f} ({src})")
    out = [
        "| labeler | list | structured | text | all fields |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, t in tally.items():
        m = sum(t[k][0] for k in KINDS)
        n = sum(t[k][1] for k in KINDS)
        out.append(f"| {name} | " + " | ".join(f"{t[k][0]} of {t[k][1]}" for k in KINDS)
                   + f" | {m} of {n} ({100 * m / max(1, n):.0f}%) |")  # fmt: skip
    out.append("")
    for name, t in tally.items():
        out.append(f"- {name}, mismatches ({len(t['miss'])}): {', '.join(t['miss']) or '-'}"
                   + (f"; no complete answer for {', '.join(t['incomplete'])}" if t["incomplete"] else ""))  # fmt: skip
    return out


def gemini_lines(rows: list[ManifestRow]) -> list[str]:
    out = [
        "| document | requests | answer valid as first sent | repair | problems before / after repair | tokens in / out | state |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        raw = cached(row).get("gemini")
        if raw is None:
            continue
        for c in raw["chunks"].values():
            rep = c.get("repair")
            fix = (
                "-"
                if not rep
                else (
                    "failed: " + rep["failed"]
                    if "failed" in rep
                    else f"kept {rep['kept']}"
                )
            )
            counts = (
                "-"
                if not rep
                else f"{len(rep['errors'])} / {len(rep.get('errors_after', rep['errors']))}"
            )
            out.append(f"| {row.doc_id[:12]} | {c.get('attempts', '-')} | {'no' if rep else ('yes' if c['status'] == 'ok' else '-')} | "
                       f"{fix} | {counts} | {c.get('tokens_in', '-')} / {c.get('tokens_out', '-')} | {c['status']}"
                       + (f": {c['error']}" if c.get("error") else "") + " |")  # fmt: skip
    errs = sorted({e.split(":")[0] + ": " + e.split(":", 1)[1].strip()[:80] for row in rows
                   for c in (cached(row).get("gemini") or {"chunks": {}})["chunks"].values()
                   for e in (c.get("repair") or {}).get("errors", [])})  # fmt: skip
    if errs:
        out += [
            "",
            "Problems the shape check found in first answers:",
            *[f"- {e}" for e in errs],
        ]
    return out


def local_lines(rows: list[ManifestRow]) -> list[str]:
    """The local model's answers as first sent (the repair has its own table)."""
    out = [
        "| document | model | fields | parts | output cap per part | time | tokens out | truncated parts | JSON failures | state |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        for name, raw in cached(row, first_sent=True).items():
            if name in PROVIDERS:
                continue
            ch = list(raw["chunks"].values())
            t = seconds(raw)
            cut = sum(bool(c.get("truncated")) for c in ch)
            bad = sum("invalid JSON" in (c.get("error") or "") for c in ch)
            caps = sorted({c.get("max_out") for c in ch if c.get("max_out")})
            out.append(f"| {row.doc_id[:12]} | {name} | {len(applicable_fields(row.doc_type))} | {len(ch)} | "
                       f"{', '.join(map(str, caps)) or '-'} | {f'{t:.0f} s' if t is not None else '-'} | "
                       f"{sum(c.get('tokens_out') or c.get('tokens_out_cut') or 0 for c in ch):,} | {cut} | {bad} | {raw_state(raw)} |")  # fmt: skip
    return out


def single_source(r: Resolved) -> bool:
    """The single-source rule, a projection only (not implemented, D-52): a flagged tier
    2 field where Gemini (side A) passes every blocking check and gives one answer for
    the whole document, and the local model (side B) still fails a blocking check after
    its repair. Tier 1 fields are never settled this way."""
    if r.state != "flagged" or r.field in TIER1 or len(r.sides) != 2:
        return False
    a, b = r.sides
    return (not failed(a["checks"], BLOCKING) and not a["candidate"].get("alternatives")
            and bool(failed(b["checks"], BLOCKING)))  # fmt: skip


def label_agrees(side: dict, gold: dict) -> bool | None:
    """Would this side have been accepted beside the existing label? None: no label."""
    if side["field"] not in gold:
        return None
    d = side["candidate"]
    c = Candidate(side["field"], d["status"], d["value_ja"], d["value_en"], d["normalized"], list(d["citations"]))  # fmt: skip
    return agree(c, gold_of(gold[side["field"]]))[0]


def pair_stats(rows: list[ManifestRow], first_sent: bool, local_prompt: str | None = None) -> list[dict]:  # fmt: skip
    """Gemini against the local model on every document where both answered, as resolve
    would see them (`first_sent`: the local answers before their repair). Per document:
    fields asked, agreeing, flagged, review items (flagged + spot-check), and what the
    single-source rule would settle: (field, Gemini's status, does Gemini match the
    existing label), the last None when the field has no label."""
    from eval.silver.run import decide

    out = []
    for row in rows:
        c = cached(row, first_sent=first_sent, local_prompt=local_prompt)
        local = [k for k in c if k not in PROVIDERS]
        if (
            "gemini" not in c
            or not local
            or not all(raw_state(c[k]) == "complete" for k in ("gemini", local[0]))
        ):
            continue
        res, _ = decide(row, [c["gemini"], c[local[0]]], overlap=True)
        asked = [r for r in res if r.state != "rule_absent"]
        mode = "comparison" if labeled_by_earlier_prompt(row.doc_id) else "labeled"
        gold = read_resolved(row.doc_id)  # reviewed labels count wherever they exist
        out.append({
            "doc": row.doc_id[:12], "mode": mode, "asked": len(asked),
            "agree": sum(r.agreement is True for r in asked),
            "flagged": sum(r.state == "flagged" for r in asked),
            "review": sum(r.state == "flagged" or r.spot for r in asked),
            "settle": [(r.field, r.sides[0]["candidate"]["status"],
                        label_agrees({**r.sides[0], "field": r.field}, gold))
                       for r in asked if single_source(r)],
        })  # fmt: skip
    return out


def totals(stats: list[dict]) -> dict:
    t = {"asked": 0, "agree": 0, "flagged": 0, "settle": 0,
         "fresh_asked": 0, "fresh_flagged": 0, "fresh_settle": 0}  # fmt: skip
    for d in stats:
        for k in ("asked", "agree", "flagged"):
            t[k] += d[k]
        t["settle"] += len(d["settle"])
        if d["mode"] == "labeled":
            t["fresh_asked"] += d["asked"]
            t["fresh_flagged"] += d["flagged"]
            t["fresh_settle"] += len(d["settle"])
    return t


def pair_lines(rows: list[ManifestRow]) -> tuple[list[str], dict]:
    """The pair table with the local answers as first sent. Fresh documents also give
    the flag rate."""
    stats = pair_stats(rows, first_sent=True)
    out = [
        "| document | mode | fields asked | agree | agreement | flagged | review items (flagged + spot-check) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for d in stats:
        out.append(
            f"| {d['doc']} | {d['mode']} | {d['asked']} | {d['agree']} | {100 * d['agree'] / max(1, d['asked']):.0f}% | {d['flagged']} | {d['review']} |"
        )
    tot = totals(stats)
    out.append(
        f"| all | | {tot['asked']} | {tot['agree']} | {100 * tot['agree'] / max(1, tot['asked']):.0f}% | {tot['flagged']} | |"
    )
    return out, tot


def dev_field_count() -> int:
    from eval.silver.run import select

    return sum(len(applicable_fields(r.doc_type)) for r in select("dev"))


def review_items(n_fields: int, flag_rate: float, settle_rate: float = 0.0) -> float:
    """Expected review items: the flagged fields the rule leaves, a SINGLE_SPOT_PERCENT
    spot-check of the ones it settles, the consensus spot-check of the accepted ones."""
    return n_fields * (flag_rate - settle_rate + settle_rate * SINGLE_SPOT_PERCENT / 100
                       + (1 - flag_rate) * SPOT_CHECK_PERCENT / 100)  # fmt: skip


def projection_lines(rows: list[ManifestRow], tot: dict) -> list[str]:
    """Days and Mac hours for the whole dev set under sv3, and review items at the
    observed flag rates."""
    from eval.silver.limiter import effective_cfg
    from eval.silver.pipeline import cfg_for, plan_parts
    from eval.silver.run import ja_sentences, price, select

    dev = select("dev")
    open_rows = [r for r in dev if r.license_class == "open"]
    restricted = [r for r in dev if r.license_class != "open"]
    two_groups = [r.doc_id[:12] for r in open_rows
                  if len({tuple(p.field_ids) for p in plan_parts(r, ja_sentences(r), cfg_for("gemini"))}) > 1]  # fmt: skip
    gem = [
        c
        for r in rows
        for c in (cached(r).get("gemini") or {"chunks": {}})["chunks"].values()
    ]
    repair_rate = sum(bool(c.get("repair")) for c in gem) / max(1, len(gem))
    g_req = math.ceil(len(open_rows) * (1 + repair_rate))
    g_rpd = effective_cfg(PROVIDERS["gemini"]).rpd
    g_days = math.ceil(g_req / g_rpd)
    # tries that got no answer (503s and other failures) in this pilot's Gemini parts
    tries = sum(c.get("attempts", 0) for c in gem)
    answered = sum(1 + bool(c.get("repair")) for c in gem if c["status"] == "ok")
    g_fail = (tries - answered) / tries if tries else 0.0
    g_days_fail = math.ceil(g_req / (g_rpd * (1 - g_fail))) if g_fail < 1 else None
    t, _ = price(restricted)
    q = t.get("groq")
    q_calls = q.calls if q else 0
    q_tok = int(
        (q.tokens_in * GROQ_RATIO[0] + q.tokens_out * GROQ_RATIO[1]) if q else 0
    )
    q_tpd = effective_cfg(PROVIDERS["groq"]).tpd or 10**12
    q_days = math.ceil(q_tok / q_tpd)
    q_days_retry = math.ceil(q_tok * (1 + 2 * GROQ_FAIL_RATE) / q_tpd)
    loc = [(len(applicable_fields(r.doc_type)), seconds(raw)) for r in rows
           for k, raw in cached(r, first_sent=True).items() if k not in PROVIDERS and raw_state(raw) == "complete" and seconds(raw)]  # fmt: skip
    per_field = sum(s for _, s in loc) / max(1, sum(n for n, _ in loc)) if loc else None  # type: ignore[misc]
    dev_fields = sum(len(applicable_fields(r.doc_type)) for r in dev)
    hours = f"{dev_fields * per_field / 3600:.1f}" if per_field else "?"
    rate_fresh = (
        tot["fresh_flagged"] / tot["fresh_asked"] if tot["fresh_asked"] else None
    )
    rate_all = tot["flagged"] / tot["asked"] if tot["asked"] else None

    def items(rate: float | None) -> str:
        return "?" if rate is None else str(round(review_items(dev_fields, rate)))

    return [
        f"Dev set: {len(dev)} documents ({len(open_rows)} open: Gemini + local; {len(restricted)} restricted: Groq + local), {dev_fields} asked fields.",
        "",
        "| labeler | documents | requests | tokens | days | notes |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| Gemini (JSON mode) | {len(open_rows)} | {g_req} | no daily token cap | {g_days} without failed requests; {g_days_fail if g_days_fail else '?'} at this pilot's failure rate ({tries - answered} of {tries} tries) | one request per document plus repairs at this pilot's rate ({100 * repair_rate:.0f}% of answers); documents needing two field groups: {len(two_groups)} |",
        f"| Groq | {len(restricted)} | {q_calls} (+ about {round(q_calls * 2 * GROQ_FAIL_RATE)} split-retry requests) | {q_tok:,} (with the split retry: {int(q_tok * (1 + 2 * GROQ_FAIL_RATE)):,}) | {q_days}; {q_days_retry} with the split retry | plan estimate scaled by the sv2 real / estimate ratio ({GROQ_RATIO[0]} in, {GROQ_RATIO[1]} out); split retry at sv2's json_validate_failed rate ({100 * GROQ_FAIL_RATE:.0f}% of parts), each failure costing two more requests of about the same size |",
        f"| local model | {len(dev)} | {len(dev)} (one part each in the plan) | runs on this Mac | {hours} Mac hours | this pilot's time per asked field ({f'{per_field:.0f} s' if per_field else '?'}, n={len(loc)} documents) x {dev_fields} asked fields |",
        "",
        f"Days = the slower cloud provider: **{max(g_days, q_days)} to {max(g_days_fail or g_days, q_days_retry)}**. The local model runs beside them on this Mac.",
        "",
        f"Review items, at the flag rate of the document labeled for real ({f'{100 * rate_fresh:.0f}%' if rate_fresh is not None else '?'}): about **{items(rate_fresh)}**; "
        f"at the Gemini-vs-local flag rate over all pilot documents ({f'{100 * rate_all:.0f}%' if rate_all is not None else '?'}): about **{items(rate_all)}**. "
        f"Both include the {SPOT_CHECK_PERCENT}% consensus spot-check of accepted fields. The restricted documents' pair is Groq + local, which this pilot did not measure.",
    ]


def repair_lines(rows: list[ManifestRow]) -> list[str]:
    """Per document: the local model's fields with shape problems, how many its one
    repair request fixed, which other fields' answers changed in the repaired answer
    (the request asks to leave them unchanged), and what the request cost."""
    out = [
        "| document | fields with shape problems | fixed by the repair | still failing | other fields whose answer changed | kept | repair time | repair tokens in / out |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        for name, raw in cached(row).items():
            if name in PROVIDERS:
                continue
            for c in raw["chunks"].values():
                rep = c.get("repair")
                if not rep:
                    out.append(
                        f"| {row.doc_id[:12]} | 0 | - | - | - | - | no request | - |"
                    )
                    continue
                before = sorted({e.split(":")[0] for e in rep["errors"]})
                kept = rep.get("kept") == "repair"
                after = {e.split(":")[0] for e in rep.get("errors_after", [])} if kept else set(before)  # fmt: skip
                first, now = candidates(row, before_repair(raw)), candidates(row, raw)
                changed = [f for f in now if f not in before and canonical(first[f]) != canonical(now[f])]  # fmt: skip
                fixed = len(before) - len(after & set(before))
                out.append(f"| {row.doc_id[:12]} | {len(before)} | {fixed} | {', '.join(sorted(after)) or '-'} | "
                           f"{', '.join(changed) or '-'} | {rep.get('kept', 'failed: ' + str(rep.get('failed')))} | "
                           f"{rep.get('seconds', '-')} s | {rep.get('tokens_in', '-')} / {rep.get('tokens_out', '-')} |")  # fmt: skip
    return out


def after_repair_lines(rows: list[ManifestRow], compared: list[ManifestRow]) -> list[str]:  # fmt: skip
    """The section "after local repair" (D-52): every number before and after."""
    pre, post = pair_stats(rows, True), pair_stats(rows, False)
    by_doc = {d["doc"]: d for d in pre}
    pairs = [
        "| document | mode | fields asked | agree (first sent / after repair) | flagged | review items (flagged + spot-check) | single-source rule would settle | flagged left with the rule |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for d in post:
        b = by_doc[d["doc"]]
        pairs.append(f"| {d['doc']} | {d['mode']} | {d['asked']} | {b['agree']} / {d['agree']} | {b['flagged']} / {d['flagged']} | "
                     f"{b['review']} / {d['review']} | {len(d['settle'])} | {d['flagged'] - len(d['settle'])} |")  # fmt: skip
    tb, ta = totals(pre), totals(post)
    pairs.append(f"| all | | {ta['asked']} | {tb['agree']} ({100 * tb['agree'] / max(1, tb['asked']):.0f}%) / "
                 f"{ta['agree']} ({100 * ta['agree'] / max(1, ta['asked']):.0f}%) | {tb['flagged']} / {ta['flagged']} | | "
                 f"{ta['settle']} | {ta['flagged'] - ta['settle']} |")  # fmt: skip
    settled = []
    for d in post:
        if d["settle"]:
            settled.append(f"- {d['doc']} ({d['mode']}): " + ", ".join(
                f"{f} (Gemini: {st}" + ("" if ok is None else ", matches the label" if ok else ", **differs from the label**")
                + ")" for f, st, ok in d["settle"]))  # fmt: skip
    judged = [ok for d in post for _, _, ok in d["settle"] if ok is not None]
    n = dev_field_count()
    proj = [
        "| flag rate from | first sent: flag rate, review items | after repair: flag rate, review items | after repair with the single-source rule: settled, review items |",
        "| --- | --- | --- | --- |",
    ]
    for label, key in (("the document labeled for real", "fresh_"), ("all pilot documents (Gemini vs local)", "")):  # fmt: skip
        if not ta[key + "asked"]:
            continue
        fb, fa = (
            tb[key + "flagged"] / tb[key + "asked"],
            ta[key + "flagged"] / ta[key + "asked"],
        )
        st = ta[key + "settle"] / ta[key + "asked"]
        proj.append(f"| {label} | {100 * fb:.0f}%, {review_items(n, fb):.0f} | {100 * fa:.0f}%, **{review_items(n, fa):.0f}** | "
                    f"{100 * st:.0f}% of asked fields, **{review_items(n, fa, st):.0f}** |")  # fmt: skip
    return [
        "### The repair, per document",
        "",
        *repair_lines(rows),
        "",
        "### The local model against the existing labels, before and after",
        "",
        *comparison_lines(compared, local_before_after),
        "",
        "### Gemini and the local model, before and after",
        "",
        *pairs,
        "",
        "### Single-source rule (projection only, not implemented)",
        "",
        f"The rule: for a flagged tier 2 field, when Gemini passes every blocking check and the local model's answer still fails one after its repair, accept Gemini's answer as `silver_single`, with a {SINGLE_SPOT_PERCENT}% spot-check into review. Tier 1 fields ({', '.join(TIER1)}) are never settled this way. Settled after repair:",
        "",
        *(settled or ["- nothing"]),
        "",
        f"Where a label exists, Gemini's answer matches it on {sum(judged)} of {len(judged)} items the rule would settle."
        if judged
        else "No item the rule would settle is on a comparison document, so none can be checked against a label.",
        "",
        "### Review items for the full dev set",
        "",
        f"{n} asked fields. Review items = flagged fields left + {SINGLE_SPOT_PERCENT}% of the settled ones + the {SPOT_CHECK_PERCENT}% consensus spot-check of the accepted ones, at the pilot's rates. The rates are Gemini + local; the restricted documents get Groq + local, not measured here, and the rule as written names Gemini.",
        "",
        *proj,
    ]


def stratified_fields(split: str, k: int) -> tuple[int, int]:
    """Asked fields of a k-document label set cut from `split`, stratified by group:
    each group keeps its share (largest remainder), at its mean asked fields per
    document. A projection; no document is picked. Returns (documents, fields)."""
    from eval.silver import run

    ls = json.loads(run.LABEL_SET.read_text())[split]
    rows = {r.doc_id: r for r in run.select(split)}
    groups: dict[str, list[int]] = {}
    for e in ls:
        groups.setdefault(e["group"], []).append(len(applicable_fields(rows[e["doc_id"]].doc_type)))  # fmt: skip
    share = {g: len(v) * k / len(ls) for g, v in groups.items()}
    keep = {g: math.floor(q) for g, q in share.items()}
    for g in sorted(share, key=lambda g: keep[g] - share[g])[: k - sum(keep.values())]:
        keep[g] += 1
    return k, round(sum(keep[g] * sum(v) / len(v) for g, v in groups.items()))


def item_pairs(field: str, c: Candidate, gold: Candidate) -> tuple[int, int, int]:
    """(items of the answer paired with a label item, label items, answer items) for a
    list field, pairing one to one with agree.item_same."""
    from eval.silver.agree import ACTIVE, item_same

    def of(x: Candidate) -> list[dict]:
        n = x.normalized if x.status == "present" and not x.parse_error else None
        its = (n or {}).get("items")
        return its if isinstance(its, list) else []

    mine, free = of(c), list(of(gold))
    paired = 0
    for it in mine:
        hit = next((g for g in free if isinstance(it, dict) and item_same(field, it, g, ACTIVE)), None)  # fmt: skip
        if hit is not None:
            free.remove(hit)
            paired += 1
    return paired, len(of(gold)), len(mine)


def local_cost(raw: dict) -> str:
    """Requests (repairs included) and wall time of one labeler on one document."""
    t = seconds(raw)
    n = sum(c.get("attempts", 1) for c in raw["chunks"].values())
    return f"{n}, {f'{t:.0f} s' if t is not None else '-'}"


def mean_of(ts: list[dict], key: str) -> float:
    return sum(t.get(key) or 0 for t in ts) / len(ts)


def l1_timing_lines(rows: list[ManifestRow], version: str) -> list[str]:
    """Per document: local requests and time, sv3 against the new version, and
    llama-server's prompt processing for the first request against the later ones
    (cache_n: prompt tokens taken from the cache)."""
    out = [
        f"| document | {PROMPT_VERSION}: requests, time | {version}: requests, time | first request: prompt tokens processed, ms | later requests: tokens taken from the cache, tokens processed, ms (mean) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        base = [r for k, r in cached(row).items() if k not in PROVIDERS]
        new = [r for k, r in cached(row, local_prompt=version).items() if k not in PROVIDERS]  # fmt: skip
        if not new:
            continue
        ch = new[0]["chunks"]
        ts = [t for i in sorted(ch, key=int) for t in ch[i].get("timings", [])]
        first = (
            f"{ts[0].get('prompt_n')}, {ts[0].get('prompt_ms') or 0:.0f}" if ts else "-"
        )
        later = ts[1:]
        rest = (f"{mean_of(later, 'cache_n'):.0f}, {mean_of(later, 'prompt_n'):.0f}, "
                f"{mean_of(later, 'prompt_ms'):.0f}") if later else "-"  # fmt: skip
        out.append(f"| {row.doc_id[:12]} | {local_cost(base[0]) if base else '-'} | {local_cost(new[0])} | {first} | {rest} |")  # fmt: skip
    return out


def matches_text(cells: list[str]) -> str:
    """ "2 of 4 (misses 28ad40, 563042)" from per-document "ok" or doc-id cells."""
    miss = [x for x in cells if x != "ok"]
    return f"{len(cells) - len(miss)} of {len(cells)}" + (f" (misses {', '.join(miss)})" if miss else "")  # fmt: skip


def l1_lines(rows: list[ManifestRow]) -> list[str]:
    """The local labeler's own prompt version against sv3 (D-53), on documents with
    labels: accuracy, agreement and flags with Gemini, cost, and the projections."""
    from eval.silver import pipeline

    v = pipeline.prompt_for("local")
    labeled = [r for r in rows if read_resolved(r.doc_id)]

    def versions(row: ManifestRow) -> dict[str, dict]:
        named = {f"gemini ({PROMPT_VERSION}, reference)": raw for k, raw in cached(row).items() if k == "gemini"}  # fmt: skip
        named |= {f"{k} {PROMPT_VERSION} (after repair)": raw for k, raw in cached(row).items() if k not in PROVIDERS}  # fmt: skip
        named |= {f"{k} {v}": raw for k, raw in cached(row, local_prompt=v).items() if k not in PROVIDERS}  # fmt: skip
        return named

    single: dict[str, list[list[str]]] = {}
    items: dict[
        str, list[list[int]]
    ] = {}  # field -> per version [paired, label, answer]
    for row in labeled:
        gold = read_resolved(row.doc_id)
        for name, raw in versions(row).items():
            if name.startswith("gemini") or raw_state(raw) != "complete":
                continue
            cands = candidates(row, raw)
            got = dict(score(row, cands, gold))
            for f in applicable_fields(row.doc_type):
                if BY_ID[f].kind == "list" and f in gold:
                    t = items.setdefault(f, [[0, 0, 0], [0, 0, 0]])[0 if PROMPT_VERSION + " " in name else 1]  # fmt: skip
                    for k, n in enumerate(item_pairs(f, cands[f], gold_of(gold[f]))):
                        t[k] += n
            for f in focused_fields(applicable_fields(row.doc_type)):
                if f in got:
                    cell = single.setdefault(f, [[], []])[0 if PROMPT_VERSION + " " in name else 1]  # fmt: skip
                    cell.append("ok" if got[f] else row.doc_id[:6])
    per_field = ["| field | kind | " + f"{PROMPT_VERSION} matches | {v} matches |", "| --- | --- | --- | --- |"]  # fmt: skip
    for f, (a, b) in single.items():
        per_field.append(
            f"| {f} | {BY_ID[f].kind} | {matches_text(a)} | {matches_text(b)} |"
        )
    per_item = [f"| field | label items | {PROMPT_VERSION}: items given, paired with a label item | {v}: items given, paired |",
                "| --- | --- | --- | --- |"]  # fmt: skip
    for f, (a, b) in items.items():
        per_item.append(f"| {f} | {a[1]} | {a[2]}, {a[0]} | {b[2]}, {b[0]} |")
    pre, post = pair_stats(labeled, False), pair_stats(labeled, False, v)
    by_doc = {d["doc"]: d for d in pre}
    pairs = [
        f"| document | fields asked | agree ({PROMPT_VERSION} / {v}) | flagged ({PROMPT_VERSION} / {v}) | flag rate ({PROMPT_VERSION} / {v}) | single-source rule would settle ({v}) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for d in post:
        b = by_doc.get(d["doc"])
        if b is None:
            continue
        pairs.append(f"| {d['doc']} | {d['asked']} | {b['agree']} / {d['agree']} | {b['flagged']} / {d['flagged']} | "
                     f"{100 * b['flagged'] / d['asked']:.0f}% / {100 * d['flagged'] / d['asked']:.0f}% | "
                     f"{', '.join(f for f, _, _ in d['settle']) or '-'} |")  # fmt: skip
    ta, tb = totals(pre), totals(post)
    if tb["asked"]:
        pairs.append(f"| all | {tb['asked']} | {ta['agree']} ({100 * ta['agree'] / ta['asked']:.0f}%) / {tb['agree']} ({100 * tb['agree'] / tb['asked']:.0f}%) | "
                     f"{ta['flagged']} / {tb['flagged']} | {100 * ta['flagged'] / ta['asked']:.0f}% / {100 * tb['flagged'] / tb['asked']:.0f}% | {tb['settle']} |")  # fmt: skip
    proj: list[str] = []
    if ta["asked"] and tb["asked"]:
        from eval.silver import run

        n_dev = sum(len(applicable_fields(r.doc_type)) for r in run.select("dev"))
        n_test = sum(len(applicable_fields(r.doc_type)) for r in run.select("test"))
        d40, n_dev40 = stratified_fields("dev", 40)
        fa, fb, st = ta["flagged"] / ta["asked"], tb["flagged"] / tb["asked"], tb["settle"] / tb["asked"]  # fmt: skip
        scen = [
            (f"(a) {PROMPT_VERSION} as now", 60, n_dev, fa, 0.0),
            (f"(b) {v}", 60, n_dev, fb, 0.0),
            (f"(c) {v} + single-source rule on dev tier 2 fields", 60, n_dev, fb, st),
            (
                f"(d) as (c), dev cut to {d40} documents, stratified",
                d40,
                n_dev40,
                fb,
                st,
            ),
        ]
        proj = [
            f"Rates from the {len(post)} documents above (Gemini vs local): flag rate {100 * fa:.0f}% ({PROMPT_VERSION}), {100 * fb:.0f}% ({v}); the rule settles {100 * st:.0f}% of asked fields. Test is always fully reviewed: every one of its {n_test} asked fields is a review item (in brackets: the test items at the flag rate, for comparison). Review items = flagged fields left + {SINGLE_SPOT_PERCENT}% of the settled ones + the {SPOT_CHECK_PERCENT}% consensus spot-check.",
            "",
            "| scenario | dev documents | dev asked fields | dev review items | test review items | total |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for name, docs, n, f, sr in scen:
            dev_items = review_items(n, f, sr)
            proj.append(f"| {name} | {docs} | {n} | **{dev_items:.0f}** | {n_test} ({review_items(n_test, f):.0f}) | **{dev_items + n_test:.0f}** |")  # fmt: skip
    return [
        f"The local labeler's own prompt version `{v}` (D-53): the same system prompt in every call, the document before the fields, list fields and contact asked one per call, a plain repair message, llama-server's prompt cache on. Gemini stays at `{PROMPT_VERSION}` (cached). The pending sv4 guide rules are not in it. Scored on every document that has labels: the 28ad40ea4b1f labels were reviewed from Gemini's and Qwen's {PROMPT_VERSION} answers, which favors those answers.",
        "",
        "### Against the labels",
        "",
        *comparison_lines(labeled, versions),
        "",
        "List fields and contact, document by document:",
        "",
        *per_field,
        "",
        "List items: a list field matches only when every item pairs (agree.item_same: same kind, dates and flags, overlapping citations, similar text), so a near miss scores like an empty answer. Items given and paired, summed over the documents:",
        "",
        *per_item,
        "",
        "### Gemini and the local model",
        "",
        *pairs,
        "",
        "### Cost and the prompt cache",
        "",
        *l1_timing_lines(labeled, v),
        "",
        "### Review items, dev and test (projection only)",
        "",
        *proj,
    ]


def full_report(rows: list[ManifestRow], notes: str = "") -> Path:
    """Rebuild the pilot report from the caches (no API calls)."""
    compared = [r for r in rows if labeled_by_earlier_prompt(r.doc_id)]
    _pairs, tot = pair_lines(rows)
    parts = [
        f"# Silver pilot, prompt {PROMPT_VERSION}",
        "",
        notes.strip(),
        "",
        "## Reviewed documents: each labeler against the existing labels",
        "",
        "Comparison mode: these documents already had labels, so nothing was written for them. The labels are sv1 "
        "consensus lines plus the reviewer's answers (`claude_chat`, a model in chat, not human-verified). **They came "
        "from Gemini and Groq plus that review, which slightly favors Gemini** (and Groq's sv1 row), and the documents "
        "were used to write the labeling guide, so every number here is optimistic. The local model's answers are shown as "
        "first sent (after repair: the last section). Match = the consensus agreement rule "
        "(status, enums and dates exact; text fuzzy with overlapping citations; the active relaxations): the answer would "
        "have been accepted beside the label. Mismatches name the review item id when the label came from the review, "
        "`consensus` when it was an sv1 consensus line.",
        "",
        *comparison_lines(compared),
        "",
        "## Gemini (JSON mode, one repair request)",
        "",
        *gemini_lines(rows),
        "",
        "## Local model (field groups under 60% of the output cap)",
        "",
        *local_lines(rows),
        "",
        "## Gemini and the local model: agreement and flags",
        "",
        *_pairs,
        "",
        "## Projection for the full dev set",
        "",
        *projection_lines(rows, tot),
        "",
        "## After local repair",
        "",
        "The local model's answers got the same shape check and one repair request as Gemini's (D-52), run on the cached answers: repair requests only, no full re-run. The sections above show the local answers as first sent.",
        "",
        *after_repair_lines(rows, compared),
        "",
    ]
    from eval.silver import pipeline

    if pipeline.prompt_for("local") != PROMPT_VERSION:
        parts += [
            f"## Local labeler {pipeline.prompt_for('local')}",
            "",
            *l1_lines(rows),
            "",
        ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(parts), encoding="utf-8")
    return REPORT
