# ruff: noqa: E501
"""On-demand English for one cited sentence (D-85). Machine translation, one sentence per
request, with the local model that is already running (llm.Client, temperature 0). It never
feeds field extraction or citations. After each translation a deterministic check compares
the numbers: every number in the Japanese must appear in the English, or `numbers_match` is
False. The translation is returned either way, never hidden or fixed.

No text is logged and nothing is written to disk here.
"""

import json
import re
from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel

from shiori_core.extract.llm import Client
from shiori_core.glossary import GLOSSARY, REGIONS, terms_in
from shiori_core.normalize import normalize
from shiori_core.value_normalize import find_dates

MAX_OUT = 512  # tokens
SCHEMA = {
    "type": "object",
    "properties": {"en": {"type": "string"}},
    "required": ["en"],
    "additionalProperties": False,
}
SYSTEM = (
    "You translate sentences from Japanese public tender documents into English. "
    'Answer in JSON: {"en": "<the translation>"}.'
)
RULES = (
    "Translate faithfully into English. Keep numbers, dates and names exactly as written. "
    "Do not add or drop information. Do not explain. "
    "Leave a person's name in its original script, with no romanization "
    "(for example: Director of the Example Center, 山田 太郎)."
)
REGION_RULE = "Name every region exactly as listed below: do not add a region and do not drop one."
DATE_RULE = (
    'Write each date listed below as month, day, year, for example "July 16, 2024".'
)


class Translation(BaseModel):
    en: str
    numbers_match: bool
    protected_lost: bool = (
        False  # a masked name or term did not come back exactly once (D-87)
    )


def one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --- abbreviations defined in the document (以下「X」という) ----------------------------------

DEFINITION = re.compile(r"[（(]以下[、,]?[「『]([^」』]{1,30})[」』]という[。.]?[）)]")
BREAK = re.compile(r"[\s、。,，「」『』（）():：;；]")  # where the defined term starts


def _suffix_holding(abbr: str, run: str) -> str | None:
    """The shortest tail of `run` that holds the letters of `abbr` in order (予決令 in
    予算決算及び会計令), or None. A Latin or mixed abbreviation (CDN) is never matched: the
    long form is not recoverable from the text, and nothing is guessed."""
    if any(ord(c) < 0x3000 for c in abbr):
        return None
    for start in range(len(run) - 1, -1, -1):
        it = iter(run[start:])
        if all(c in it for c in abbr):
            return run[start:]
    return None


def find_abbreviations(texts: Iterable[str]) -> dict[str, str]:
    """{abbreviation: the term it stands for} from definitions of the form
    `予算決算及び会計令（以下「予決令」という。）` in the document's own text (normalized
    sentences). Only definitions whose long form can be read off the text; an abbreviation
    the document does not define is never added."""
    out: dict[str, str] = {}
    for text in texts:
        for m in DEFINITION.finditer(text):
            abbr = m.group(1)
            run = BREAK.split(text[: m.start()])[-1]
            long = _suffix_holding(abbr, run)
            if long and long != abbr and abbr not in out:
                out[abbr] = long
    return out


# --- dates ---------------------------------------------------------------------------------

ERA_WORDS = re.compile("令和|平成|昭和|大正")


def era_dates(norm_text: str) -> list[tuple[str, str]]:
    """[(the date as written, "July 16, 2024")] for each complete era date in the sentence,
    converted by the project's date code. An incomplete date (year and month only) is skipped."""
    return [
        (f.text, f"{f.value:%B} {f.value.day}, {f.value.year}")
        for f in find_dates(norm_text)
        if f.value and ERA_WORDS.match(f.text)
    ]


# --- protected spans (D-87) --------------------------------------------------------------
# A person's name (from the structured contracting_officer value) and the quoted term of a
# 以下「X」という clause stay in Japanese. They are replaced by a meaningless placeholder before
# the model sees the sentence and put back after. A placeholder that does not come back exactly
# once means `protected_lost`; the output is returned as the model wrote it, never repaired.

PLACEHOLDER = "⟦P{}⟧"
PLACEHOLDERS = re.compile(r"⟦P(\d+)⟧")
PLACEHOLDER_RULE = "Copy each placeholder such as ⟦P1⟧ into the English exactly as it is, once, where the text it stands for belongs. Never translate it, change it or drop it."


def _name_pattern(name: str) -> re.Pattern[str]:
    """The name as it may be written in the sentence: its parts in order, with or without
    (full- or half-width) spaces between them."""
    return re.compile(r"[\s\u3000]*".join(re.escape(part) for part in name.split()))


def protect(text: str, names: Iterable[str] = ()) -> tuple[str, dict[str, str]]:
    """(the text with each protected span replaced by ⟦Pn⟧, {placeholder: original}). Spans: the
    quoted term of every 以下「X」という clause, and each given name where it occurs. Names are
    only the ones passed in; nothing is guessed from the text."""
    spans = [m.span(1) for m in DEFINITION.finditer(text)]
    for name in names:
        if name.strip():
            spans += [m.span() for m in _name_pattern(name.strip()).finditer(text)]
    chosen: list[tuple[int, int]] = []
    for a, b in sorted(set(spans), key=lambda x: (x[0], -x[1])):
        if not chosen or a >= chosen[-1][1]:  # an overlapping span is dropped
            chosen.append((a, b))
    out, mapping, last = [], {}, 0
    for n, (a, b) in enumerate(chosen, 1):
        out += [text[last:a], PLACEHOLDER.format(n)]
        mapping[PLACEHOLDER.format(n)] = text[a:b]
        last = b
    return "".join(out) + text[last:], mapping


def restore(en: str, mapping: dict[str, str]) -> tuple[str, bool]:
    """(the English with the originals put back, protected_lost)."""
    seen = PLACEHOLDERS.findall(en)
    lost = any(seen.count(k[2:-1].lstrip("P")) != 1 for k in mapping) or any(f"⟦P{i}⟧" not in mapping for i in seen)  # fmt: skip
    return PLACEHOLDERS.sub(lambda m: mapping.get(m.group(0), m.group(0)), en), lost


def prompt(text: str, abbreviations: dict[str, str] | None = None) -> str:
    norm = normalize(text)[0]
    terms = terms_in(norm)
    fixed = [f"{ja} = {en}" for ja, en in terms if ja not in REGIONS]
    regions = [f"{ja} = {en}" for ja, en in terms if ja in REGIONS]
    abbrs = []
    for abbr, long in (abbreviations or {}).items():
        if abbr in norm:
            en = GLOSSARY.get(long)
            abbrs.append(f"{abbr} = short for {long}" + (f", write it as: {en}" if en else ", translate it as that name is translated"))  # fmt: skip
    dates = [f"{ja} = {en}" for ja, en in era_dates(norm)]
    parts = [RULES]
    if PLACEHOLDERS.search(text):
        parts.append(PLACEHOLDER_RULE)
    for head, rows in (
        ("Use these renderings for fixed terms:", fixed),
        ("Abbreviations this document defines:", abbrs),
        (REGION_RULE, regions),
        (DATE_RULE, dates),
    ):
        if rows:
            parts.append(head + "".join(f"\n- {r}" for r in rows))
    return "\n\n".join(parts) + f"\n\nJapanese sentence:\n{one_line(text)}"


def translate_sentence(
    client: Client, sentence_text: str, abbreviations: dict[str, str] | None = None
) -> str:
    """The English for one sentence, as one line. Raises on a failed call or an answer that
    is not the expected JSON (the caller decides what to show)."""
    raw = client.complete(SYSTEM, prompt(sentence_text, abbreviations), SCHEMA, MAX_OUT)
    return one_line(str(json.loads(raw)["en"]))


# --- the numbers check ---------------------------------------------------------------------

ERAS = {
    "令和": 2018,
    "平成": 1988,
    "昭和": 1925,
    "大正": 1911,
}  # year N of the era = base + N
MONTHS = [date(2000, m, 1).strftime("%B").lower() for m in range(1, 13)]
SCALE = {"万": 10**4, "億": 10**8, "千": 10**3}  # 690千円 may be written 690,000
NUMBER = re.compile(r"(令和|平成|昭和|大正)?(\d+(?:\.\d+)?)(年|月|[万億千])?")
# A leading section number such as (4) or 2. is a marker, not data; the model may drop it.
MARKER = re.compile(r"^\s*(?:第\d+[条章]?|[(（]\d+[)）]|\d+[.．、])\s*")
EN_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _plain(x: float) -> str:
    return str(int(x)) if x == int(x) else str(x)


# 令和4・5・6年度 (written with ･ or ・): the years 4, 5 and 6, each as written or as the Gregorian year.
ERA_LIST = re.compile(r"(令和|平成|昭和|大正)(\d+(?:[・･]\d+)+)年")


def needed(ja: str) -> list[set[str]]:
    """For each number in the Japanese, the set of English spellings that would satisfy it."""
    text = MARKER.sub("", normalize(ja)[0])
    out: list[set[str]] = []
    for m in ERA_LIST.finditer(text):
        out += [
            {n, str(ERAS[m.group(1)] + int(n))} for n in re.split(r"[・･]", m.group(2))
        ]
    text = ERA_LIST.sub(" ", text)
    for m in NUMBER.finditer(text):
        era, n, unit = m.groups()
        ok = {n.rstrip("0").rstrip(".") if "." in n else str(int(n))}
        if era and unit == "年":
            ok.add(str(ERAS[era] + int(float(n))))  # 令和6年: "6" or "2024"
        if unit == "月" and 1 <= float(n) <= 12:
            ok.add(f"month:{MONTHS[int(float(n)) - 1]}")  # 10月: "10" or "October"
        if unit in SCALE:
            ok.add(_plain(float(n) * SCALE[unit]))  # 100万: "100" or "1000000"
        out.append(ok)
    return out


def english_numbers(en: str) -> set[str]:
    nums = {m.replace(",", "").lstrip("0") or "0" for m in EN_NUMBER.findall(en)}
    low = en.lower()
    return nums | {f"month:{name}" for name in MONTHS if name in low}


def numbers_match(ja: str, en: str) -> bool:
    have = english_numbers(en)
    return all(ok & have for ok in needed(ja))


def translate(
    client: Client,
    sentence_text: str,
    abbreviations: dict[str, str] | None = None,
    names: Iterable[str] = (),
) -> Translation:
    """`names`: the person names the structured fields give for this sentence (D-87)."""
    masked, mapping = protect(sentence_text, names)
    raw = translate_sentence(client, masked, abbreviations)
    en, lost = restore(raw, mapping)
    return Translation(
        en=en, numbers_match=numbers_match(sentence_text, en), protected_lost=lost
    )
