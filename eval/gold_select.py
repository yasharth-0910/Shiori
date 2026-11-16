"""Pick the 20 documents of the gold set (data/eval/gold_set.json, D-61).

    uv run python -m eval.gold_select

Only open-license documents of the dev split. The five pilot documents come first if
they qualify (wave 0, already labeled), then bundle-aware, org-capped picking fills the
strata, then the rest is dealt into waves of 5 so every wave touches every stratum.
Seeded and deterministic. Nothing is relaxed when a stratum can't be filled: the
shortfall is written to the file and the report. Reads the manifests, splits.json and
the label-set scan cache; writes only the two output files. Never touches the test
split. Dev-time only. Output holds doc ids and metadata, never document text.
"""

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from collector.manifest import BundleRow, ManifestRow, read_rows

SEED = 20261016
SPLIT = "dev"
SPLITS_PATH = Path("data/eval/splits.json")
BUNDLES_PATH = Path("data/manifests/bundles.jsonl")
SCAN_PATH = Path("data/processed/_label_scan.json")  # from eval.label_set, read only
GOLD_PATH = Path("data/eval/gold_set.json")
REPORT_PATH = Path("eval/reports/gold_set.md")

TOTAL = 20
WAVE_SIZE = 5
ORG_MAX = 6
MIN_ORGS = 4
MIN_SUMMARY = 6  # p-portal HTML notices with an English Summary
MIN_JA = 5  # same floor as eval.label_set
TARGET = {"notice": 12, "bid_instructions": 4, "spec": 4}  # notice is "about 12"
PILOT = ("f19cddbd4cba", "563042df9941", "4b0b9d8229c7", "28ad40ea4b1f", "4c40bbd831fe")
RESERVE_ORDER = ("bid_instructions", "spec", "notice_summary", "notice_other")
RESERVE_N = 5
GROUP = {"notice": "notice", "tender_page": "notice",
         "bid_instructions": "bid_instructions", "spec": "spec"}  # fmt: skip


def stratum(r: ManifestRow) -> str:
    g = GROUP[r.doc_type]
    if g != "notice":
        return g
    summary = r.source == "p-portal" and r.format == "html" and r.has_english_summary
    return "notice_summary" if summary else "notice_other"


def group(r: ManifestRow) -> str:
    return GROUP[r.doc_type]


def skip_reason(r: ManifestRow, info: dict[str, dict]) -> str | None:
    """Why a document can't be in the gold set (None = fine)."""
    i = info.get(r.doc_id)
    if r.text_layer == "none":
        return "text_layer none"
    if i is None or not i.get("ok") or i.get("n_ja", 0) < MIN_JA:
        return "not extractable"
    if i["ocr_pages"] * 4 > (r.pages or 0):  # more than a quarter of the pages need OCR
        return "mostly OCR" if r.pages else "OCR page in a page-less document"
    return None


def candidates(
    rows: list[ManifestRow], info: dict[str, dict], splits: dict[str, str]
) -> tuple[list[ManifestRow], Counter]:
    """Open dev documents of the three groups that need no (or little) OCR."""
    pool, skipped = [], Counter()
    for r in sorted(rows, key=lambda r: r.doc_id):
        if splits.get(r.issuer_org) != SPLIT or r.license_class != "open":
            continue
        if r.doc_type not in GROUP:
            continue
        why = skip_reason(r, info)
        if why:
            skipped[why] += 1
        else:
            pool.append(r)
    return pool, skipped


def pick(
    pool: list[ManifestRow], bundles: list[BundleRow], seed: int = SEED
) -> tuple[list[ManifestRow], list[ManifestRow], dict[str, str]]:
    """(pilot rows that qualify, other chosen rows, shortfalls)."""
    rng = random.Random(seed)
    bundle_of = {d: b.bundle_id for b in bundles for d in b.doc_ids}
    chosen: list[ManifestRow] = [
        r for r in pool if r.doc_id[:12] in PILOT
    ]  # sorted by doc_id already
    pilot_ids = {r.doc_id for r in chosen}
    pilot_bundles = {bundle_of.get(r.doc_id) for r in chosen} - {None}
    orgs: Counter = Counter(r.issuer_org for r in chosen)
    groups: Counter = Counter(group(r) for r in chosen)

    def room(r: ManifestRow) -> bool:
        return (
            r.doc_id not in {c.doc_id for c in chosen}
            and orgs[r.issuer_org] < ORG_MAX
            and len(chosen) < TOTAL
        )

    def add(r: ManifestRow) -> None:
        chosen.append(r)
        orgs[r.issuer_org] += 1
        groups[group(r)] += 1

    # 1. instructions and specs first (only one org issues them): alternate the two,
    #    documents from the pilot's bundles first so tenders stay together.
    side = {
        g: sorted(
            (r for r in pool if group(r) == g and r.doc_id not in pilot_ids),
            key=lambda r: (bundle_of.get(r.doc_id) not in pilot_bundles, rng.random()),
        )
        for g in ("bid_instructions", "spec")
    }
    progress = True
    while progress:
        progress = False
        for g in ("bid_instructions", "spec"):
            if groups[g] < TARGET[g]:
                nxt = next((r for r in side[g] if room(r)), None)
                if nxt:
                    add(nxt)
                    progress = True

    # 2. notices: English-Summary p-portal pages to MIN_SUMMARY, then the rest, one
    #    organization at a time. The notice target is "about 12": it also takes the
    #    places the other two strata could not fill, so the set still reaches 20.
    def fill(stratum_name: str, limit: int) -> None:
        by_org: dict[str, list[ManifestRow]] = defaultdict(list)
        for r in pool:
            if stratum(r) == stratum_name and room(r):
                by_org[r.issuer_org].append(r)
        order = sorted(by_org)
        rng.shuffle(order)
        for o in order:
            rng.shuffle(by_org[o])
        while len(chosen) < limit and any(by_org.values()):
            for o in order:
                while by_org[o] and not room(by_org[o][-1]):
                    by_org[o].pop()
                if by_org[o] and len(chosen) < limit:
                    add(by_org[o].pop())

    have = sum(stratum(r) == "notice_summary" for r in chosen)
    fill("notice_summary", len(chosen) + max(0, MIN_SUMMARY - have))
    fill("notice_other", TOTAL)
    fill("notice_summary", TOTAL)

    short: dict[str, str] = {}
    for g, t in TARGET.items():
        if groups[g] < t:
            short[g] = f"wanted {t}, got {groups[g]}"
    if len(chosen) < TOTAL:
        short["total"] = f"wanted {TOTAL}, got {len(chosen)}"
    if sum(stratum(r) == "notice_summary" for r in chosen) < MIN_SUMMARY:
        short["notice_summary"] = f"wanted at least {MIN_SUMMARY}"
    if len(orgs) < MIN_ORGS:
        short["organizations"] = f"wanted at least {MIN_ORGS}, got {len(orgs)}"
    pilot = [r for r in chosen if r.doc_id in pilot_ids]
    return pilot, [r for r in chosen if r.doc_id not in pilot_ids], short


def make_waves(rest: list[ManifestRow]) -> list[list[ManifestRow]]:
    """Deal by stratum so each wave gets some of everything."""
    n = -(-len(rest) // WAVE_SIZE)
    order = {s: i for i, s in enumerate(RESERVE_ORDER)}
    waves: list[list[ManifestRow]] = [[] for _ in range(n)]
    for k, r in enumerate(sorted(rest, key=lambda r: (order[stratum(r)], r.doc_id))):
        w = k % n
        while len(waves[w]) >= WAVE_SIZE:
            w = (w + 1) % n
        waves[w].append(r)
    return waves


def pick_reserve(
    pool: list[ManifestRow], used: set[str], seed: int
) -> list[ManifestRow]:
    rng = random.Random(seed + 1)
    left = {s: [] for s in RESERVE_ORDER}
    for r in pool:
        if r.doc_id not in used:
            left[stratum(r)].append(r)
    for v in left.values():
        rng.shuffle(v)
    out: list[ManifestRow] = []
    while len(out) < RESERVE_N and any(left.values()):
        for s in RESERVE_ORDER:
            if left[s] and len(out) < RESERVE_N:
                out.append(left[s].pop())
    return out


def bundle_stats(
    chosen: list[ManifestRow], bundles: list[BundleRow]
) -> tuple[int, int]:
    """(bundles with notice + instructions + spec chosen, bundles with 2+ chosen)."""
    ids = {r.doc_id: r for r in chosen}
    full = multi = 0
    for b in bundles:
        mine = [ids[d] for d in b.doc_ids if d in ids]
        multi += len(mine) >= 2
        full += {group(r) for r in mine} == set(TARGET)
    return full, multi


def entry(r: ManifestRow, bundle: dict[str, str], wave: int, **extra) -> dict:
    return {"doc_id": r.doc_id, "wave": wave, "stratum": stratum(r),
            "doc_type": r.doc_type, "org": r.issuer_org, "pages": r.pages,
            "source": r.source, "bundle_id": bundle.get(r.doc_id), **extra}  # fmt: skip


def build(
    rows: list[ManifestRow],
    info: dict[str, dict],
    splits: dict[str, str],
    bundles: list[BundleRow],
    seed: int = SEED,
) -> dict:
    pool, skipped = candidates(rows, info, splits)
    pilot, rest, short = pick(pool, bundles, seed)
    bundle = {d: b.bundle_id for b in bundles for d in b.doc_ids}
    waves = [{"wave": 0, "already_labeled": True,
              "docs": [entry(r, bundle, 0) for r in pilot]}] if pilot else []  # fmt: skip # noqa: E501
    for k, w in enumerate(make_waves(rest), 1):
        waves.append({"wave": k, "already_labeled": False,
                      "docs": [entry(r, bundle, k) for r in w]})  # fmt: skip
    used = {r.doc_id for r in pilot + rest}
    full, multi = bundle_stats(pilot + rest, bundles)
    return {
        "seed": seed,
        "split": SPLIT,
        "rules": {
            "total": TOTAL,
            "wave_size": WAVE_SIZE,
            "org_max": ORG_MAX,
            "min_orgs": MIN_ORGS,
            "min_notice_summary": MIN_SUMMARY,
            "target": TARGET,
            "min_japanese_sentences": MIN_JA,
        },  # fmt: skip
        "pilot_qualified": sorted(r.doc_id[:12] for r in pilot),
        "pilot_left_out": sorted(
            p for p in PILOT if p not in {r.doc_id[:12] for r in pilot}
        ),
        "open_dev_by_type": dict(
            Counter(
                r.doc_type
                for r in rows
                if splits.get(r.issuer_org) == SPLIT and r.license_class == "open"
            )
        ),  # fmt: skip
        "skipped": dict(skipped),
        "shortfalls": short,
        "bundles_complete": full,
        "bundles_with_two_or_more": multi,
        "waves": waves,
        "reserve": [entry(r, bundle, -1) for r in pick_reserve(pool, used, seed)],
    }


def report(g: dict) -> str:
    docs = [d for w in g["waves"] for d in w["docs"]]
    p = lambda d: d["doc_id"][:8]  # noqa: E731
    out = [
        "# Gold set selection",
        "",
        f"`uv run python -m eval.gold_select`, seed {g['seed']}, split {g['split']}, "
        "license_class open only. Ids are 8-character prefixes; no document text.",
        "",
        "Open dev documents by doc_type: "
        + ", ".join(f"{k} {v}" for k, v in sorted(g["open_dev_by_type"].items())),
        "",
        "Skipped (notice, tender_page, bid_instructions, spec only): "
        f"{g['skipped'] or 'none'}",
        "",
        f"Pilot documents that qualify: {', '.join(g['pilot_qualified']) or 'none'}; "
        f"left out: {', '.join(g['pilot_left_out']) or 'none'}",
        "",
        f"Shortfalls: {g['shortfalls'] or 'none'}",
        "",
        "Bundles with notice, instructions and spec all selected: "
        f"{g['bundles_complete']}; "
        f"bundles with two or more selected: {g['bundles_with_two_or_more']}",
        "",
        "## Counts per stratum",
        "",
        "| stratum | selected | wanted |",
        "|---|---|---|",
    ]
    c = Counter(d["stratum"] for d in docs)
    for s, want in (
        ("notice (all)", TARGET["notice"]),
        ("bid_instructions", 4),
        ("spec", 4),
    ):
        n = sum(v for k, v in c.items() if k.startswith(s.split()[0]))
        out.append(f"| {s} | {n} | about {want} |")
    out += [f"| notice_summary | {c['notice_summary']} | at least {MIN_SUMMARY} |",
            f"| notice_other | {c['notice_other']} | |", ""]  # fmt: skip
    out += [
        "## Counts per organization",
        "",
        "| organization | documents |",
        "|---|---|",
    ]
    out += [
        f"| {o} | {n} |" for o, n in sorted(Counter(d["org"] for d in docs).items())
    ]
    out += ["", "## Waves", "",
            "| wave | id | doc_type | organization | pages | stratum |",
            "|---|---|---|---|---|---|"]  # fmt: skip
    for w in g["waves"]:
        tag = " (already labeled)" if w["already_labeled"] else ""
        out += [f"| {w['wave']}{tag} | {p(d)} | {d['doc_type']} | {d['org']} "
                f"| {d['pages'] or '-'} | {d['stratum']} |"
                for d in w["docs"]]  # fmt: skip
    out += ["", "## Reserve", "", "| id | doc_type | organization | pages | stratum |",
            "|---|---|---|---|---|"]  # fmt: skip
    out += [f"| {p(d)} | {d['doc_type']} | {d['org']} | {d['pages'] or '-'} "
            f"| {d['stratum']} |" for d in g["reserve"]]  # fmt: skip
    return "\n".join(out) + "\n"


def main() -> None:
    info = json.loads(SCAN_PATH.read_text())["docs"]
    splits = json.loads(SPLITS_PATH.read_text())
    bundles = [
        BundleRow.model_validate_json(line)
        for line in BUNDLES_PATH.read_text().splitlines()
        if line.strip()
    ]
    g = build(read_rows(), info, splits, bundles)
    GOLD_PATH.write_text(json.dumps(g, ensure_ascii=False, indent=2) + "\n")
    REPORT_PATH.write_text(report(g))
    print(report(g))


if __name__ == "__main__":
    main()
