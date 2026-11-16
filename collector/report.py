"""Corpus stats from the manifests. uv run python -m collector.report

Writes data/manifests/corpus_report.md and prints it.
"""

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from collector.manifest import (
    BUNDLES_PATH,
    DOCUMENTS_PATH,
    BundleRow,
    ManifestRow,
    read_bundles,
    read_rows,
)

REPORT_PATH = Path("data/manifests/corpus_report.md")
PAGE_BUCKETS = [(1, 5), (6, 10), (11, 30), (31, 100), (101, 10_000)]
SPLIT_SHARES = {"train": 0.6, "dev": 0.2, "test": 0.2}  # eval_protocol.md
REAL_VOLUME = 5  # an org with at least this many docs counts toward a split
MANUAL_SECTION = "\n## Spot check"  # written by hand, kept when the report is rewritten


def candidate_split(org_docs: dict[str, int]) -> dict[str, str]:
    """A deterministic org -> split proposal, for checking that a split is workable.

    Org counts per split follow SPLIT_SHARES. Orgs go largest first, each to the split
    with room left whose share of documents is furthest below its target. Not the
    real split: that is decided in Phase 3 and written to data/eval/splits.json.
    """
    n = len(org_docs)
    slots = {k: round(n * share) for k, share in SPLIT_SHARES.items() if k != "train"}
    slots["train"] = n - sum(slots.values())
    total = sum(org_docs.values()) or 1
    docs = dict.fromkeys(SPLIT_SHARES, 0)
    assignment: dict[str, str] = {}
    for org in sorted(org_docs, key=lambda o: (-org_docs[o], o)):
        open_splits = [k for k in SPLIT_SHARES if slots[k] > 0]
        split = min(open_splits, key=lambda k: docs[k] / total - SPLIT_SHARES[k])
        assignment[org] = split
        slots[split] -= 1
        docs[split] += org_docs[org]
    return assignment


def is_complete(bundle: BundleRow, rows_by_id: dict[str, ManifestRow]) -> bool:
    """A bundle is complete when it has at least a notice and a spec."""
    types = {rows_by_id[d].doc_type for d in bundle.doc_ids if d in rows_by_id}
    return {"notice", "spec"} <= types


def render(rows: list[ManifestRow], bundles: dict[str, BundleRow]) -> str:
    rows_by_id = {r.doc_id: r for r in rows}
    pdfs = [r for r in rows if r.format == "pdf"]
    out = [
        "# Corpus report",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d} by "
        "`uv run python -m collector.report` "
        f"from `{DOCUMENTS_PATH}` and `{BUNDLES_PATH}`.",
        "",
        f"Documents: {len(rows)}. "
        f"Issuing organizations: {len({r.issuer_org for r in rows})}. "
        f"Bundles: {len(bundles)}.",
        "",
    ]
    out += _table("Documents per source", Counter(r.source for r in rows))
    out += _table("Documents per format", Counter(r.format for r in rows))
    out += _table(
        "Documents per issuing organization", Counter(r.issuer_org for r in rows)
    )
    out += _table("Documents per doc_type", Counter(r.doc_type for r in rows))
    out += _table(
        "Documents per license_class (D-16)", Counter(r.license_class for r in rows)
    )
    out += _it_section(rows)
    out += _table("Text layer (pdf only)", Counter(r.text_layer or "?" for r in pdfs))
    page_counts = Counter(_bucket(r.pages) for r in pdfs if r.pages is not None)
    out += _table(
        "Page count (pdf only)",
        page_counts,
        order=[f"{a}-{b}" for a, b in PAGE_BUCKETS],
    )
    total_pages = sum(r.pages or 0 for r in pdfs)
    out += [f"Total pdf pages: {total_pages}.", ""]

    complete = [b for b in bundles.values() if is_complete(b, rows_by_id)]
    out += [
        "## Bundles",
        "",
        f"{len(bundles)} bundles, {len(complete)} complete "
        "(at least a notice and a spec).",
        "",
        "| bundle_id | title | docs | doc types | complete |",
        "|---|---|---|---|---|",
    ]
    for b in sorted(bundles.values(), key=lambda b: b.bundle_id):
        types = Counter(rows_by_id[d].doc_type for d in b.doc_ids if d in rows_by_id)
        type_text = ", ".join(
            f"{t} {n}" if n > 1 else t for t, n in sorted(types.items())
        )
        title = b.title_ja.replace("|", "/")
        mark = "yes" if is_complete(b, rows_by_id) else ""
        out.append(
            f"| `{b.bundle_id}` | {title} | {len(b.doc_ids)} | {type_text} | {mark} |"
        )
    in_bundles = {d for b in bundles.values() for d in b.doc_ids}
    # ZIPs stay out of bundles by design (D-21); their PDFs go in.
    loose = [r for r in rows if r.doc_id not in in_bundles and r.format != "zip"]
    extracted = sum(r.extracted_from is not None for r in rows)
    out += [
        "",
        f"Documents in no bundle (ZIPs excluded): {len(loose)}. "
        f"PDFs extracted from ZIPs: {extracted}.",
        "",
    ]
    out += _split_section(rows, bundles, rows_by_id)
    return "\n".join(out)


def _split_section(
    rows: list[ManifestRow],
    bundles: dict[str, BundleRow],
    rows_by_id: dict[str, ManifestRow],
) -> list[str]:
    # ZIPs are containers; their PDFs are counted instead (D-21).
    docs = [r for r in rows if r.format != "zip"]
    per_org = Counter(r.issuer_org for r in docs)
    split = candidate_split(dict(per_org))
    licenses: dict[str, set[str]] = {}
    for r in docs:
        licenses.setdefault(r.issuer_org, set()).add(r.license_class)
    org_bundles = Counter(
        rows_by_id[b.doc_ids[0]].issuer_org
        for b in bundles.values()
        if b.doc_ids and b.doc_ids[0] in rows_by_id
    )
    real = [o for o, n in per_org.items() if n >= REAL_VOLUME]
    out = [
        "## Documents per org and candidate split",
        "",
        "Checks whether an org-level split (D-07, eval_protocol.md) is workable. The "
        "split column is a deterministic proposal from `candidate_split` in "
        "`collector/report.py` (org counts 60/20/20, largest orgs placed first). The "
        "real split is decided in Phase 3. ZIP rows are not counted. Restricted and "
        "unknown documents may be used in any split (D-22).",
        "",
        f"Organizations with {REAL_VOLUME}+ documents: {len(real)} of {len(per_org)}.",
        "",
        "| org | license | docs | bundles | candidate split |",
        "|---|---|---|---|---|",
    ]
    for org, n in per_org.most_common():
        lic = "/".join(sorted(licenses[org]))
        out.append(f"| {org} | {lic} | {n} | {org_bundles[org]} | {split[org]} |")
    out += [
        "",
        f"| split | orgs | orgs with {REAL_VOLUME}+ docs | docs | share of docs "
        "| open docs |",
        "|---|---|---|---|---|---|",
    ]
    for name in SPLIT_SHARES:
        orgs = [o for o, s in split.items() if s == name]
        n_real = sum(o in real for o in orgs)
        n_docs = sum(per_org[o] for o in orgs)
        n_open = sum(
            1 for r in docs if split[r.issuer_org] == name and r.license_class == "open"
        )
        share = n_docs / max(len(docs), 1)
        out.append(
            f"| {name} | {len(orgs)} | {n_real} | {n_docs} | {share:.0%} | {n_open} |"
        )
    test_real = sorted(
        (o for o, s in split.items() if s == "test" and o in real),
        key=lambda o: -per_org[o],
    )
    enough = "yes" if len(test_real) >= 4 else "no"
    out += [
        "",
        f"Does test rest on at least 4 organizations with {REAL_VOLUME}+ documents? "
        f"{enough}: {len(test_real)} ("
        + ", ".join(f"{o} {per_org[o]}" for o in test_real)
        + ").",
    ]
    return [*out, ""]


def _it_section(rows: list[ManifestRow]) -> list[str]:
    """IT counts with the strict cues (D-27): a cue in the title or bundle title."""
    docs = [r for r in rows if r.format != "zip"]
    per_source = Counter(r.source for r in docs)
    it = Counter(r.source for r in docs if r.is_it)
    out = [
        "## IT documents (is_it, D-27)",
        "",
        f"{sum(it.values())} of {len(docs)} documents (ZIPs not counted) are IT: "
        "システム, クラウド, ソフトウェア, データ or 開発 in the title or the "
        "bundle title.",
        "",
        "| source | docs | IT docs |",
        "|---|---|---|",
    ]
    out += [f"| {s} | {n} | {it[s]} |" for s, n in per_source.most_common()]
    return [*out, ""]


def _table(
    title: str, counts: Counter[str], order: list[str] | None = None
) -> list[str]:
    keys = order or [k for k, _ in counts.most_common()]
    lines = [f"## {title}", "", "| | count |", "|---|---|"]
    lines += [f"| {k} | {counts.get(k, 0)} |" for k in keys]
    return [*lines, ""]


def _bucket(pages: int) -> str:
    return next(f"{a}-{b}" for a, b in PAGE_BUCKETS if pages <= b)


def main() -> None:
    text = render(read_rows(), read_bundles())
    if REPORT_PATH.exists():  # keep the hand-written spot check at the end
        old = REPORT_PATH.read_text(encoding="utf-8")
        i = old.find(MANUAL_SECTION)
        text += old[i:] if i >= 0 else ""
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
