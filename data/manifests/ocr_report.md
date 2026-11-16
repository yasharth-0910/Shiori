# OCR report

Generated 2026-10-02 by `uv run python -m eval.ocr_report`, extractor version 0.3.0. Engine: NDLOCR-Lite (D-36), CPU, pages rendered at 200 dpi. Only aggregate numbers and doc_id/page references are in this file (D-22).

## Rendered-scan test set (D-23a)

200 text pages drawn round-robin over (source, doc_type) strata (`random.Random(20261002)`), from 200 documents in 16 sources and 10 doc_types, each with at least 80 text-layer characters. Ground truth is the text layer. **Rendered pages are cleaner than real scans, so the clean row is an upper bound**; degraded = random skew of 1 to 2 degrees, Gaussian blur (sigma 0.8 px), Gaussian noise (sigma 6). How scoring works is in the docstring of `eval/ocr_report.py`: by geometry, so reading order is not counted as error.

### Summary

| variant | text-layer chars | CER | digit errors | unit errors | text-layer lines dropped | OCR-only lines | OCR s/page (timed now) |
|---|---|---|---|---|---|---|---|
| clean | 159299 | 6.90% | 1256 of 8204 (15.31%) | 121 of 1915 (6.32%) | 633 of 8616 | 19 of 8114 | 2.3 |
| degraded | 159355 | 6.76% | 1114 of 8204 (13.58%) | 94 of 1915 (4.91%) | 553 of 8616 | 20 of 8207 | 2.3 |

Digit errors: text-layer digits that were changed or lost, plus digits OCR added. Unit errors: the same for 年月日時分円万億.

In short:

- clean: CER 6.90% over all pages, 3.20% on text the detector found; 14 of 366 dates, times, amounts and fiscal years lost or changed, 0 values added that the text layer does not have.
- degraded: CER 6.76% over all pages, 3.84% on text the detector found; 15 of 364 dates, times, amounts and fiscal years lost or changed, 4 values added that the text layer does not have.
- The degraded run is not worse than the clean one: blur and noise at this strength do not hurt the recogniser, and which text gets detected moves in both directions from page to page (some tables are found only after the image is perturbed). Treat differences of a point or two between the runs as noise.
- The text-layer value counts differ by a few between the runs because the comparison cuts both sides into the same lines, and the lines differ.

### Detection versus reading

Most of the CER is text OCR never detected, not text it misread. The first table counts only text-layer characters that sit inside a detected OCR line (what the recogniser had to read); the second splits the pages by what is on them. Table share: the part of a page's text lines that sit in ruled table cells (D-31). A4 = 595 x 842 pt; NDLOCR's detector resizes every image to 1024 x 1024 pixels, so on a page larger than A4 small text becomes too small to find (not tiled yet, open question).

| variant | chars in detected lines | CER there | digits there | digit errors there | share of all errors from undetected text |
|---|---|---|---|---|---|
| clean | 153202 | 3.20% | 7877 | 929 (11.79%) | 55% |
| degraded | 154515 | 3.84% | 7920 | 830 (10.48%) | 45% |

| page class | pages | chars clean | CER clean | CER in detected lines clean | median page CER clean | chars degraded | CER degraded | CER in detected lines degraded | median page CER degraded |
|---|---|---|---|---|---|---|---|---|---|
| A4 or smaller, few tables (under 20% of lines) | 121 | 98492 | 4.40% | 2.87% | 4.34% | 98537 | 4.66% | 2.79% | 4.26% |
| A4 or smaller, with tables | 69 | 46280 | 6.91% | 3.93% | 5.11% | 46291 | 7.49% | 4.34% | 4.77% |
| larger than A4 (1.3 x A4 or more) | 10 | 14527 | 23.89% | 3.15% | 2.67% | 14527 | 18.66% | 9.81% | 12.68% |

clean: of 200 pages with 50+ characters, 4 have CER under 1%, 25 under 2%, 116 under 5%, 11 are 20% or worse.

degraded: of 200 pages with 50+ characters, 6 have CER under 1%, 32 under 2%, 119 under 5%, 13 are 20% or worse.


### Dates, times, amounts and fiscal years

Converted values found by the value converters on each side and compared as values. **missing**: the text layer has it, OCR text has no equal value (lost or changed). **extra**: OCR text has a value the text layer does not (a changed digit gives one missing and one extra; extra without missing is OCR reading something the text layer lacks). **Extra values are the costly failure**: a plausible wrong date.

| kind | variant | text layer | exact | missing | extra |
|---|---|---|---|---|---|
| date | clean | 189 | 183 | 6 (3.17%) | 0 |
| date | degraded | 189 | 184 | 5 (2.65%) | 1 |
| time | clean | 83 | 81 | 2 (2.41%) | 0 |
| time | degraded | 83 | 80 | 3 (3.61%) | 0 |
| amount | clean | 21 | 18 | 3 (14.29%) | 0 |
| amount | degraded | 20 | 17 | 3 (15.00%) | 1 |
| fiscal year | clean | 73 | 70 | 3 (4.11%) | 0 |
| fiscal year | degraded | 72 | 68 | 4 (5.56%) | 2 |

Value errors by location (values shown for `open` documents only):

| variant | doc_id | page | kind | what | values |
|---|---|---|---|---|---|
| clean | `1b0397f3428e` | 6 | fiscal year | lost | (restricted) |
| clean | `1b0397f3428e` | 6 | fiscal year | lost | (restricted) |
| clean | `b65ec3def67b` | 1 | date | lost | (restricted) |
| clean | `b65ec3def67b` | 1 | time | lost | (restricted) |
| clean | `27229c8f9d29` | 1 | amount | lost | (restricted) |
| clean | `27229c8f9d29` | 1 | date | lost | (restricted) |
| clean | `27229c8f9d29` | 1 | time | lost | (restricted) |
| clean | `fd2cdc4954a0` | 5 | date | lost | (restricted) |
| clean | `070b894ee590` | 5 | date | lost | (restricted) |
| clean | `070b894ee590` | 5 | amount | lost | (restricted) |
| clean | `073ad71ae492` | 1 | amount | lost | `10` -> `` |
| clean | `72cf89b9a2b7` | 1 | fiscal year | lost | `2026-04-01..2027-03-31` -> `` |
| clean | `8666347d881d` | 1 | date | lost | (restricted) |
| clean | `a1dd4cb6ff9b` | 1 | date | lost | (restricted) |
| degraded | `8a6bb534ce38` | 1 | date | changed | `2026-07-01` -> `2024-07-01` |
| degraded | `0caedcbd7355` | 1 | fiscal year | changed | `2026-04-01..2027-03-31` -> `1933-04-01..1934-03-31` |
| degraded | `79004c98b435` | 1 | fiscal year | added | `` -> `2026-04-01..2027-03-31` |
| degraded | `a92bb2644787` | 2 | amount | added | (restricted) |
| degraded | `1b0397f3428e` | 6 | fiscal year | lost | (restricted) |
| degraded | `1b0397f3428e` | 6 | fiscal year | lost | (restricted) |
| degraded | `b65ec3def67b` | 1 | date | lost | (restricted) |
| degraded | `b65ec3def67b` | 1 | time | lost | (restricted) |
| degraded | `b65ec3def67b` | 1 | time | lost | (restricted) |
| degraded | `27229c8f9d29` | 1 | amount | lost | (restricted) |
| degraded | `27229c8f9d29` | 1 | date | lost | (restricted) |
| degraded | `27229c8f9d29` | 1 | time | lost | (restricted) |
| degraded | `fd2cdc4954a0` | 5 | date | lost | (restricted) |
| degraded | `070b894ee590` | 5 | date | lost | (restricted) |
| degraded | `070b894ee590` | 5 | amount | lost | (restricted) |
| degraded | `073ad71ae492` | 1 | amount | lost | `10` -> `` |
| degraded | `72cf89b9a2b7` | 1 | fiscal year | lost | `2026-04-01..2027-03-31` -> `` |

### CER per source

| source | pages | chars | CER clean | CER degraded |
|---|---|---|---|---|
| kagoshima | 1 | 369 | 33.33% | 32.25% |
| hachioji | 14 | 12425 | 19.53% | 8.00% |
| matsue | 1 | 574 | 16.20% | 14.81% |
| kawaguchi | 2 | 777 | 12.74% | 12.10% |
| wakayama_pref | 20 | 20098 | 10.12% | 10.63% |
| digital | 17 | 11597 | 7.30% | 7.80% |
| niigata_pref | 14 | 15368 | 6.66% | 5.88% |
| yokosuka | 2 | 1287 | 6.22% | 5.83% |
| nara_city | 16 | 10581 | 5.92% | 7.00% |
| okayama_pref | 21 | 14899 | 5.28% | 5.52% |
| koriyama | 26 | 15735 | 4.94% | 4.57% |
| asahikawa | 20 | 14564 | 4.23% | 4.15% |
| hokkaido | 19 | 19280 | 3.97% | 6.32% |
| funabashi | 22 | 17200 | 3.29% | 5.70% |
| kanazawa | 2 | 3309 | 2.96% | 10.37% |
| jma | 3 | 1236 | 2.83% | 2.27% |

### CER per doc_type

| doc_type | pages | chars | CER clean | CER degraded |
|---|---|---|---|---|
| rfi_material | 1 | 492 | 26.42% | 26.22% |
| other | 29 | 23350 | 19.77% | 14.95% |
| result | 14 | 4779 | 8.39% | 6.32% |
| forms | 17 | 6916 | 5.83% | 5.74% |
| bid_instructions | 31 | 23693 | 5.66% | 5.82% |
| spec | 36 | 29787 | 5.31% | 5.30% |
| draft_contract | 14 | 16532 | 4.68% | 4.01% |
| evaluation_criteria | 13 | 9575 | 4.52% | 7.45% |
| notice | 29 | 23230 | 3.50% | 4.51% |
| qa | 16 | 20945 | 2.41% | 5.06% |

### Error kinds

Share of all errors, by what OCR did to the character.

| kind | clean | degraded |
|---|---|---|
| dropped line or text not detected | 6097 (55%) | 4840 (45%) |
| character added | 3345 (30%) | 3751 (35%) |
| character dropped | 680 (6%) | 1123 (10%) |
| digit changed | 393 (4%) | 418 (4%) |
| kanji confused | 165 (2%) | 191 (2%) |
| symbol confused | 104 (1%) | 90 (1%) |
| kana confused | 65 (1%) | 111 (1%) |
| latin confused | 22 (0%) | 37 (0%) |
| symbol for latin | 21 (0%) | 11 (0%) |
| kana for latin | 21 (0%) | 3 (0%) |
| kana for symbol | 18 (0%) | 19 (0%) |
| kanji for symbol | 17 (0%) | 26 (0%) |
| kana for kanji | 13 (0%) | 53 (0%) |
| symbol for kana | 10 (0%) | 22 (0%) |
| kanji for kana | 8 (0%) | 43 (0%) |
| kanji for latin | 8 (0%) | 1 (0%) |
| symbol for kanji | 7 (0%) | 14 (0%) |
| latin for symbol | 2 (0%) | 2 (0%) |
| latin for kanji | 1 (0%) | 10 (0%) |
| latin for kana | 0 (0%) | 4 (0%) |

`kanji confused`: one kanji read as another. `X for Y`: a character of one script read as another (a kanji for a kana, say). `character dropped / added`: OCR left a character out or invented one. `dropped line or text not detected`: text-layer characters inside no OCR line box.

### Reading order

| variant | consecutive OCR line pairs | reversed against the text layer |
|---|---|---|
| clean | 7895 | 628 (7.95%) |
| degraded | 7987 | 791 (9.90%) |

Order is judged against MuPDF's block order, which is not always right either (tables, side-by-side columns), so a reversal is a difference, not proof that OCR is wrong. Look at the worst pages below before drawing conclusions.

### Most common kanji confusions (`open` documents only)

| text layer | OCR read | count (both runs) |
|---|---|---|
| 日 | 目 | 6 |
| 速 | 連 | 5 |
| 士 | 土 | 4 |
| 遠 | 連 | 3 |
| 保 | 供 | 2 |
| 札 | 礼 | 2 |
| 入 | 人 | 2 |
| 傘 | 率 | 2 |
| 暴 | 農 | 2 |
| 土 | 士 | 2 |
| 働 | 動 | 2 |
| 願 | 順 | 2 |
| 徴 | 微 | 2 |
| 座 | 産 | 2 |
| 通 | 過 | 2 |

### The 20 worst pages (by clean CER, pages with at least 50 characters)

| doc_id | page | source | doc_type | license | chars | CER clean | CER degraded | lines dropped | main error kind |
|---|---|---|---|---|---|---|---|---|---|
| `9b8e4d2059ea` | 1 | hachioji | other | restricted | 1791 | 97.88% | 2.85% | 132 | dropped line or text not detected |
| `603ca9f96221` | 1 | wakayama_pref | other | open | 1375 | 97.09% | 92.80% | 138 | dropped line or text not detected |
| `27229c8f9d29` | 1 | nara_city | result | restricted | 178 | 84.83% | 74.72% | 40 | dropped line or text not detected |
| `070b894ee590` | 5 | niigata_pref | bid_instructions | restricted | 282 | 81.21% | 79.43% | 27 | dropped line or text not detected |
| `fd1a4b7d9a7a` | 33 | digital | other | open | 268 | 78.73% | 86.57% | 23 | dropped line or text not detected |
| `69bb4a0580c8` | 2 | niigata_pref | other | restricted | 142 | 77.46% | 51.41% | 20 | dropped line or text not detected |
| `624348e86337` | 4 | nara_city | other | restricted | 124 | 41.13% | 37.90% | 10 | dropped line or text not detected |
| `f42b30db2010` | 1 | kagoshima | other | restricted | 369 | 33.33% | 32.25% | 45 | dropped line or text not detected |
| `34ef78f9cc26` | 13 | okayama_pref | bid_instructions | open | 134 | 26.87% | 53.73% | 7 | character added |
| `2a4dacf5624b` | 6 | digital | rfi_material | open | 492 | 26.42% | 26.22% | 1 | digit changed |
| `b74a93b7fe6c` | 1 | funabashi | result | restricted | 212 | 22.17% | 10.85% | 0 | character added |
| `83c59eee4162` | 1 | nara_city | forms | restricted | 216 | 19.91% | 9.72% | 0 | character dropped |
| `52a5fe7ab337` | 1 | koriyama | result | unknown | 193 | 19.69% | 3.11% | 0 | kanji confused |
| `1b0397f3428e` | 6 | hachioji | spec | restricted | 1285 | 17.35% | 17.43% | 33 | dropped line or text not detected |
| `78404300765b` | 1 | hokkaido | draft_contract | open | 124 | 16.94% | 9.68% | 1 | character added |
| `af3b4990fbd8` | 1 | nara_city | forms | restricted | 151 | 16.56% | 10.60% | 0 | character dropped |
| `6b36d69abc0d` | 1 | okayama_pref | bid_instructions | open | 116 | 16.38% | 16.38% | 7 | dropped line or text not detected |
| `b65ec3def67b` | 1 | matsue | other | restricted | 574 | 16.20% | 14.81% | 1 | character added |
| `ac58cfb92021` | 23 | hachioji | spec | restricted | 832 | 15.62% | 19.59% | 0 | character added |
| `133bbf881b4d` | 14 | nara_city | draft_contract | restricted | 157 | 15.29% | 14.01% | 1 | dropped line or text not detected |

## Real scanned, outlined and mixed pages

43 pages in 13 documents go through `load_document` (scanned and outlined pages read by OCR, mixed pages keep their text layer). No ground truth exists for these. Debug renders with sentence boxes: `data/processed/<doc_id>/debug/page-NNN.png`, sentences in `data/processed/<doc_id>/sentences.txt`. `OCR-only chars` (mixed pages): characters OCR reads outside every text-layer line, i.e. text that lives in the page's images; renders in `data/processed/<doc_id>/ocr_mixed/` (orange = OCR text with no text-layer line).

| doc_id | source | page | kind | lines | chars | sentences | dates | times | amounts | looping | OCR-only chars |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `fd1a4b7d9a7a` | digital | 18 | mixed | 4 | 31 | 2 | 0 | 0 | 0 |  | 0 |
| `7c76af66d35d` | toyama | 1 | outlined | 17 | 236 | 12 | 0 | 0 | 0 | 0 |  |
| `7c76af66d35d` | toyama | 2 | outlined | 69 | 470 | 63 | 0 | 0 | 3 | 0 |  |
| `7c76af66d35d` | toyama | 3 | outlined | 74 | 529 | 65 | 0 | 0 | 1 | 0 |  |
| `7c76af66d35d` | toyama | 4 | outlined | 44 | 672 | 37 | 0 | 0 | 1 | 0 |  |
| `7c76af66d35d` | toyama | 5 | outlined | 38 | 752 | 33 | 2 | 2 | 0 | 0 |  |
| `7c76af66d35d` | toyama | 6 | outlined | 35 | 911 | 22 | 0 | 0 | 0 | 0 |  |
| `7c76af66d35d` | toyama | 7 | outlined | 35 | 914 | 21 | 0 | 0 | 0 | 0 |  |
| `7c76af66d35d` | toyama | 8 | outlined | 36 | 894 | 24 | 0 | 0 | 0 | 0 |  |
| `7c76af66d35d` | toyama | 9 | outlined | 38 | 892 | 23 | 0 | 0 | 0 | 0 |  |
| `7c76af66d35d` | toyama | 10 | outlined | 37 | 919 | 21 | 0 | 0 | 0 | 0 |  |
| `7c76af66d35d` | toyama | 11 | outlined | 6 | 172 | 1 | 0 | 0 | 0 | 0 |  |
| `7fb45ac7dec4` | okayama_pref | 1 | scanned | 1 | 1 | 1 | 0 | 0 | 0 | 0 |  |
| `fc885fc55e07` | hokkaido | 26 | mixed | 74 | 468 | 2 | 0 | 0 | 0 |  | 129 |
| `aeedf544969c` | asahikawa | 1 | outlined | 31 | 634 | 25 | 2 | 0 | 1 | 0 |  |
| `aeedf544969c` | asahikawa | 2 | outlined | 31 | 765 | 27 | 0 | 0 | 0 | 0 |  |
| `aeedf544969c` | asahikawa | 3 | outlined | 32 | 842 | 23 | 0 | 0 | 0 | 0 |  |
| `aeedf544969c` | asahikawa | 4 | outlined | 32 | 872 | 20 | 0 | 0 | 0 | 0 |  |
| `aeedf544969c` | asahikawa | 5 | outlined | 26 | 602 | 19 | 1 | 0 | 0 | 0 |  |
| `6bed5f0434e7` | koriyama | 2 | mixed | 94 | 320 | 20 | 0 | 0 | 0 |  | 0 |
| `e102e3ce787c` | nara_city | 1 | scanned | 50 | 558 | 35 | 0 | 0 | 0 | 0 |  |
| `e102e3ce787c` | nara_city | 2 | scanned | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| `e102e3ce787c` | nara_city | 3 | scanned | 5 | 79 | 5 | 0 | 0 | 0 | 1 |  |
| `e102e3ce787c` | nara_city | 4 | scanned | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| `e102e3ce787c` | nara_city | 5 | scanned | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| `01204a43ed1d` | asahikawa | 7 | scanned | 7 | 53 | 7 | 0 | 0 | 0 | 0 |  |
| `e81e9338bfca` | asahikawa | 11 | scanned | 7 | 53 | 7 | 0 | 0 | 0 | 0 |  |
| `12e3ac14da00` | hachioji | 1 | outlined | 37 | 1015 | 28 | 1 | 0 | 0 | 0 |  |
| `12e3ac14da00` | hachioji | 2 | outlined | 42 | 1081 | 33 | 0 | 0 | 0 | 0 |  |
| `12e3ac14da00` | hachioji | 3 | outlined | 36 | 922 | 30 | 0 | 0 | 0 | 0 |  |
| `12e3ac14da00` | hachioji | 4 | outlined | 46 | 892 | 36 | 0 | 0 | 0 | 0 |  |
| `6df340ac7a35` | hachioji | 1 | outlined | 24 | 804 | 18 | 0 | 0 | 0 | 0 |  |
| `69bb4a0580c8` | niigata_pref | 4 | mixed | 20 | 77 | 19 | 0 | 0 | 0 |  | 28 |
| `69bb4a0580c8` | niigata_pref | 5 | mixed | 20 | 78 | 19 | 0 | 0 | 0 |  | 162 |
| `69bb4a0580c8` | niigata_pref | 6 | mixed | 20 | 79 | 19 | 0 | 0 | 0 |  | 0 |
| `69bb4a0580c8` | niigata_pref | 7 | mixed | 22 | 94 | 21 | 0 | 0 | 0 |  | 0 |
| `69bb4a0580c8` | niigata_pref | 8 | mixed | 29 | 208 | 27 | 0 | 0 | 0 |  | 0 |
| `69bb4a0580c8` | niigata_pref | 9 | mixed | 24 | 141 | 25 | 0 | 0 | 0 |  | 0 |
| `69bb4a0580c8` | niigata_pref | 10 | mixed | 22 | 111 | 21 | 0 | 0 | 0 |  | 0 |
| `4c51f1da8161` | niigata_pref | 1 | scanned | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| `4c51f1da8161` | niigata_pref | 2 | scanned | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| `4c51f1da8161` | niigata_pref | 3 | scanned | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| `4c51f1da8161` | niigata_pref | 4 | scanned | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |

### Five to look at first

Each page for a different reason (one per document, except the failure case). The file to open is the debug render. `looping` counts OCR lines that look like the recogniser running away on a region that is not text (`looping()` in `eval/ocr_report.py`).

| doc_id | source | page | kind | lines | looping | why | render |
|---|---|---|---|---|---|---|---|
| `7c76af66d35d` | toyama | 5 | outlined | 38 | 0 | outlined text with dates, times or amounts (the case that matters most) | `data/processed/7c76af66d35dec3e4a82f4a7ef985809119e2d6230641c9a57dd99fc68e4a5e6/debug/page-005.png` |
| `aeedf544969c` | asahikawa | 1 | outlined | 31 | 0 | outlined text with dates, times or amounts (the case that matters most) | `data/processed/aeedf544969c41e5baa77b679f6370ffde8f982d14cca012b228c85e187f7a49/debug/page-001.png` |
| `e102e3ce787c` | nara_city | 1 | scanned | 50 | 0 | copier scan of a table, no text layer at all | `data/processed/e102e3ce787c732cb1e488a0d1cfbb00bff78e24444fdd3a065c5505884d2ab1/debug/page-001.png` |
| `01204a43ed1d` | asahikawa | 7 | scanned | 7 | 0 | scan inside an otherwise text PDF, small text in a screenshot | `data/processed/01204a43ed1d39b64a992e02c2e89711e6c1520f78694a777ca64d6fdd638b2d/debug/page-007.png` |
| `e102e3ce787c` | nara_city | 3 | scanned | 5 | 1 | drawing scan where the recogniser still produces filler in a line | `data/processed/e102e3ce787c732cb1e488a0d1cfbb00bff78e24444fdd3a065c5505884d2ab1/debug/page-003.png` |

