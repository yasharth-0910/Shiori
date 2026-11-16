# Segmentation report

Generated 2026-10-02 by `uv run python -m eval.segmentation_report`, extractor version 0.3.0. Phase 2 part B: header/footer exclusion (D-30), normalization, sentences, section paths, value converters. Part C: scanned and outlined pages are read by OCR (D-36) and have sentences with source `ocr`; HTML notices are included (D-37).

PDFs: 322. Processed: 322. Failed: 0. Time: 111 s for 1864 pages, ingest to sentences.

## Sentences

48701 sentences. Per text or mixed page: mean 26.3, median 24, max 233; 3 text pages have none. Length in characters: median 19, 99th percentile 152, max 650.

In a table cell: 14687 (30%). Running across a page break: 347. Lines left out as page numbers: 977; as repeated headers or footers (D-30): 43.

## Section paths

Sentences with a non-empty section path: 42743 (88%). By doc_type:

| doc_type | sentences | with path |
|---|---|---|
| spec | 17596 | 94% |
| bid_instructions | 10405 | 94% |
| other | 5760 | 69% |
| draft_contract | 5035 | 96% |
| notice | 4351 | 94% |
| qa | 1838 | 40% |
| evaluation_criteria | 1346 | 77% |
| forms | 894 | 53% |
| rfi_material | 840 | 99% |
| result | 636 | 64% |

Documents where section parsing found nothing: 56. By doc_type: other 19, qa 12, forms 10, result 5, evaluation_criteria 4, spec 2, notice 2, draft_contract 1, bid_instructions 1. The ones whose doc_type usually has numbering:

| doc_id | source | doc_type | pages | sentences |
|---|---|---|---|---|
| `d360751d6e65` | kawaguchi | spec | 1 | 37 |
| `c74468a39091` | hachioji | notice | 1 | 19 |
| `57b01b6de42c` | okayama_pref | spec | 1 | 173 |
| `78404300765b` | hokkaido | draft_contract | 1 | 31 |
| `43e3356bb579` | nara_city | notice | 1 | 4 |
| `6df340ac7a35` | hachioji | bid_instructions | 1 | 18 |

## OCR and English sentences

Sentences from OCR pages (source `ocr`): 636 in 8 documents, 416 with a section path. Sentences marked English (`language` en): 719 in 51 documents (110 in PDFs, 609 in HTML), 701 of them with a one-level path (the Summary heading's). Documents with an English Summary heading: 43.

## HTML notices

HTML documents: 181, all read (3.4 s). 14780 sentences, 9907 (67%) with a section path. Anchors are offsets into the extracted text (D-37). By source:

| source | documents | sentences | with path | no sentences |
|---|---|---|---|---|
| asahikawa | 6 | 341 | 29% | 0 |
| digital | 8 | 447 | 87% | 0 |
| funabashi | 4 | 353 | 39% | 0 |
| hachioji | 8 | 636 | 19% | 0 |
| hokkaido | 8 | 409 | 0% | 0 |
| koriyama | 8 | 324 | 13% | 0 |
| nara_city | 8 | 319 | 52% | 0 |
| niigata_pref | 3 | 339 | 96% | 0 |
| okayama_pref | 8 | 44 | 0% | 0 |
| p-portal | 112 | 11272 | 76% | 0 |
| wakayama_pref | 8 | 296 | 39% | 0 |

## Value converters

Run on `text_norm` of every Japanese sentence, PDF and HTML (English ones are skipped). Found = the pattern matched; converted = a value came out. Everything else returned None with a reason.

| kind | found | converted | share |
|---|---|---|---|
| dates | 3170 | 2644 | 83% |
| fiscal years | 844 | 842 | 100% |
| times | 1270 | 1267 | 100% |
| amounts | 383 | 338 | 88% |

Dates converted **with a weekday warning** (DATE-5, the weekday written disagrees with the calendar; the date is returned with both readings): 9. `令和8年3月3日(水)` (actual 火, written 水; 4a654d8861b5 p1_s11); `令和9年3月30日(月)` (actual 火, written 月; 44473a6e7b5e p1_s14); `令和8年(2026年)6月9日(月)` (actual 火, written 月; caba0430715a p2_s7); `令和8年(2026年)9月29日(木)` (actual 火, written 木; 241c50823d77 p1_s22); restricted: 63a52ed6024c p10_s26.

Deadline flags found: arrival_required 140, postmark_ok 3. Tax wording found: tax_excluded 220, tax_included 66.

Top 20 reasons a match did not convert. Examples are the matched string from `open` documents, else the location in a restricted one:

| kind | reason | count | examples |
|---|---|---|---|
| dates | no year | 214 | `5月30日` (fd1a4b7d9a7a p7_s3); `4月1日` (fd1a4b7d9a7a p7_s3); `5月27日` (6af28f8826d9 p11_s2) |
| dates | year and month only | 200 | `令和8年2月` (10be3ae3df34 p1_s4); `令和8年2月` (c8448fb9a328 p1_s5); `令和3年10月` (2a4dacf5624b p9_s17) |
| dates | blank date (form field) | 104 | `令和  年  月  日` (2baf60234d67 p4_s2); `令和 年月日` (10f4a05d46b7 p1_s19); `令和  年  月  日` (75a0c52799f9 p1_s12) |
| amounts | blank amount (form field) | 29 | `金     円` (75a0c52799f9 p1_s6); `金     円` (abb788301429 p1_s6); `金     円` (07926eba62b4 p1_s6) |
| amounts | placeholder | 10 | `●円` (756d17c84006 p33_s14); `○円` (756d17c84006 p33_s38); `●円` (56d0c0a1cc3f p1_s14) |
| dates | year without era | 8 | restricted: ab5e74f19ac1 p4_s27; `8年3月31日` (6f9dfa9369ed h_s24); `7年2月7日` (6f9dfa9369ed h_s41) |
| amounts | bad separators | 3 | restricted: 7c76af66d35d p3_s55 |
| amounts | no number before 万/億/兆 | 3 | `万円` (706d5a67cebd p5_s10); restricted: ac58cfb92021 p19_s30 |
| fiscal years | blank fiscal year (form field) | 1 | `令和○年度` (79004c98b435 p3_s8) |
| fiscal years | implausible year | 1 | restricted: ac58cfb92021 p25_s1 |
| times | hour out of range | 1 | `午後14時` (28e4e61233d5 h_s53) |
| times | ambiguous 午後0時 | 1 | `午後0時00分` (3fc322cb5b33 h_s69) |
| times | ambiguous 午後12時 | 1 | `午後12時00分` (714055a2a2b8 h_s39) |

## Two-column pages

A page is listed when at least 5 rows have a body text line (not in a table, 6+ characters) entirely left of the page middle and another entirely right of it. `jumps` counts how often reading order switches between the halves: about two per row means the columns are interleaved line by line.

| doc_id | source | page | side-by-side rows | jumps |
|---|---|---|---|---|
| `a92bb2644787` | niigata_pref | 2 | 18 | 2 |
| `6b36d69abc0d` | okayama_pref | 8 | 9 | 20 |
| `34ef78f9cc26` | okayama_pref | 10 | 9 | 20 |
| `6af28f8826d9` | digital | 49 | 8 | 3 |
| `34ef78f9cc26` | okayama_pref | 8 | 6 | 17 |
| `4965207bb115` | wakayama_pref | 11 | 5 | 11 |
| `6b36d69abc0d` | okayama_pref | 6 | 5 | 15 |

## Review sample

10 documents (`random.Random(20261002)`): 3 notice, 3 spec, the rest other doc types, a different source each where possible, open documents first. Each has `sentences.txt` (`<id> | <section path> | <text_orig>`) and one PNG per page under `debug/`.

| doc_id | source | doc_type | license | pages | sentences | files |
|---|---|---|---|---|---|---|
| `2f2f5bd332965253eed43d739e56e7859b149afa0d157ea3c89dfdd7d0d8b419` | wakayama_pref | notice | open | 4 | 100 | `data/processed/2f2f5bd332965253eed43d739e56e7859b149afa0d157ea3c89dfdd7d0d8b419/sentences.txt`, `debug/` |
| `f84a8e9838c8f5291292a6d654897a93d6fb0d5a5bf1be530a0b765cc7ab8b12` | hokkaido | notice | open | 4 | 82 | `data/processed/f84a8e9838c8f5291292a6d654897a93d6fb0d5a5bf1be530a0b765cc7ab8b12/sentences.txt`, `debug/` |
| `47fcd6f239bc4fe0397d81afb90882fdaabbbce5c851721bcc78d4f19c127c3a` | jma | notice | open | 12 | 104 | `data/processed/47fcd6f239bc4fe0397d81afb90882fdaabbbce5c851721bcc78d4f19c127c3a/sentences.txt`, `debug/` |
| `6af28f8826d91f65dee9cc3789f08b302fee7b41f6fb3e6d1020023f151b7586` | digital | spec | open | 97 | 2043 | `data/processed/6af28f8826d91f65dee9cc3789f08b302fee7b41f6fb3e6d1020023f151b7586/sentences.txt`, `debug/` |
| `23ea23bdf058bcfff7f08c0d31668ca84d4c1bf40e0f798f99bf03c7b612638f` | okayama_pref | spec | open | 9 | 448 | `data/processed/23ea23bdf058bcfff7f08c0d31668ca84d4c1bf40e0f798f99bf03c7b612638f/sentences.txt`, `debug/` |
| `aeedf544969c41e5baa77b679f6370ffde8f982d14cca012b228c85e187f7a49` | asahikawa | spec | restricted | 5 | 114 | `data/processed/aeedf544969c41e5baa77b679f6370ffde8f982d14cca012b228c85e187f7a49/sentences.txt`, `debug/` |
| `bd6a6cf5d25926e2359c9d8f34eba4e3fb4a7490c0c5cea32de58868e9eee431` | koriyama | forms | unknown | 2 | 32 | `data/processed/bd6a6cf5d25926e2359c9d8f34eba4e3fb4a7490c0c5cea32de58868e9eee431/sentences.txt`, `debug/` |
| `16e2b89c613c9852d055047b8365db779b7e3d2cf822aff51b2ebde66ee1aca6` | funabashi | evaluation_criteria | restricted | 2 | 86 | `data/processed/16e2b89c613c9852d055047b8365db779b7e3d2cf822aff51b2ebde66ee1aca6/sentences.txt`, `debug/` |
| `76d222a8231fbaf64b5f7cbe96ad6f43c0c9ef7b7192bbc296fbb673b75bec86` | niigata_pref | other | restricted | 1 | 21 | `data/processed/76d222a8231fbaf64b5f7cbe96ad6f43c0c9ef7b7192bbc296fbb673b75bec86/sentences.txt`, `debug/` |
| `7677f1e5d5e006ecc1208a0ee8737adb27048429409ca95436f90b8637426432` | hachioji | bid_instructions | restricted | 2 | 56 | `data/processed/7677f1e5d5e006ecc1208a0ee8737adb27048429409ca95436f90b8637426432/sentences.txt`, `debug/` |

Restricted and unknown documents (D-22) stay on this machine: show a reviewer their sentences.txt only on screen or not at all.
