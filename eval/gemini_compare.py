# ruff: noqa: E501
"""Compare the rules extractor with Gemini's silver answers on 50 documents (no model, no network).

    uv run python -m eval.gemini_compare

Reads data/cache/gemini_ref/gemini_fields.csv and the document list in data/cache/gemini_batches/index.md,
finds each PDF in data/manifests/documents.jsonl by its 12-character doc id prefix, and runs the sidecar's
path (read_pages, doc type from the first page, segment, rules.extract). Writes, under data/cache/gemini_compare/
(gitignored): report.md (counts and doc id prefixes only) and disagreements.tsv (Japanese text; one line per
both_found_differ). Gemini is a silver reference, not ground truth: its quotes are not verbatim. Documents whose
issuer is in the test split are refused, not read.
"""

import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from shiori_core.doctype import detect_doc_type, first_page_lines
from shiori_core.extract import rules
from shiori_core.extract.rules import Extracted
from shiori_core.fields import BY_ID
from shiori_core.ingest import read_pages
from shiori_core.normalize import normalize
from shiori_core.segment import segment
from shiori_core.value_normalize import find_dates

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data/cache/gemini_ref/gemini_fields.csv"
INDEX = ROOT / "data/cache/gemini_batches/index.md"
OUT = ROOT / "data/cache/gemini_compare"
FIELDS = (
    "title",
    "issuer_org",
    "contracting_officer",
    "notice_date",
    "performance_period",
)
CLASSES = (
    "both_found_agree",
    "both_found_differ",
    "we_found_gemini_not_stated",
    "gemini_found_we_not_found",
    "both_not_found",
)
# Second set (rule fields with an enum, flag or rate form). Sixth class: Gemini gave an answer
# whose free English text no keyword rule below maps to the field's form (counted, never guessed).
RULE_FIELDS = (
    "procurement_type",
    "award_method",
    "item_category",
    "bid_bond",
    "performance_bond",
    "tax_basis",
    "language_currency",
    "submission_modes",
    "wto_covered",
    "spec_access",
    "unified_qualification",
)
CLASSES6 = (*CLASSES, "unmapped")
_NOT_FOUND = re.compile(
    r"(?i)\s*(not stated|not explicitly|not required|in another document)"
)
_CJK = re.compile(r"[぀-ヿ一-鿿々]+")
_TITLEISH = re.compile(r"[官長知事殿庁省局部課県市府町村]|参事|担当")


def flat(s: str) -> str:
    """NFKC, no whitespace: the form two Japanese strings are compared in."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def contains_either(a: str, b: str) -> bool:
    a, b = flat(a), flat(b)
    return bool(a and b) and (a in b or b in a)


def gemini_found(answer: str) -> bool:
    return bool(answer.strip()) and not _NOT_FOUND.match(answer)


def iso_dates(text: str) -> list[str]:
    """ISO dates in a Japanese string, by the project's own normalizer and date finder."""
    return [
        d.value.isoformat()
        for d in find_dates(normalize(text)[0])
        if d.value is not None
    ]


def officer_tokens(answer_en: str) -> list[str]:
    """Person-name tokens in Gemini's answer: Japanese runs that are not a post (長, 官, 知事...)."""
    return [t for t in _CJK.findall(answer_en) if not _TITLEISH.search(t)]


# --- second set of fields: Gemini's English text mapped to our form by keywords ---------------
# One table, used by the mappers and printed in the report. Patterns run on lower-cased answer_en.
KEYWORDS: dict[str, list[tuple[str, str]]] = {
    "procurement_type": [  # read on the head of the answer (before the first ( — ; :); exactly one label
        ("open_competitive", r"open competitive|general competitive|open bid|open tender"),
        ("designated_competitive", r"designated (?:competitive|bid|tender)|nominated"),
        ("proposal_competition", r"proposal|planning competition"),
        ("public_solicitation", r"public solicitation|public call|open call"),
        ("negotiated", r"negotiated|private contract|discretionary"),
        ("open_counter", r"open counter"),
        ("other", r"^other\b"),
    ],
    "award_method": [  # head of the answer, exactly one label
        ("lowest_price", r"lowest|minimum price"),
        ("best_value", r"best value|overall evaluation|comprehensive evaluation|most advantageous"),
        ("other", r"^other\b"),
    ],
    "tax_basis": [  # the label whose keyword comes first; an answer starting with "both" is unmapped
        ("bid_excludes_tax", r"exclud|tax-excl|before (?:consumption )?tax"),
        ("bid_includes_tax", r"includ|tax-incl"),
    ],
    "wto_covered": [  # the label whose keyword comes first
        ("false", r"not covered|does not apply|not subject|not applicable|outside|exempt"),
        ("true", r"^yes|covered|appl(?:y|ies)|subject to|governed by"),
    ],
    "spec_access": [  # the label whose keyword comes first ("in another document" counts as found here)
        ("see_other_document", r"^in another document|attached|separate sheet|separate (?:draft )?specification"),
        ("email_after_pledge", r"e-?mail"),
        ("at_counter", r"counter|window|in person|inspect|reading room|viewing"),
        ("public", r"download|posted|published|website|electronic procurement|public"),
    ],
    "bond": [  # bid_bond and performance_bond: required (also "required ... waived with conditions") vs waived
        ("waived", r"waive|exempt"),
        ("required", r"required|must|at least|or more|deposit"),
        ("rate", r"(\d+(?:\.\d+)?)\s*/\s*100|(\d+(?:\.\d+)?)\s*%"),
    ],
    "submission_modes": [  # modes = labels found after the "refused" span is cut out; union over the whole answer
        ("in_person", r"in[- ]person|hand[- ]deliver|bring|at the tender|counter"),
        ("mail", r"(?<!e)(?<!e-)mail|postal|\bpost\b"),
        ("electronic", r"electronic|e-?mail|online"),
        ("refused", r"(?:mail|post)[^.;()]{0,40}(?:not accepted|not allowed|(?<!not )refused|rejected|invalid|prohibited)|(?:not accept|refuse|do not allow)[^.;]{0,30}(?:mail|post)"),
    ],
    "language_currency": [  # a part Gemini does not give is not compared
        ("ja", r"japanese(?! (?:yen|currency))|in japanese"),
        ("en", r"english"),
        ("JPY", r"yen|japanese currency|jpy|円"),
        ("language_not_stated", r"language[^.;]{0,25}\bnot\b"),
    ],
    "unified_qualification": [  # kind; grades compared only when both sides give them
        ("local", r"^local equivalent"),
        ("unified", r"unified|全省庁統一"),
        ("grades", r"grades?\s+(\b[a-d]\b(?:(?:\s*[,/&]\s*(?:(?:or|and)\s+)?|\s+(?:or|and)\s+)\b[a-d]\b)*)"),
    ],
    "item_category": [  # codes: parenthesised 2-5 digit numbers, years (19xx, 20xx) left out
        ("code", r"\(\s*(\d{2,5})\s*\)"),
    ],
}  # fmt: skip
# Side notes in Gemini's text that name a mode only to say it is absent, refused or is not a bid channel.
_MODE_NOISE = r"electronic[^.;]{0,30}not (?:explicitly )?stated|(?:fax and )?e-?mail[^.;]{0,15}refused|electronic data"
_HEAD_SPLIT = re.compile(r"[(（—;:]|\s-\s")
_ENUM_KEY = {
    "procurement_type": "type",
    "award_method": "method",
    "tax_basis": "basis",
    "spec_access": "mode",
    "wto_covered": "covered",
}


def kw(key: str, text: str) -> dict[str, int]:
    """label -> start of its first keyword match in the lower-cased text (labels with no match left out)."""
    t = text.lower()
    out = {}
    for label, pat in KEYWORDS[key]:
        if m := re.search(pat, t):
            out[label] = m.start()
    return out


def gemini_form(field: str, answer_en: str) -> object | None:
    """Gemini's answer in our comparable form, or None when no keyword rule maps it (unmapped)."""
    a = answer_en
    if field in ("procurement_type", "award_method"):
        f = kw(field, _HEAD_SPLIT.split(a.lower())[0])
        return next(iter(f)) if len(f) == 1 else None
    if field in ("tax_basis", "spec_access", "wto_covered"):
        if field == "tax_basis" and re.match(r"(?i)\s*both\b", a):
            return None
        f = kw(field, a)
        v = min(f, key=lambda k: f[k]) if f else None
        return (v == "true") if field == "wto_covered" and v else v
    if field.endswith("_bond"):
        f = kw("bond", a)
        if "required" not in f and "waived" not in f:
            return None
        need = "required" in f
        rate = None
        if need and (m := re.search(dict(KEYWORDS["bond"])["rate"], a.lower())):
            rate = float(m.group(1) or m.group(2))
        return (need, rate)
    if field == "submission_modes":
        t = a.lower()
        pat = dict(KEYWORDS["submission_modes"])["refused"]
        refused = re.search(pat, t)
        t = re.sub(_MODE_NOISE, " ", re.sub(pat, " ", t))
        f = kw("submission_modes", t)
        modes = frozenset(k for k in ("in_person", "mail", "electronic") if k in f)
        refused = (
            bool(refused) and "mail" not in modes
        )  # "registered mail only (ordinary mail is invalid)" allows mail
        return (modes, refused) if modes or refused else None
    if field == "language_currency":
        f = kw(field, a)
        ja, en = "ja" in f, "en" in f
        lang = None if "language_not_stated" in f else "ja+en" if ja and en else "ja" if ja else "en" if en else None  # fmt: skip
        cur = "JPY" if "JPY" in f else None
        return (lang, cur) if lang or cur else None
    if field == "unified_qualification":
        f = kw(field, a)
        kind = "local" if "local" in f else "unified" if "unified" in f else None
        if kind is None:
            return None
        m = re.search(dict(KEYWORDS[field])["grades"], a.lower())
        return (kind, frozenset(re.findall("[a-d]", m.group(1).upper() if m else "")) if m else frozenset())  # fmt: skip
    if field == "item_category":
        codes = {c for c in re.findall(dict(KEYWORDS[field])["code"], a) if not re.fullmatch(r"(?:19|20)\d\d", c)}  # fmt: skip
        return frozenset(codes) if codes else None
    raise KeyError(field)


def our_form(field: str, ours: Extracted) -> object:
    """Our normalized value in the same form (a pointer is the string see_other_document)."""
    n = ours.normalized
    if field in _ENUM_KEY:
        if ours.status == "see_other_document":
            return "see_other_document"
        return n.get(_ENUM_KEY[field])
    if field.endswith("_bond"):
        return (n.get("status") in ("required", "waived_with_proviso"), n.get("rate_percent"))  # fmt: skip
    if field == "submission_modes":
        return (frozenset(n.get("modes", [])), bool(n.get("mail_not_allowed")))
    if field == "language_currency":
        return (n.get("language"), n.get("currency"))
    if field == "unified_qualification":
        return ("unified", frozenset(n.get("grades", [])))
    return frozenset(n.get("codes", []))  # item_category


def same_form(field: str, mine: object, theirs: object) -> bool:
    if field.endswith("_bond"):
        (m_need, m_rate), (t_need, t_rate) = mine, theirs  # type: ignore[misc]
        return m_need == t_need and (
            m_rate is None or t_rate is None or m_rate == t_rate
        )
    if field == "language_currency":  # only the parts Gemini gives
        return all(t is None or t == m for m, t in zip(mine, theirs, strict=True))  # type: ignore[call-overload]
    if field == "unified_qualification":
        (m_kind, m_g), (t_kind, t_g) = mine, theirs  # type: ignore[misc]
        return m_kind == t_kind and (not m_g or not t_g or m_g == t_g)
    return mine == theirs


def compare_rule_field(field: str, ours: Extracted | None, answer_en: str) -> str:
    """One of CLASSES6. Gemini's side is read by keyword rules only; no keyword hit = unmapped."""
    we = ours is not None
    g = gemini_found(answer_en) or (
        field == "spec_access" and answer_en.lower().startswith("in another document")
    )
    theirs = gemini_form(field, answer_en) if g else None
    if g and theirs is None:
        return "unmapped"
    if not (we or g):
        return "both_not_found"
    if not g:
        return "we_found_gemini_not_stated"
    if ours is None:
        return "gemini_found_we_not_found"
    ok = same_form(field, our_form(field, ours), theirs)
    return "both_found_agree" if ok else "both_found_differ"


def compare(
    field: str, ours: Extracted | None, answer_en: str, quote_ja: str
) -> tuple[str, bool]:
    """(class, gemini_value_unparsed). Gemini's side is read with code only, never a model."""
    if field in RULE_FIELDS:
        return compare_rule_field(field, ours, answer_en), False
    we = ours is not None and ours.status == "present"
    g = gemini_found(answer_en)
    unparsed = False
    if field == "issuer_org":
        runs = _CJK.findall(answer_en)
        g = g and bool(runs)
    elif field == "contracting_officer":
        runs = officer_tokens(answer_en)
        g = g and bool(runs)  # a post with "individual name not stated" is not a name
    elif field == "notice_date":
        gd = iso_dates(quote_ja)
        unparsed = g and not gd
    elif field == "performance_period":
        gd = iso_dates(quote_ja)
        unparsed = g and not gd
    if not (we or g):
        return "both_not_found", False
    if not g:
        return "we_found_gemini_not_stated", False
    if not we:
        return "gemini_found_we_not_found", unparsed
    assert ours is not None
    n = ours.normalized
    if field == "title":
        same = contains_either(ours.value_ja, quote_ja)
    elif field == "issuer_org":
        same = any(contains_either(ours.value_ja, r) for r in runs)
    elif field == "contracting_officer":
        mine = flat(str(n.get("name", "")))
        same = bool(mine) and any(contains_either(mine, r) for r in runs)
    elif field == "notice_date":
        same = bool(gd) and gd[0] == n.get("date")
    else:  # performance_period: (start, end); one Gemini date is the end
        gs, ge = (
            (None, gd[0]) if len(gd) == 1 else (gd[0], gd[-1]) if gd else (None, None)
        )
        same = bool(gd) and (n.get("start"), n.get("end")) == (gs, ge)
    return ("both_found_agree" if same else "both_found_differ"), unparsed


def read_index() -> list[tuple[str, str]]:
    """(12-char doc id prefix, issuer) per row of the batches index."""
    rows = []
    for line in INDEX.read_text().splitlines():
        c = [x.strip() for x in line.strip("|").split("|")]
        if len(c) >= 6 and re.fullmatch(r"[0-9a-f]{12}", c[2]):
            rows.append((c[2], c[3]))
    return rows


def run_one(path: Path) -> tuple[str, dict[str, Extracted], dict[str, int]]:
    """The sidecar's path for one file: (doc_type, answers, field -> page of its first citation)."""
    doc = read_pages(path)
    doc_type = (
        detect_doc_type(first_page_lines(doc.pages[0])) if doc.pages else "notice"
    )
    sents = segment(doc.pages)
    found = rules.extract(doc_type, sents)
    page = {s.id: s.page for s in sents}
    return (
        doc_type,
        found,
        {f: page.get(x.citations[0], 0) for f, x in found.items() if x.citations},
    )


def one_line(s: str) -> str:
    return re.sub(r"[\t\r\n]+", " / ", s)


def main() -> None:
    splits = json.loads((ROOT / "data/eval/splits.json").read_text())
    manifest = [
        json.loads(x)
        for x in (ROOT / "data/manifests/documents.jsonl").read_text().splitlines()
    ]
    gem: dict[tuple[str, str], dict[str, str]] = {}
    for r in csv.DictReader(CSV.open(encoding="utf-8")):
        if r["field"] in FIELDS or r["field"] in RULE_FIELDS:
            gem.setdefault((r["doc_prefix"], r["field"]), r)
    by_field = {f: Counter() for f in (*FIELDS, *RULE_FIELDS)}
    by_issuer: dict[str, Counter] = {}
    by_issuer2: dict[str, Counter] = {}
    unmapped_tsv = ["doc\tfield\tour_value_ja\tgemini_answer_en\tgemini_quote_ja"]
    na: Counter = (
        Counter()
    )  # gaps on a field that does not apply to the detected doc type
    unparsed: Counter = Counter()
    failures: dict[str, list[str]] = {}
    types: Counter = Counter()
    tsv = ["doc\tfield\tour_value_ja\tour_page\tgemini_answer_en\tgemini_quote_ja"]
    done = 0
    for prefix, issuer in read_index():
        rows = [m for m in manifest if m["doc_id"].startswith(prefix)]
        if len(rows) != 1:
            failures["manifest_match_" + str(len(rows))] = failures.get(
                "manifest_match_" + str(len(rows)), []
            ) + [prefix]
            continue
        m = rows[0]
        if splits.get(m["issuer_org"]) == "test":
            failures.setdefault("test_split_refused", []).append(prefix)
            continue
        try:
            doc_type, found, pages = run_one(ROOT / m["path"])
        except Exception as e:  # counted by type, listed by prefix; never the message
            failures.setdefault(type(e).__name__, []).append(prefix)
            continue
        done += 1
        types[doc_type] += 1
        for f in FIELDS:
            g = gem.get((prefix[:8], f), {"answer_en": "", "quote_ja": ""})
            cls, bad = compare(f, found.get(f), g["answer_en"], g["quote_ja"])
            by_field[f][cls] += 1
            by_issuer.setdefault(issuer, Counter())[cls] += 1
            unparsed[f] += bad
            if (
                cls == "gemini_found_we_not_found"
                and doc_type not in BY_ID[f].applies_to
            ):
                na[f] += 1
            if cls == "both_found_differ":
                x = found[f]
                tsv.append("\t".join([prefix[:8], f, one_line(x.value_ja), str(pages.get(f, "")), one_line(g["answer_en"]), one_line(g["quote_ja"])]))  # fmt: skip
        for f in RULE_FIELDS:
            g = gem.get((prefix[:8], f), {"answer_en": "", "quote_ja": ""})
            cls, _ = compare(f, found.get(f), g["answer_en"], g["quote_ja"])
            by_field[f][cls] += 1
            by_issuer2.setdefault(issuer, Counter())[cls] += 1
            if (
                cls == "gemini_found_we_not_found"
                and doc_type not in BY_ID[f].applies_to
            ):
                na[f] += 1
            x = found.get(f)
            if cls == "both_found_differ" and x:
                tsv.append("\t".join([prefix[:8], f, one_line(x.value_ja), str(pages.get(f, "")), one_line(g["answer_en"]), one_line(g["quote_ja"])]))  # fmt: skip
            if cls == "unmapped":
                unmapped_tsv.append("\t".join([prefix[:8], f, one_line(x.value_ja) if x else "", one_line(g["answer_en"]), one_line(g["quote_ja"])]))  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "disagreements.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    (OUT / "unmapped.tsv").write_text("\n".join(unmapped_tsv) + "\n", encoding="utf-8")
    head = (
        "| field | "
        + " | ".join(CLASSES)
        + " | gap on non-applicable doc type | gemini date unparsed |"
    )
    sep = "|---|" + "---|" * (len(CLASSES) + 2)
    md = ["# Gemini vs rules extractor", "", f"Documents processed: {done} of {len(read_index())}. Doc types detected: {dict(types)}.", "",
          "Gemini is a silver reference. Counts and doc id prefixes only; text is in disagreements.tsv.", "", "## Per field", "", head, sep]  # fmt: skip
    md += [
        f"| {f} | "
        + " | ".join(str(by_field[f][c]) for c in CLASSES)
        + f" | {na[f]} | {unparsed[f]} |"
        for f in FIELDS
    ]
    md += [
        "",
        "## Per issuer (all five fields summed)",
        "",
        "| issuer | " + " | ".join(CLASSES) + " |",
        "|---|" + "---|" * len(CLASSES),
    ]
    md += [
        f"| {i} | " + " | ".join(str(c[k]) for k in CLASSES) + " |"
        for i, c in sorted(by_issuer.items())
    ]
    head2 = "| field | " + " | ".join(CLASSES6) + " | gap on non-applicable doc type |"
    md += ["", "## Rule fields (second set)", "",
           "Gemini's English text is mapped to our form by the keyword rules listed at the end of this section. `unmapped` = Gemini gave an answer and no keyword rule maps it (counted whether or not we found a value). Our rules never emit item_category, so it can only be gemini_found_we_not_found, unmapped or both_not_found.",
           "", head2, "|---|" + "---|" * (len(CLASSES6) + 1)]  # fmt: skip
    md += [
        f"| {f} | "
        + " | ".join(str(by_field[f][c]) for c in CLASSES6)
        + f" | {na[f]} |"
        for f in RULE_FIELDS
    ]
    md += ["", "## Per issuer (the rule fields summed)", "", "| issuer | " + " | ".join(CLASSES6) + " |", "|---|" + "---|" * len(CLASSES6)]  # fmt: skip
    md += [f"| {i} | " + " | ".join(str(c[k]) for k in CLASSES6) + " |" for i, c in sorted(by_issuer2.items())]  # fmt: skip
    md += ["", "## Keyword mapping used (patterns run on lower-cased answer_en)", ""]
    md += [
        f"- {k} / {lab}: `{pat}`" for k, rows in KEYWORDS.items() for lab, pat in rows
    ]
    md += ["",
           "- bid_bond, performance_bond: compared as required (ours: required or waived_with_proviso) vs waived; the rate is compared only when both sides give one. Gemini 'required ... waived with conditions' counts as required. Rate = first `n/100` or `n%` in the answer.",
           "- spec_access: our pointer (status see_other_document) is the value see_other_document.",
           "- language_currency: only the parts Gemini gives are compared against ours (ja, JPY).",
           "- unified_qualification: compared as kind (unified vs local) and, when both give grades, the grade set.",
           "- submission_modes: email and electronic both map to electronic; a refusal span and a few side notes (`electronic ... not stated`, `email ... refused`, `electronic data`) are cut out before the keywords are read, and it counts as mail_not_allowed only when no other mail mention is left.",
           ]  # fmt: skip
    md += ["", "## Failures by type", ""] + (
        [f"- {k}: {len(v)} ({', '.join(v)})" for k, v in failures.items()] or ["- none"]
    )
    (OUT / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(
        f"documents processed: {done}; failures: { {k: len(v) for k, v in failures.items()} }"
    )
    print(head.replace("| field", "| field", 1))
    for f in FIELDS:
        print(
            f"| {f} | "
            + " | ".join(str(by_field[f][c]) for c in CLASSES)
            + f" | {na[f]} | {unparsed[f]} |"
        )
    print(head2)
    for f in RULE_FIELDS:
        print(f"| {f} | " + " | ".join(str(by_field[f][c]) for c in CLASSES6) + f" | {na[f]} |")  # fmt: skip
    print(
        f"disagreements: {len(tsv) - 1}; unmapped: {len(unmapped_tsv) - 1}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
