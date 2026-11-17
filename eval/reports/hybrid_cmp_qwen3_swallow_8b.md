# Hybrid extractor: list fields (cmp_qwen3_swallow_8b)

Rules for everything they answer, `Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 14 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-17T18:50:24+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 59 of 99 (60%) | 59 of 187 (32%) | 2 of 39 (5%) | 2 of 39 (5%) | 231 of 330 (70%) | 137 (model calls only) | 51 |
| rules only (0 items by design) | - (0 items given) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (39 fields here).

Calls: 38 calls (0 retried), 1 not found after the retry (Truncated). Items proposed 330, kept 99; dropped by reason: duplicate 41, schema 150, unknown_id 23, value_not_in_citation 17.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 37 of 70 (53%) | 37 of 80 (46%) | 1 of 13 (8%) | 1 of 13 (8%) |
| deadlines | - (0 of 0) | 0 of 42 (0%) | 0 of 13 (0%) | 0 of 13 (0%) |
| required_documents | 22 of 29 (76%) | 22 of 65 (34%) | 1 of 13 (8%) | 1 of 13 (8%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 89 | 3 / 8 / 6 | 6 |
| 58f13b9c2e87 | notice | 71 | 4 / 10 / 6 | 6 |
| a81e99fecea5 | notice | 96 | 6 / 18 / 8 | 7 |
| 136dfba9ee59 | notice | 204 | 0 / 9 / 0 | 2 |
| d230e51e2805 | notice | 138 | 3 / 11 / 6 | 1 |
| 6b7142ab74f4 | notice | 80 | 4 / 10 / 7 | 9 |
| 84e9d0c8325c | notice | 94 | 3 / 16 / 8 | 7 |
| 594c3cb69c53 | notice | 132 | 3 / 11 / 8 | 40 |
| a13baaac55c8 | notice | 197 | 7 / 17 / 16 | 37 |
| 563042df9941 | notice | 75 | 2 / 10 / 8 | 3 |
| 4b0b9d8229c7 | notice | 24 | 0 / 5 / 0 | 8 |
| d40000275df6 | bid_instructions | 344 | 5 / 37 / 7 | 47 |
| 28ad40ea4b1f | bid_instructions | 377 | 19 / 25 / 19 | 58 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 64 | 0 | 9 | 5 | duplicate 4 |
| f19cddbd4cba | deadlines | 9 | 11 | 0 | 2 | 0 | schema 2 |
| f19cddbd4cba | required_documents | 22 | 14 | 0 | 1 | 1 | - |
| 58f13b9c2e87 | eligibility | 19 | 46 | 0 | 5 | 5 | - |
| 58f13b9c2e87 | deadlines | 10 | 8 | 0 | 3 | 0 | schema 3 |
| 58f13b9c2e87 | required_documents | 18 | 17 | 0 | 4 | 1 | value_not_in_citation 3 |
| a81e99fecea5 | eligibility | 22 | 61 | 0 | 8 | 8 | - |
| a81e99fecea5 | deadlines | 16 | 21 | 0 | 6 | 0 | schema 6 |
| a81e99fecea5 | required_documents | 35 | 14 | 0 | 1 | 0 | unknown_id 1 |
| 136dfba9ee59 | eligibility | 28 | 187 | 0 | 0 | 0 | Truncated |
| 136dfba9ee59 | deadlines | 11 | 3 | 0 | 0 | 0 | - |
| 136dfba9ee59 | required_documents | 38 | 14 | 0 | 2 | 0 | value_not_in_citation 2 |
| d230e51e2805 | eligibility | 20 | 50 | 0 | 6 | 6 | - |
| d230e51e2805 | deadlines | 18 | 5 | 0 | 0 | 0 | - |
| d230e51e2805 | required_documents | 27 | 82 | 0 | 1 | 0 | unknown_id 1 |
| 6b7142ab74f4 | eligibility | 20 | 51 | 0 | 6 | 6 | - |
| 6b7142ab74f4 | deadlines | 9 | 15 | 0 | 9 | 0 | schema 9 |
| 6b7142ab74f4 | required_documents | 22 | 14 | 0 | 1 | 1 | - |
| 84e9d0c8325c | eligibility | 22 | 60 | 0 | 8 | 8 | - |
| 84e9d0c8325c | deadlines | 16 | 21 | 0 | 6 | 0 | schema 6 |
| 84e9d0c8325c | required_documents | 35 | 13 | 0 | 1 | 0 | unknown_id 1 |
| 594c3cb69c53 | eligibility | 20 | 54 | 0 | 7 | 7 | - |
| 594c3cb69c53 | deadlines | 8 | 61 | 0 | 40 | 0 | schema 40 |
| 594c3cb69c53 | required_documents | 22 | 17 | 0 | 1 | 1 | - |
| a13baaac55c8 | eligibility | 17 | 68 | 0 | 11 | 7 | value_not_in_citation 4 |
| a13baaac55c8 | deadlines | 30 | 14 | 0 | 2 | 0 | schema 2 |
| a13baaac55c8 | required_documents | 67 | 114 | 0 | 40 | 9 | value_not_in_citation 1, duplicate 30 |
| 563042df9941 | eligibility | 8 | 43 | 0 | 5 | 5 | - |
| 563042df9941 | deadlines | 13 | 7 | 0 | 3 | 0 | schema 3 |
| 563042df9941 | required_documents | 31 | 25 | 0 | 3 | 3 | - |
| 4b0b9d8229c7 | deadlines | 14 | 16 | 0 | 8 | 0 | schema 8 |
| 4b0b9d8229c7 | required_documents | 14 | 7 | 0 | 0 | 0 | - |
| d40000275df6 | eligibility | 28 | 155 | 0 | 14 | 7 | duplicate 7 |
| d40000275df6 | deadlines | 82 | 103 | 0 | 40 | 0 | schema 40 |
| d40000275df6 | required_documents | 170 | 86 | 0 | 0 | 0 | - |
| 28ad40ea4b1f | eligibility | 7 | 76 | 0 | 6 | 6 | - |
| 28ad40ea4b1f | deadlines | 61 | 113 | 0 | 31 | 0 | schema 31 |
| 28ad40ea4b1f | required_documents | 105 | 188 | 0 | 40 | 13 | unknown_id 20, value_not_in_citation 7 |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
