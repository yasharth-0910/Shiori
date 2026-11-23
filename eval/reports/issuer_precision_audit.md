# issuer_org precision audit (D-108 rules vs the Gemini web-chat reference)

Date: 2026-11-24. Dev split only, rules only (no model, no cloud call). Doc id prefixes, organization names and counts only; no document text.

Which 11: the dev bid_instructions and spec documents (30) where the rules give an issuer_org that passes `run_checks` (same list as D-108: 11 of 30). Rule values come from `core/shiori_core/extract/rules.py` through the same path as `eval.run`.

Reference: `data/cache/gemini_ref/gemini_fields.csv` (answer column) and `data/cache/gemini_batches/index.md`. Silver only, not a native reading (see `data/cache/gemini_ref/README.md`).

Rule used to judge: `docs/labeling_guide.md`, the org rule (ministry or 〇〇庁 at national level, otherwise the prefecture or the city; internal bodies are departments).

## Counts

- equal: 2
- differ: 0
- no reference: 9

## Table

| doc | type | rule value | Gemini reference | result | right under the guide |
|---|---|---|---|---|---|
| e81e9338 | bid_instructions | 旭川市 | none | no reference | 旭川市 is a city, fits |
| 2ed05ba9 | bid_instructions | 旭川市 | none | no reference | fits |
| d4000027 | bid_instructions | 和歌山県 | none | no reference | fits (also the existing label value) |
| 08ec571d | bid_instructions | 旭川市 | none | no reference | fits |
| 34ea5d0b | bid_instructions | 旭川市 | 旭川市 (answer); quote column is a department line, 旭川市市民生活部地域活動推進課 | equal (see note) | rule |
| a2728e6b | bid_instructions | 旭川市 | 旭川市 (answer); quote column is a department line, 旭川市総務部総務課総務係 | equal (see note) | rule |
| 081d2756 | bid_instructions | 和歌山県 | none | no reference | fits (this document is the labeling guide's example for 和歌山県) |
| 11ead9a5 | bid_instructions | 旭川市 | none | no reference | fits |
| 6387bfc3 | spec | 旭川市 | none | no reference | fits |
| 9b6a573a | spec | 旭川市 | none | no reference | fits |
| ae487875 | spec | 旭川市 | none | no reference | fits |

Note on the two references: Gemini's answer column is 旭川市 for both, equal to the rule. Its quote column holds a department name (市民生活部地域活動推進課, 総務部総務課総務係). Compared as strings that quote would differ, but it is a unit below the city, so by the guide the rule's 旭川市 is the right value and the quote is a department (the README already says Gemini quotes neighbouring text for issuer_org).

## Differences

None. Count of rule values that look wrong under the guide: 0 of 11. No rule was changed.

## What this does and does not show

- Only 2 of 11 have a reference at all (both 旭川市). The other 9 rest on the guide rule alone; their check is that the value is a prefecture or city name and passes `run_checks`, not an independent second reading.
- The 9 unreferenced ones (7 旭川市, 2 和歌山県 counting d4000027 and 081d2756) are the same two names the references and labels already use. A native reader still has to confirm one document each, as D-108 says.
- Known ceiling, unchanged: the name ends at the first 市 or 県 (四日市市 would be cut to 四日市). No such document in these 11.
