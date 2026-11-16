"""Build text_norm and its offset map back to text_orig (TXT-2), one character at a
time, so every normalized character knows which original glyph it came from.

    text_norm, norm_to_orig = normalize(text_orig, marker_end)

Order, per character:

1. Circled numbers and circled katakana (`①`, `㋐`) are kept as they are. NFKC would
   turn `①` into `1`, losing that it is a list marker (TXT-3), and `様式３①～③`
   ("forms 3-1 to 3-3", doc ab5e74f1..., Yokosuka) would become `様式31~3`.
   Private Use Area characters are kept as they are too (TXT-11, TXT-12).
2. Everything else goes through NFKC: full-width ASCII to half-width, half-width
   katakana to full-width, `⑴` to `(1)` (TXT-13), Kangxi radicals to kanji (TXT-15).
   NFKC can turn one character into several (`㈱` -> `(株)`); all of them point back to
   the one original. A combining mark it produces (half-width `ﾞ`) is composed onto
   the previous character, which keeps that character's index.
3. Lookalikes are mapped to one form (TXT-4, TXT-14, TXT-16): wave dashes, dashes,
   kanji variants, ornate parentheses, Cyrillic O, mis-mapped vertical glyphs, and
   `ー` between two digits.
4. Where two lines were joined (the sentence ran over a line break) and both sides
   are Latin letters or digits, one space is put back: `Japan` + `TEL` is `Japan TEL`,
   not `JapanTEL` (doc 2f2f5bd3..., Wakayama p4). It maps to the first character of the
   second line, i.e. back to the line break. Such a space is never removed by step 5.
5. Spaces are removed last, and only these (TXT-9, TXT-10): a single space between two
   digits, between a digit and a date or money unit (either order), or between an era
   name and a digit; and the single spaces inside a letter-spaced run of 3+ CJK
   characters. Spaces right after a list marker (text[:marker_end], found by
   segment.py before any of this) are never removed, so `５ １次選考` (section 5,
   "first-round selection", doc ab5e74f1...) stays `5 1次選考`, not `51次選考`.

The map never goes backwards and every entry is a valid index into text_orig.
"""

import re
import unicodedata
from collections.abc import Sequence

# Kept out of NFKC (step 1): ①-⑳, ㉑-㉟, ㊱-㊿, ⓪, ㋐-㋾ (circled katakana).
_KEEP = re.compile(r"[①-⑳㉑-㉟㊱-㊿⓪㋐-㋾]")


def _is_pua(ch: str) -> bool:
    return 0xE000 <= ord(ch) <= 0xF8FF


# Step 3, applied to NFKC output. TXT-14 entries were read off the rendered page of
# doc 6b36d69a... (Okayama, p9); the other code points seen there (䣓 䣔 䣕 ᵰ) are
# not read yet and stay as they are.
LOOKALIKES = {
    "〜": "~",  # U+301C wave dash; ～ (U+FF5E) is already ~ after NFKC (TXT-4)
    "‐": "-",  # U+2010 hyphen
    "‑": "-",  # U+2011 non-breaking hyphen
    "–": "-",  # U+2013 en dash
    "—": "-",  # U+2014 em dash
    "―": "-",  # U+2015 horizontal bar (様式３―Ａ, doc ab5e74f1...)
    "−": "-",  # U+2212 minus sign
    "髙": "高",  # TXT-4 kanji variants, for matching only
    "﨑": "崎",
    "邊": "辺",
    "﴾": "(",  # U+FD3E, doc 6af28f88... (TXT-16)
    "﴿": ")",
    "О": "O",  # U+041E Cyrillic, doc 52b0c72c... (TXT-16)
    "ᵯ": "「",  # TXT-14
    "䣖": "」",
    "ᶌ": "ー",
    "䥹": "(",
    "䥺": ")",
    "䣎": "。",
}

_UNITS = set("年月日時分円万億")
_ERAS = {"令和", "平成", "昭和", "大正", "明治"}
_CJK = r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff々〆]"  # kana and kanji
# TXT-10: 3+ single CJK characters, each separated by exactly one space, with
# nothing but a space or the text edge on either side.
_LETTER_SPACED = re.compile(rf"(?<!\S){_CJK}(?: {_CJK}){{2,}}(?!\S)")


def _chars(text: str) -> tuple[list[str], list[int]]:
    """Steps 1 to 3: one output character per list entry, with its source index."""
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(text):
        if _KEEP.match(ch) or _is_pua(ch):
            pieces = ch
        else:
            pieces = "".join(
                LOOKALIKES.get(c, c) for c in unicodedata.normalize("NFKC", ch)
            )
        for c in pieces:
            if unicodedata.combining(c) and out:
                composed = unicodedata.normalize("NFC", out[-1] + c)
                if len(composed) == 1:
                    out[-1] = composed
                    continue
            out.append(c)
            idx.append(i)
    for k in range(1, len(out) - 1):
        if out[k] == "ー" and out[k - 1].isdigit() and out[k + 1].isdigit():
            out[k] = "-"  # a range or dash between numbers, not a long vowel (TXT-4)
    return out, idx


def _digit(c: str) -> bool:
    return c.isascii() and c.isdigit()


def _alnum(c: str) -> bool:
    return c.isascii() and c.isalnum()


def _put_back_spaces(
    out: list[str], idx: list[int], joins: Sequence[int]
) -> tuple[list[str], list[int], set[int]]:
    """Step 4: a space at each join (index in the original text of the first character
    of the second line) where both neighbours are ASCII letters or digits. Returns the
    new lists and the positions of the spaces added."""
    at = set(joins)
    new_out: list[str] = []
    new_idx: list[int] = []
    added: set[int] = set()
    for k, c in enumerate(out):
        if (
            k
            and idx[k] in at
            and idx[k - 1] < idx[k]
            and _alnum(out[k - 1])
            and _alnum(c)
        ):
            added.add(len(new_out))
            new_out.append(" ")
            new_idx.append(idx[k])
        new_out.append(c)
        new_idx.append(idx[k])
    return new_out, new_idx, added


def _drop_spaces(
    out: list[str], idx: list[int], protected: range, added: set[int]
) -> set[int]:
    """Step 5: positions in out whose space is removed."""
    drop: set[int] = set()
    for k in range(1, len(out) - 1):
        if out[k] != " " or idx[k] in protected or k in added:
            continue
        prev, nxt = out[k - 1], out[k + 1]
        if prev == " " or nxt == " ":
            continue  # only single spaces; wider gaps are layout (TXT-1)
        era = "".join(out[max(0, k - 2) : k]) in _ERAS
        if (
            (_digit(prev) and (_digit(nxt) or nxt in _UNITS))
            or (prev in _UNITS and _digit(nxt))
            or (era and (_digit(nxt) or nxt == "元"))
        ):
            drop.add(k)
    joined = "".join(out)
    for m in _LETTER_SPACED.finditer(joined):
        drop.update(
            k
            for k in range(m.start(), m.end())
            if out[k] == " " and idx[k] not in protected and k not in added
        )
    return drop


def normalize(
    text: str, marker_end: int = 0, joins: Sequence[int] = ()
) -> tuple[str, list[int]]:
    """text_norm and norm_to_orig for `text`. text[:marker_end] is a list marker;
    the spaces right after it are kept. `joins`: indices in `text` where a line break
    was joined (step 4)."""
    out, idx = _chars(text)
    out, idx, added = _put_back_spaces(out, idx, joins)
    after = marker_end
    while after < len(text) and text[after].isspace():
        after += 1
    protected = range(marker_end, after) if marker_end else range(0)
    drop = _drop_spaces(out, idx, protected, added)
    keep = [k for k in range(len(out)) if k not in drop]
    return "".join(out[k] for k in keep), [idx[k] for k in keep]
