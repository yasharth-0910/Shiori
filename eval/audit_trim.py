"""Shorter readers' audit sheet for a native Japanese reader (dev-time only).

Reads data/cache/audit/audit_rows.json (and the dev label files, read-only, for the
fields a label marks absent). Writes readers_audit_v2.csv, readers_audit_v2.xlsx,
readers_audit_v2_key.json and readers_audit_instructions.txt next to it. No label file
is written, no model or network is used. Status, tier, reasons, model names and
agreement are left out of the sheet so the reader is not primed.
"""

import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Protocol

AUDIT_DIR = Path("data/cache/audit")
ROWS_IN = AUDIT_DIR / "audit_rows.json"
CSV_OUT = AUDIT_DIR / "readers_audit_v2.csv"
XLSX_OUT = AUDIT_DIR / "readers_audit_v2.xlsx"
KEY_OUT = AUDIT_DIR / "readers_audit_v2_key.json"
INSTRUCTIONS_OUT = AUDIT_DIR / "readers_audit_instructions.txt"
LABELS_DIR = Path("data/eval/dev/labels")
ID_REGISTRY = Path("data/cache/labeling/export/ids.json")
SEED = 20261119
KEEP = 45
NOT_FOUND_ROWS = 5
ELIGIBILITY_MIN = 10
MIN_DOCS = 8
# Audit rows that must be in the sheet (original "no" in audit_rows.json): Article 70
# with a なお proviso (83, 109, 125), organized crime in 28ad40ea (9) and d4000027
# (55), and an Article 71 row (88).
FORCED = (83, 109, 125, 9, 55, 88)
BOND_FIELDS = ("performance_bond", "bid_bond")
# Fields a bidder expects to find; one Not found row each, in this order.
NOT_FOUND_FIELDS = ("deadlines", "contact", "bid_bond", "delivery_location", "contact")
EXTRA_LABELS = {
    "deadlines": "Submission deadline",
    "contact": "Contact",
    "bid_bond": "Bid deposit (bond)",
    "delivery_location": "Delivery place",
}
NOT_FOUND_Q = "Does this document state this anywhere?"
YNU = " (Yes / No / Unsure)"
HEADERS = [
    "No",
    "Document",
    "Field",
    "Japanese source sentence(s)",
    "Our English answer",
    "Is the English correct?" + YNU,
    "Is this the right sentence for this field?" + YNU,
    "Correct English (if wrong)",
    "Correct Japanese (if wrong)",
    "Comment",
    "Where (page or section)?",
]

# internal prefix -> plain English
PREFIXES = {
    "other/requirement:": "Requirement:",
    "legal/requirement:": "Requirement:",
    "unified_qualification/requirement:": "Qualification requirement:",
    "legal/disqualification:": "Cannot bid if:",
    "other/disqualification:": "Cannot bid if:",
    "bid_opening:": "Bid opening:",
    "question:": "Questions due:",
    "briefing:": "Briefing:",
    "electronic:": "Electronic submission due:",
    "other:": "Due:",
}
REF_KIND = {"bid_instructions": "the bid instructions", "spec": "the specification"}
MODE_TEXT = {
    "in_person": "in person",
    "mail": "by mail",
    "electronic": "electronically",
}
ISO = re.compile(r"(\d{4})-(\d\d)-(\d\d)T(\d\d:\d\d):\d\d\+09:00")
CUT = re.compile(r"[、，をにはがとのへもやて]$|(及び|又は|並びに|かつ|ただし|または)$")
SRC_LINE = re.compile(r"^\[([^\]]+)\] (.*)$")


class Sentences(Protocol):
    """Where the sheet gets sentence text, section and the next sentence."""

    def get(self, doc: str, sid: str) -> tuple[str, str] | None:
        """(section, text) of a sentence."""

    def next_of(self, doc: str, sid: str) -> tuple[str, str] | None:
        """(id, text) of the sentence after sid."""


def plain_json(obj: object) -> str | None:
    """Plain English for the JSON shapes in the sheet; None = drop the row."""
    if isinstance(obj, dict) and isinstance(obj.get("ref"), dict):
        kind = REF_KIND.get(obj["ref"].get("kind", ""))
        return f"See {kind}." if kind else None
    if isinstance(obj, dict) and isinstance(obj.get("modes"), list):
        modes = [MODE_TEXT[m] for m in obj["modes"] if m in MODE_TEXT]
        if not modes:
            return None
        if len(modes) == 1:
            joined = modes[0]
        else:
            joined = ", ".join(modes[:-1]) + " or " + modes[-1]
        text = f"Can submit {joined}"
        return text + (". Mail is not allowed." if obj.get("mail_not_allowed") else "")
    return None


def clean_en(en: str) -> str | None:
    """Plain-English answer, or None if it cannot be made readable (drop row)."""
    en = en.strip()
    if "{" in en:
        head, _, tail = en.partition("{")
        try:
            body = json.loads("{" + tail)
        except ValueError:
            return None
        if head.strip():  # real English before the JSON blob: keep it, drop the blob
            en = head.strip()
        else:
            return plain_json(body)
    for old, new in PREFIXES.items():
        if en.startswith(old):
            en = f"{new} {en[len(old) :].strip()}"
            break
    en = ISO.sub(r"\1-\2-\3 \4", en)
    return en.replace(" arrival_required", " (must arrive by then)")


def is_empty_answer(en: str) -> bool:
    return not en.strip() or "not found" in en.lower()


def key_of(row: dict) -> str:
    """Same Japanese sentence = same example. No ja: use the source text."""
    return row["ja"].strip() or SRC_LINE.sub(r"\2", row["src"]).strip()


def is_trivial_bond(row: dict) -> bool:
    text = row["en"].lower()
    waived = "waive" in text or "exempt" in text or row["ja"].strip().startswith("免除")
    return row["field"] in BOND_FIELDS and waived


def drop_duplicates(rows: list[dict]) -> list[dict]:
    """One row per sentence per document (a unified_qualification row beats an
    eligibility row for the same sentence), then one per sentence overall, then at
    most one waived-bond row. Forced rows win ties."""

    def rank(r: dict) -> tuple[bool, bool, int]:
        return (r["no"] not in FORCED, r["field"] == "eligibility", r["no"])

    seen_doc: dict[tuple[str, str], dict] = {}
    for r in sorted(rows, key=rank):
        seen_doc.setdefault((r["doc"], key_of(r)), r)
    seen_all: dict[str, dict] = {}
    for r in sorted(seen_doc.values(), key=rank):
        seen_all.setdefault(key_of(r), r)
    out, bond_kept = [], False
    for r in sorted(seen_all.values(), key=lambda r: r["no"]):
        if is_trivial_bond(r):
            if bond_kept:
                continue
            bond_kept = True
        out.append(r)
    return out


def pick(rows: list[dict], seed: int = SEED, keep: int = KEEP) -> list[dict]:
    """Forced rows, then eligibility up to ELIGIBILITY_MIN, then a round robin over
    the other fields, always taking from the least-used document first."""
    rng = random.Random(seed)
    pool = sorted(drop_duplicates(rows), key=lambda r: r["no"])
    rng.shuffle(pool)
    chosen = [r for r in pool if r["no"] in FORCED]
    docs = Counter(r["doc"] for r in chosen)

    def take(q: list[dict]) -> None:
        best = min(q, key=lambda r: docs[r["doc"]])
        q.remove(best)
        chosen.append(best)
        docs[best["doc"]] += 1

    rest = [r for r in pool if r not in chosen]
    elig = [r for r in rest if r["field"] == "eligibility"]
    while sum(r["field"] == "eligibility" for r in chosen) < ELIGIBILITY_MIN and elig:
        take(elig)
    queues: dict[str, list[dict]] = defaultdict(list)
    for r in rest:
        if r["field"] != "eligibility":
            queues[r["field"]].append(r)
    while len(chosen) < keep and any(queues.values()):
        for field in sorted(queues):
            if queues[field] and len(chosen) < keep:
                take(queues[field])
    return chosen


def finish_sentence(row: dict, lookup: Sentences) -> None:
    """Last source sentence stops mid-sentence: add the next one to the SOURCE column
    only. The Japanese cell is the label's value and is never changed."""
    lines = row["src"].split("\n")
    m = SRC_LINE.match(lines[-1]) if lines[-1] else None
    if not m or not CUT.search(m.group(2).rstrip()):
        return
    nxt = lookup.next_of(row["doc"], m.group(1))
    if nxt:
        row["src"] += f"\n[{nxt[0]}] {nxt[1]}"


def add_section(row: dict, lookup: Sentences) -> None:
    """Put the section of the first source sentence on top of the source cell."""
    m = SRC_LINE.match(row["src"].split("\n")[0])
    found = lookup.get(row["doc"], m.group(1)) if m else None
    if found and found[0]:
        row["src"] = f"Section: {found[0]}\n{row['src']}"


def read_absent(
    docs: set[str], labels_dir: Path = LABELS_DIR
) -> dict[str, dict[str, str]]:
    """field -> {doc prefix: full doc id} for dev label lines with status absent."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for p in sorted(labels_dir.glob("*.jsonl")):
        if p.name[:8] not in docs:
            continue
        for line in p.read_text().splitlines():
            d = json.loads(line)
            if d["status"] == "absent":
                out[d["field"]][p.name[:8]] = d["doc_id"]
    return out


def not_found_rows(
    absent: dict[str, dict[str, str]], used_docs: Counter, seed: int = SEED
) -> list[dict]:
    """One row per entry of NOT_FOUND_FIELDS, each from a different document,
    preferring documents with the fewest rows. The English cell stays empty."""
    rng = random.Random(seed)
    out: list[dict] = []
    taken: set[str] = set()
    for field in NOT_FOUND_FIELDS:
        cands = sorted(d for d in absent.get(field, {}) if d not in taken)
        if not cands:
            continue
        rng.shuffle(cands)
        doc = min(cands, key=lambda d: used_docs[d])
        taken.add(doc)
        out.append(
            {
                "doc": doc,
                "doc_id": absent[field][doc],
                "field": field,
                "field_label": EXTRA_LABELS.get(field, field),
                "ja": "",
                "en": "",
                "src": "",
                "_not_found": True,
                "no": 0,
            }
        )
    return out


def build_rows(
    raw: list[dict], lookup: Sentences, absent: dict[str, dict[str, str]]
) -> list[dict]:
    prepared = []
    for r in raw:
        if is_empty_answer(r["en"]):
            continue
        en = clean_en(r["en"])
        if en is not None:
            prepared.append({**r, "en": en})
    chosen = pick(prepared, keep=KEEP - NOT_FOUND_ROWS)
    chosen = [{**r, "audit_no": r["no"]} for r in chosen]
    for r in chosen:
        finish_sentence(r, lookup)
        add_section(r, lookup)
    nf = not_found_rows(absent, Counter(r["doc"] for r in chosen))
    for r in nf:
        r["audit_no"] = None
    rows = sorted(chosen + nf, key=lambda r: (r["doc"], r["field"], r["no"]))
    for i, r in enumerate(rows, 1):
        r["no"] = i
    return rows


class RealSentences:
    """Sentences of the manifest documents, from the extractor cache (dev-time)."""

    def __init__(self) -> None:
        from collector.manifest import read_rows

        self.manifest = read_rows()
        self.cache: dict[str, list] = {}

    def _doc(self, doc: str) -> list:
        from eval.documents import load_sentences

        if doc not in self.cache:
            row = next(r for r in self.manifest if r.doc_id.startswith(doc))
            self.cache[doc] = [s for s in load_sentences(row) if s.language == "ja"]
        return self.cache[doc]

    def get(self, doc: str, sid: str) -> tuple[str, str] | None:
        for s in self._doc(doc):
            if s.id == sid:
                titles = [
                    t or p
                    for p, t in zip(s.section_path, s.section_titles, strict=False)
                ]
                return " > ".join(titles), s.text_orig
        return None

    def next_of(self, doc: str, sid: str) -> tuple[str, str] | None:
        ss = self._doc(doc)
        for i, s in enumerate(ss):
            if s.id == sid and i + 1 < len(ss):
                return ss[i + 1].id, ss[i + 1].text_orig
        return None


def open_docs(raw: list[dict]) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    from collector.manifest import read_rows

    manifest = read_rows()
    keep: dict[str, Any] = {}
    dropped: list[tuple[str, str]] = []
    for d in sorted({r["doc"] for r in raw}):
        row = next((m for m in manifest if m.doc_id.startswith(d)), None)
        if row is not None and row.license_class == "open":
            keep[d] = row
        else:
            dropped.append((d, row.license_class if row else "not in manifest"))
    return keep, dropped


def sheet_values(r: dict, docs: dict[str, Any]) -> list[str]:
    title = docs[r["doc"]].title_ja
    base = [str(r["no"]), f"{title} [{r['doc']}]", r["field_label"]]
    if r.get("_not_found"):
        return base + ["", "", NOT_FOUND_Q, "", "", "", "", ""]
    return base + [r["src"], r["en"], "", "", "", "", "", ""]


def item_ids(r: dict, registry: dict) -> list[str]:
    """Review item ids for this document and field (best effort)."""
    doc_id = r.get("doc_id", "")
    return sorted(
        i
        for i, v in registry.get("items", {}).items()
        if v["doc_id"] == doc_id and v["field"] == r["field"]
    )


def key_rows(rows: list[dict], docs: dict[str, Any]) -> list[dict]:
    reg = json.loads(ID_REGISTRY.read_text()) if ID_REGISTRY.exists() else {}
    out = []
    for r in rows:
        full = docs[r["doc"]].doc_id
        r["doc_id"] = full
        out.append(
            {
                "no": r["no"],
                "doc": r["doc"],
                "doc_id": full,
                "field": r["field"],
                "kind": "absent_label" if r.get("_not_found") else "answer",
                "label_item_ids": [] if r.get("_not_found") else item_ids(r, reg),
                "audit_row_no": r["audit_no"],
            }
        )
    return out


def write_csv(rows: list[dict], docs: dict[str, Any], path: Path = CSV_OUT) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        for r in rows:
            w.writerow(sheet_values(r, docs))


def write_xlsx(rows: list[dict], docs: dict[str, Any], path: Path = XLSX_OUT) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    font = "Yu Gothic"  # has Japanese glyphs on Windows and in Office on Mac
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Readers audit"
    ws.append(HEADERS)
    for r in rows:
        ws.append(sheet_values(r, docs))
    for c in ws[1]:
        c.font = Font(name=font, bold=True)
        c.fill = PatternFill("solid", fgColor="DDDDDD")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for col, w in zip(
        "ABCDEFGHIJK", (5, 30, 18, 60, 38, 15, 18, 30, 30, 30, 24), strict=True
    ):
        ws.column_dimensions[col].width = w
    ws.row_dimensions[1].height = 48
    ws.freeze_panes = "A2"
    dv = DataValidation(type="list", formula1='"Yes,No,Unsure"', allow_blank=True)
    ws.add_data_validation(dv)
    for i, r in enumerate(rows, 2):
        for c in ws[i]:
            c.font = Font(name=font)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        if r.get("_not_found"):
            ws.merge_cells(f"F{i}:G{i}")  # the question sits over both columns
            ws.row_dimensions[i].height = 32
        else:
            dv.add(f"F{i}:G{i}")
    wb.save(path)


INSTRUCTIONS = """\
Reader's audit: instructions

This sheet checks 45 short English answers that a computer program wrote after reading
Japanese public tender documents. Each row shows the Japanese sentence, the English
answer, and a question. Please tell us whether the English matches the Japanese.

It should take 30 to 45 minutes. If you cannot tell, write Unsure. That is fine.
Nothing here is graded, and we are not testing you. We are testing the program.

All the documents are public.

Some rows ask "Does this document state this anywhere?" For those, write the page or
section in the Where column, or "Not stated".

Write your answer and any short note in the empty columns at the right.
"""


def build() -> None:
    raw = json.loads(ROWS_IN.read_text())
    docs, dropped = open_docs(raw)
    rows = build_rows(
        [r for r in raw if r["doc"] in docs],
        RealSentences(),
        read_absent(set(docs)),
    )
    if len({r["doc"] for r in rows}) < MIN_DOCS:
        sys.exit(f"fewer than {MIN_DOCS} documents in the sheet")
    key = key_rows(rows, docs)
    write_csv(rows, docs)
    KEY_OUT.write_text(json.dumps(key, ensure_ascii=False, indent=1))
    INSTRUCTIONS_OUT.write_text(INSTRUCTIONS)
    try:
        write_xlsx(rows, docs)
        xlsx = "written"
    except ImportError:
        xlsx = "NOT written: openpyxl is not installed (run uv sync online)"
    print(f"rows: {len(rows)} of {len(raw)}; excluded (not open): {dropped or 'none'}")
    print("xlsx:", xlsx)
    print("per field:", dict(Counter(r["field"] for r in rows)))
    print("per doc:", dict(Counter(r["doc"] for r in rows)))
    print(
        "Not found rows:", [(r["field"], r["doc"]) for r in rows if r.get("_not_found")]
    )


if __name__ == "__main__":
    if sys.argv[1:] != ["build"]:
        sys.exit("usage: python -m eval.audit_trim build")
    build()
