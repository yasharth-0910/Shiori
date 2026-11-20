# ruff: noqa: E501
"""Rules plus the local scalar fallback, compared with Gemini's silver answers (local model only, no network).

    uv run python -m eval.gemini_scalar_compare [--limit N]

For the documents in data/cache/gemini_batches/index.md: the sidecar's path (read_pages, doc type from page 1,
segment, rules.extract), then one grouped scalar call per prompt variant for the fields the rules left empty
(llm.scalar_sentences / scalar_prompt / scalar_schema as shipped; only the system prompt differs, defined here):

    B  = the current scalar system prompt without "When unsure, answer null."
    B2 = B plus wording rules (exact copy, ISO date only in the date field, scope and place null cases)

Writes data/cache/gemini_compare/scalars_report.md (counts and doc id prefixes only) and scalars.tsv (Japanese text,
gitignored). A model answer counts as ours only when it passes the pipeline's checks (llm._scalar_answer, as the
shipped fallback does); every raw answer is in the tsv with whether it passed value_in_citation. Starts and stops
one llama-server (eval.hybrid.Server). Gemini is a silver reference, not ground truth.
"""

import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

from shiori_core.doctype import detect_doc_type, first_page_lines
from shiori_core.extract import llm, rules
from shiori_core.extract.rules import Extracted
from shiori_core.fields import BY_ID
from shiori_core.ingest import read_pages
from shiori_core.segment import segment

from eval import hybrid
from eval.gemini_compare import (
    CLASSES,
    contains_either,
    gemini_found,
    iso_dates,
    read_index,
)
from eval.gemini_compare import (
    compare as compare5,
)
from eval.scalar_probe import make_complete

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data/cache/gemini_ref/gemini_fields.csv"
OUT = ROOT / "data/cache/gemini_compare"
FIELDS = ("title", "issuer_org", "contracting_officer", "notice_date", "performance_period", "scope_summary", "delivery_deadline", "delivery_location")  # fmt: skip
# The scalar system prompt as shipped before 2026-11-21 (D-95), kept here so B and B2 stay what was measured.
OLD_SYSTEM = (
    "You read part of a Japanese public tender document. Each sentence is written as "
    "[id] text. For each field listed, answer with an object, or null when the document does "
    "not state it. Use only what the sentences say. value_ja is copied exactly from the "
    "sentences (several sentences: one per line); citations are the ids it comes from, exactly "
    "as shown. When unsure, answer null."
)
B = OLD_SYSTEM.replace(" When unsure, answer null.", "")
B2 = (
    B
    + " value_ja must be copied exactly from the sentences, with no added spaces."
    + " Put the ISO date only in the date field, and quote the date as written in value_ja."
    + " For scope_summary and delivery_location answer null if the text only says see the spec (仕様書による) or does not label the place as 納入場所 or 履行場所."
    + " Never answer scope_summary with a copy of the title."
    + " For delivery_deadline answer null unless the sentence labels the date as 納入期限 or 納期; the end of a contract period or performance period is not a delivery deadline."
    + " For delivery_location answer null for places where bids are opened or inquiries are answered (入札室, 開札場所, 問い合わせ先); use it only for a place labelled 納入場所, 履行場所 or 委託場所."
)
VARIANTS = {"B": B, "B2": B2}


def compare(field: str, ours: Extracted | None, answer_en: str, quote_ja: str) -> str:
    """The five classes. The five fields of eval.gemini_compare go through its own rules; the rest here."""
    if field in (
        "title",
        "issuer_org",
        "contracting_officer",
        "notice_date",
        "performance_period",
    ):
        return compare5(field, ours, answer_en, quote_ja)[0]
    we, g = ours is not None and ours.status == "present", gemini_found(answer_en)
    if field == "delivery_deadline":
        gd = iso_dates(quote_ja)
        g = g and bool(gd)
    if not (we or g):
        return "both_not_found"
    if not g:
        return "we_found_gemini_not_stated"
    if not we or ours is None:
        return "gemini_found_we_not_found"
    if field == "delivery_deadline":
        same = gd[0] == ours.normalized.get("date")
    else:  # scope_summary, delivery_location: one contains the other
        same = contains_either(ours.value_ja, quote_ja)
    return "both_found_agree" if same else "both_found_differ"


def one_line(s: str) -> str:
    return re.sub(r"[\t\r\n]+", " / ", s)


def main(argv: list[str]) -> None:
    started = time.monotonic()
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    splits = json.loads((ROOT / "data/eval/splits.json").read_text())
    manifest = [
        json.loads(x)
        for x in (ROOT / "data/manifests/documents.jsonl").read_text().splitlines()
    ]
    gem: dict[tuple[str, str], dict[str, str]] = {}
    for r in csv.DictReader(CSV.open(encoding="utf-8")):
        if r["field"] in FIELDS:
            gem.setdefault((r["doc_prefix"], r["field"]), r)
    index = read_index()[:limit]
    classes = {v: {f: Counter() for f in FIELDS} for v in ("rules", *VARIANTS)}
    seconds: dict[str, list[float]] = {v: [] for v in VARIANTS}
    raw: dict[str, Counter] = {
        v: Counter() for v in VARIANTS
    }  # non_null, passed_checks, failed_value_in_citation
    failures: dict[str, list[str]] = {}
    tsv = [
        "variant\tdoc\tfield\tour_value_ja\tcited_ids\tpage\tvalue_in_citation\tseconds\tgemini_answer_en\tgemini_quote_ja"
    ]
    hybrid.State.server = hybrid.Server()
    try:
        for prefix, _issuer in index:
            rows = [m for m in manifest if m["doc_id"].startswith(prefix)]
            if len(rows) != 1 or splits.get(rows[0]["issuer_org"]) == "test":
                failures.setdefault("not_run", []).append(prefix)
                continue
            try:
                doc = read_pages(ROOT / rows[0]["path"])
                doc_type = (
                    detect_doc_type(first_page_lines(doc.pages[0]))
                    if doc.pages
                    else "notice"
                )
                sents = segment(doc.pages)
                ja = [s for s in sents if s.language == "ja"]
                found = rules.extract(doc_type, sents)
            except Exception as e:  # counted by type; never the message
                failures.setdefault(type(e).__name__, []).append(prefix)
                continue
            by_all = {s.id: s for s in ja}
            asked = [
                f
                for f in llm.SCALAR_FIELDS
                if doc_type in BY_ID[f].applies_to and f not in found
            ]
            sent = llm.scalar_sentences(asked, ja) if asked else []
            by_sent = {s.id: s for s in sent}
            g = {
                f: gem.get((prefix[:8], f), {"answer_en": "", "quote_ja": ""})
                for f in FIELDS
            }
            for f in FIELDS:
                classes["rules"][f][
                    compare(f, found.get(f), g[f]["answer_en"], g[f]["quote_ja"])
                ] += 1
                if f in found:
                    x = found[f]
                    tsv.append("\t".join(["rules", prefix[:8], f, one_line(x.value_ja), ",".join(x.citations), str(by_all[x.citations[0]].page), "True", "", one_line(g[f]["answer_en"]), one_line(g[f]["quote_ja"])]))  # fmt: skip
            for name, system in VARIANTS.items():
                answers: dict = {}
                secs = 0.0
                if sent:
                    calls: list[dict] = []
                    t0 = time.monotonic()
                    try:
                        answers = json.loads(make_complete(calls)(system, llm.scalar_prompt(asked, sent), llm.scalar_schema(asked), llm.SCALAR_MAX_OUT))  # fmt: skip
                    except (OSError, ValueError, KeyError) as e:
                        failures.setdefault(f"call_{type(e).__name__}", []).append(
                            f"{name}:{prefix[:8]}"
                        )
                    secs = time.monotonic() - t0
                    seconds[name].append(secs)
                kept: dict[str, Extracted] = {}
                for f in asked:
                    a = answers.get(f) if isinstance(answers, dict) else None
                    if not isinstance(a, dict):
                        continue
                    raw[name]["non_null"] += 1
                    x, why = llm._scalar_answer(f, a, by_sent, doc_type)
                    cit = [c for c in (a.get("citations") or []) if c in by_all]
                    in_cit = bool(cit) and rules.value_in_citation((a.get("value_ja") or "").strip(), [by_all[c] for c in cit])  # fmt: skip
                    if x is not None:
                        kept[f] = x
                        raw[name]["passed_checks"] += 1
                    tsv.append("\t".join([name, prefix[:8], f, one_line(a.get("value_ja") or ""), ",".join(a.get("citations") or []), str(by_all[cit[0]].page) if cit else "", str(in_cit), f"{secs:.1f}", one_line(g[f]["answer_en"]), one_line(g[f]["quote_ja"])]))  # fmt: skip
                for f in FIELDS:
                    classes[name][f][
                        compare(
                            f,
                            found.get(f) or kept.get(f),
                            g[f]["answer_en"],
                            g[f]["quote_ja"],
                        )
                    ] += 1
    finally:
        hybrid.stop()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scalars.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    md = ["# Rules + scalar fallback vs Gemini", "", f"Documents: {len(index)} in the index slice. Counts and doc id prefixes only; text is in scalars.tsv.",
          "'rules' is the rules alone. B and B2 are rules plus the scalar fallback with that system prompt (an answer counts only when it passes the pipeline's checks).", ""]  # fmt: skip
    for v in ("rules", *VARIANTS):
        md += [
            f"## {v}",
            "",
            "| field | " + " | ".join(CLASSES) + " |",
            "|---|" + "---|" * len(CLASSES),
        ]
        md += [
            f"| {f} | " + " | ".join(str(classes[v][f][c]) for c in CLASSES) + " |"
            for f in FIELDS
        ]
        if v in VARIANTS:
            sec = sorted(seconds[v])
            med = (
                sec[len(sec) // 2]
                if len(sec) % 2
                else (sec[len(sec) // 2 - 1] + sec[len(sec) // 2]) / 2
                if sec
                else 0.0
            )
            md += ["", f"model calls: {len(sec)}; model answers non-null: {raw[v]['non_null']}; passed the pipeline's checks: {raw[v]['passed_checks']}; failed the pipeline's checks: {raw[v]['non_null'] - raw[v]['passed_checks']}; median seconds per call: {med:.1f}; total seconds in calls: {sum(sec):.0f}"]  # fmt: skip
        md.append("")
    md += [
        f"Total run time: {(time.monotonic() - started) / 60:.1f} minutes (rules, ingest and model calls, model start included).",
        "",
    ]
    md += ["## Failures", ""] + (
        [f"- {k}: {', '.join(v)}" for k, v in failures.items()] or ["- none"]
    )
    (OUT / "scalars_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for line in md:
        print(line)


if __name__ == "__main__":
    main(sys.argv[1:])
