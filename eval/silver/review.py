# ruff: noqa: E501
"""Review export and import, built for pasting into a chat with a Japanese-reading
reviewer (D-43).

    export: flagged fields (and a seeded 5% consensus spot-check) -> batch-NN.md files
    import: the reviewer's one-line answers -> labels with reviewed_by "claude_chat"
        (a model in chat) or "claude_code" (a Claude Code review session, D-55)
    review-stats: per provider and field type, how often its candidate was right
    calibrate: two answer files for the same batch, side by side

Candidates are shown as A and B without provider names; export/mapping.json records
which provider each letter is, per item. List fields also get C, the union of A's and
B's items. A reopened consensus (`reopen`) may carry a third labeler's answer as C. Import is all-or-nothing: one malformed line and nothing is written. It
re-runs the automatic checks on every answer, records which candidate was taken
(`provenance.reviewed_choice`) and appends one line per answer to reviews.jsonl for
review-stats. It never produces `human_audited`.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from shiori_core.fields import BY_ID, FIELD_IDS
from shiori_core.models import EXTRACTOR_VERSION, Sentence

from collector.manifest import ManifestRow, read_rows
from eval.documents import load_sentences
from eval.silver import config
from eval.silver.agree import union_items
from eval.silver.checks import HARD, failed, run_checks
from eval.silver.config import TIER1
from eval.silver.model import Candidate, canonical, from_row
from eval.silver.pipeline import (
    _write,
    answers,
    cand_dict,
    decisions_path,
    label_line,
    load_raw,
    materialize,
    provenance,
    raw_path,
    read_resolved,
    rebuild_flagged,
    write_resolved,
)
from eval.silver.prompt import applicable_fields, field_line

SPLITS = Path("data/eval/splits.json")
MAX_ITEMS = 12
MAX_CHARS = 25_000
MAX_SENTENCE = 500
KEYS = {"status", "value_ja", "value_en", "cites", "note", "normalized"}

ANSWER_FORMAT = """Reply with one line per item and nothing else. Item ids are F-0001 style.

    F-0012 | accept A
    F-0012 | accept B | note=why (optional)
    F-0012 | accept C
    F-0012 | absent | note=why
    F-0012 | custom | status=present | value_ja=... | value_en=... | cites=p2_s12,p2_s13 | normalized={"date":"2026-10-13"} | note=...

- accept A / accept B / accept C: that candidate is right as shown. On list fields C is the union of A's and B's items; on a reopened item C is a third labeler's answer.
- absent: the document does not state this field (or the field does not apply).
- custom: your own answer. status is present, absent or see_other_document. value_ja must be copied exactly from a cited sentence. cites are any Japanese sentence ids of the document (the lists below show the likely ones). normalized is the field's JSON value (forms listed below); present text fields (title, issuer_org, scope_summary, delivery_location) have none. see_other_document always needs normalized={"ref":{"kind":"spec|bid_instructions|other_notice|kokuji|other","text_ja":"..."}}, text fields too. Do not put " | " inside a value.
- "consensus spot-check" items: A and B agree. Say accept A if it is right, otherwise answer absent or custom.
- Dates are JST. Weekday disagreements (DATE-5) happen in the sources: decide from context and say so in note.
- If you cannot decide an item confidently, give your best answer and start its note with UNSURE: (accept lines take note= too)."""


def _ids_path() -> Path:
    return config.CACHE / "export" / "ids.json"


def _registry() -> dict:
    p = _ids_path()
    return json.loads(p.read_text()) if p.exists() else {"next": 1, "items": {}}


def item_id(reg: dict, doc_id: str, field: str, kind: str) -> str:
    for i, v in reg["items"].items():
        if (v["doc_id"], v["field"], v["kind"]) == (doc_id, field, kind):
            return i
    i = f"F-{reg['next']:04d}"
    reg["next"] += 1
    reg["items"][i] = {"doc_id": doc_id, "field": field, "kind": kind}
    return i


def _mapping_path() -> Path:
    return config.CACHE / "export" / "mapping.json"


def provider_of(side: dict) -> str:
    return side["candidate"]["labeler"].split("/")[0]


def union_candidate(item: dict) -> Candidate | None:
    """C: for a list field where both A and B list items, the union of their items,
    deduplicated (agree.item_same). None otherwise, and when the item already has a
    third side (a reopened consensus)."""
    if (
        BY_ID[item["field"]].kind != "list"
        or item["kind"] == "spot"
        or len(item["sides"]) != 2
    ):
        return None
    lists = [
        s["candidate"]["normalized"]["items"]
        for s in item["sides"]
        if s["candidate"]["status"] == "present"
        and isinstance((s["candidate"]["normalized"] or {}).get("items"), list)
    ]
    if len(lists) < 2:
        return None
    items = union_items(item["field"], lists)
    return from_row({"field": item["field"], "status": "present", "normalized": {"items": items},
                     "value_ja": "", "value_en": "", "citations": []}, "union")  # fmt: skip


def load_items() -> list[dict]:
    p = config.CACHE / "flagged.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _cand_text(side: dict) -> str:
    c = side["candidate"]
    alts = c.get("alternatives") or []
    bits = [f"status={c['status']}"]
    if c["value_ja"]:
        bits.append(f"value_ja={c['value_ja']}")
    if c["value_en"]:
        bits.append(f"value_en={c['value_en']}")
    if c["citations"]:
        bits.append("cites=" + ",".join(c["citations"]))
    if c["normalized"]:
        bits.append("normalized=" + json.dumps(c["normalized"], ensure_ascii=False))
    if c["parse_error"]:
        bits.append(f"PARSE ERROR: {c['parse_error']}")
    checks = " ".join(f"{n}:{'ok' if v else 'FAIL'}" for n, v in side["checks"])
    text = " | ".join(bits) + (f"\n   checks: {checks}" if checks else "")
    for alt in alts:  # another part of the same document said something else
        text += "\n   another part of the document said: " + _cand_text(
            {"candidate": alt, "checks": []}
        )
    return text


def context(ss: list[Sentence], ids: set[str]) -> list[Sentence]:
    keep: set[int] = set()
    for i, s in enumerate(ss):
        if s.id in ids:
            keep |= set(range(max(0, i - 2), min(len(ss), i + 3)))
    return [ss[i] for i in sorted(keep)]


def render_item(iid: str, it: dict, row: ManifestRow, ja: list[Sentence]) -> str:
    spot = it["kind"] == "spot"
    cited = {c for s in it["sides"] for c in s["candidate"]["citations"]}
    sents = context(ja, cited)
    lines = [f"## {iid}" + ("  [consensus spot-check]" if spot else "")]
    lines.append(
        f"doc {row.doc_id[:12]} | source {row.source} | doc_type {row.doc_type} | license {row.license_class} | field {it['field']}"
    )
    lines.append("why: " + "; ".join(it["reasons"]))
    if spot:
        lines.append("A and B agree: " + _cand_text(it["sides"][0]))
    else:
        for tag, side in zip("ABC", it["sides"], strict=False):
            lines.append(f"{tag}: " + _cand_text(side))
        c = union_candidate(it)
        if c is not None:
            lines.append(
                "C (union of A and B items): "
                + _cand_text({"candidate": cand_dict(c), "checks": []})
            )
    lines.append("sentences (id | section | text):")
    for s in sents:
        path = "/".join(s.section_path) or "-"
        lines.append(
            f"{s.id} | {path} | {' '.join(s.text_orig.split())[:MAX_SENTENCE]}"
        )
    return "\n".join(lines)


def priority(it: dict) -> tuple:
    f = it["field"]
    tier = TIER1.index(f) if f in TIER1 else len(TIER1)
    return (
        f not in TIER1,
        it["kind"] == "spot",
        tier,
        FIELD_IDS.index(f),
        it["doc_id"],
    )


def header(n: int, total: int, fields: set[str], wave: int | None = None) -> str:
    defs = "\n".join(field_line(f) for f in FIELD_IDS if f in fields)
    tag = "" if wave is None else f" (gold wave {wave})"
    return f"# Shiori review batch {n:02d} of {total:02d}{tag}\n\nYou review pre-labels for Japanese public tender documents (silver labels). {ANSWER_FORMAT}\n\nField forms used in this batch:\n{defs}\n\n"


def export(split: str, open_only: bool, select, wave: int | None = None) -> list[Path]:  # fmt: skip
    """Review batches in export/. A gold wave (D-62) writes batch-w<N>-NN.md and
    replaces only its own wave's files; the plain export writes batch-NN.md."""
    rows = {r.doc_id: r for r in select(split, open_only)}
    items = sorted((i for i in load_items() if i["doc_id"] in rows), key=priority)
    reg = _registry()
    cache: dict[str, list[Sentence]] = {}
    texts: list[tuple[str, str]] = []
    for it in items:
        d = it["doc_id"]
        if d not in cache:
            cache[d] = [s for s in load_sentences(rows[d]) if s.language == "ja"]
        iid = item_id(reg, d, it["field"], it["kind"])
        texts.append((it["field"], render_item(iid, it, rows[d], cache[d])))
    _write(_ids_path(), json.dumps(reg))
    mp = _mapping_path()
    mapping = json.loads(mp.read_text()) if mp.exists() else {}
    for it in items:
        iid = item_id(reg, it["doc_id"], it["field"], it["kind"])
        m = {
            tag: provider_of(side)
            for tag, side in zip("ABC", it["sides"], strict=False)
        }
        if union_candidate(it) is not None:
            m["C"] = "union"
        mapping[iid] = m
    _write(mp, json.dumps(mapping, indent=1, sort_keys=True))
    batches: list[list[tuple[str, str]]] = [[]]
    for f, t in texts:
        cur = batches[-1]
        size = (
            len(header(1, 1, {x for x, _ in cur} | {f}))
            + sum(len(x) + 2 for _, x in cur)
            + len(t)
        )
        if cur and (len(cur) >= MAX_ITEMS or size > MAX_CHARS):
            batches.append([])
        batches[-1].append((f, t))
    out_dir = config.CACHE / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "batch-" if wave is None else f"batch-w{wave}-"
    for old in out_dir.glob(stem + ("[0-9]*.md" if wave is None else "*.md")):
        old.unlink()
    paths = []
    for n, b in enumerate((b for b in batches if b), 1):
        p = out_dir / f"{stem}{n:02d}.md"
        _write(
            p,
            header(n, len([x for x in batches if x]), {f for f, _ in b}, wave)
            + "\n\n".join(t for _, t in b)
            + "\n",
        )
        paths.append(p)
    return paths


# --- import ----------------------------------------------------------------------------


def choice_of(a: "Answer", item: dict) -> str:
    """provenance.reviewed_choice: the provider of the accepted side, union, or custom."""
    if not a.action.startswith("accept"):
        return "custom"
    i = "ABC".index(a.action[-1])
    if i < len(item["sides"]):
        return provider_of(item["sides"][i])
    return "union"


def shown(item: dict) -> dict[str, Candidate]:
    """The candidates the reviewer saw, by provider name (and "union" for C)."""
    out = {provider_of(s): _cand(item, i) for i, s in enumerate(item["sides"])}
    c = union_candidate(item)
    if c is not None:
        out["union"] = c
    return out


def review_record(iid: str, item: dict, choice: str, final: Candidate, cands: dict[str, Candidate]) -> dict:  # fmt: skip
    """One reviewed item for review-stats: per shown candidate, was it right? Right =
    the reviewer took it, or the final answer is the same answer (normalize_answer)."""
    return {"iid": iid, "doc_id": item["doc_id"], "field": item["field"], "kind": item["kind"],
            "choice": choice,
            "right": {p: p == choice or canonical(c) == canonical(final) for p, c in cands.items()}}  # fmt: skip


def record_review(iid: str, item: dict, choice: str, final: Candidate) -> None:
    rec = review_record(iid, item, choice, final, shown(item))
    with (config.CACHE / "reviews.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")


def review_stats(records: list[dict]) -> str:
    """Markdown: per provider and field type, how often its candidate was right when
    shown, with the item ids behind every number."""
    cells: dict[tuple[str, str], dict[str, list[str]]] = {}
    for r in records:
        kind = BY_ID[r["field"]].kind
        for p, ok in r["right"].items():
            cell = cells.setdefault((p, kind), {"right": [], "wrong": []})
            cell["right" if ok else "wrong"].append(r["iid"])
    out = ["| provider | field type | shown | right | right % | right (items) | wrong (items) |",
           "| --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for (p, kind), c in sorted(cells.items()):
        n = len(c["right"]) + len(c["wrong"])
        out.append(f"| {p} | {kind} | {n} | {len(c['right'])} | {100 * len(c['right']) / n:.0f}% | "
                   f"{', '.join(c['right']) or '-'} | {', '.join(c['wrong']) or '-'} |")  # fmt: skip
    totals: dict[str, list[int]] = {}
    for (p, _), c in cells.items():
        t = totals.setdefault(p, [0, 0])
        t[0] += len(c["right"])
        t[1] += len(c["right"]) + len(c["wrong"])
    out.append("")
    out += [
        f"- {p}: right {r} of {n} shown ({100 * r / n:.0f}%)"
        for p, (r, n) in sorted(totals.items())
    ]
    return "\n".join(out)


@dataclass
class Answer:
    lineno: int
    iid: str
    action: str  # accept A | accept B | absent | custom
    kv: dict[str, str]


def parse_reply(text: str) -> tuple[list[Answer], list[str]]:
    answers, errors = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line.startswith("F-"):
            continue  # prose around the answers
        parts = [p.strip() for p in line.split(" | ")]
        iid = parts[0]
        if len(iid) != 6 or not iid[2:].isdigit() or len(parts) < 2:
            errors.append(f"line {n}: expected 'F-0001 | action ...'")
            continue
        act = parts[1]
        if act in ("accept A", "accept B", "accept C"):
            note = parts[2] if len(parts) == 3 else ""
            if len(parts) > 3 or (note and not note.startswith("note=")):
                errors.append(f"line {n} ({iid}): only note= may follow '{act}'")
                continue
            answers.append(Answer(n, iid, act, {"note": note[5:]} if note else {}))
            continue
        if act not in ("absent", "custom"):
            errors.append(f"line {n} ({iid}): unknown action {act!r}")
            continue
        kv, bad = {}, None
        for p in parts[2:]:
            k, eq, v = p.partition("=")
            if not eq or k not in KEYS:
                bad = f"bad field {p[:30]!r}"
                break
            kv[k] = v
        if bad:
            errors.append(f"line {n} ({iid}): {bad}")
        elif act == "custom" and kv.get("status") not in (
            "present",
            "absent",
            "see_other_document",
        ):
            errors.append(
                f"line {n} ({iid}): custom needs status=present|absent|see_other_document"
            )
        elif act == "absent" and set(kv) - {"note"}:
            errors.append(f"line {n} ({iid}): absent takes only note=")
        else:
            answers.append(Answer(n, iid, act, kv))
    return answers, errors


def _cand(item: dict, side: int) -> Candidate:
    d = item["sides"][side]["candidate"]
    return Candidate(item["field"], d["status"], d["value_ja"], d["value_en"], d["normalized"], list(d["citations"]), labeler=d["labeler"], parse_error=d["parse_error"])  # fmt: skip


def candidate_for(a: Answer, item: dict, reviewer: str = "claude_chat") -> Candidate:
    if a.action.startswith("accept"):
        i = "ABC".index(a.action[-1])
        if i < len(item["sides"]):
            return _cand(item, i)
        c = union_candidate(item)
        if c is None:
            raise ValueError(f"this item has no candidate {a.action[-1]}")
        return c
    if a.action == "absent" or a.kv.get("status") == "absent":
        return Candidate(item["field"], status="absent", labeler=reviewer)
    row = {
        "field": item["field"],
        "status": a.kv["status"],
        "value_ja": a.kv.get("value_ja", ""),
        "value_en": a.kv.get("value_en", ""),
        "normalized": a.kv.get("normalized", ""),
        "citations": [c for c in a.kv.get("cites", "").split(",") if c],
    }
    return from_row(row, reviewer)


REVIEWERS = ("claude_chat", "claude_code")


def unsure_ids(text: str) -> list[str]:
    """Items whose note starts with UNSURE: (docs/review_session.md)."""
    return [a.iid for a in parse_reply(text)[0] if a.kv.get("note", "").strip().startswith("UNSURE:")]  # fmt: skip


def import_answers(text: str, reviewer: str = "claude_chat") -> tuple[int, list[str]]:
    """(labels written, errors). Nothing is written when there are errors. `reviewer`
    is claude_chat (a model in chat) or claude_code (a Claude Code review session,
    D-55); both give silver_model_reviewed, never human_audited. A line whose note
    starts with UNSURE: is not imported: it is held, with its item, in
    answers/held-unsure.md for a second review (`unsure_ids` lists them)."""
    if reviewer not in REVIEWERS:
        raise ValueError(f"reviewer must be one of {REVIEWERS}")
    answers, errors = parse_reply(text)
    reg = _registry()
    flagged = {(i["doc_id"], i["field"], i["kind"]): i for i in load_items()}
    rows = {r.doc_id: r for r in read_rows()}
    splits = json.loads(SPLITS.read_text())
    seen: set[str] = set()
    plan = []
    held: dict[str, str] = {}
    lines_of = text.splitlines()
    ss_cache: dict[str, list[Sentence]] = {}
    for a in answers:
        meta = reg["items"].get(a.iid)
        item = (
            flagged.get((meta["doc_id"], meta["field"], meta["kind"])) if meta else None
        )
        if a.iid in seen:
            errors.append(f"line {a.lineno} ({a.iid}): answered twice")
            continue
        seen.add(a.iid)
        if item is None:
            errors.append(
                f"line {a.lineno} ({a.iid}): unknown item, or already resolved"
            )
            continue
        if a.kv.get("note", "").strip().startswith("UNSURE:"):
            held[a.iid] = lines_of[a.lineno - 1].strip()
            continue
        row = rows[item["doc_id"]]
        if row.doc_id not in ss_cache:
            ss_cache[row.doc_id] = load_sentences(row)
        by_id = {s.id: s for s in ss_cache[row.doc_id]}
        try:
            c = candidate_for(a, item, reviewer)
        except ValueError as e:
            errors.append(f"line {a.lineno} ({a.iid}): {e}")
            continue
        if a.action.startswith("accept") and c.parse_error:
            errors.append(
                f"line {a.lineno} ({a.iid}): {a.action[-1]} has a parse error, answer custom"
            )
            continue
        en = " ".join(s.text_orig for s in ss_cache[row.doc_id] if s.language == "en")
        checks = run_checks(c, row, by_id, en)
        bad = failed(checks, HARD)
        if bad:
            errors.append(
                f"line {a.lineno} ({a.iid}): fails {', '.join(bad)}"
                + (
                    f" ({c.check_notes['schema_valid']})"
                    if "schema_valid" in bad and c.check_notes.get("schema_valid")
                    else ""
                )
            )
            continue
        plan.append((a, item, row, c, checks))
    if errors:
        return 0, errors
    by_doc: dict[str, dict[str, dict]] = {}
    for a, item, row, c, checks in plan:
        labelers = [tuple(x) for x in item["labelers"]]
        overlap = any(x[0] == "local" for x in labelers)
        agreement = bool(item["agreement"]) if len(labelers) >= 2 else None
        note = a.kv.get("note") or None
        if a.action.startswith("accept"):
            note = f"accepted {a.action[-1]}" + (f"; {note}" if note else "")
        choice = choice_of(a, item)
        prov = provenance(labelers, agreement, checks, overlap, reviewed_by=reviewer, review_note=note,
                          final_state="silver_model_reviewed", reviewed_choice=choice,
                          prompt_version=item.get("prompt_version", "sv1"))  # fmt: skip
        record_review(a.iid, item, choice, c)
        line = label_line(row, c, item["field"], prov)
        line["extractor_version"] = EXTRACTOR_VERSION
        by_doc.setdefault(row.doc_id, read_resolved(row.doc_id))[item["field"]] = line
        if item["kind"] == "spot":
            before = Candidate(item["field"], **{k: v for k, v in item["sides"][0]["candidate"].items() if k in ("status", "value_ja", "value_en", "normalized", "citations")})  # fmt: skip
            changed = c.key() != before.key()
            with (config.CACHE / "spotcheck.jsonl").open("a") as f:
                f.write(json.dumps({"doc_id": row.doc_id, "field": item["field"], "changed": changed}) + "\n")  # fmt: skip
    for doc_id, lines in by_doc.items():
        write_resolved(doc_id, lines)
        p = decisions_path(doc_id)
        d = json.loads(p.read_text())
        done = {
            (it["field"], it["kind"]) for _, it, r, _, _ in plan if r.doc_id == doc_id
        }
        d["items"] = [i for i in d["items"] if (i["field"], i["kind"]) not in done]
        _write(p, json.dumps(d, ensure_ascii=False))
        materialize(rows[doc_id], splits)
    rebuild_flagged()
    write_held(held, reviewer)
    return len(plan), []


def held_paths() -> tuple[Path, Path]:
    d = config.CACHE / "answers"
    return d / "held-unsure.md", d / "held-unsure.json"


def write_held(new: dict[str, str], reviewer: str) -> None:
    """answers/held-unsure.md: every held UNSURE answer whose item is still open, with
    the item as the export shows it, in the batch answer format so a chat can answer
    them. The held lines are kept in held-unsure.json; an item answered since (imported
    or reopened) drops out. Both files are gitignored (restricted text)."""
    md, js = held_paths()
    if not new and not js.exists():
        return
    old = json.loads(js.read_text()) if js.exists() else {}
    held = {**old, **{i: {"line": ln, "reviewer": reviewer} for i, ln in new.items()}}
    reg = _registry()
    flagged = {(i["doc_id"], i["field"], i["kind"]): i for i in load_items()}
    rows = {r.doc_id: r for r in read_rows()}
    ss: dict[str, list[Sentence]] = {}
    keep, parts = {}, []
    for iid in sorted(held):
        meta = reg["items"].get(iid)
        item = (
            flagged.get((meta["doc_id"], meta["field"], meta["kind"])) if meta else None
        )
        if item is None:
            continue
        keep[iid] = held[iid]
        row = rows[item["doc_id"]]
        if row.doc_id not in ss:
            ss[row.doc_id] = [s for s in load_sentences(row) if s.language == "ja"]
        parts.append(render_item(iid, item, row, ss[row.doc_id])
                     + f"\nheld answer ({held[iid]['reviewer']}, not imported): {held[iid]['line']}")  # fmt: skip
    _write(js, json.dumps(keep, ensure_ascii=False, indent=1))
    fields = {reg["items"][i]["field"] for i in keep}
    defs = "\n".join(field_line(f) for f in FIELD_IDS if f in fields)
    head = (f"# Held UNSURE items ({len(keep)})\n\nA reviewer answered these items but was not "
            "sure, so import held them back. Each item ends with the held answer. Review them "
            f"again and answer every item. {ANSWER_FORMAT}\n\nField forms used here:\n{defs}\n\n")  # fmt: skip
    _write(md, head + "\n\n".join(parts) + "\n")


# --- calibrate -------------------------------------------------------------------------


def answer_key(a: Answer, item: dict | None) -> str:
    """What an answer says, notes and English left out. While the item is still open
    the answer is built as a candidate and compared by model.canonical, so accept A
    and a custom answer equal to A are the same answer; once imported, the line's own
    fields are compared."""
    if item is not None:
        try:
            return canonical(candidate_for(a, item))
        except ValueError:
            pass
    kv = {k: v for k, v in a.kv.items() if k not in ("note", "value_en")}
    action = "absent" if a.kv.get("status") == "absent" else a.action
    return json.dumps([action, {} if action == "absent" else kv], sort_keys=True, ensure_ascii=False)  # fmt: skip


def calibrate(text_a: str, text_b: str, name_a: str = "a", name_b: str = "b") -> str:
    """Two answer files for the same batch: how often they give the same answer, and
    every item where they differ with both lines side by side. Writes nothing."""
    reg = _registry()
    flagged = {(i["doc_id"], i["field"], i["kind"]): i for i in load_items()}
    (ans_a, err_a), (ans_b, err_b) = parse_reply(text_a), parse_reply(text_b)
    lines_a, lines_b = ({ln.split(" | ")[0]: ln for ln in map(str.strip, t.splitlines())
                         if ln.startswith("F-")} for t in (text_a, text_b))  # fmt: skip
    by_a, by_b = {x.iid: x for x in ans_a}, {x.iid: x for x in ans_b}
    both = [i for i in by_a if i in by_b]
    out = [f"# Calibration: {name_a} vs {name_b}", ""]
    out += [f"- {name_a}: {e}" for e in err_a] + [f"- {name_b}: {e}" for e in err_b]
    diff = []
    for iid in both:
        meta = reg["items"].get(iid)
        item = (
            flagged.get((meta["doc_id"], meta["field"], meta["kind"])) if meta else None
        )
        if answer_key(by_a[iid], item) != answer_key(by_b[iid], item):
            diff.append((iid, meta))
    same = len(both) - len(diff)
    out.append(f"Items in both: {len(both)}; same answer: {same}"
               + (f" ({100 * same / len(both):.0f}%)" if both else "") + ".")  # fmt: skip
    for name, mine, other in ((name_a, by_a, by_b), (name_b, by_b, by_a)):
        only = [i for i in mine if i not in other]
        if only:
            out.append(f"Only in {name}: {', '.join(only)}.")
    for name, text in ((name_a, text_a), (name_b, text_b)):
        u = unsure_ids(text)
        out.append(
            f"UNSURE in {name}: {len(u)}" + (f" ({', '.join(u)})" if u else "") + "."
        )
    if diff:
        out += ["", "## Items that differ", ""]
    for iid, meta in diff:
        where = f" (doc {meta['doc_id'][:12]}, {meta['field']})" if meta else ""
        out += [
            f"### {iid}{where}",
            f"- {name_a}: `{lines_a[iid]}`",
            f"- {name_b}: `{lines_b[iid]}`",
            "",
        ]
    return "\n".join(out).rstrip() + "\n"


# --- reopen ----------------------------------------------------------------------------


def reopen(row: ManifestRow, field: str, reason: str, extra: str | None = None,
           show_label: bool = False, reviewed: bool = False) -> dict:  # fmt: skip
    """Turn an accepted consensus field back into a review item (D-51, D-52). The
    resolved line is removed; the item shows the original labelers' answers, rebuilt
    from their cached raw answers, or with `show_label` the label line itself as A.
    `extra` adds one more cached answer as the last candidate: `name[@prompt]`, name a
    cloud provider (gemini, groq) or a local model (Qwen3.5-9B-Q4_K_M), prompt by
    default the line's own. It joins the item's labelers (a local one makes the
    reviewed label carry labeler_overlap). Refuses a reviewed line unless `reviewed`
    is given; that item has kind `reopened`, so it gets a new item id and the first
    review stays in reviews.jsonl under the old one. A label file that
    already exists is left as it is until the review is imported, when `materialize`
    rewrites it with the reviewed line (the reopen-and-review path)."""
    from eval.silver.config import PROVIDERS
    from eval.silver.pipeline import raw_state

    line = read_resolved(row.doc_id).get(field)
    state = (line or {}).get("provenance", {}).get("final_state")
    ok = (
        ("silver_consensus", "silver_model_reviewed")
        if reviewed
        else ("silver_consensus",)
    )
    if state not in ok:
        raise ValueError(
            f"{field} is not an accepted consensus line of {row.doc_id[:12]}"
            + ("" if reviewed else " (a reviewed line needs --reviewed)")
        )
    assert line is not None
    prov = line["provenance"]
    prompt = prov["prompt_version"]
    labelers = [(p["provider"], p["model"], p["date"], p.get("prompt_version") or prompt)
                for p in prov["pre_labelers"]]  # fmt: skip
    asked = [] if show_label else [(p, m, pr) for p, m, _, pr in labelers]
    if extra:
        name, _, xprompt = extra.partition("@")
        p, m = (name, PROVIDERS[name].model) if name in PROVIDERS else ("local", name)
        raw = load_raw(raw_path(row.doc_id, p, m, xprompt or prompt))
        if raw_state(raw) != "complete":
            raise ValueError(f"no complete cached answer of {extra} for {row.doc_id[:12]}")  # fmt: skip
        labelers.append(
            (p, m, max(c["date"] for c in raw["chunks"].values()), xprompt or prompt)
        )
        asked.append((p, m, xprompt or prompt))
    ss = load_sentences(row)
    by_id = {s.id: s for s in ss}
    en = " ".join(s.text_orig for s in ss if s.language == "en")
    cands = []
    if show_label:
        cands.append(Candidate(field, line["status"], line.get("value_ja"), line.get("value_en"),
                               line.get("normalized"), list(line.get("citations", [])),
                               labeler=f"label/{prompt}"))  # fmt: skip
    for p, m, pr in asked:
        raw = load_raw(raw_path(row.doc_id, p, m, pr))
        cands.append(answers(raw, f"{p}/{m}", applicable_fields(row.doc_type), by_id)[field])  # fmt: skip
    sides = [{"labeler": c.labeler, "candidate": cand_dict(c),
              "checks": run_checks(c, row, by_id, en)} for c in cands]  # fmt: skip
    kind = "reopened" if state == "silver_model_reviewed" else "flagged"
    item = {"doc_id": row.doc_id, "field": field, "kind": kind, "reasons": [reason],
            "sides": sides, "agreement": False, "labelers": labelers,
            "prompt_version": prompt}  # fmt: skip
    lines = read_resolved(row.doc_id)
    del lines[field]
    write_resolved(row.doc_id, lines)
    p = decisions_path(row.doc_id)
    d = json.loads(p.read_text()) if p.exists() else {"items": []}
    d["items"] = [i for i in d["items"] if i["field"] != field] + [item]
    _write(p, json.dumps(d, ensure_ascii=False))
    rebuild_flagged()
    return item
