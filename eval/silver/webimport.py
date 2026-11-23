# ruff: noqa: E501
"""Gemini web-chat answers (D-104) stored as the raw answers of a labeler named "web".

`uv run python -m eval.silver webimport <dir>` reads <dir>/<8-char doc prefix>.md (one
```json block, then an optional "## Uncertain points" list), runs the checks every
labeler's answers get (checks.run_checks, schema 1.1.0 for the entry shape), and writes
data/cache/labeling/raw/<doc>/web__gemini-web__sv4-web__<ver>__1.0.0.json in the layout
the other labelers use. The prompt version "sv4-web" keeps these answers apart from the
API runs: compare.cached and the status counts only look at "sv4" for non-local
labelers. No network, no model. The report has ids, field names and counts only."""

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from shiori_core.fields import SCHEMA_VERSION

from collector.manifest import ManifestRow
from eval.label_format import LabelLine
from eval.silver.checks import BLOCKING, line_dict, run_checks
from eval.silver.model import from_row
from eval.silver.pipeline import _write, raw_path
from eval.silver.prompt import applicable_fields, rows_of
from eval.silver.run import ja_sentences, select

PROVIDER, MODEL, PROMPT = "web", "gemini-web", "sv4-web"
REPORT = Path("eval/reports/web_import_check.md")
EXCLUDED = {"52bba5f9": "D-102"}  # test document whose cue was tuned on its title
ENTRY_KEYS = {"status", "ref", "value_ja", "value_en", "citations", "reason"}
_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.S)
_NOTES = re.compile(r"^##\s*Uncertain points\s*$", re.M | re.I)


def split_reply(text: str) -> tuple[dict | None, list[str], str]:
    """(answer, uncertain-point lines, problem). A problem means nothing can be stored."""
    blocks = _FENCE.findall(text)
    if len(blocks) != 1:
        return None, [], f"{len(blocks)} json blocks, expected 1"
    try:
        answer = json.loads(blocks[0])
    except ValueError:
        return None, [], "json block is not valid JSON"
    if not (isinstance(answer, dict) and isinstance(answer.get("fields"), dict)):
        return None, [], 'answer is not {"fields": {...}, "normalized": {...}}'
    if not isinstance(answer.get("normalized"), dict):
        return None, [], "normalized is not an object"
    m = _NOTES.search(text.rsplit("```", 1)[-1])
    tail = text.rsplit("```", 1)[-1][m.end() :] if m else ""
    notes = [
        x.strip()[2:].strip() for x in tail.splitlines() if re.match(r"\s*[*-] ", x)
    ]
    return answer, notes, ""


def check_answer(
    row: ManifestRow, answer: dict
) -> tuple[list[tuple[str, str, bool]], list[str]]:
    """([(field, check, passed)], structure problems). Structure problems are fields
    missing or not asked, entry keys that differ from the sv4 shape, and a `normalized`
    key missing for a listed non-text field."""
    from shiori_core.fields import BY_ID

    asked = applicable_fields(row.doc_type)
    by_id = {s.id: s for s in ja_sentences(row)}
    entries, problems = answer["fields"], []
    problems += [
        f"{f}: not asked for a {row.doc_type}" for f in entries if f not in asked
    ]
    for f in asked:
        if f not in entries:
            problems.append(f"{f}: missing")
        elif not isinstance(entries[f], dict) or not ENTRY_KEYS <= set(entries[f]):
            problems.append(f"{f}: entry keys differ from the sv4 shape")
        if BY_ID[f].kind != "text" and f not in answer["normalized"]:
            problems.append(f"{f}: no key in normalized")
    rows = rows_of(answer) or []
    out: list[tuple[str, str, bool]] = []
    for r in rows:
        f = str(r.get("field"))
        if f not in asked:
            continue
        c = from_row(r, f"{PROVIDER}/{MODEL}")
        if c.parse_error:
            out.append((f, "schema_valid", False))
            continue
        try:
            LabelLine.model_validate(
                {**line_dict(c, row), "schema_version": SCHEMA_VERSION}
            )
        except ValueError:
            out.append((f, "schema_valid", False))
            continue
        out.append((f, "schema_valid", True))
        out += [
            (f, n, ok) for n, ok in run_checks(c, row, by_id) if n != "schema_valid"
        ]
    return out, problems


def store(row: ManifestRow, answer: dict, notes: list[str], source: str) -> Path:
    ja = ja_sentences(row)
    fields = applicable_fields(row.doc_type)
    chunk = {"status": "ok", "response": json.dumps(answer, ensure_ascii=False),
             "tokens_in": 0, "tokens_out": 0, "attempts": 1, "seconds": 0,
             "sentence_ids": [s.id for s in ja], "field_ids": fields,
             "date": datetime.now(UTC).date().isoformat(),
             "source_file": source, "uncertain_notes": notes}  # fmt: skip
    raw = {"chunks": {"0": chunk}, "provider": PROVIDER, "model": MODEL,
           "n_chunks": 1, "prompt_version": PROMPT}  # fmt: skip
    path = raw_path(row.doc_id, PROVIDER, MODEL, PROMPT)
    _write(path, json.dumps(raw, ensure_ascii=False))
    return path


def webimport(folder: Path, report: Path | None = None) -> tuple[str, int]:
    """Import every <prefix>.md in `folder`. Returns (report text, failure count)."""
    report = report or REPORT
    files = sorted(folder.glob("*.md"))
    docs, fails, advice, refused, per_field = [], [], [], [], Counter()
    for p in files:
        if p.stem == "README":
            continue
        pre = p.stem
        if pre in EXCLUDED:
            refused.append((pre, f"excluded ({EXCLUDED[pre]})"))
            continue
        rows = select(None, False, [pre])
        if len(rows) != 1:
            refused.append((pre, f"{len(rows)} documents match the prefix"))
            continue
        row = rows[0]
        if row.license_class != "open":
            refused.append((pre, f"license {row.license_class}, not open (D-62)"))
            continue
        answer, notes, why = split_reply(p.read_text(encoding="utf-8"))
        if answer is None:
            refused.append((pre, f"not stored: {why}"))
            continue
        results, problems = check_answer(row, answer)
        store(row, answer, notes, p.name)
        # BLOCKING checks stop a field in the other labelers' runs; the rest are advisory
        bad = {(f, n) for f, n, ok in results if not ok and n in BLOCKING}
        advice += [(pre, f, n) for f, n, ok in results if not ok and n not in BLOCKING]
        for f, n in sorted(bad):
            fails.append((pre, f, n))
        for pr in problems:
            fails.append((pre, pr.split(":")[0], "structure: " + pr.split(": ", 1)[-1]))
        asked = applicable_fields(row.doc_type)
        for f in asked:
            per_field[f, "asked"] += 1
            per_field[f, "failed"] += any(x == f for x, _ in bad) or any(
                x.startswith(f + ":") for x in problems
            )
        docs.append(
            (
                pre,
                row.doc_type,
                len(asked),
                len({f for f, _ in bad}),
                len({f for d, f, _ in advice if d == pre}),
                len(notes),
            )
        )
    lines = [
        "# Web import check (Gemini web chat, prompt sv4-web, D-104)",
        "",
        f"Counts only: item ids, doc id prefixes, field names. Schema {SCHEMA_VERSION}.",
        "",
        "## Per document",
        "",
        "| doc | type | fields asked | passed | failed | advisory only | uncertain notes |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {d} | {t} | {a} | {a - f} | {f} | {v} | {n} |" for d, t, a, f, v, n in docs
    ]
    lines += ["", "## Per field (over the imported documents)", "",
              "| field | asked | passed | failed |", "|---|---|---|---|"]  # fmt: skip
    for f in sorted({f for f, _ in per_field}):
        a, b = per_field[f, "asked"], per_field[f, "failed"]
        lines.append(f"| {f} | {a} | {a - b} | {b} |")
    lines += ["", "## Failures (doc, field, check)", ""]
    lines += [f"- {d} {f} {n}" for d, f, n in fails] or ["none"]
    lines += ["", "## Advisory checks that failed (do not stop a field)", ""]
    lines += [f"- {d} {f} {n}" for d, f, n in advice] or ["none"]
    lines += ["", "## Not imported", ""]
    lines += [f"- {d}: {w}" for d, w in refused] or ["none"]
    text = "\n".join(lines) + "\n"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(text, encoding="utf-8")
    return text, len(fails) + len(refused)
