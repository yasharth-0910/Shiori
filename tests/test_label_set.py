"""data/eval/label_set.json follows the Phase 3 plan and the frozen splits (D-40)."""

import json
from collections import Counter
from pathlib import Path

from collector.manifest import read_rows

REPO_ROOT = Path(__file__).resolve().parent.parent
QUOTAS = {
    "dev": {"notice": 30, "bid_instructions": 15, "spec": 15},
    "test": {"notice": 20, "bid_instructions": 10, "spec": 10},
}


def test_label_set_matches_quotas_splits_and_manifest() -> None:
    ls = json.loads((REPO_ROOT / "data/eval/label_set.json").read_text())
    splits = json.loads((REPO_ROOT / "data/eval/splits.json").read_text())
    rows = {
        r.doc_id: r for r in read_rows(REPO_ROOT / "data/manifests/documents.jsonl")
    }
    seen: set[str] = set()
    for split, quotas in QUOTAS.items():
        docs = ls[split]
        for d in docs:
            row = rows[d["doc_id"]]
            assert splits[row.issuer_org] == split, d["doc_id"]
            assert row.license_class == d["license_class"]
            assert d["doc_id"] not in seen
            seen.add(d["doc_id"])
        got = Counter(d["group"] for d in docs)
        for group, n in quotas.items():
            assert got[group] == n or group in " ".join(ls["shortfalls"]), (
                split,
                group,
            )
    assert not ls["shortfalls"] or all(
        isinstance(v, str) for v in ls["shortfalls"].values()
    )
    dev = ls["dev"]
    assert (
        sum(d["source"] == "p-portal" and d["has_english_summary"] for d in dev) >= 10
    )
    assert sum(d["ocr_pages"] > 0 for d in dev) >= 3
