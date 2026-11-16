# Label set

`label_set.json`: the documents to label, seed 20261003 (D-40). Written by `uv run python -m eval.label_set`. Seeded random sampling inside each split, per group (notice or tender_page / bid_instructions / spec), round-robin over organizations. Eligible: extracts without errors and has 5+ Japanese sentences. Dev keeps every document with OCR pages and the 10 p-portal English Summary notices before the fill.

## Shortfalls

None: every stratum is full.

## dev: 60 documents

- groups: notice 30/30, bid_instructions 15/15, spec 15/15
- open 37, restricted or unknown 23
- format: html 26, pdf 34
- documents with OCR pages: 3
- p-portal HTML notices with an English Summary: 15

| org | docs | notice | bid_instructions | spec | open | pdf | html |
|---|---|---|---|---|---|---|---|
| 旭川市 | 16 | 3 | 6 | 7 | 0 | 16 | 0 |
| 和歌山県 | 15 | 3 | 7 | 5 | 15 | 12 | 3 |
| 新潟県 | 7 | 2 | 2 | 3 | 0 | 6 | 1 |
| 厚生労働省 | 5 | 5 | 0 | 0 | 5 | 0 | 5 |
| 法務省 | 5 | 5 | 0 | 0 | 5 | 0 | 5 |
| 内閣府 | 4 | 4 | 0 | 0 | 4 | 0 | 4 |
| 総務省 | 4 | 4 | 0 | 0 | 4 | 0 | 4 |
| 農林水産省 | 4 | 4 | 0 | 0 | 4 | 0 | 4 |

## test: 40 documents

- groups: notice 20/20, bid_instructions 10/10, spec 10/10
- open 30, restricted or unknown 10
- format: html 14, pdf 26
- documents with OCR pages: 0
- p-portal HTML notices with an English Summary: 3

| org | docs | notice | bid_instructions | spec | open | pdf | html |
|---|---|---|---|---|---|---|---|
| 船橋市 | 10 | 2 | 4 | 4 | 0 | 8 | 2 |
| 岡山県 | 9 | 2 | 4 | 3 | 9 | 9 | 0 |
| 北海道 | 8 | 3 | 2 | 3 | 8 | 6 | 2 |
| 文部科学省 | 3 | 3 | 0 | 0 | 3 | 0 | 3 |
| 最高裁判所 | 3 | 3 | 0 | 0 | 3 | 0 | 3 |
| 気象衛星センター | 3 | 3 | 0 | 0 | 3 | 3 | 0 |
| 経済産業省 | 2 | 2 | 0 | 0 | 2 | 0 | 2 |
| 防衛省 | 2 | 2 | 0 | 0 | 2 | 0 | 2 |
