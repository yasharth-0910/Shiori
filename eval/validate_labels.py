"""Validate label files against the schema and the documents they describe.

    uv run python -m eval.validate_labels [label.jsonl ...]

With no arguments it checks every file under data/eval/ and data/eval_private/.
Exit code 1 when anything is wrong. Per file it checks:

- every line parses (label_format.LabelLine: schema version, status rules, shape of
  `normalized`, provenance states) and there is exactly one line per v1 field;
- extractor_version equals the current extractor's (labels are tied to sentence ids);
- every cited sentence exists in the document and is Japanese, never English Summary;
- a field that does not apply to the document's type is absent (field_schema.md);
- normalized values re-run through the converters: dates, times, deadline flags, fiscal
  years, tax wording, percentages, category codes, grades, phone and email must be
  readable in the sentences cited for them;
- the path rule (D-24): open documents under data/eval/, others under
  data/eval_private/, in the split directory splits.json gives for the document's org.

Dev-time only. Prints doc ids, fields and rule names, never document text.
"""

import json
import sys
from pathlib import Path

from pydantic import ValidationError
from shiori_core.checks import check_values
from shiori_core.fields import BY_ID, FIELD_IDS, validate_normalized
from shiori_core.models import EXTRACTOR_VERSION, Sentence

from collector.manifest import ManifestRow, read_rows
from eval.documents import load_sentences
from eval.label_format import LabelLine

EVAL_DIR = Path("data/eval")
PRIVATE_DIR = Path("data/eval_private")
SPLITS_PATH = EVAL_DIR / "splits.json"


def _texts(sentences: dict[str, Sentence], ids: list[str]) -> list[Sentence]:
    return [sentences[i] for i in ids if i in sentences]


def validate_lines(
    raw: list[dict],
    row: ManifestRow,
    sentences: list[Sentence],
) -> list[str]:
    """Everything that needs the document. Returns error strings, empty when valid."""
    by_id = {s.id: s for s in sentences}
    errs: list[str] = []
    lines: list[LabelLine] = []
    for n, r in enumerate(raw, 1):
        try:
            lines.append(LabelLine.model_validate(r))
        except ValidationError as e:
            errs += [f"line {n} ({r.get('field')}): {x['msg']}" for x in e.errors()]
    seen = [ln.field for ln in lines]
    if not errs and sorted(seen) != sorted(FIELD_IDS):
        missing = sorted(set(FIELD_IDS) - set(seen))
        dup = sorted({f for f in seen if seen.count(f) > 1})
        errs.append(
            f"need exactly one line per field: missing {missing}, duplicated {dup}"
        )
    for ln in lines:
        tag = f"{ln.field}"
        if ln.doc_id != row.doc_id:
            errs.append(f"{tag}: doc_id {ln.doc_id} is not the file's document")
        if ln.extractor_version != EXTRACTOR_VERSION:
            errs.append(f"{tag}: extractor_version {ln.extractor_version} != current")
        for c in ln.citations:
            s = by_id.get(c)
            if s is None:
                errs.append(f"{tag}: citation {c} is not a sentence of the document")
            elif s.language != "ja":
                errs.append(f"{tag}: citation {c} is English text, cite Japanese only")
        if ln.status != "absent" and row.doc_type not in BY_ID[ln.field].applies_to:
            errs.append(
                f"{tag}: does not apply to doc_type {row.doc_type}, must be absent"
            )
        if ln.status == "present" and not any(
            e.startswith(f"{tag}: citation") for e in errs
        ):
            model = validate_normalized(ln.field, ln.normalized)
            if model is not None:
                ss_of = lambda ids: _texts(by_id, ids)  # noqa: E731
                errs += check_values(ln.field, model, ss_of, ln.citations)
    return errs


def check_path(path: Path, row: ManifestRow, splits: dict[str, str]) -> list[str]:
    """D-24: open -> data/eval/, else data/eval_private/; and the split directory."""
    errs: list[str] = []
    root = path.parent.parent.parent.name
    if row.license_class == "open" and root != EVAL_DIR.name:
        errs.append(f"open document's labels belong in {EVAL_DIR}/ (D-24)")
    if row.license_class != "open" and root != PRIVATE_DIR.name:
        errs.append(
            f"{row.license_class} document's labels belong in {PRIVATE_DIR}/ (D-24)"
        )
    want = splits.get(row.issuer_org)
    if want is None:
        errs.append(f"org {row.issuer_org} is not in splits.json")
    elif path.parent.parent.name != want:
        errs.append(f"org is in split {want}, file is under {path.parent.parent.name}/")
    if path.parent.name != "labels":
        errs.append("label files live in <split>/labels/")
    return errs


def validate_file(
    path: Path, rows: dict[str, ManifestRow], splits: dict[str, str]
) -> list[str]:
    row = rows.get(path.stem)
    if row is None:
        return [f"{path.stem} is not in the manifest"]
    errs = check_path(path, row, splits)
    try:
        raw = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    except json.JSONDecodeError as e:
        return [*errs, f"not JSON lines: {e.msg}"]
    return errs + validate_lines(raw, row, load_sentences(row))


def main(argv: list[str]) -> int:
    rows = {r.doc_id: r for r in read_rows()}
    splits = json.loads(SPLITS_PATH.read_text())
    paths = [Path(a) for a in argv] or sorted(
        p for d in (EVAL_DIR, PRIVATE_DIR) for p in d.glob("*/labels/*.jsonl")
    )
    bad = 0
    for p in paths:
        errs = validate_file(p, rows, splits)
        bad += bool(errs)
        for e in errs:
            print(f"{p}: {e}")
    print(f"{len(paths)} files, {bad} with errors")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
