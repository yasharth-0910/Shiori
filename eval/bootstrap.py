"""Paired bootstrap over documents for two saved dev run reports
(docs/measurement_plan.md section 5).

    uv run python -m eval.bootstrap eval/reports/run_<A>.json eval/reports/run_<B>.json

A is the baseline, B the change. Reads the two report files only: no document, no label
file, no model, no network. The reports do not store label file hashes, so identical
labels cannot be proven from them; a row whose label status differs is refused.
"""

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

from pydantic import BaseModel, StrictBool

RESAMPLES = 10_000
SEED = 20261128
METRICS = (
    ("Verified accuracy", "verified_ok"),
    ("Wrong-answer rate", "wrong_shown"),
)


class Record(BaseModel):
    doc: str
    field: str
    gold: str
    pred: str
    value_ok: StrictBool
    verified_ok: StrictBool
    wrong_shown: StrictBool


class Report(BaseModel):
    name: str
    split: str
    extractor_version: str
    schema_version: str
    records: list[Record]


Rows = dict[tuple[str, str], Record]


def load(path: Path) -> Report:
    data = json.loads(path.read_text())
    # split first, so a non-dev report is refused before its rows are used
    if data.get("split") != "dev":
        raise ValueError(f"{path.name}: split is {data.get('split')!r}, only dev")
    return Report.model_validate(data)


def paired(a: Report, b: Report) -> tuple[Rows, Rows]:
    """The two reports' rows by (doc, field), refused unless they can be compared."""
    for r in (a, b):
        if r.split != "dev":
            raise ValueError(f"{r.name}: split is {r.split!r}, only dev")
    for key in ("extractor_version", "schema_version"):
        if getattr(a, key) != getattr(b, key):
            raise ValueError(f"{key} differs: {getattr(a, key)} and {getattr(b, key)}")
    ra, rb = ({(x.doc, x.field): x for x in r.records} for r in (a, b))
    for r, rows in ((a, ra), (b, rb)):
        if len(rows) != len(r.records):
            raise ValueError(f"{r.name}: a (doc, field) row appears twice")
    docs_a, docs_b = ({doc for doc, _ in rows} for rows in (ra, rb))
    if docs_a != docs_b:
        raise ValueError(f"documents differ: {sorted(docs_a ^ docs_b)}")
    if ra.keys() != rb.keys():
        raise ValueError(f"rows differ: {sorted(ra.keys() ^ rb.keys())[:5]}")
    changed = sorted(k for k in ra if ra[k].gold != rb[k].gold)
    if changed:
        raise ValueError(f"label status differs between the reports: {changed[:5]}")
    # one document gives a zero-width interval, which would claim any difference
    if len(docs_a) < 2:
        raise ValueError(f"at least 2 documents are needed, got {len(docs_a)}")
    return ra, rb


def bootstrap(ra: Rows, rb: Rows, attr: str) -> dict:
    """delta = (sum B - sum A) / sum rows; a drawn document brings all its rows for
    both runs. Every metric uses the same seed, so the same draws."""
    per_doc: dict[str, list[int]] = {}  # doc -> [rows, sum B - sum A]
    up = down = 0
    for key in sorted(ra):
        d = getattr(rb[key], attr) - getattr(ra[key], attr)
        t = per_doc.setdefault(key[0], [0, 0])
        t[0] += 1
        t[1] += d
        up += d == 1
        down += d == -1
    docs = list(per_doc.values())
    rng = random.Random(SEED)
    deltas = []
    for _ in range(RESAMPLES):
        draw = rng.choices(docs, k=len(docs))
        deltas.append(sum(d for _, d in draw) / sum(n for n, _ in draw))
    # n=40 cuts every 2.5%; "inclusive" is linear interpolation between the deltas
    cuts = statistics.quantiles(deltas, n=40, method="inclusive")
    return {
        "a": sum(getattr(x, attr) for x in ra.values()),
        "b": sum(getattr(x, attr) for x in rb.values()),
        "rows": len(ra),
        "delta": (up - down) / len(ra),
        "low": cuts[0],
        "high": cuts[-1],
        "false_to_true": up,
        "true_to_false": down,
    }


def readable_gain(rows: int, docs: int, pi: float = 0.10, rho: float = 0.05) -> float:
    """Section 2's smallest readable gain; pi and rho are assumed, not measured."""
    k = 2.802
    design = 1 + (rows / docs - 1) * rho
    return k * math.sqrt(pi * design / (rows + k * k * design))


def verdict(acc: dict, docs: int) -> str:
    if acc["low"] > 0:
        return "Verdict: gain (lower bound of verified accuracy is above 0)."
    if acc["high"] < 0:
        return "Verdict: loss (upper bound of verified accuracy is below 0)."
    gain = 100 * readable_gain(acc["rows"], docs)
    return (
        f"Verdict: no measurable difference. Smallest readable gain about {gain:.1f} "
        "points (section 2, assumed pi 0.10 and rho 0.05)."
    )


def render(a: Report, b: Report) -> str:
    ra, rb = paired(a, b)
    docs = len({doc for doc, _ in ra})
    results = {attr: bootstrap(ra, rb, attr) for _, attr in METRICS}
    out = [
        f"A: {a.name}   B: {b.name}",
        f"{docs} documents, {len(ra)} rows, extractor {a.extractor_version}, "
        f"schema {a.schema_version}, {RESAMPLES} resamples, seed {SEED}",
        "Scores are against model-reviewed silver labels (D-41). The reports store no "
        "label file hashes, so identical labels are not proven.",
    ]
    for title, attr in METRICS:
        r = results[attr]
        n = r["rows"]
        out += [
            "",
            f"{title}: A {r['a']} of {n} ({100 * r['a'] / n:.1f}%), "
            f"B {r['b']} of {n} ({100 * r['b'] / n:.1f}%)",
            f"  delta B - A {100 * r['delta']:+.2f} points, 95% interval "
            f"{100 * r['low']:+.2f} to {100 * r['high']:+.2f}",
            f"  rows flipped: {r['false_to_true']} false to true, "
            f"{r['true_to_false']} true to false",
        ]
    pointers = [
        sum(x.pred == "see_other_document" and not x.value_ok for x in rows.values())
        for rows in (ra, rb)
    ]
    out += [
        f"  wrong see_other_document (not in the rate above): A {pointers[0]}, "
        f"B {pointers[1]}",
        "",
        verdict(results["verified_ok"], docs),
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="eval.bootstrap", description=(__doc__ or "").split("\n")[0]
    )
    ap.add_argument("a", type=Path, help="baseline run_*.json")
    ap.add_argument("b", type=Path, help="changed run_*.json")
    args = ap.parse_args(argv)
    try:
        print(render(load(args.a), load(args.b)))
    except (OSError, ValueError) as e:  # pydantic and JSON errors are ValueErrors
        print(f"refused: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
