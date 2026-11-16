"""Write data/eval/splits.json (org -> train | dev | test) and data/eval/splits.md.

    uv run python -m eval.splits

Starts from the deterministic candidate split in corpus_report.md
(collector.report.candidate_split), applies the overrides below, checks the Phase 3
constraints and writes the result. No randomness. The file is frozen once committed
(D-40): tests/test_splits.py fails if any org's assignment changes.
"""

import json
from collections import Counter
from pathlib import Path

from collector.manifest import ManifestRow, read_rows
from collector.report import candidate_split

SPLITS_PATH = Path("data/eval/splits.json")
NOTES_PATH = Path("data/eval/splits.md")
REAL_VOLUME = 5
# Why each org moved away from the candidate split (D-40). Dev and test each need
# 15/10 spec and 15/10 bid_instructions documents (label_set.json) and only the
# bundle-based sources have those. The candidate put two open, spec-rich orgs in train.
OVERRIDES = {
    "和歌山県": ("dev", "open; 8 spec and 8 bid_instructions, dev had 10 and 8"),
    "北海道": ("test", "open; 7 spec and 2 bid_instructions, test had 9 and 10"),
}


def build(rows: list[ManifestRow]) -> dict[str, str]:
    docs = [r for r in rows if r.format != "zip"]
    per_org = Counter(r.issuer_org for r in docs)
    split = candidate_split(dict(per_org))
    for org, (to, _) in OVERRIDES.items():
        split[org] = to
    return dict(sorted(split.items()))


def check(
    split: dict[str, str], rows: list[ManifestRow]
) -> list[tuple[str, bool, str]]:
    """(constraint, passed, evidence) for each Phase 3 split constraint."""
    docs = [r for r in rows if r.format != "zip"]
    per_org = Counter(r.issuer_org for r in docs)
    n = len(per_org)
    by = {
        s: [o for o in per_org if split.get(o) == s] for s in ("train", "dev", "test")
    }
    open_orgs = {
        o
        for o in per_org
        if all(r.license_class == "open" for r in docs if r.issuer_org == o)
    }
    real = {o for o, c in per_org.items() if c >= REAL_VOLUME}
    portal = {r.issuer_org for r in docs if r.source == "p-portal"}
    out = [
        (
            "every org assigned once",
            set(split) == set(per_org),
            f"{len(split)} of {n} orgs",
        ),
        (
            "about 60/20/20 of orgs (each within 1 of round(share x orgs))",
            all(abs(len(by[s]) - round(n * sh)) <= 1 for s, sh in
                (("train", 0.6), ("dev", 0.2), ("test", 0.2))),
            ", ".join(f"{s} {len(by[s])}" for s in by),
        ),
    ]  # fmt: skip
    for s in ("dev", "test"):
        ok = sorted(o for o in by[s] if o in open_orgs and o in real)
        out.append(
            (
                f"{s}: 2+ open orgs with 5+ docs",
                len(ok) >= 2,
                f"{len(ok)}: {', '.join(ok)}",
            )
        )
    big = sorted(o for o in by["test"] if o in real)
    out.append(
        ("test: 4+ orgs with 5+ docs", len(big) >= 4, f"{len(big)}: {', '.join(big)}")
    )
    spread = {s: sorted(o for o in by[s] if o in portal) for s in by}
    out.append((
        "p-portal ministries in all three splits",
        all(spread.values()),
        "; ".join(f"{s} {len(v)}" for s, v in spread.items()),
    ))  # fmt: skip
    return out


def render(split: dict[str, str], rows: list[ManifestRow]) -> str:
    docs = [r for r in rows if r.format != "zip"]
    lines = [
        "# Splits (frozen, D-40)",
        "",
        "`splits.json` maps each issuing organization to `train`, `dev` or "
        "`test`. Built by `uv run python -m eval.splits`: the candidate split from "
        "`corpus_report.md` plus two overrides, no randomness. Do not change an "
        "assignment without a new decision "
        "entry; `tests/test_splits.py` holds a copy and fails on any difference.",
        "",
        "## Overrides of the candidate split",
        "",
    ]
    lines += [f"- {o} to {to}: {why}" for o, (to, why) in OVERRIDES.items()]
    lines += [
        "",
        "## Constraint checks",
        "",
        "| constraint | passed | evidence |",
        "|---|---|---|",
    ]
    lines += [
        f"| {c} | {'yes' if ok else 'NO'} | {ev} |" for c, ok, ev in check(split, rows)
    ]
    lines += [
        "",
        "## Result",
        "",
        "| split | orgs | docs | open docs | restricted or unknown docs |",
        "|---|---|---|---|---|",
    ]
    for s in ("train", "dev", "test"):
        d = [r for r in docs if split[r.issuer_org] == s]
        n_open = sum(r.license_class == "open" for r in d)
        lines.append(
            f"| {s} | {sum(v == s for v in split.values())} | {len(d)} | {n_open} "
            f"| {len(d) - n_open} |"
        )
    lines += ["", "## Orgs", ""]
    for s in ("train", "dev", "test"):
        lines.append(f"- **{s}**: " + ", ".join(o for o, v in split.items() if v == s))
    lines += [
        "",
        "Not merged: 気象衛星センター belongs to 気象庁 (D-25); no 気象庁 notice was "
        "collected, so nothing needed merging and 気象衛星センター stays in test as "
        "the candidate had it.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    rows = read_rows()
    split = build(rows)
    failed = [c for c, ok, _ in check(split, rows) if not ok]
    if failed:
        raise SystemExit(f"constraints failed: {failed}")
    SPLITS_PATH.write_text(json.dumps(split, ensure_ascii=False, indent=1) + "\n")
    NOTES_PATH.write_text(render(split, rows))
    print(NOTES_PATH.read_text())


if __name__ == "__main__":
    main()
