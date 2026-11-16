# ruff: noqa: E501
"""Replay of the pilot review (sv2): the reviewer's answers as a regression set.

Imports nothing and writes no label. Inputs:
- the answers (data/cache/labeling/answers/pilot-all.txt);
- the exported batches the reviewer saw (export/batch-NN.md) and export/ids.json: what
  "accept A" meant is read back from the batch text, so it does not depend on code
  that has changed since;
- the sv1 raw answers in the cache, rebuilt into candidates with today's parsing and
  chunk merging, then resolved with a chosen set of agreement relaxations.

An item is settled automatically when resolve() accepts the field; it is settled
correctly when the accepted candidate is the reviewer's answer (model.canonical),
wrongly otherwise. A relaxation may be switched on (agree.ACTIVE) only if it settles at
least one item correctly and never settles one wrongly.
"""

import json
import re
from pathlib import Path

from shiori_core.fields import BY_ID
from shiori_core.models import Sentence

from collector.manifest import ManifestRow, read_rows
from eval.documents import load_sentences
from eval.silver import config
from eval.silver.agree import ACTIVE, RELAXATIONS
from eval.silver.config import PROVIDERS
from eval.silver.model import Candidate, canonical, from_row
from eval.silver.pipeline import answers, load_raw, raw_path, resolve
from eval.silver.prompt import applicable_fields
from eval.silver.review import Answer, parse_reply, review_stats

SV1 = "sv1"
SV1_PAIR = ("gemini", "groq")  # sides A and B of the sv1 pilot (SLOTS order then)


def answers_path() -> Path:
    return config.CACHE / "answers" / "pilot-all.txt"


def batches_dir() -> Path:
    """A frozen copy of the pilot's export (batch-NN.md and ids.json): `export` replaces
    the files in export/, and the replay must read what the reviewer saw."""
    return config.CACHE / "answers" / "pilot-batches"


# --- what the reviewer saw -------------------------------------------------------------


def parse_side(field: str, text: str) -> Candidate:
    """One rendered candidate (review._cand_text without the checks line) back into a
    Candidate."""
    c = Candidate(field)
    for bit in text.split(" | "):
        key, _, val = bit.partition("=")
        if bit.startswith("PARSE ERROR: "):
            c.parse_error = bit.removeprefix("PARSE ERROR: ")
        elif key == "status":
            c.status = val
        elif key == "value_ja":
            c.value_ja = val
        elif key == "value_en":
            c.value_en = val
        elif key == "cites":
            c.citations = val.split(",")
        elif key == "normalized":
            c.normalized = json.loads(val)
    return c


_ITEM = re.compile(r"^## (F-\d{4})", re.M)
_SIDE_END = r"(?=\n   checks:|\n   another part|\n[ABC]: |\n[ABC] \(|\nsentences \(|\Z)"


def parse_batches(export_dir: Path) -> dict[str, dict]:
    """item id -> {field, kind, A, B} as shown in the batches."""
    out: dict[str, dict] = {}
    for p in sorted(export_dir.glob("batch-*.md")):
        text = p.read_text(encoding="utf-8")
        starts = [m.start() for m in _ITEM.finditer(text)] + [len(text)]
        for a, b in zip(starts, starts[1:], strict=False):
            block = text[a:b]
            iid = block[3:9]
            field = re.search(r"\| field (\w+)", block).group(1)  # type: ignore[union-attr]
            spot = re.search(r"\nA and B agree: (.*?)" + _SIDE_END, block, re.S)
            if spot:
                c = parse_side(field, spot.group(1))
                out[iid] = {"field": field, "kind": "spot", "A": c, "B": c}
                continue
            sides = {
                tag: parse_side(field, m.group(1))
                for tag in "AB"
                if (m := re.search(rf"\n{tag}: (.*?)" + _SIDE_END, block, re.S))
            }
            out[iid] = {"field": field, "kind": "flagged", **sides}
    return out


def truth_of(a: Answer, field: str, shown: dict[str, Candidate]) -> Candidate:
    if a.action.startswith("accept"):
        return shown[a.action[-1]]
    if a.action == "absent" or a.kv.get("status") == "absent":
        return Candidate(field, status="absent")
    return from_row(
        {"field": field, "status": a.kv["status"], "value_ja": a.kv.get("value_ja", ""),
         "value_en": a.kv.get("value_en", ""), "normalized": a.kv.get("normalized", ""),
         "citations": [x for x in a.kv.get("cites", "").split(",") if x]},
        "reviewer",
    )  # fmt: skip


def load_pilot(path: Path | None = None) -> list[dict]:
    """One dict per answered item: iid, doc_id, field, kind, answer, shown, truth."""
    text = (path or answers_path()).read_text(encoding="utf-8")
    ans, errors = parse_reply(text)
    if errors:
        raise ValueError("; ".join(errors))
    reg = json.loads((batches_dir() / "ids.json").read_text())["items"]
    batches = parse_batches(batches_dir())
    items = []
    for a in ans:
        meta, b = reg[a.iid], batches[a.iid]
        shown = {"A": b["A"], "B": b["B"]}
        items.append({"iid": a.iid, "doc_id": meta["doc_id"], "field": meta["field"],
                      "kind": meta["kind"], "answer": a, "shown": shown,
                      "truth": truth_of(a, meta["field"], shown)})  # fmt: skip
    return items


# --- what today's code makes of the cached sv1 answers --------------------------------


def rebuild(
    row: ManifestRow,
) -> tuple[list[Sentence], list[dict[str, Candidate]], list]:
    """Candidates per slot (gemini, groq) from the sv1 raw cache, parsed and merged by
    today's code."""
    sentences = load_sentences(row)
    by_id = {s.id: s for s in sentences}
    cands, labelers = [], []
    for p in SV1_PAIR:
        raw = load_raw(raw_path(row.doc_id, p, PROVIDERS[p].model, SV1))
        cands.append(answers(raw, f"{p}/{PROVIDERS[p].model}", applicable_fields(row.doc_type), by_id))  # fmt: skip
        labelers.append((p, PROVIDERS[p].model, max(c["date"] for c in raw["chunks"].values())))  # fmt: skip
    return sentences, cands, labelers


def evaluate(items: list[dict], rules: frozenset[str]) -> dict[str, str]:
    """item id -> auto_correct | auto_wrong | flagged, under these relaxations."""
    rows = {r.doc_id: r for r in read_rows()}
    decided: dict[str, dict] = {}
    for d in {it["doc_id"] for it in items}:
        sentences, cands, labelers = rebuild(rows[d])
        res = resolve(rows[d], sentences, cands, labelers, False, rules)
        decided[d] = {r.field: r for r in res}
    out = {}
    for it in items:
        r = decided[it["doc_id"]][it["field"]]
        if r.state != "accepted" or r.line is None:
            out[it["iid"]] = "flagged"
            continue
        ln = r.line
        pick = Candidate(it["field"], ln["status"], ln["value_ja"], ln["value_en"], ln["normalized"], ln["citations"])  # fmt: skip
        out[it["iid"]] = (
            "auto_correct"
            if canonical(pick) == canonical(it["truth"])
            else "auto_wrong"
        )
    return out


def relaxation_replay(items: list[dict]) -> list[dict]:
    """Per relaxation: items it settles correctly that the baseline does not, and every
    item it settles wrongly. passes = at least one new correct and no new wrong."""
    base = evaluate(items, frozenset())
    rows = [{"rule": "baseline", "correct": [i for i, v in base.items() if v == "auto_correct"],
             "wrong": [i for i, v in base.items() if v == "auto_wrong"], "new": [], "passes": None}]  # fmt: skip
    for name in RELAXATIONS:
        ev = evaluate(items, frozenset({name}))
        new = [
            i
            for i, v in ev.items()
            if v == "auto_correct" and base[i] != "auto_correct"
        ]
        wrong = [
            i for i, v in ev.items() if v == "auto_wrong" and base[i] != "auto_wrong"
        ]
        rows.append({"rule": name, "correct": [i for i, v in ev.items() if v == "auto_correct"],
                     "new": new, "wrong": wrong, "passes": bool(new) and not wrong})  # fmt: skip
    ev = evaluate(items, ACTIVE)
    rows.append({"rule": "ACTIVE (" + ", ".join(sorted(ACTIVE)) + ")",
                 "correct": [i for i, v in ev.items() if v == "auto_correct"],
                 "new": [i for i, v in ev.items() if v == "auto_correct" and base[i] != "auto_correct"],
                 "wrong": [i for i, v in ev.items() if v == "auto_wrong"], "passes": None})  # fmt: skip
    return rows


# --- every review round, on the candidates as shown -----------------------------------

# (answer files, frozen batches the reviewer saw), oldest first. A later file's answer to
# the same item wins (pilot-extra*.txt answered items pilot-all.txt left open).
REVIEW_ROUNDS = (
    (("pilot-all.txt", "pilot-extra.txt", "pilot-extra2.txt"), "pilot-batches"),  # sv1
    (
        ("pilot2.txt", "pilot4.txt"),
        "pilot2-batches",
    ),  # sv3 (F-0039 was in it, held back)
    (("pilot3.txt",), "pilot3-batches"),  # F-0057, the reopened scope_summary
)


def load_reviews() -> list[dict]:
    """Every answered item of every round: iid, field, kind, shown {A, B}, truth.
    Items whose batch is not frozen are left out (none today)."""
    reg = json.loads((config.CACHE / "export" / "ids.json").read_text())["items"]
    items: dict[str, dict] = {}
    for files, folder in REVIEW_ROUNDS:
        batches = parse_batches(config.CACHE / "answers" / folder)
        for name in files:
            path = config.CACHE / "answers" / name
            if not path.exists():
                continue
            ans, errors = parse_reply(path.read_text(encoding="utf-8"))
            if errors:
                raise ValueError(f"{name}: " + "; ".join(errors))
            for a in ans:
                b = batches.get(a.iid)
                if b is None or "A" not in b or "B" not in b:
                    continue
                field = reg[a.iid]["field"]
                shown = {"A": b["A"], "B": b["B"]}
                items[a.iid] = {"iid": a.iid, "doc_id": reg[a.iid]["doc_id"], "field": field,
                                "kind": b["kind"], "answer": a, "shown": shown,
                                "truth": truth_of(a, field, shown)}  # fmt: skip
    return [items[i] for i in sorted(items)]


def shown_pair_replay(items: list[dict], rule: str) -> dict:
    """One relaxation on top of ACTIVE, judged on the candidate pairs exactly as the
    reviewer saw them (no re-parsing of old caches, so every round counts). An item is
    newly settled when A and B agree with the rule and did not without it; settled
    correctly when A (the side resolve keeps) is the reviewer's answer
    (model.canonical), wrongly otherwise. The blocking checks are not re-run here."""
    from eval.silver.agree import agree

    with_rule = ACTIVE | {rule}
    fields = RULE_FIELDS.get(rule)
    out: dict = {"rule": rule, "items": len(items), "new_correct": [], "new_wrong": [],
                 "field_items": [i["iid"] for i in items if fields and i["field"] in fields]}  # fmt: skip
    for it in items:
        a, b = it["shown"]["A"], it["shown"]["B"]
        if a.parse_error or b.parse_error:
            continue
        if agree(a, b, with_rule)[0] and not agree(a, b, ACTIVE - {rule})[0]:
            ok = canonical(a) == canonical(it["truth"])
            out["new_correct" if ok else "new_wrong"].append(it["iid"])
    return out


RULE_FIELDS = {"eligibility_negation": {"eligibility"}}


def rounds_table(items: list[dict]) -> str:
    """Markdown: every relaxation replayed on every review round (shown_pair_replay)."""
    lines = [f"Reviewed items with a frozen batch: {len(items)} ({items[0]['iid']} to {items[-1]['iid']}).", "",
             "| rule | active | settles correctly (new) | settles wrongly | reviewed items of its field |",
             "| --- | --- | --- | --- | --- |"]  # fmt: skip
    for rule in RELAXATIONS:
        r = shown_pair_replay(items, rule)
        lines.append(f"| {rule} | {'yes' if rule in ACTIVE else 'no'} | {', '.join(r['new_correct']) or '-'} | "
                     f"{', '.join(r['new_wrong']) or '-'} | {', '.join(r['field_items']) or 'all'} |")  # fmt: skip
    return "\n".join(lines)


# --- which provider was A and which B in the pilot export ------------------------------


def _full(x: Candidate, y: Candidate) -> bool:
    return canonical(x) == canonical(y) and sorted(x.citations) == sorted(y.citations)


def _loose(x: Candidate, y: Candidate) -> bool:
    """Same quote and citations; the value may differ where today's code reads the
    cached answer differently (the ref of a text field that sv1 dropped, or another
    part chosen by the new merge)."""
    return bool(x.citations) and sorted(x.citations) == sorted(y.citations) and (x.value_ja or "") == (y.value_ja or "")  # fmt: skip


def _order(a: Candidate, b: Candidate, g: Candidate, q: Candidate, same) -> str | None:
    direct = (same(a, g) and not same(a, q)) or (same(b, q) and not same(b, g))
    swapped = (same(a, q) and not same(a, g)) or (same(b, g) and not same(b, q))
    if direct != swapped:
        return "A=gemini, B=groq" if direct else "A=groq, B=gemini"
    return None


def recover_mapping() -> dict:
    """The pilot export did not record which provider was A. resolve() builds the
    candidates in SLOTS order (gemini, groq) and labels them A, B; this checks that
    claim against the cache: each shown side is compared with the candidates rebuilt
    from each provider's cached sv1 answer. A side is evidence when it matches one
    provider's candidate and not the other's."""
    reg = json.loads((batches_dir() / "ids.json").read_text())["items"]
    batches = parse_batches(batches_dir())
    rows = {r.doc_id: r for r in read_rows()}
    built = {d: rebuild(rows[d])[1] for d in {m["doc_id"] for m in reg.values()}}
    verdict: dict[str, list[str]] = {"A=gemini, B=groq": [], "A=groq, B=gemini": [], "inconclusive": []}  # fmt: skip
    for iid, meta in sorted(reg.items()):
        g, q = (built[meta["doc_id"]][i][meta["field"]] for i in (0, 1))
        a, b = batches[iid]["A"], batches[iid]["B"]
        found = _order(a, b, g, q, _full) or _order(a, b, g, q, _loose)
        verdict[found or "inconclusive"].append(iid)
    return verdict


def pilot_mapping(verdict: dict) -> dict:
    """mapping.json entries for the pilot items: A gemini, B groq for all (see report)."""
    reg = json.loads((batches_dir() / "ids.json").read_text())["items"]
    note = "recovered after the fact: SLOTS order in resolve(), checked against the sv1 cache"
    return {iid: {"A": "gemini", "B": "groq", "recovered": note} for iid in sorted(reg)}


def pilot_records(items: list[dict], mapping: dict) -> list[dict]:
    """review-stats records for the pilot, from the answers and what was shown."""
    out = []
    for it in items:
        m, a = mapping[it["iid"]], it["answer"]
        choice = m[a.action[-1]] if a.action.startswith("accept") else "custom"
        right = {m[t]: m[t] == choice or canonical(it["shown"][t]) == canonical(it["truth"]) for t in "AB"}  # fmt: skip
        out.append({"iid": it["iid"], "doc_id": it["doc_id"], "field": it["field"],
                    "kind": it["kind"], "choice": choice, "right": right})  # fmt: skip
    return out


def report(
    items: list[dict], replay: list[dict], verdict: dict, records: list[dict]
) -> str:
    n = len(items)
    kinds = {k: sum(BY_ID[it["field"]].kind == k for it in items) for k in ("text", "structured", "list")}  # fmt: skip
    lines = [
        "# Pilot review: provider stats, mapping recovery, agreement replay (sv2 work)",
        "",
        f"Inputs: {n} answered items of the sv1 pilot (`pilot-all.txt`; F-0022 is unanswered), "
        f"the exported batches the reviewer saw, and the sv1 raw answers in the cache. "
        f"Field types: {kinds['text']} text, {kinds['structured']} structured, {kinds['list']} list. "
        "Three documents, so every rate below is a rough indication. The reviewer is `claude_chat` "
        '(a model in chat), so "right" means "what the reviewer chose", not verified truth. '
        "Rebuild: `uv run python -m eval.silver replay --out eval/reports/silver_pilot_review.md`.",
        "",
        "## Which provider was A and which B",
        "",
        "The pilot export did not record it. `resolve()` builds the candidates in `SLOTS` order "
        "(gemini, groq; unchanged since the pilot commit 56a3a79) and labels them A, B. Check: every "
        "candidate shown in the batches is compared with the one rebuilt from each provider's "
        "cached sv1 answer (status, value, citations).",
        "",
    ]
    for k, ids in verdict.items():
        lines.append(f"- {k}: {len(ids)} ({', '.join(ids) or '-'})")
    lines += [
        "",
        "A side counts as evidence when it matches one provider's rebuilt candidate and not the "
        "other's: first by value and citations; where that cannot tell, by quote and citations. Inconclusive items "
        "are ones where A and B were the same answer (consensus spot-checks, both absent), so "
        "the order cannot be seen. `export/mapping.json` records A = gemini, B = groq for every "
        "pilot item.",
        "",
        "## How often each provider's candidate was right when shown",
        "",
        "Right = the reviewer accepted it, or the reviewer's final answer is the same answer "
        "(status, value; English text and item order ignored). Spot-check items count for both.",
        "",
        review_stats(records),
        "",
        "Note: on F-0029 (and Gemini's F-0024) the shown candidate was a see_other_document "
        "text field whose ref the sv1 parser had dropped (the step-0 bug), so it counts as wrong "
        "here; the reviewer's note on F-0029 says both candidates had the right content. "
        '"Same answer" compares status and value only, so a candidate with the right '
        "normalized value but an unusable quote (Groq's F-0009, an ellipsis) counts as right.",
        "",
        "## Agreement relaxations, replayed",
        "",
        "Each rule is replayed alone on top of the baseline (sv2 parsing, chunk merging and the "
        "cue fix, sv1 agreement). Settled = the field would have been accepted without review. "
        "A rule passes when it settles at least one item correctly that the baseline does not, "
        "and never settles an item wrongly (accepting a candidate the reviewer rejected or "
        "replaced). Status, enum, date and amount comparisons are never loosened.",
        "",
        "| rule | what it does | settles correctly (new) | settles wrongly | passes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in replay:
        what = RELAXATIONS.get(r["rule"]) or (
            "sv2 parsing, merging and cue fix; sv1 agreement"
            if r["rule"] == "baseline"
            else "the rules switched on, together, on top of the baseline"
        )
        new = (
            ", ".join(r["new"]) if r["rule"] != "baseline" else ", ".join(r["correct"])
        )
        lines.append(f"| {r['rule']} | {what} | {new or '-'} | {', '.join(r['wrong']) or '-'} | "
                     f"{'-' if r['passes'] is None else ('yes' if r['passes'] else 'no')} |")  # fmt: skip
    return "\n".join(lines) + "\n"
