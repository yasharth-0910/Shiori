# Extraction report

Generated 2026-10-02 by `uv run python -m eval.extraction_report`, extractor version 0.3.0. Phase 2 parts A to C: characters, lines, page kinds, header/footer flags, and OCR (D-36) for scanned and outlined pages. Normalization and segmentation are in `segmentation_report.md`.

PDFs in manifest: 322. Extracted: 322. Failed: 0. Pages: 1864.

## Pages per kind

| kind | pages |
|---|---|
| text | 1818 |
| mixed | 10 |
| scanned | 12 |
| outlined | 21 |
| blank | 3 |

Rules in `core/shiori_core/ingest.py`. By source:

| source | text | mixed | scanned | outlined | blank |
|---|---|---|---|---|---|
| asahikawa | 138 | 0 | 2 | 5 | 0 |
| digital | 470 | 1 | 0 | 0 | 0 |
| funabashi | 151 | 0 | 0 | 0 | 1 |
| hachioji | 181 | 0 | 0 | 5 | 1 |
| hokkaido | 213 | 1 | 0 | 0 | 0 |
| jma | 34 | 0 | 0 | 0 | 0 |
| kagoshima | 1 | 0 | 0 | 0 | 0 |
| kanazawa | 6 | 0 | 0 | 0 | 0 |
| kawaguchi | 4 | 0 | 0 | 0 | 0 |
| koriyama | 156 | 1 | 0 | 0 | 0 |
| matsue | 1 | 0 | 0 | 0 | 0 |
| nara_city | 102 | 0 | 5 | 0 | 0 |
| niigata_pref | 66 | 7 | 4 | 0 | 0 |
| okayama_pref | 106 | 0 | 1 | 0 | 0 |
| toyama | 0 | 0 | 0 | 11 | 0 |
| wakayama_pref | 167 | 0 | 0 | 0 | 1 |
| yokosuka | 22 | 0 | 0 | 0 | 0 |

## Pages that are not plain text

| doc_id | source | license | page | kind | chars | img | paths | producer |
|---|---|---|---|---|---|---|---|---|
| `fd1a4b7d9a7a` | digital | open | 18 | mixed | 27 | 0.60 | None | Microsoft® Word for Microsoft 365 |
| `c4ba28b735d6` | funabashi | restricted | 2 | blank | 0 | 0.00 | 0 | Microsoft® Word for Microsoft 365 |
| `7c76af66d35d` | toyama | unknown | 1 | outlined | 0 | 0.00 | 36108 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 2 | outlined | 1 | 0.00 | 26646 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 3 | outlined | 1 | 0.00 | 30229 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 4 | outlined | 1 | 0.00 | 33871 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 5 | outlined | 1 | 0.00 | 34734 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 6 | outlined | 1 | 0.00 | 45869 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 7 | outlined | 1 | 0.00 | 45658 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 8 | outlined | 1 | 0.00 | 43733 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 9 | outlined | 1 | 0.00 | 43716 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 10 | outlined | 1 | 0.00 | 44376 | Microsoft: Print To PDF |
| `7c76af66d35d` | toyama | unknown | 11 | outlined | 2 | 0.00 | 9715 | Microsoft: Print To PDF |
| `12f50d0602ce` | wakayama_pref | open | 3 | blank | 0 | 0.00 | 0 | Microsoft: Print To PDF |
| `7fb45ac7dec4` | okayama_pref | open | 1 | scanned | 0 | 0.95 | 1 |  |
| `fc885fc55e07` | hokkaido | open | 26 | mixed | 31 | 0.51 | None | 一太郎 |
| `aeedf544969c` | asahikawa | restricted | 1 | outlined | 18 | 0.00 | 30395 | Microsoft: Print To PDF |
| `aeedf544969c` | asahikawa | restricted | 2 | outlined | 0 | 0.00 | 32707 | Microsoft: Print To PDF |
| `aeedf544969c` | asahikawa | restricted | 3 | outlined | 0 | 0.00 | 39327 | Microsoft: Print To PDF |
| `aeedf544969c` | asahikawa | restricted | 4 | outlined | 0 | 0.00 | 37655 | Microsoft: Print To PDF |
| `aeedf544969c` | asahikawa | restricted | 5 | outlined | 0 | 0.00 | 29084 | Microsoft: Print To PDF |
| `6bed5f0434e7` | koriyama | unknown | 2 | mixed | 213 | 0.62 | None | iText® Core 8.0.5 (AGPL version) ©2000-2 |
| `e102e3ce787c` | nara_city | restricted | 1 | scanned | 0 | 1.00 | 0 | KONICA MINOLTA bizhub C451i |
| `e102e3ce787c` | nara_city | restricted | 2 | scanned | 0 | 1.00 | 0 | KONICA MINOLTA bizhub C451i |
| `e102e3ce787c` | nara_city | restricted | 3 | scanned | 0 | 1.00 | 0 | KONICA MINOLTA bizhub C451i |
| `e102e3ce787c` | nara_city | restricted | 4 | scanned | 0 | 1.00 | 0 | KONICA MINOLTA bizhub C451i |
| `e102e3ce787c` | nara_city | restricted | 5 | scanned | 0 | 1.00 | 0 | KONICA MINOLTA bizhub C451i |
| `01204a43ed1d` | asahikawa | restricted | 7 | scanned | 2 | 0.51 | 1 | JUST Note |
| `e81e9338bfca` | asahikawa | restricted | 11 | scanned | 2 | 0.51 | 1 | JUST Note |
| `12e3ac14da00` | hachioji | restricted | 1 | outlined | 1 | 0.00 | 34369 | Microsoft: Print To PDF |
| `12e3ac14da00` | hachioji | restricted | 2 | outlined | 1 | 0.00 | 35510 | Microsoft: Print To PDF |
| `12e3ac14da00` | hachioji | restricted | 3 | outlined | 1 | 0.00 | 28210 | Microsoft: Print To PDF |
| `12e3ac14da00` | hachioji | restricted | 4 | outlined | 1 | 0.00 | 27924 | Microsoft: Print To PDF |
| `6df340ac7a35` | hachioji | restricted | 1 | outlined | 8 | 0.00 | 26861 | Microsoft: Print To PDF |
| `ac58cfb92021` | hachioji | restricted | 27 | blank | 0 | 0.00 | 0 | iText® Core 8.0.5 (AGPL version) ©2000-2 |
| `69bb4a0580c8` | niigata_pref | restricted | 4 | mixed | 76 | 0.62 | None | Microsoft® Excel® for Microsoft 365 |
| `69bb4a0580c8` | niigata_pref | restricted | 5 | mixed | 77 | 0.68 | None | Microsoft® Excel® for Microsoft 365 |
| `69bb4a0580c8` | niigata_pref | restricted | 6 | mixed | 78 | 0.68 | None | Microsoft® Excel® for Microsoft 365 |
| `69bb4a0580c8` | niigata_pref | restricted | 7 | mixed | 93 | 0.64 | None | Microsoft® Excel® for Microsoft 365 |
| `69bb4a0580c8` | niigata_pref | restricted | 8 | mixed | 207 | 0.64 | None | Microsoft® Excel® for Microsoft 365 |
| `69bb4a0580c8` | niigata_pref | restricted | 9 | mixed | 140 | 0.59 | None | Microsoft® Excel® for Microsoft 365 |
| `69bb4a0580c8` | niigata_pref | restricted | 10 | mixed | 110 | 0.59 | None | Microsoft® Excel® for Microsoft 365 |
| `4c51f1da8161` | niigata_pref | restricted | 1 | scanned | 0 | 1.00 | 0 | DocuCentre-V 4070 |
| `4c51f1da8161` | niigata_pref | restricted | 2 | scanned | 4 | 1.00 | 0 | DocuCentre-V 4070 |
| `4c51f1da8161` | niigata_pref | restricted | 3 | scanned | 0 | 1.00 | 0 | DocuCentre-V 4070 |
| `4c51f1da8161` | niigata_pref | restricted | 4 | scanned | 0 | 1.00 | 0 | DocuCentre-V 4070 |

## OCR

Pages read by OCR (scanned and outlined): 33, in 9 documents; 26 of them gave text: 836 lines, 16534 characters. Mixed pages keep their text layer. Quality is measured in `ocr_report.md`.

## Failures

None.

Failures are per file: a file either loads or it doesn't; pages don't fail on their own.

## Timing

Total 77.0 s for 1864 pages: 41.3 ms per page on average (MacBook Air M4, includes reading the file, hashing it and, for the 9 documents with scanned or outlined pages, loading the OCR models once and reading those pages).

Slowest per page:

| doc_id | source | pages | ms per page |
|---|---|---|---|
| `7c76af66d35d` | toyama | 11 | 1487 |
| `12e3ac14da00` | hachioji | 4 | 1271 |
| `6df340ac7a35` | hachioji | 1 | 1116 |
| `aeedf544969c` | asahikawa | 5 | 1065 |
| `e102e3ce787c` | nara_city | 5 | 932 |

## Lines per page

Mean 41.6, median 39, max 263. Counts include lines made only of space glyphs.

## Headers, footers and page numbers

Lines flagged `page_number`: 977 in 98 documents. Lines flagged `header_footer`: 43 in 4 documents.

## Vertical lines

110 non-blank lines flagged vertical in 21 documents.

| doc_id | vertical lines |
|---|---|
| `ac58cfb92021` | 21 |
| `a0f13100504f` | 18 |
| `23ea23bdf058` | 12 |
| `e357de690785` | 10 |
| `7c76af66d35d` | 9 |
| `167bd103087a` | 6 |
| `6b36d69abc0d` | 4 |
| `1b0397f3428e` | 4 |
| `9b8e4d2059ea` | 4 |
| `d313a5093ec9` | 3 |

## Unmapped or mis-mapped glyphs

Suspect characters (`ingest.is_suspect`): U+FFFD, control characters, Phonetic Extensions and CJK Extension A. Documents with any:

| doc_id | source | suspect chars | chars |
|---|---|---|---|
| `6b36d69abc0d` | okayama_pref | 12 | 2100 |
| `34ef78f9cc26` | okayama_pref | 20 | 2526 |

Pages where 5% or more of the characters are suspect: `6b36d69abc0d` p9, `6b36d69abc0d` p10, `34ef78f9cc26` p12, `34ef78f9cc26` p13.

Private Use Area characters, kept as they are (TXT-11, TXT-12):

| doc_id | code points |
|---|---|
| `073ad71ae492` | U+F02C x4 |
| `2a4dacf5624b` | U+F09F x5 |
| `7337b4148c56` | U+F02C x2 |
| `756d17c84006` | U+F09E x31 |
| `94521ecfd7f4` | U+E27D x1 |
| `b16ad9882fbc` | U+F8FD x1 |
| `d313a5093ec9` | U+F09E x28 |
| `ed1aebdc6e36` | U+F09E x10 |
| `faef6e6a09d9` | U+E27D x6 |

## Sample for hand inspection

20 documents: every document with a scanned or outlined page, then random documents round-robin over sources (`random.Random(20261002)`). Renders are in the folder shown, one PNG per page.

| doc_id | source | license | pages | kinds | debug render |
|---|---|---|---|---|---|
| `7c76af66d35dec3e4a82f4a7ef985809119e2d6230641c9a57dd99fc68e4a5e6` | toyama | unknown | 11 | outlined 11 | `data/processed/7c76af66d35dec3e4a82f4a7ef985809119e2d6230641c9a57dd99fc68e4a5e6/debug/` |
| `7fb45ac7dec4a28fe8a308b3592213b6c51c860463e9e84aa6028da5a464cf09` | okayama_pref | open | 1 | scanned 1 | `data/processed/7fb45ac7dec4a28fe8a308b3592213b6c51c860463e9e84aa6028da5a464cf09/debug/` |
| `aeedf544969c41e5baa77b679f6370ffde8f982d14cca012b228c85e187f7a49` | asahikawa | restricted | 5 | outlined 5 | `data/processed/aeedf544969c41e5baa77b679f6370ffde8f982d14cca012b228c85e187f7a49/debug/` |
| `e102e3ce787c732cb1e488a0d1cfbb00bff78e24444fdd3a065c5505884d2ab1` | nara_city | restricted | 5 | scanned 5 | `data/processed/e102e3ce787c732cb1e488a0d1cfbb00bff78e24444fdd3a065c5505884d2ab1/debug/` |
| `01204a43ed1d39b64a992e02c2e89711e6c1520f78694a777ca64d6fdd638b2d` | asahikawa | restricted | 7 | text 6, scanned 1 | `data/processed/01204a43ed1d39b64a992e02c2e89711e6c1520f78694a777ca64d6fdd638b2d/debug/` |
| `e81e9338bfca59272821534968626248fa69a45d9c3e9c8fa350887166fb1089` | asahikawa | restricted | 11 | text 10, scanned 1 | `data/processed/e81e9338bfca59272821534968626248fa69a45d9c3e9c8fa350887166fb1089/debug/` |
| `12e3ac14da00d04928b0148cc3d9d9d3fa60a80fb66e8a791dacf0106f4e1481` | hachioji | restricted | 4 | outlined 4 | `data/processed/12e3ac14da00d04928b0148cc3d9d9d3fa60a80fb66e8a791dacf0106f4e1481/debug/` |
| `6df340ac7a354265283b2cb70d049aabcd62be71f3c5021e7e559412c05fb8e8` | hachioji | restricted | 1 | outlined 1 | `data/processed/6df340ac7a354265283b2cb70d049aabcd62be71f3c5021e7e559412c05fb8e8/debug/` |
| `4c51f1da81610f2a1392d7e6e778d1110b9cfd3d943bc83a3e61dc48e3461768` | niigata_pref | restricted | 4 | scanned 4 | `data/processed/4c51f1da81610f2a1392d7e6e778d1110b9cfd3d943bc83a3e61dc48e3461768/debug/` |
| `737f48e78112b5e581fc18785d88a666403f5b4f1f77ad11775453975ab9ff69` | hokkaido | open | 3 | text 3 | `data/processed/737f48e78112b5e581fc18785d88a666403f5b4f1f77ad11775453975ab9ff69/debug/` |
| `1d5b1d3cf90b054a209d4c738332950d11bff2b4c5015a33327fb38db88bb8ad` | koriyama | unknown | 7 | text 7 | `data/processed/1d5b1d3cf90b054a209d4c738332950d11bff2b4c5015a33327fb38db88bb8ad/debug/` |
| `bdbd81a9013bf14be7b9e30314f7247e777f3606b1fea48e4008a2cb6ffff8c5` | digital | open | 1 | text 1 | `data/processed/bdbd81a9013bf14be7b9e30314f7247e777f3606b1fea48e4008a2cb6ffff8c5/debug/` |
| `12f50d0602ce35d34a27055226991593730b4b9ebb11c7ad721ea8dd9572cad2` | wakayama_pref | open | 3 | text 2, blank 1 | `data/processed/12f50d0602ce35d34a27055226991593730b4b9ebb11c7ad721ea8dd9572cad2/debug/` |
| `b74a93b7fe6c36ba62fcb88c070fa97c851b0636b487d19be226f0f7867008fd` | funabashi | restricted | 1 | text 1 | `data/processed/b74a93b7fe6c36ba62fcb88c070fa97c851b0636b487d19be226f0f7867008fd/debug/` |
| `2aa7506afc0882cdbe20dfe37fd643ab19099247fc0450613da07c427a81973c` | jma | open | 12 | text 12 | `data/processed/2aa7506afc0882cdbe20dfe37fd643ab19099247fc0450613da07c427a81973c/debug/` |
| `d43dd5c2172babbdc20b5f799a48d5c8663b8a4ece1bdcaf4c9ce044b119dcca` | kanazawa | restricted | 3 | text 3 | `data/processed/d43dd5c2172babbdc20b5f799a48d5c8663b8a4ece1bdcaf4c9ce044b119dcca/debug/` |
| `d360751d6e655ed1919d3a57d5e0415eaa428bb8b5e439f35882a76a8c6aa453` | kawaguchi | unknown | 1 | text 1 | `data/processed/d360751d6e655ed1919d3a57d5e0415eaa428bb8b5e439f35882a76a8c6aa453/debug/` |
| `ab5e74f19ac1513ce3df1e38a65c656e7111ab5b65152fa4982ae74358446d3f` | yokosuka | restricted | 11 | text 11 | `data/processed/ab5e74f19ac1513ce3df1e38a65c656e7111ab5b65152fa4982ae74358446d3f/debug/` |
| `f42b30db20109094e710e5f531ec6b2d6213607a5beaa276d419e39029e50cd5` | kagoshima | restricted | 1 | text 1 | `data/processed/f42b30db20109094e710e5f531ec6b2d6213607a5beaa276d419e39029e50cd5/debug/` |
| `b65ec3def67b8936e9b51017e80315a33837e1663814d4845139fc8374fddd3a` | matsue | restricted | 1 | text 1 | `data/processed/b65ec3def67b8936e9b51017e80315a33837e1663814d4845139fc8374fddd3a/debug/` |
