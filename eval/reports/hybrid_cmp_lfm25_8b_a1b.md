# Hybrid extractor: list fields (cmp_lfm25_8b_a1b)

Rules for everything they answer, `LFM2.5-8B-A1B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 14 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-17T20:12:38+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 19 of 62 (31%) | 19 of 187 (10%) | 1 of 39 (3%) | 1 of 39 (3%) | 229 of 291 (79%) | 23 (model calls only) | 8 |
| rules only (0 items by design) | - (0 items given) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (39 fields here).

Calls: 38 calls (0 retried), 0 not found after the retry (none). Items proposed 291, kept 62; dropped by reason: date_or_time_not_in_citation 33, duplicate 1, schema 110, unknown_id 12, value_not_in_citation 73.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 7 of 40 (18%) | 7 of 80 (9%) | 1 of 13 (8%) | 1 of 13 (8%) |
| deadlines | 3 of 3 (100%) | 3 of 42 (7%) | 0 of 13 (0%) | 0 of 13 (0%) |
| required_documents | 9 of 19 (47%) | 9 of 65 (14%) | 0 of 13 (0%) | 0 of 13 (0%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 13 | 0 / 8 / 5 | 4 |
| 58f13b9c2e87 | notice | 11 | 1 / 10 / 2 | 5 |
| a81e99fecea5 | notice | 26 | 4 / 18 / 7 | 15 |
| 136dfba9ee59 | notice | 27 | 0 / 9 / 5 | 15 |
| d230e51e2805 | notice | 23 | 2 / 11 / 2 | 14 |
| 6b7142ab74f4 | notice | 19 | 1 / 10 / 3 | 12 |
| 84e9d0c8325c | notice | 19 | 3 / 16 / 5 | 11 |
| 594c3cb69c53 | notice | 14 | 3 / 11 / 5 | 4 |
| a13baaac55c8 | notice | 41 | 4 / 17 / 18 | 33 |
| 563042df9941 | notice | 17 | 1 / 10 / 3 | 14 |
| 4b0b9d8229c7 | notice | 7 | 0 / 5 / 0 | 11 |
| d40000275df6 | bid_instructions | 62 | 0 / 37 / 5 | 45 |
| 28ad40ea4b1f | bid_instructions | 43 | 0 / 25 / 2 | 46 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 5 | 0 | 4 | 4 | - |
| f19cddbd4cba | deadlines | 9 | 4 | 0 | 4 | 0 | schema 3, date_or_time_not_in_citation 1 |
| f19cddbd4cba | required_documents | 22 | 3 | 0 | 1 | 1 | - |
| 58f13b9c2e87 | eligibility | 19 | 3 | 0 | 1 | 0 | value_not_in_citation 1 |
| 58f13b9c2e87 | deadlines | 10 | 4 | 0 | 4 | 0 | schema 1, date_or_time_not_in_citation 3 |
| 58f13b9c2e87 | required_documents | 18 | 3 | 0 | 2 | 2 | - |
| a81e99fecea5 | eligibility | 22 | 12 | 0 | 7 | 4 | value_not_in_citation 3 |
| a81e99fecea5 | deadlines | 16 | 9 | 0 | 10 | 1 | schema 2, date_or_time_not_in_citation 7 |
| a81e99fecea5 | required_documents | 35 | 5 | 0 | 5 | 2 | value_not_in_citation 3 |
| 136dfba9ee59 | eligibility | 28 | 19 | 0 | 13 | 5 | value_not_in_citation 8 |
| 136dfba9ee59 | deadlines | 11 | 6 | 0 | 6 | 0 | schema 2, date_or_time_not_in_citation 4 |
| 136dfba9ee59 | required_documents | 38 | 3 | 0 | 1 | 0 | value_not_in_citation 1 |
| d230e51e2805 | eligibility | 20 | 4 | 0 | 1 | 1 | - |
| d230e51e2805 | deadlines | 18 | 16 | 0 | 14 | 0 | date_or_time_not_in_citation 13, schema 1 |
| d230e51e2805 | required_documents | 27 | 3 | 0 | 1 | 1 | - |
| 6b7142ab74f4 | eligibility | 20 | 10 | 0 | 5 | 2 | value_not_in_citation 3 |
| 6b7142ab74f4 | deadlines | 9 | 5 | 0 | 9 | 0 | schema 8, date_or_time_not_in_citation 1 |
| 6b7142ab74f4 | required_documents | 22 | 3 | 0 | 1 | 1 | - |
| 84e9d0c8325c | eligibility | 22 | 11 | 0 | 7 | 4 | value_not_in_citation 3 |
| 84e9d0c8325c | deadlines | 16 | 5 | 0 | 6 | 0 | schema 3, date_or_time_not_in_citation 3 |
| 84e9d0c8325c | required_documents | 35 | 4 | 0 | 3 | 1 | value_not_in_citation 2 |
| 594c3cb69c53 | eligibility | 20 | 5 | 0 | 2 | 2 | - |
| 594c3cb69c53 | deadlines | 8 | 5 | 0 | 6 | 2 | schema 3, date_or_time_not_in_citation 1 |
| 594c3cb69c53 | required_documents | 22 | 3 | 0 | 1 | 1 | - |
| a13baaac55c8 | eligibility | 17 | 18 | 0 | 13 | 9 | unknown_id 1, value_not_in_citation 3 |
| a13baaac55c8 | deadlines | 30 | 13 | 0 | 26 | 0 | schema 26 |
| a13baaac55c8 | required_documents | 67 | 11 | 0 | 12 | 9 | value_not_in_citation 2, duplicate 1 |
| 563042df9941 | eligibility | 8 | 9 | 0 | 6 | 3 | value_not_in_citation 3 |
| 563042df9941 | deadlines | 13 | 5 | 0 | 10 | 0 | schema 10 |
| 563042df9941 | required_documents | 31 | 3 | 0 | 1 | 0 | value_not_in_citation 1 |
| 4b0b9d8229c7 | deadlines | 14 | 5 | 0 | 10 | 0 | schema 10 |
| 4b0b9d8229c7 | required_documents | 14 | 2 | 0 | 1 | 0 | value_not_in_citation 1 |
| d40000275df6 | eligibility | 28 | 17 | 0 | 6 | 4 | unknown_id 1, value_not_in_citation 1 |
| d40000275df6 | deadlines | 82 | 9 | 0 | 4 | 0 | schema 1, unknown_id 3 |
| d40000275df6 | required_documents | 170 | 35 | 0 | 40 | 1 | unknown_id 6, value_not_in_citation 33 |
| 28ad40ea4b1f | eligibility | 7 | 13 | 0 | 7 | 2 | value_not_in_citation 5 |
| 28ad40ea4b1f | deadlines | 61 | 23 | 0 | 40 | 0 | schema 40 |
| 28ad40ea4b1f | required_documents | 105 | 8 | 0 | 1 | 0 | unknown_id 1 |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
