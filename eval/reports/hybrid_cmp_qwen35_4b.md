# Hybrid extractor: list fields (cmp_qwen35_4b)

Rules for everything they answer, `Qwen3.5-4B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 14 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-17T21:17:31+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 93 of 159 (58%) | 93 of 187 (50%) | 2 of 39 (5%) | 2 of 39 (5%) | 36 of 195 (18%) | 55 (model calls only) | 20 |
| rules only (0 items by design) | - (0 items given) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (39 fields here).

Calls: 38 calls (0 retried), 0 not found after the retry (none). Items proposed 195, kept 159; dropped by reason: date_or_time_not_in_citation 7, duplicate 2, schema 22, unknown_id 1, value_not_in_citation 4.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 48 of 75 (64%) | 48 of 80 (60%) | 1 of 13 (8%) | 1 of 13 (8%) |
| deadlines | 12 of 26 (46%) | 12 of 42 (29%) | 0 of 13 (0%) | 0 of 13 (0%) |
| required_documents | 33 of 58 (57%) | 33 of 65 (51%) | 1 of 13 (8%) | 1 of 13 (8%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 48 | 3 / 8 / 14 | 0 |
| 58f13b9c2e87 | notice | 33 | 6 / 10 / 10 | 1 |
| a81e99fecea5 | notice | 45 | 9 / 18 / 11 | 6 |
| 136dfba9ee59 | notice | 47 | 5 / 9 / 9 | 4 |
| d230e51e2805 | notice | 59 | 11 / 11 / 14 | 0 |
| 6b7142ab74f4 | notice | 52 | 6 / 10 / 9 | 3 |
| 84e9d0c8325c | notice | 62 | 8 / 16 / 10 | 7 |
| 594c3cb69c53 | notice | 55 | 8 / 11 / 13 | 0 |
| a13baaac55c8 | notice | 69 | 10 / 17 / 14 | 3 |
| 563042df9941 | notice | 59 | 5 / 10 / 16 | 1 |
| 4b0b9d8229c7 | notice | 12 | 2 / 5 / 2 | 6 |
| d40000275df6 | bid_instructions | 113 | 8 / 37 / 10 | 4 |
| 28ad40ea4b1f | bid_instructions | 119 | 12 / 25 / 27 | 1 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 34 | 0 | 8 | 8 | - |
| f19cddbd4cba | deadlines | 9 | 6 | 0 | 2 | 2 | - |
| f19cddbd4cba | required_documents | 22 | 8 | 0 | 4 | 4 | - |
| 58f13b9c2e87 | eligibility | 19 | 19 | 0 | 5 | 5 | - |
| 58f13b9c2e87 | deadlines | 10 | 8 | 0 | 3 | 2 | date_or_time_not_in_citation 1 |
| 58f13b9c2e87 | required_documents | 18 | 6 | 0 | 3 | 3 | - |
| a81e99fecea5 | eligibility | 22 | 29 | 0 | 8 | 8 | - |
| a81e99fecea5 | deadlines | 16 | 7 | 0 | 6 | 0 | schema 6 |
| a81e99fecea5 | required_documents | 35 | 9 | 0 | 3 | 3 | - |
| 136dfba9ee59 | eligibility | 28 | 26 | 0 | 6 | 5 | value_not_in_citation 1 |
| 136dfba9ee59 | deadlines | 11 | 10 | 0 | 3 | 0 | schema 1, date_or_time_not_in_citation 2 |
| 136dfba9ee59 | required_documents | 38 | 11 | 0 | 4 | 4 | - |
| d230e51e2805 | eligibility | 20 | 30 | 0 | 6 | 6 | - |
| d230e51e2805 | deadlines | 18 | 17 | 0 | 5 | 5 | - |
| d230e51e2805 | required_documents | 27 | 12 | 0 | 3 | 3 | - |
| 6b7142ab74f4 | eligibility | 20 | 34 | 0 | 7 | 5 | value_not_in_citation 1, duplicate 1 |
| 6b7142ab74f4 | deadlines | 9 | 7 | 0 | 2 | 1 | date_or_time_not_in_citation 1 |
| 6b7142ab74f4 | required_documents | 22 | 11 | 0 | 3 | 3 | - |
| 84e9d0c8325c | eligibility | 22 | 40 | 0 | 8 | 7 | value_not_in_citation 1 |
| 84e9d0c8325c | deadlines | 16 | 11 | 0 | 6 | 0 | schema 6 |
| 84e9d0c8325c | required_documents | 35 | 12 | 0 | 3 | 3 | - |
| 594c3cb69c53 | eligibility | 20 | 32 | 0 | 6 | 6 | - |
| 594c3cb69c53 | deadlines | 8 | 10 | 0 | 3 | 3 | - |
| 594c3cb69c53 | required_documents | 22 | 14 | 0 | 4 | 4 | - |
| a13baaac55c8 | eligibility | 17 | 25 | 0 | 5 | 5 | - |
| a13baaac55c8 | deadlines | 30 | 11 | 0 | 3 | 0 | schema 3 |
| a13baaac55c8 | required_documents | 67 | 32 | 0 | 9 | 9 | - |
| 563042df9941 | eligibility | 8 | 35 | 0 | 11 | 10 | duplicate 1 |
| 563042df9941 | deadlines | 13 | 10 | 0 | 2 | 2 | - |
| 563042df9941 | required_documents | 31 | 13 | 0 | 4 | 4 | - |
| 4b0b9d8229c7 | deadlines | 14 | 7 | 0 | 6 | 0 | schema 6 |
| 4b0b9d8229c7 | required_documents | 14 | 5 | 0 | 2 | 2 | - |
| d40000275df6 | eligibility | 28 | 40 | 0 | 5 | 4 | value_not_in_citation 1 |
| d40000275df6 | deadlines | 82 | 36 | 0 | 6 | 3 | date_or_time_not_in_citation 3 |
| d40000275df6 | required_documents | 170 | 37 | 0 | 3 | 3 | - |
| 28ad40ea4b1f | eligibility | 7 | 29 | 0 | 6 | 6 | - |
| 28ad40ea4b1f | deadlines | 61 | 44 | 0 | 8 | 8 | - |
| 28ad40ea4b1f | required_documents | 105 | 47 | 0 | 14 | 13 | unknown_id 1 |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
