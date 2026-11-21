# Hybrid extractor: list fields (application_after2)

Rules for everything they answer, `Qwen3.5-9B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 15 documents scored, extractor version 0.3.0, schema 1.1.0, 2026-11-21T18:42:12+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 138 of 175 (79%) | 138 of 198 (70%) | 14 of 42 (33%) | 14 of 42 (33%) | 39 of 214 (18%) | 116 (model calls only) | 43 |
| rules only (0 items by design) | - (0 items given) | 0 of 198 (0%) | 1 of 42 (2%) | 1 of 42 (2%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (42 fields here).

Calls: 41 calls (0 retried), 0 not found after the retry (none). Items proposed 214, kept 175; dropped by reason: date_or_time_not_in_citation 16, duplicate 11, same_sentence 1, schema 2, unknown_id 1, value_not_in_citation 1.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 61 of 69 (88%) | 61 of 84 (73%) | 8 of 14 (57%) | 8 of 14 (57%) |
| deadlines | 19 of 39 (49%) | 19 of 45 (42%) | 0 of 14 (0%) | 0 of 14 (0%) |
| required_documents | 58 of 67 (87%) | 58 of 69 (84%) | 6 of 14 (43%) | 6 of 14 (43%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 52 | 6 / 8 / 8 | 0 |
| 58f13b9c2e87 | notice | 70 | 6 / 10 / 7 | 3 |
| a81e99fecea5 | notice | 124 | 13 / 18 / 15 | 1 |
| 136dfba9ee59 | notice | 73 | 6 / 9 / 7 | 2 |
| d230e51e2805 | notice | 127 | 10 / 11 / 12 | 4 |
| 6b7142ab74f4 | notice | 139 | 9 / 10 / 12 | 4 |
| 84e9d0c8325c | notice | 129 | 13 / 16 / 15 | 1 |
| 594c3cb69c53 | notice | 99 | 9 / 11 / 11 | 0 |
| 5d75d4a67c71 | notice | 112 | 9 / 11 / 10 | 4 |
| a13baaac55c8 | notice | 116 | 13 / 17 / 15 | 0 |
| 563042df9941 | notice | 75 | 8 / 10 / 10 | 0 |
| 4b0b9d8229c7 | notice | 35 | 3 / 5 / 5 | 0 |
| d40000275df6 | bid_instructions | 312 | 16 / 37 / 25 | 5 |
| 28ad40ea4b1f | bid_instructions | 281 | 17 / 25 / 23 | 8 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 26 | 0 | 5 | 4 | - |
| f19cddbd4cba | deadlines | 9 | 15 | 0 | 2 | 2 | - |
| f19cddbd4cba | required_documents | 22 | 11 | 0 | 2 | 2 | - |
| 58f13b9c2e87 | eligibility | 19 | 28 | 0 | 5 | 4 | - |
| 58f13b9c2e87 | deadlines | 10 | 24 | 0 | 3 | 0 | date_or_time_not_in_citation 3 |
| 58f13b9c2e87 | required_documents | 18 | 18 | 0 | 3 | 3 | - |
| a81e99fecea5 | eligibility | 22 | 64 | 0 | 8 | 7 | - |
| a81e99fecea5 | deadlines | 16 | 39 | 0 | 5 | 4 | schema 1 |
| a81e99fecea5 | required_documents | 35 | 21 | 0 | 4 | 4 | - |
| 136dfba9ee59 | eligibility | 28 | 46 | 0 | 6 | 5 | value_not_in_citation 1 |
| 136dfba9ee59 | deadlines | 11 | 9 | 0 | 1 | 0 | date_or_time_not_in_citation 1 |
| 136dfba9ee59 | required_documents | 38 | 18 | 0 | 2 | 2 | - |
| d230e51e2805 | eligibility | 20 | 71 | 0 | 10 | 5 | duplicate 4 |
| d230e51e2805 | deadlines | 18 | 38 | 0 | 5 | 5 | - |
| d230e51e2805 | required_documents | 27 | 18 | 0 | 2 | 2 | - |
| 6b7142ab74f4 | eligibility | 20 | 87 | 0 | 10 | 5 | duplicate 4 |
| 6b7142ab74f4 | deadlines | 9 | 25 | 0 | 3 | 3 | - |
| 6b7142ab74f4 | required_documents | 22 | 27 | 0 | 4 | 4 | - |
| 84e9d0c8325c | eligibility | 22 | 57 | 0 | 8 | 7 | - |
| 84e9d0c8325c | deadlines | 16 | 42 | 0 | 5 | 4 | schema 1 |
| 84e9d0c8325c | required_documents | 35 | 30 | 0 | 4 | 4 | - |
| 594c3cb69c53 | eligibility | 20 | 54 | 0 | 6 | 6 | - |
| 594c3cb69c53 | deadlines | 8 | 25 | 0 | 3 | 3 | - |
| 594c3cb69c53 | required_documents | 22 | 20 | 0 | 2 | 2 | - |
| 5d75d4a67c71 | eligibility | 19 | 57 | 0 | 8 | 4 | duplicate 3 |
| 5d75d4a67c71 | deadlines | 9 | 40 | 0 | 5 | 4 | same_sentence 1 |
| 5d75d4a67c71 | required_documents | 20 | 16 | 0 | 2 | 2 | - |
| a13baaac55c8 | eligibility | 17 | 38 | 0 | 4 | 4 | - |
| a13baaac55c8 | deadlines | 30 | 15 | 0 | 1 | 1 | - |
| a13baaac55c8 | required_documents | 67 | 63 | 0 | 10 | 10 | - |
| 563042df9941 | eligibility | 8 | 30 | 0 | 5 | 5 | - |
| 563042df9941 | deadlines | 13 | 26 | 0 | 3 | 3 | - |
| 563042df9941 | required_documents | 31 | 19 | 0 | 2 | 2 | - |
| 4b0b9d8229c7 | deadlines | 14 | 25 | 0 | 3 | 3 | - |
| 4b0b9d8229c7 | required_documents | 14 | 10 | 0 | 2 | 2 | - |
| d40000275df6 | eligibility | 28 | 72 | 0 | 7 | 7 | - |
| d40000275df6 | deadlines | 82 | 79 | 0 | 8 | 3 | date_or_time_not_in_citation 5 |
| d40000275df6 | required_documents | 170 | 161 | 0 | 15 | 15 | - |
| 28ad40ea4b1f | eligibility | 7 | 65 | 0 | 6 | 6 | - |
| 28ad40ea4b1f | deadlines | 61 | 113 | 0 | 11 | 4 | date_or_time_not_in_citation 7 |
| 28ad40ea4b1f | required_documents | 105 | 103 | 0 | 14 | 13 | unknown_id 1 |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
