"""Pick the documents to label (data/eval/label_set.json, D-40).

    uv run python -m eval.label_set

Seeded random sampling, stratified inside each split by document group and, inside a
group, round-robin across organizations so no org fills the quota alone. Only documents
that extract without errors and give at least MIN_SENTENCES Japanese sentences are
eligible. When a stratum can't be filled, the shortfall is written to the file and the
report; nothing is relaxed. Dev-time only. The files hold doc ids and metadata, never
document text.
"""

import json
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from shiori_core.fields import SCHEMA_VERSION
from shiori_core.ingest import PasswordProtectedError
from shiori_core.models import EXTRACTOR_VERSION

from collector.manifest import ManifestRow, read_rows
from eval.documents import extract, load_sentences

SEED = 20261003
MIN_SENTENCES = 5
SPLITS_PATH = Path("data/eval/splits.json")
LABEL_SET_PATH = Path("data/eval/label_set.json")
REPORT_PATH = Path("data/eval/label_set.md")
SCAN_PATH = Path("data/processed/_label_scan.json")  # cache, gitignored

GROUPS = {
    "notice": ("notice", "tender_page"),
    "bid_instructions": ("bid_instructions",),
    "spec": ("spec",),
}
QUOTAS = {
    "dev": {"notice": 30, "bid_instructions": 15, "spec": 15},
    "test": {"notice": 20, "bid_instructions": 10, "spec": 10},
}
DEV_MIN_ENGLISH_SUMMARY = 10  # p-portal HTML notices with an English Summary
DEV_MIN_OCR = 3  # documents that include OCR pages


def scan(rows: list[ManifestRow]) -> dict[str, dict]:
    """doc_id -> {ok, err, n_ja, ocr_pages}. PDFs are first read without OCR to count
    scanned and outlined pages; only documents that have some are read again with OCR
    (sentences cached by eval.documents). Results are cached by extractor version."""
    cache: dict[str, dict] = {}
    if SCAN_PATH.exists():
        data = json.loads(SCAN_PATH.read_text())
        if data.get("extractor_version") == EXTRACTOR_VERSION:
            cache = data["docs"]
    for r in rows:
        if r.doc_id in cache:
            continue
        try:
            doc = extract(r, ocr=False)
            ocr_pages = sum(p.kind in ("scanned", "outlined") for p in doc.pages)
            sentences = load_sentences(r) if ocr_pages else doc.sentences
            cache[r.doc_id] = {
                "ok": True,
                "n_ja": sum(s.language == "ja" for s in sentences),
                "ocr_pages": ocr_pages,
            }
        except PasswordProtectedError:
            cache[r.doc_id] = {"ok": False, "err": "password protected"}
        except Exception as e:  # report by type, keep going
            cache[r.doc_id] = {"ok": False, "err": type(e).__name__}
        SCAN_PATH.write_text(
            json.dumps({"extractor_version": EXTRACTOR_VERSION, "docs": cache})
        )
    return cache


def round_robin(
    pool: list[ManifestRow], k: int, rng: random.Random
) -> list[ManifestRow]:
    """k documents, one org at a time in a seeded order, each org's docs shuffled."""
    by_org: dict[str, list[ManifestRow]] = defaultdict(list)
    for r in sorted(pool, key=lambda r: r.doc_id):
        by_org[r.issuer_org].append(r)
    orgs = sorted(by_org)
    rng.shuffle(orgs)
    for o in orgs:
        rng.shuffle(by_org[o])
    out: list[ManifestRow] = []
    while len(out) < k and any(by_org.values()):
        for o in orgs:
            if by_org[o] and len(out) < k:
                out.append(by_org[o].pop())
    return out


def pick(
    rows: list[ManifestRow], info: dict[str, dict], splits: dict[str, str]
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    rng = random.Random(SEED)
    eligible = [
        r
        for r in rows
        if r.format != "zip"
        and info[r.doc_id]["ok"]
        and info[r.doc_id]["n_ja"] >= MIN_SENTENCES
    ]
    chosen: dict[str, list[dict]] = {}
    notes: dict[str, str] = {}
    for split, quotas in QUOTAS.items():
        mine = [r for r in eligible if splits[r.issuer_org] == split]
        picked: dict[str, list[ManifestRow]] = {}
        for group, types in GROUPS.items():
            pool = [r for r in mine if r.doc_type in types]
            first: list[ManifestRow] = []
            if split == "dev":
                # Take every dev document with OCR pages, then the English Summary
                # notices, before the open fill: those minimums must hold.
                first += [r for r in pool if info[r.doc_id]["ocr_pages"]]
                if group == "notice":
                    es = [
                        r
                        for r in pool
                        if r.source == "p-portal" and r.has_english_summary
                    ]
                    need = DEV_MIN_ENGLISH_SUMMARY
                    first += round_robin(es, need, rng)
            first = list({r.doc_id: r for r in first}.values())
            rest = [r for r in pool if r.doc_id not in {f.doc_id for f in first}]
            take = first + round_robin(rest, quotas[group] - len(first), rng)
            picked[group] = take[: max(quotas[group], len(first))]
            if len(picked[group]) < quotas[group]:
                notes[f"{split}/{group}"] = (
                    f"wanted {quotas[group]}, only {len(picked[group])} eligible"
                )
        chosen[split] = [
            {
                "doc_id": r.doc_id,
                "group": g,
                "org": r.issuer_org,
                "doc_type": r.doc_type,
                "source": r.source,
                "format": r.format,
                "license_class": r.license_class,
                "has_english_summary": bool(r.has_english_summary),
                "ocr_pages": info[r.doc_id]["ocr_pages"],
            }
            for g, rs in picked.items()
            for r in rs
        ]
    n_es = sum(
        d["source"] == "p-portal" and d["has_english_summary"] for d in chosen["dev"]
    )
    if n_es < DEV_MIN_ENGLISH_SUMMARY:
        notes["dev/english_summary"] = f"wanted {DEV_MIN_ENGLISH_SUMMARY}, got {n_es}"
    n_ocr = sum(d["ocr_pages"] > 0 for d in chosen["dev"])
    if n_ocr < DEV_MIN_OCR:
        notes["dev/ocr"] = f"wanted {DEV_MIN_OCR} documents with OCR pages, got {n_ocr}"
    return chosen, notes


def render(chosen: dict[str, list[dict]], notes: dict[str, str]) -> str:
    out = [
        "# Label set",
        "",
        f"`label_set.json`: the documents to label, seed {SEED} (D-40). Written by "
        "`uv run python -m eval.label_set`. Seeded random sampling inside each split, "
        "per group (notice or tender_page / bid_instructions / spec), round-robin over "
        f"organizations. Eligible: extracts without errors and has {MIN_SENTENCES}+ "
        "Japanese sentences. Dev keeps every document with OCR pages and the "
        f"{DEV_MIN_ENGLISH_SUMMARY} p-portal English Summary notices before the fill.",
        "",
        "## Shortfalls",
        "",
    ]
    out += [f"- {k}: {v}" for k, v in notes.items()] or ["None: every stratum is full."]
    for split, docs in chosen.items():
        n_open = sum(d["license_class"] == "open" for d in docs)
        groups = Counter(d["group"] for d in docs)
        n_es = sum(d["source"] == "p-portal" and d["has_english_summary"] for d in docs)
        out += [
            "",
            f"## {split}: {len(docs)} documents",
            "",
            "- groups: "
            + ", ".join(f"{g} {groups[g]}/{QUOTAS[split][g]}" for g in GROUPS),
            f"- open {n_open}, restricted or unknown {len(docs) - n_open}",
            "- format: "
            + ", ".join(
                f"{k} {v}"
                for k, v in sorted(Counter(d["format"] for d in docs).items())
            ),
            f"- documents with OCR pages: {sum(d['ocr_pages'] > 0 for d in docs)}",
            f"- p-portal HTML notices with an English Summary: {n_es}",
            "",
            "| org | docs | notice | bid_instructions | spec | open | pdf | html |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for org in sorted(
            {d["org"] for d in docs},
            key=lambda o: (-sum(d["org"] == o for d in docs), o),
        ):
            mine = [d for d in docs if d["org"] == org]
            g = Counter(d["group"] for d in mine)
            n_pdf = sum(d["format"] == "pdf" for d in mine)
            out.append(
                f"| {org} | {len(mine)} | {g['notice']} | {g['bid_instructions']} "
                f"| {g['spec']} "
                f"| {sum(d['license_class'] == 'open' for d in mine)} "
                f"| {n_pdf} | {len(mine) - n_pdf} |"
            )
    out.append("")
    return "\n".join(out)


def main() -> None:
    rows = [r for r in read_rows() if r.format != "zip"]
    splits = json.loads(SPLITS_PATH.read_text())
    info = scan(rows)
    chosen, notes = pick(rows, info, splits)
    LABEL_SET_PATH.write_text(
        json.dumps(
            {
                "seed": SEED,
                "schema_version": SCHEMA_VERSION,
                "extractor_version": EXTRACTOR_VERSION,
                "created": date.today().isoformat(),
                "shortfalls": notes,
                **chosen,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n"
    )
    REPORT_PATH.write_text(render(chosen, notes))
    print(REPORT_PATH.read_text())


if __name__ == "__main__":
    main()
