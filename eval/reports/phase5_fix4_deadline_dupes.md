# Fix 4: same-datetime, same-sentence deadline copies (D-72)

Replay of `llm._drop_same_sentence_copies` on the kept deadline items of each saved trace in `data/cache/hybrid/`. No model run, no scorer, so these are item counts, not verified-accuracy scores. Rows are deadline items kept by the old code (before) and by the old code plus the new drop (after). `cmp` is the dev comparison (13 documents with deadline calls per model), `cmp5d` is the 3-model run on `5d75d4a67c71` only. The traces predate the change, so the new code is applied to their kept items; everything else in them is unchanged.

| trace | model | deadline rows before | after | dropped |
| --- | --- | --- | --- | --- |
| cmp | gemma4_e4b | 22 | 22 | 0 |
| cmp | lfm25_12b_jp | 2 | 2 | 0 |
| cmp | lfm25_8b_a1b | 3 | 3 | 0 |
| cmp | nemotron_nano_9b_jp | 8 | 8 | 0 |
| cmp | qwen35_4b | 26 | 26 | 0 |
| cmp | qwen35_9b | 35 | 35 | 0 |
| cmp | qwen3_swallow_8b | 0 | 0 | 0 |
| cmp | sarashina22_3b | 0 | 0 | 0 |
| cmp5d | gemma4_e4b | 6 | 3 | 3 |
| cmp5d | qwen35_9b | 6 | 3 | 3 |
| cmp5d | qwen3_swallow_8b | 3 | 3 | 0 |

## Dropped rows (doc prefix, sentence ids, kind, datetime)

- cmp5d_gemma4_e4b: 5d75d4a67c71 h_s45 electronic 2026-10-02T17:00:00+09:00
- cmp5d_gemma4_e4b: 5d75d4a67c71 h_s46 other 2026-10-14T17:00:00+09:00
- cmp5d_gemma4_e4b: 5d75d4a67c71 h_s47 electronic 2026-10-15T11:00:00+09:00
- cmp5d_qwen35_9b: 5d75d4a67c71 h_s45 electronic 2026-10-02T17:00:00+09:00
- cmp5d_qwen35_9b: 5d75d4a67c71 h_s46 other 2026-10-14T17:00:00+09:00
- cmp5d_qwen35_9b: 5d75d4a67c71 h_s47 electronic 2026-10-15T11:00:00+09:00
