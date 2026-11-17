# Hybrid extractor: list fields (cmp_lfm25_12b_jp)

Rules for everything they answer, `LFM2.5-1.2B-JP-202606-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 14 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-17T20:40:47+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 6 of 38 (16%) | 6 of 187 (3%) | 1 of 39 (3%) | 1 of 39 (3%) | 260 of 298 (87%) | 46 (model calls only) | 17 |
| rules only (0 items by design) | - (0 items given) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (39 fields here).

Calls: 38 calls (0 retried), 4 not found after the retry (Truncated). Items proposed 298, kept 38; dropped by reason: date_or_time_not_in_citation 40, duplicate 2, schema 40, unknown_id 55, value_not_in_citation 123.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 4 of 31 (13%) | 4 of 80 (5%) | 1 of 13 (8%) | 1 of 13 (8%) |
| deadlines | 1 of 2 (50%) | 1 of 42 (2%) | 0 of 13 (0%) | 0 of 13 (0%) |
| required_documents | 1 of 5 (20%) | 1 of 65 (2%) | 0 of 13 (0%) | 0 of 13 (0%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 40 | 0 / 8 / 3 | 22 |
| 58f13b9c2e87 | notice | 41 | 0 / 10 / 8 | 21 |
| a81e99fecea5 | notice | 41 | 1 / 18 / 2 | 25 |
| 136dfba9ee59 | notice | 27 | 0 / 9 / 1 | 18 |
| d230e51e2805 | notice | 55 | 0 / 11 / 0 | 6 |
| 6b7142ab74f4 | notice | 27 | 0 / 10 / 1 | 13 |
| 84e9d0c8325c | notice | 40 | 1 / 16 / 6 | 22 |
| 594c3cb69c53 | notice | 56 | 0 / 11 / 1 | 4 |
| a13baaac55c8 | notice | 33 | 2 / 17 / 6 | 15 |
| 563042df9941 | notice | 29 | 1 / 10 / 5 | 16 |
| 4b0b9d8229c7 | notice | 19 | 0 / 5 / 0 | 15 |
| d40000275df6 | bid_instructions | 145 | 1 / 37 / 3 | 54 |
| 28ad40ea4b1f | bid_instructions | 84 | 0 / 25 / 2 | 29 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 27 | 0 | 16 | 3 | value_not_in_citation 11, duplicate 2 |
| f19cddbd4cba | deadlines | 9 | 9 | 0 | 6 | 0 | date_or_time_not_in_citation 1, schema 5 |
| f19cddbd4cba | required_documents | 22 | 4 | 0 | 3 | 0 | value_not_in_citation 3 |
| 58f13b9c2e87 | eligibility | 19 | 27 | 0 | 15 | 7 | value_not_in_citation 8 |
| 58f13b9c2e87 | deadlines | 10 | 11 | 0 | 11 | 0 | date_or_time_not_in_citation 11 |
| 58f13b9c2e87 | required_documents | 18 | 4 | 0 | 3 | 1 | value_not_in_citation 2 |
| a81e99fecea5 | eligibility | 22 | 23 | 0 | 13 | 2 | value_not_in_citation 11 |
| a81e99fecea5 | deadlines | 16 | 14 | 0 | 11 | 0 | date_or_time_not_in_citation 1, schema 10 |
| a81e99fecea5 | required_documents | 35 | 4 | 0 | 3 | 0 | unknown_id 3 |
| 136dfba9ee59 | eligibility | 28 | 15 | 0 | 10 | 1 | value_not_in_citation 9 |
| 136dfba9ee59 | deadlines | 11 | 8 | 0 | 8 | 0 | date_or_time_not_in_citation 8 |
| 136dfba9ee59 | required_documents | 38 | 3 | 0 | 1 | 0 | value_not_in_citation 1 |
| d230e51e2805 | eligibility | 20 | 48 | 0 | 0 | 0 | Truncated |
| d230e51e2805 | deadlines | 18 | 4 | 0 | 3 | 0 | date_or_time_not_in_citation 3 |
| d230e51e2805 | required_documents | 27 | 4 | 0 | 3 | 0 | unknown_id 1, value_not_in_citation 2 |
| 6b7142ab74f4 | eligibility | 20 | 20 | 0 | 9 | 1 | value_not_in_citation 8 |
| 6b7142ab74f4 | deadlines | 9 | 3 | 0 | 2 | 0 | date_or_time_not_in_citation 1, schema 1 |
| 6b7142ab74f4 | required_documents | 22 | 4 | 0 | 3 | 0 | value_not_in_citation 3 |
| 84e9d0c8325c | eligibility | 22 | 20 | 0 | 13 | 6 | value_not_in_citation 7 |
| 84e9d0c8325c | deadlines | 16 | 15 | 0 | 12 | 0 | date_or_time_not_in_citation 1, schema 11 |
| 84e9d0c8325c | required_documents | 35 | 4 | 0 | 3 | 0 | unknown_id 3 |
| 594c3cb69c53 | eligibility | 20 | 49 | 0 | 0 | 0 | Truncated |
| 594c3cb69c53 | deadlines | 8 | 3 | 0 | 2 | 0 | date_or_time_not_in_citation 1, schema 1 |
| 594c3cb69c53 | required_documents | 22 | 4 | 0 | 3 | 1 | value_not_in_citation 2 |
| a13baaac55c8 | eligibility | 17 | 22 | 0 | 14 | 5 | value_not_in_citation 9 |
| a13baaac55c8 | deadlines | 30 | 5 | 0 | 3 | 0 | date_or_time_not_in_citation 2, schema 1 |
| a13baaac55c8 | required_documents | 67 | 6 | 0 | 4 | 1 | value_not_in_citation 3 |
| 563042df9941 | eligibility | 8 | 11 | 0 | 6 | 3 | value_not_in_citation 3 |
| 563042df9941 | deadlines | 13 | 14 | 0 | 12 | 2 | date_or_time_not_in_citation 10 |
| 563042df9941 | required_documents | 31 | 4 | 0 | 3 | 0 | value_not_in_citation 3 |
| 4b0b9d8229c7 | deadlines | 14 | 16 | 0 | 12 | 0 | date_or_time_not_in_citation 1, schema 11 |
| 4b0b9d8229c7 | required_documents | 14 | 4 | 0 | 3 | 0 | unknown_id 1, value_not_in_citation 2 |
| d40000275df6 | eligibility | 28 | 29 | 0 | 17 | 3 | value_not_in_citation 9, unknown_id 5 |
| d40000275df6 | deadlines | 82 | 53 | 0 | 0 | 0 | Truncated |
| d40000275df6 | required_documents | 170 | 62 | 0 | 40 | 0 | unknown_id 39, value_not_in_citation 1 |
| 28ad40ea4b1f | eligibility | 7 | 3 | 0 | 1 | 0 | unknown_id 1 |
| 28ad40ea4b1f | deadlines | 61 | 52 | 0 | 0 | 0 | Truncated |
| 28ad40ea4b1f | required_documents | 105 | 28 | 0 | 30 | 2 | value_not_in_citation 26, unknown_id 2 |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
