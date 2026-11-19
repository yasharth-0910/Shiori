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
MAX_CANDIDATES = 4
# Plain-English meaning of each Not found field, shown under the field name.
FIELD_MEANING = {
    "deadlines": "Submission deadline: the last date and time to hand in a bid",
    "contact": "Contact: who to ask about the tender (office, phone or email)",
    "bid_bond": "Bid deposit: money a bidder must pay before bidding",
    "delivery_location": "Delivery place: where the goods or work must be delivered",
}
# Words searched in the ORIGINAL Japanese text (never normalized text) to find
# candidate sentences for a Not found row. First the heading cues in
# docs/field_schema.md, then broader body-text words for the same field.
AUDIT_KEYWORDS = {
    # schema cues, plus 締切/期限/日時 for body text like "期限までに提出すること"
    "deadlines": (
        "入札日時", "入札書の受領期限", "提出期限", "受付期間", "開札の日時",
        "開札日時", "受領期限", "必着", "質問", "質疑", "入札説明会", "説明会",
        "締切", "期限", "日時",
    ),
    # schema cues, plus spelling variants (問合せ) and phone/mail words
    "contact": (
        "問い合わせ先", "問合せ先", "問い合わせ", "問合せ", "連絡先", "担当",
        "電話", "TEL", "FAX", "電子メール", "メールアドレス",
    ),
    # schema cue 入札保証金, plus the short form 保証金 used in body text
    "bid_bond": ("入札保証金", "保証金"),
    # schema cues, plus 納入先/納品先/履行地 used in specifications
    "delivery_location": ("納入場所", "履行場所", "納入先", "納品先", "履行地"),
}  # fmt: skip
NOT_FOUND_ANSWER = "Not found"
NOT_FOUND_Q = "Does any sentence in D answer this field?" + " (Yes / No / Unsure)"
NOT_FOUND_WHICH = "Which number? (1-4, or none)"
AUTO_CONFIRMED = "auto_confirmed_no_keyword_hit"
AUTO_NOTE = (
    "no keyword match in the document's sentences; this means no keyword match, "
    "not proof of absence"
)
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

    def all_of(self, doc: str) -> list[tuple[str, str, str]]:
        """(id, section, original text) of every sentence, in document order."""
        ...


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


def candidates(
    doc: str, field: str, lookup: Sentences, limit: int = MAX_CANDIDATES
) -> list[tuple[str, str, str]]:
    """Sentences whose original text contains a keyword of the field, best first:
    most distinct keywords, then document order. (id, section, text)."""
    words = AUDIT_KEYWORDS[field]
    scored = []
    for i, (sid, section, text) in enumerate(lookup.all_of(doc)):
        hits = sum(w in text for w in words)
        if hits:
            scored.append((-hits, i, (sid, section, text)))
    return [c for _, _, c in sorted(scored)[:limit]]


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
) -> tuple[list[dict], list[dict]]:
    """(rows for the sheet, Not found rows dropped for having no keyword hit)."""
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
    nf, auto = [], []
    for r in not_found_rows(absent, Counter(r["doc"] for r in chosen)):
        r["audit_no"] = None
        r["candidates"] = candidates(r["doc"], r["field"], lookup)
        (nf if r["candidates"] else auto).append(r)
    rows = sorted(chosen + nf, key=lambda r: (r["doc"], r["field"], r["no"]))
    for i, r in enumerate(rows, 1):
        r["no"] = i
    return rows, auto


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

    @staticmethod
    def _section(s: Any) -> str:
        titles = [
            t or p for p, t in zip(s.section_path, s.section_titles, strict=False)
        ]
        return " > ".join(titles)

    def get(self, doc: str, sid: str) -> tuple[str, str] | None:
        for s in self._doc(doc):
            if s.id == sid:
                return self._section(s), s.text_orig
        return None

    def all_of(self, doc: str) -> list[tuple[str, str, str]]:
        return [(s.id, self._section(s), s.text_orig) for s in self._doc(doc)]

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


def candidate_lines(r: dict) -> str:
    """1) [p3_s15] section > text, one per line; the text is the original."""
    return "\n".join(
        f"{i}) [{sid}] {section + ' > ' if section else ''}{text}"
        for i, (sid, section, text) in enumerate(r["candidates"], 1)
    )


def sheet_values(r: dict, docs: dict[str, Any]) -> list[str]:
    title = docs[r["doc"]].title_ja
    base = [str(r["no"]), f"{title} [{r['doc']}]"]
    if r.get("_not_found"):
        field = f"{r['field_label']}\n{FIELD_MEANING[r['field']]}"
        return base + [
            field, candidate_lines(r), NOT_FOUND_ANSWER, NOT_FOUND_Q,
            NOT_FOUND_WHICH, "", "", "",
        ]  # fmt: skip
    return base + [r["field_label"], r["src"], r["en"], "", "", "", "", ""]


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


NAVY, GREEN, SAND, WHITE = "2B4263", "2F6B4F", "F6EFE0", "FFFFFF"
ANSWER_FILL, NF_FILL, LINE = "EEF5F0", "FFF3D6", "CFC8B4"
WIDTHS = (6, 30, 18, 64, 38, 22, 22, 32, 32, 30)  # columns A to J


def write_xlsx(rows: list[dict], docs: dict[str, Any], path: Path = XLSX_OUT) -> None:
    """Colored sheet: navy question columns, green answer columns, rows shaded by
    document, Not found rows in yellow. A 'Start here' tab holds the instructions."""
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    def fill(rgb: str) -> PatternFill:
        return PatternFill("solid", fgColor=rgb)

    thin = Side(style="thin", color=LINE)
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    jp = "Noto Sans JP"  # Excel and Sheets fall back to a Japanese font if missing
    wb = Workbook()
    start = wb.active
    assert start is not None
    start.title = "Start here"
    start.sheet_view.showGridLines = False
    start.column_dimensions["A"].width = 3
    start.column_dimensions["B"].width = 110
    start.column_dimensions["C"].width = 90
    start["B2"] = "Shiori: reader check"
    start["B2"].font = Font(name="Arial", size=20, bold=True, color=NAVY)
    start["B3"] = "Thank you for helping. This takes about 30 to 45 minutes."
    start["B3"].font = Font(name="Arial", size=12, color="5A5446")
    n_last = len(rows) + 1
    guide = [
        ("What this is", "A computer program read public Japanese procurement "
         'documents and wrote short English answers. Each row on the "Audit" tab '
         "shows the Japanese sentence and the English answer."),
        ("What to do", "For each row, pick Yes, No or Unsure from the dropdowns in the "
         "green columns. If the English is wrong, type the correct English (and "
         "Japanese, if you can) in the next columns."),
        ("Not found rows", 'Rows with a yellow cell say "Not found": the program found '
         "nothing for that field. Column D lists up to 4 Japanese sentences from the "
         "same document that might be about it. Pick Yes, No or Unsure in the first "
         "green column for the whole group. In the next column type the number of the "
         "sentence that answers it (1 to 4), or none. No need to search the PDF. The "
         "sentences are picked by keyword, so No means none of these 4."),
        ("If you are not sure", "Choose Unsure. That is a fine answer."),
        ("Is this graded?", "No. Nothing here is graded and you are not being tested. "
         "The program is."),
        ("The documents", "All the documents are public."),
    ]  # fmt: skip
    for i, (label, text) in enumerate(guide, 5):
        for col, val, bold in (("B", label, True), ("C", text, False)):
            c = start[f"{col}{i}"]
            c.value = val
            c.font = Font(
                name="Arial", size=11, bold=bold, color=NAVY if bold else None
            )
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = Border(bottom=thin)
        start.row_dimensions[i].height = 96 if label == "Not found rows" else 48
    start["B12"] = "Colour key"
    start["B12"].font = Font(name="Arial", size=11, bold=True, color=NAVY)
    key = [
        ("Left columns (navy headers)", SAND,
         "What the program produced. Please do not edit."),
        ("Right columns (green headers)", ANSWER_FILL, "Your answers go here."),
        ("Yellow cells", NF_FILL,
         "Not found: the program found nothing for this field."),
    ]  # fmt: skip
    for i, (label, rgb, text) in enumerate(key, 13):
        start[f"B{i}"] = label
        start[f"B{i}"].fill = fill(rgb)
        start[f"C{i}"] = text
        for col in "BC":
            start[f"{col}{i}"].font = Font(name="Arial", size=10)
            start[f"{col}{i}"].border = box
    start["B17"] = "Rows answered"
    start["B17"].font = Font(name="Arial", size=11, bold=True, color=NAVY)
    start["C17"] = f'=COUNTA(Audit!F2:F{n_last})&" of {len(rows)}"'
    start["C17"].font = Font(name="Arial", size=11, bold=True)
    ws = wb.create_sheet("Audit")
    ws.append(HEADERS)
    for r in rows:
        ws.append(sheet_values(r, docs))
    for j, c in enumerate(ws[1]):
        c.font = Font(name="Arial", size=11, bold=True, color=WHITE)
        c.fill = fill(NAVY if j < 5 else GREEN)
        c.border = box
        c.alignment = Alignment(
            wrap_text=True,
            vertical="center",
            horizontal="center" if j in (0, 5, 6) else "left",
        )
    for col, w in zip("ABCDEFGHIJ", WIDTHS, strict=True):
        ws.column_dimensions[col].width = w
    ws.row_dimensions[1].height = 54
    ws.freeze_panes = "A2"
    dv = DataValidation(type="list", formula1='"Yes,No,Unsure"', allow_blank=True)
    ws.add_data_validation(dv)
    shade, prev = SAND, None
    for i, r in enumerate(rows, 2):
        if prev is not None and r["doc"] != prev:
            shade = WHITE if shade == SAND else SAND
        new_doc = r["doc"] != prev
        prev = r["doc"]
        nf = bool(r.get("_not_found"))
        for j, c in enumerate(ws[i]):
            answer = j >= 5
            c.fill = fill(ANSWER_FILL if answer else shade)
            if nf and j in (3, 4):
                c.fill = fill(NF_FILL)
            top = Side(style="medium", color=NAVY) if new_doc and i > 2 else thin
            c.border = Border(left=thin, right=thin, top=top, bottom=thin)
            c.font = Font(
                name=jp if j in (1, 3) else "Arial",
                size=10,
                bold=j == 2,
                italic=nf and j == 6,
                color="9A9486" if nf and j == 6 else None,
            )
            c.alignment = Alignment(
                wrap_text=True,
                vertical="top",
                horizontal="center" if j in (0, 5, 6) else "left",
            )
        dv.add(f"F{i}" if nf else f"F{i}:G{i}")
    # Colored dropdown answers: Yes green, No red, Unsure amber.
    for word, bg, fg in (
        ("Yes", "CFE8D5", "1E5B33"),
        ("No", "F6CFCB", "8A1F14"),
        ("Unsure", "FBE7B5", "7A5300"),
    ):
        ws.conditional_formatting.add(
            f"F2:G{n_last}",
            CellIsRule(
                operator="equal",
                formula=[f'"{word}"'],
                fill=PatternFill(bgColor=bg, fill_type="solid"),
                font=Font(color=fg),
            ),
        )
    wb.active = 1
    wb.save(path)


INSTRUCTIONS = """\
Reader's audit: instructions

This sheet checks about 45 short English answers that a computer program wrote after
reading Japanese public tender documents. Most rows show a Japanese sentence, the
English answer, and a question. Please tell us whether the English matches the Japanese.

It should take 30 to 45 minutes. If you cannot tell, write Unsure. That is fine.
Nothing here is graded, and we are not testing you. We are testing the program.

All the documents are public.

A few rows say "Not found" in the English column. The program found nothing for that
field, so there is no English to check. Column D lists up to 4 Japanese sentences from
the same document that might be about the field (the field is explained in plain
English in column C). Read them and answer:
  - Column F: does any of those sentences answer the field? Yes, No or Unsure.
  - Column G: if yes, type its number (1 to 4) over the printed text. If none,
    type none.
You do not need to search the PDF. If none of the sentences fit, "No" is the answer.
The sentences are picked by keyword, so a "No" means none of these 4, not that the
document never says it.

Write your answer and any short note in the empty columns at the right.
"""


def build() -> None:
    raw = json.loads(ROWS_IN.read_text())
    docs, dropped = open_docs(raw)
    rows, auto = build_rows(
        [r for r in raw if r["doc"] in docs],
        RealSentences(),
        read_absent(set(docs)),
    )
    if len({r["doc"] for r in rows}) < MIN_DOCS:
        sys.exit(f"fewer than {MIN_DOCS} documents in the sheet")
    key = key_rows(rows, docs)
    key += [
        {
            "no": None,
            "doc": r["doc"],
            "doc_id": r["doc_id"],
            "field": r["field"],
            "kind": AUTO_CONFIRMED,
            "note": AUTO_NOTE,
        }
        for r in auto
    ]
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
    ids = json.loads(ID_REGISTRY.read_text()) if ID_REGISTRY.exists() else {}
    for r in rows + auto:
        if r.get("_not_found"):
            kept = r in rows
            print(
                f"Not found: item_ids={item_ids(r, ids)} doc={r['doc']} "
                f"field={r['field']} keywords={AUDIT_KEYWORDS[r['field']]} "
                f"candidates={len(r['candidates'])} "
                f"{'kept' if kept else AUTO_CONFIRMED}"
            )


if __name__ == "__main__":
    if sys.argv[1:] != ["build"]:
        sys.exit("usage: python -m eval.audit_trim build")
    build()
