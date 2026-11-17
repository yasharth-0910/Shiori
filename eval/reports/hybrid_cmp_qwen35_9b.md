# Hybrid extractor: list fields (cmp_qwen35_9b)

Rules for everything they answer, `Qwen3.5-9B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 14 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-17T18:18:15+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 123 of 164 (75%) | 123 of 187 (66%) | 10 of 39 (26%) | 10 of 39 (26%) | 21 of 185 (11%) | 95 (model calls only) | 35 |
| rules only (0 items by design) | - (0 items given) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (39 fields here).

Calls: 38 calls (0 retried), 0 not found after the retry (none). Items proposed 185, kept 164; dropped by reason: date_or_time_not_in_citation 11, duplicate 8, unknown_id 1, value_not_in_citation 1.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 49 of 71 (69%) | 49 of 80 (61%) | 1 of 13 (8%) | 1 of 13 (8%) |
| deadlines | 24 of 35 (69%) | 24 of 42 (57%) | 4 of 13 (31%) | 4 of 13 (31%) |
| required_documents | 50 of 58 (86%) | 50 of 65 (77%) | 5 of 13 (38%) | 5 of 13 (38%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 49 | 4 / 8 / 9 | 0 |
| 58f13b9c2e87 | notice | 55 | 6 / 10 / 8 | 3 |
| a81e99fecea5 | notice | 109 | 14 / 18 / 18 | 0 |
| 136dfba9ee59 | notice | 82 | 4 / 9 / 7 | 3 |
| d230e51e2805 | notice | 116 | 11 / 11 / 13 | 4 |
| 6b7142ab74f4 | notice | 107 | 8 / 10 / 11 | 4 |
| 84e9d0c8325c | notice | 94 | 13 / 16 / 15 | 0 |
| 594c3cb69c53 | notice | 88 | 10 / 11 / 11 | 0 |
| a13baaac55c8 | notice | 101 | 13 / 17 / 15 | 0 |
| 563042df9941 | notice | 74 | 5 / 10 / 10 | 0 |
| 4b0b9d8229c7 | notice | 40 | 5 / 5 / 5 | 1 |
| d40000275df6 | bid_instructions | 269 | 18 / 37 / 25 | 5 |
| 28ad40ea4b1f | bid_instructions | 149 | 12 / 25 / 17 | 1 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 26 | 0 | 5 | 5 | - |
| f19cddbd4cba | deadlines | 9 | 14 | 0 | 2 | 2 | - |
| f19cddbd4cba | required_documents | 22 | 10 | 0 | 2 | 2 | - |
| 58f13b9c2e87 | eligibility | 19 | 26 | 0 | 5 | 5 | - |
| 58f13b9c2e87 | deadlines | 10 | 18 | 0 | 3 | 0 | date_or_time_not_in_citation 3 |
| 58f13b9c2e87 | required_documents | 18 | 11 | 0 | 3 | 3 | - |
| a81e99fecea5 | eligibility | 22 | 44 | 0 | 8 | 8 | - |
| a81e99fecea5 | deadlines | 16 | 42 | 0 | 6 | 6 | - |
| a81e99fecea5 | required_documents | 35 | 24 | 0 | 4 | 4 | - |
| 136dfba9ee59 | eligibility | 28 | 48 | 0 | 6 | 5 | value_not_in_citation 1 |
| 136dfba9ee59 | deadlines | 11 | 17 | 0 | 2 | 0 | date_or_time_not_in_citation 2 |
| 136dfba9ee59 | required_documents | 38 | 17 | 0 | 2 | 2 | - |
| d230e51e2805 | eligibility | 20 | 66 | 0 | 10 | 6 | duplicate 4 |
| d230e51e2805 | deadlines | 18 | 36 | 0 | 5 | 5 | - |
| d230e51e2805 | required_documents | 27 | 14 | 0 | 2 | 2 | - |
| 6b7142ab74f4 | eligibility | 20 | 68 | 0 | 10 | 6 | duplicate 4 |
| 6b7142ab74f4 | deadlines | 9 | 26 | 0 | 3 | 3 | - |
| 6b7142ab74f4 | required_documents | 22 | 14 | 0 | 2 | 2 | - |
| 84e9d0c8325c | eligibility | 22 | 50 | 0 | 8 | 8 | - |
| 84e9d0c8325c | deadlines | 16 | 23 | 0 | 3 | 3 | - |
| 84e9d0c8325c | required_documents | 35 | 21 | 0 | 4 | 4 | - |
| 594c3cb69c53 | eligibility | 20 | 48 | 0 | 6 | 6 | - |
| 594c3cb69c53 | deadlines | 8 | 23 | 0 | 3 | 3 | - |
| 594c3cb69c53 | required_documents | 22 | 17 | 0 | 2 | 2 | - |
| a13baaac55c8 | eligibility | 17 | 32 | 0 | 4 | 4 | - |
| a13baaac55c8 | deadlines | 30 | 14 | 0 | 1 | 1 | - |
| a13baaac55c8 | required_documents | 67 | 55 | 0 | 10 | 10 | - |
| 563042df9941 | eligibility | 8 | 29 | 0 | 5 | 5 | - |
| 563042df9941 | deadlines | 13 | 29 | 0 | 3 | 3 | - |
| 563042df9941 | required_documents | 31 | 17 | 0 | 2 | 2 | - |
| 4b0b9d8229c7 | deadlines | 14 | 30 | 0 | 4 | 3 | date_or_time_not_in_citation 1 |
| 4b0b9d8229c7 | required_documents | 14 | 10 | 0 | 2 | 2 | - |
| d40000275df6 | eligibility | 28 | 66 | 0 | 7 | 7 | - |
| d40000275df6 | deadlines | 82 | 70 | 0 | 8 | 3 | date_or_time_not_in_citation 5 |
| d40000275df6 | required_documents | 170 | 132 | 0 | 15 | 15 | - |
| 28ad40ea4b1f | eligibility | 7 | 54 | 0 | 6 | 6 | - |
| 28ad40ea4b1f | deadlines | 61 | 41 | 0 | 3 | 3 | - |
| 28ad40ea4b1f | required_documents | 105 | 54 | 0 | 9 | 8 | unknown_id 1 |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
