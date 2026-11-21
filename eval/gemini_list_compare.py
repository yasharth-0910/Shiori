# ruff: noqa: E501
"""The full hybrid pipeline's list fields, compared with Gemini's list items (local model only, no network).

    uv run python -m eval.gemini_list_compare [--limit N] [--report-only]

For the 50 documents in data/cache/gemini_batches/index.md: the sidecar's path (read_pages, doc type from page 1,
segment, rules.extract), then the shipped local model calls: llm.extract_lists (eligibility, deadlines,
required_documents) and llm.extract_scalars (D-95, on), with the shipped prompts and one llama-server
(eval.hybrid.Server, Qwen3.5-9B). The model's items are cached per document in
data/cache/gemini_compare/lists_cache/<12-char doc prefix>.json, so a stopped run resumes where it stopped
(a document with a failed model call is not cached and is asked again on the next run).

Gemini's rows in data/cache/gemini_ref/gemini_fields.csv: 'eligibility N' -> eligibility, 'deadline N' ->
deadlines, 'document N' -> required_documents. A row whose answer_en says not stated is no item.

Matching (also written into the report): a Gemini item and one of our items match when, after NFKC and with all
whitespace removed ("flat"),
  text:  one text contains the other, where our text is value_ja of the item (eligibility text_ja, document
         name_ja, for a deadline the original wording of its cited sentences) and Gemini's is quote_ja or any
         piece of it (quote_ja is cut at line breaks and at "..." or an ellipsis; pieces under 3 characters
         are ignored); or
  cited: Gemini's quote (or a piece of it) is inside one of the sentences our item cites, or one of those
         sentences is inside the quote.
Both need at least 3 flat characters on each side. Gemini quotes are not verbatim, so a miss is not an error.

Writes data/cache/gemini_compare/lists_report.md (counts and doc id prefixes only) and lists.tsv (Japanese text,
gitignored). Dev-time only; no cloud call. Gemini is a silver reference, not ground truth.
"""

import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from shiori_core.doctype import detect_doc_type, first_page_lines
from shiori_core.extract import llm, rules
from shiori_core.extract.rules import Extracted
from shiori_core.ingest import read_pages
from shiori_core.segment import segment

from eval import hybrid
from eval.gemini_compare import flat, gemini_found, read_index

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data/cache/gemini_ref/gemini_fields.csv"
OUT = ROOT / "data/cache/gemini_compare"
CACHE = OUT / "lists_cache"
PIDFILE = OUT / "lists.pid"
FIELDS = llm.LIST_FIELDS  # eligibility, deadlines, required_documents
GEMINI_PREFIX = {"eligibility": "eligibility", "deadline": "deadlines", "document": "required_documents"}  # fmt: skip
MIN = 3  # flat characters a text needs to count in a match
_SPLIT = re.compile(r"[\r\n]+|\.{3,}|…+|…")


# --- matching (pure, tested with made-up strings) ---------------------------------------------


def pieces(quote: str) -> list[str]:
    """Gemini's quote cut at line breaks and ellipses, short pieces dropped."""
    return [p for p in (flat(x) for x in _SPLIT.split(quote)) if len(p) >= MIN]


def _inside(a: str, b: str) -> bool:
    return len(a) >= MIN and len(b) >= MIN and (a in b or b in a)


def match_how(our_text: str, our_cited: list[str], quote: str) -> str:
    """'text', 'cited' or '' (no match), by the rules in the module docstring."""
    ps = pieces(quote)
    t = flat(our_text)
    if any(_inside(t, p) for p in ps):
        return "text"
    if any(_inside(flat(c), p) for c in our_cited for p in ps):
        return "cited"
    return ""


def match_items(ours: list[dict], theirs: list[dict]) -> tuple[list[tuple[int, str] | None], list[tuple[int, str] | None]]:  # fmt: skip
    """For each of our items the first Gemini item it matches, and for each Gemini item the first of ours:
    (index, how) or None."""
    ours_to: list[tuple[int, str] | None] = [None] * len(ours)
    theirs_to: list[tuple[int, str] | None] = [None] * len(theirs)
    for i, o in enumerate(ours):
        for j, g in enumerate(theirs):
            how = match_how(o["value_ja"], o["cited_text"], g["quote_ja"])
            if how:
                ours_to[i] = ours_to[i] or (j, how)
                theirs_to[j] = theirs_to[j] or (i, how)
    return ours_to, theirs_to


# --- one document -------------------------------------------------------------------------------


def our_items(x: Extracted, by_id: dict) -> list[dict]:
    """The items of a list answer, flat and JSON-able (the text is local only)."""
    out = []
    for it in x.normalized["items"]:
        cited = [by_id[c] for c in it["citations"] if c in by_id]
        cited_text = [s.text_orig for s in cited]
        if x.field in llm.TEXT_KEY:
            value = it[llm.TEXT_KEY[x.field]]
            in_cit = rules.value_in_citation(value, cited)
        else:  # deadlines: the value is the date or the relative text; the text is what it cites
            value = "\n".join(cited_text)
            rel = it.get("relative_text")
            in_cit = True if rel is None else rules.value_in_citation(rel, cited)
        kind = it.get("kind", "")
        out.append({
            "value_ja": value, "label": f"{kind}/{it['polarity']}" if "polarity" in it else kind,
            "when": it.get("datetime") or it.get("relative_text") or "",
            "cited_ids": it["citations"], "cited_text": cited_text,
            "page": cited[0].page if cited else 0, "value_in_citation": in_cit,
        })  # fmt: skip
    return out


def run_doc(path: Path, client: llm.Client) -> dict:
    """The sidecar's path, then the shipped model calls. Raises nothing for a failed call: it is in `failed`."""
    t0 = time.monotonic()
    doc = read_pages(path)
    doc_type = (
        detect_doc_type(first_page_lines(doc.pages[0])) if doc.pages else "notice"
    )
    sents = segment(doc.pages)
    by_id = {s.id: s for s in sents if s.language == "ja"}
    base = rules.extract(doc_type, sents)
    stats: list[llm.CallStat] = []
    lists = llm.extract_lists(doc_type, sents, client.complete, stats)
    t_lists = time.monotonic()
    scalars = llm.extract_scalars(doc_type, sents, client.complete, set(base), stats)
    t1 = time.monotonic()
    return {
        "doc_type": doc_type,
        "items": {f: our_items(lists[f], by_id) if f in lists else [] for f in FIELDS},
        "scalars_kept": len(scalars),
        "failed": [
            f"{s.field}:{s.call_failed}"
            for s in stats
            if s.call_failed and s.call_failed != "Truncated"
        ],  # fmt: skip
        "truncated": [s.field for s in stats if s.call_failed == "Truncated"],
        "seconds": t1 - t0,
        "model_seconds": sum(s.seconds for s in stats),
        "list_seconds": t_lists - t0,
    }


# --- Gemini's items -----------------------------------------------------------------------------


def gemini_items() -> dict[tuple[str, str], list[dict]]:
    """(doc prefix of 8, our field) -> items Gemini stated; plus the ones it marked not stated, as a count."""
    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in csv.DictReader(CSV.open(encoding="utf-8")):
        m = re.fullmatch(r"(eligibility|deadline|document) (\d+)", r["field"])
        if m and gemini_found(r["answer_en"]):
            out[(r["doc_prefix"], GEMINI_PREFIX[m[1]])].append({**r, "n": m[2]})
    return out


def one_line(s: str) -> str:
    return re.sub(r"[\t\r\n]+", " / ", s)


# --- the run ------------------------------------------------------------------------------------


def stamp(done: int, total: int, started: float) -> None:
    print(
        f"{done}/{total} documents, {(time.monotonic() - started) / 60:.1f} min",
        flush=True,
    )


def main(argv: list[str]) -> None:
    started = time.monotonic()
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    report_only = "--report-only" in argv
    splits = json.loads((ROOT / "data/eval/splits.json").read_text())
    manifest = [json.loads(x) for x in (ROOT / "data/manifests/documents.jsonl").read_text().splitlines()]  # fmt: skip
    index = read_index()[:limit]
    CACHE.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()))
    failures: dict[str, list[str]] = {}
    results: dict[str, dict] = {}
    client: llm.Client | None = None
    try:
        for n, (prefix, _issuer) in enumerate(index, 1):
            rows = [m for m in manifest if m["doc_id"].startswith(prefix)]
            if len(rows) != 1 or splits.get(rows[0]["issuer_org"]) == "test":
                failures.setdefault("not_run", []).append(prefix[:8])
                continue
            cache = CACHE / f"{prefix}.json"
            if cache.exists():
                results[prefix] = json.loads(cache.read_text(encoding="utf-8"))
                stamp(n, len(index), started)
                continue
            if report_only:
                failures.setdefault("not_cached", []).append(prefix[:8])
                continue
            try:
                if (
                    client is None
                ):  # the server starts only when a document is not cached
                    hybrid.State.server = hybrid.Server()
                    client = llm.Client(hybrid.PORT)
                res = run_doc(ROOT / rows[0]["path"], client)
            except Exception as e:  # counted by type; never the message
                failures.setdefault(type(e).__name__, []).append(prefix[:8])
                stamp(n, len(index), started)
                continue
            if res["failed"]:  # a failed call is not cached, the next run asks again
                for f in res["failed"]:
                    failures.setdefault("call_" + f.split(":")[1], []).append(f"{prefix[:8]}:{f.split(':')[0]}")  # fmt: skip
            else:
                cache.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            results[prefix] = res
            stamp(n, len(index), started)
    finally:
        hybrid.stop()
        PIDFILE.unlink(missing_ok=True)
    write_outputs(index, results, failures, started)


def write_outputs(index: list[tuple[str, str]], results: dict[str, dict], failures: dict[str, list[str]], started: float) -> None:  # fmt: skip
    gem = gemini_items()
    tsv = ["doc\tfield\tour_value_ja\tkind_or_polarity\twhen\tcited_ids\tpage\tvalue_in_citation\tmatched_gemini\tmatch\tgemini_answer_en\tgemini_quote_ja"]  # fmt: skip
    cnt = {f: Counter() for f in FIELDS}
    unmatched_docs: dict[str, list[str]] = {f: [] for f in FIELDS}
    for prefix, res in results.items():
        p8 = prefix[:8]
        for f in FIELDS:
            ours = res["items"][f]
            theirs = gem.get((p8, f), [])
            o2g, g2o = match_items(ours, theirs)
            c = cnt[f]
            c["docs"] += 1
            c["gemini"] += len(theirs)
            c["ours"] += len(ours)
            c["gemini_no_quote"] += sum(1 for g in theirs if not pieces(g["quote_ja"]))
            c["gemini_matched"] += sum(1 for m in g2o if m)
            c["ours_matched"] += sum(1 for m in o2g if m)
            c["ours_unmatched"] += sum(1 for m in o2g if not m)
            c["ours_unmatched_gemini_none"] += (
                sum(1 for m in o2g if not m) if not theirs else 0
            )
            c["ours_not_in_citation"] += sum(
                1 for o in ours if not o["value_in_citation"]
            )
            c["docs_gemini_items_ours_none"] += 1 if theirs and not ours else 0
            c["docs_ours_items_gemini_none"] += 1 if ours and not theirs else 0
            if any(not m for m in g2o):
                unmatched_docs[f].append(p8)
            for o, m in zip(ours, o2g, strict=True):
                g = theirs[m[0]] if m else None
                tsv.append("\t".join([p8, f, one_line(o["value_ja"]), o["label"], o["when"], ",".join(o["cited_ids"]), str(o["page"]), str(o["value_in_citation"]), f"{g['field']}" if g else "none", m[1] if m else "", one_line(g["answer_en"]) if g else "", one_line(g["quote_ja"]) if g else ""]))  # fmt: skip
            for g, m in zip(theirs, g2o, strict=True):
                if not m:  # a Gemini item none of ours matched
                    tsv.append("\t".join([p8, f, "", "", "", "", "", "", g["field"], "gemini_only", one_line(g["answer_en"]), one_line(g["quote_ja"])]))  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lists.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    secs = sorted(r["seconds"] for r in results.values())
    med = secs[len(secs) // 2] if len(secs) % 2 else ((secs[len(secs) // 2 - 1] + secs[len(secs) // 2]) / 2 if secs else 0.0)  # fmt: skip
    md = [
        "# Hybrid list fields vs Gemini",
        "",
        f"Documents in the index slice: {len(index)}; with results here: {len(results)}. Counts and doc id prefixes only; text is in lists.tsv.",
        "Full hybrid path: rules, then llm.extract_lists and llm.extract_scalars as shipped, Qwen3.5-9B on one local llama-server, no network. Gemini is a silver reference and its quotes are not verbatim.",
        "",
        "## How items were matched",
        "",
        "A Gemini item (a row 'eligibility N', 'deadline N' or 'document N' whose answer_en does not say not stated) and one of our items match when, after NFKC and removal of all whitespace, one of these holds. Each side needs at least 3 characters.",
        "",
        "- text: one text contains the other. Our text is the item's value_ja (eligibility text_ja, document name_ja; for a deadline, the original wording of the sentences it cites). Gemini's text is quote_ja or any piece of it; quote_ja is cut at line breaks and at '...' or an ellipsis, and pieces under 3 characters are ignored.",
        "- cited: Gemini's quote (or a piece) is inside one of the sentences our item cites, or one of those sentences is inside the quote.",
        "",
        "Recall = Gemini items matched by at least one of ours. Precision = our items matched by at least one Gemini item. An item can match several on the other side; each counts once.",
        "",
        "## Per field",
        "",
        "| field | docs | Gemini items | our items | Gemini matched (recall) | ours matched (precision) | ours with no Gemini counterpart | of those, docs where Gemini listed none | our items failing value_in_citation |",
        "|---|---|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    for f in FIELDS:
        c = cnt[f]
        pct = lambda a, b: f"{a} of {b} ({100 * a / b:.0f}%)" if b else f"{a} of 0"  # noqa: E731
        md.append(f"| {f} | {c['docs']} | {c['gemini']} | {c['ours']} | {pct(c['gemini_matched'], c['gemini'])} | {pct(c['ours_matched'], c['ours'])} | {c['ours_unmatched']} | {c['ours_unmatched_gemini_none']} | {c['ours_not_in_citation']} |")  # fmt: skip
    md += ["", "## Per field, documents", ""]
    for f in FIELDS:
        c = cnt[f]
        md.append(f"- {f}: documents where Gemini has items and we have none: {c['docs_gemini_items_ours_none']}; where we have items and Gemini has none: {c['docs_ours_items_gemini_none']}; Gemini items with no usable quote (cannot match): {c['gemini_no_quote']}")  # fmt: skip
        md.append(f"  - doc prefixes with at least one Gemini item no item of ours matched: {', '.join(unmatched_docs[f]) or 'none'}")  # fmt: skip
    md += [
        "",
        "## Time",
        "",
        f"seconds per document (model calls plus ingest, this run or the run that cached it): median {med:.1f}, total {sum(secs):.0f} over {len(secs)} documents; scalar fallback answers kept: {sum(r['scalars_kept'] for r in results.values())}",  # fmt: skip
        f"documents with a truncated list call: {', '.join(p[:8] + ':' + ','.join(r['truncated']) for p, r in results.items() if r['truncated']) or 'none'}",  # fmt: skip
        f"wall time of this run: {(time.monotonic() - started) / 60:.1f} minutes (a resumed run counts only its own part).",
        "",
        "## Failures",
        "",
        *([f"- {k}: {', '.join(v)}" for k, v in failures.items()] or ["- none"]),
        "",
    ]  # fmt: skip
    (OUT / "lists_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main(sys.argv[1:])
