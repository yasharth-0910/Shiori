# Hybrid extractor: list fields (cmp_gemma4_e4b)

Rules for everything they answer, `gemma-4-E4B-it-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 14 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-17T21:39:49+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 114 of 154 (74%) | 114 of 187 (61%) | 10 of 39 (26%) | 10 of 39 (26%) | 80 of 234 (34%) | 75 (model calls only) | 28 |
| rules only (0 items by design) | - (0 items given) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (39 fields here).

Calls: 38 calls (0 retried), 0 not found after the retry (none). Items proposed 234, kept 154; dropped by reason: date_or_time_not_in_citation 11, duplicate 5, schema 55, unknown_id 1, value_not_in_citation 8.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 48 of 65 (74%) | 48 of 80 (60%) | 3 of 13 (23%) | 3 of 13 (23%) |
| deadlines | 9 of 22 (41%) | 9 of 42 (21%) | 1 of 13 (8%) | 1 of 13 (8%) |
| required_documents | 57 of 67 (85%) | 57 of 65 (88%) | 6 of 13 (46%) | 6 of 13 (46%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 30 | 2 / 8 / 6 | 2 |
| 58f13b9c2e87 | notice | 33 | 6 / 10 / 7 | 5 |
| a81e99fecea5 | notice | 61 | 11 / 18 / 12 | 12 |
| 136dfba9ee59 | notice | 81 | 3 / 9 / 4 | 12 |
| d230e51e2805 | notice | 67 | 11 / 11 / 11 | 2 |
| 6b7142ab74f4 | notice | 63 | 8 / 10 / 12 | 0 |
| 84e9d0c8325c | notice | 101 | 11 / 16 / 12 | 15 |
| 594c3cb69c53 | notice | 65 | 8 / 11 / 9 | 3 |
| a13baaac55c8 | notice | 74 | 12 / 17 / 15 | 1 |
| 563042df9941 | notice | 48 | 3 / 10 / 7 | 6 |
| 4b0b9d8229c7 | notice | 40 | 2 / 5 / 5 | 9 |
| d40000275df6 | bid_instructions | 238 | 19 / 37 / 28 | 8 |
| 28ad40ea4b1f | bid_instructions | 152 | 18 / 25 / 26 | 5 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 16 | 0 | 4 | 4 | - |
| f19cddbd4cba | deadlines | 9 | 6 | 0 | 2 | 0 | schema 2 |
| f19cddbd4cba | required_documents | 22 | 7 | 0 | 2 | 2 | - |
| 58f13b9c2e87 | eligibility | 19 | 16 | 0 | 4 | 4 | - |
| 58f13b9c2e87 | deadlines | 10 | 9 | 0 | 5 | 0 | schema 5 |
| 58f13b9c2e87 | required_documents | 18 | 9 | 0 | 3 | 3 | - |
| a81e99fecea5 | eligibility | 22 | 28 | 0 | 8 | 8 | - |
| a81e99fecea5 | deadlines | 16 | 18 | 0 | 12 | 0 | schema 12 |
| a81e99fecea5 | required_documents | 35 | 15 | 0 | 4 | 4 | - |
| 136dfba9ee59 | eligibility | 28 | 61 | 0 | 11 | 2 | value_not_in_citation 7, duplicate 2 |
| 136dfba9ee59 | deadlines | 11 | 9 | 0 | 3 | 0 | schema 3 |
| 136dfba9ee59 | required_documents | 38 | 11 | 0 | 2 | 2 | - |
| d230e51e2805 | eligibility | 20 | 28 | 0 | 5 | 5 | - |
| d230e51e2805 | deadlines | 18 | 27 | 0 | 6 | 4 | schema 2 |
| d230e51e2805 | required_documents | 27 | 13 | 0 | 2 | 2 | - |
| 6b7142ab74f4 | eligibility | 20 | 35 | 0 | 6 | 6 | - |
| 6b7142ab74f4 | deadlines | 9 | 15 | 0 | 3 | 3 | - |
| 6b7142ab74f4 | required_documents | 22 | 13 | 0 | 3 | 3 | - |
| 84e9d0c8325c | eligibility | 22 | 40 | 0 | 8 | 8 | - |
| 84e9d0c8325c | deadlines | 16 | 41 | 0 | 15 | 0 | schema 15 |
| 84e9d0c8325c | required_documents | 35 | 20 | 0 | 4 | 4 | - |
| 594c3cb69c53 | eligibility | 20 | 38 | 0 | 6 | 6 | - |
| 594c3cb69c53 | deadlines | 8 | 10 | 0 | 3 | 0 | schema 3 |
| 594c3cb69c53 | required_documents | 22 | 17 | 0 | 3 | 3 | - |
| a13baaac55c8 | eligibility | 17 | 26 | 0 | 4 | 3 | value_not_in_citation 1 |
| a13baaac55c8 | deadlines | 30 | 10 | 0 | 1 | 1 | - |
| a13baaac55c8 | required_documents | 67 | 38 | 0 | 11 | 11 | - |
| 563042df9941 | eligibility | 8 | 24 | 0 | 5 | 5 | - |
| 563042df9941 | deadlines | 13 | 13 | 0 | 6 | 0 | schema 6 |
| 563042df9941 | required_documents | 31 | 11 | 0 | 2 | 2 | - |
| 4b0b9d8229c7 | deadlines | 14 | 31 | 0 | 12 | 3 | schema 7, date_or_time_not_in_citation 2 |
| 4b0b9d8229c7 | required_documents | 14 | 8 | 0 | 2 | 2 | - |
| d40000275df6 | eligibility | 28 | 60 | 0 | 7 | 7 | - |
| d40000275df6 | deadlines | 82 | 75 | 0 | 13 | 6 | date_or_time_not_in_citation 6, duplicate 1 |
| d40000275df6 | required_documents | 170 | 103 | 0 | 16 | 15 | duplicate 1 |
| 28ad40ea4b1f | eligibility | 7 | 37 | 0 | 7 | 7 | - |
| 28ad40ea4b1f | deadlines | 61 | 54 | 0 | 9 | 5 | duplicate 1, date_or_time_not_in_citation 3 |
| 28ad40ea4b1f | required_documents | 105 | 60 | 0 | 15 | 14 | unknown_id 1 |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
