"""webcheck (D-111): read-only license check before any upload of a document to a chat.

Prints each document prefix with its license class from data/manifests/documents.jsonl.
Only `open` passes; restricted, unknown (counted as restricted, D-44), missing fail."""

import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[2] / "data/manifests/documents.jsonl"


def webcheck(
    prefixes: list[str], manifest: Path = MANIFEST
) -> tuple[list[str], list[str]]:
    """Return (one line per prefix, prefixes that are not open)."""
    rows = [json.loads(x) for x in manifest.read_text().splitlines() if x.strip()]
    lines, bad = [], []
    for p in prefixes:
        classes = {r.get("license_class") for r in rows if r["doc_id"].startswith(p)}
        cls = (
            classes.pop()
            if len(classes) == 1
            else ("missing" if not classes else "ambiguous")
        )
        lines.append(f"{p} {cls}")
        if cls != "open":
            bad.append(p)
    return lines, bad
