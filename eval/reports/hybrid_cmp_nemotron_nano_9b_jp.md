# Hybrid extractor: list fields (cmp_nemotron_nano_9b_jp)

Rules for everything they answer, `NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 14 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-17T20:07:07+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 62 of 102 (61%) | 62 of 187 (33%) | 3 of 39 (8%) | 3 of 39 (8%) | 124 of 226 (55%) | 328 (model calls only) | 121 |
| rules only (0 items by design) | - (0 items given) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (39 fields here).

Calls: 38 calls (2 retried), 2 not found after the retry (TimeoutError). Items proposed 226, kept 102; dropped by reason: date_or_time_not_in_citation 26, duplicate 4, schema 44, unknown_id 2, value_not_in_citation 48.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 24 of 45 (53%) | 24 of 80 (30%) | 1 of 13 (8%) | 1 of 13 (8%) |
| deadlines | 3 of 8 (38%) | 3 of 42 (7%) | 0 of 13 (0%) | 0 of 13 (0%) |
| required_documents | 35 of 49 (71%) | 35 of 65 (54%) | 2 of 13 (15%) | 2 of 13 (15%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 225 | 2 / 8 / 7 | 9 |
| 58f13b9c2e87 | notice | 209 | 4 / 10 / 6 | 5 |
| a81e99fecea5 | notice | 284 | 10 / 18 / 11 | 6 |
| 136dfba9ee59 | notice | 676 | 2 / 9 / 2 | 1 |
| d230e51e2805 | notice | 230 | 5 / 11 / 9 | 4 |
| 6b7142ab74f4 | notice | 279 | 2 / 10 / 8 | 6 |
| 84e9d0c8325c | notice | 369 | 4 / 16 / 7 | 18 |
| 594c3cb69c53 | notice | 291 | 4 / 11 / 8 | 6 |
| a13baaac55c8 | notice | 314 | 9 / 17 / 12 | 4 |
| 563042df9941 | notice | 197 | 3 / 10 / 7 | 2 |
| 4b0b9d8229c7 | notice | 115 | 2 / 5 / 2 | 12 |
| d40000275df6 | bid_instructions | 1071 | 8 / 37 / 10 | 32 |
| 28ad40ea4b1f | bid_instructions | 326 | 7 / 25 / 13 | 19 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 112 | 0 | 5 | 4 | value_not_in_citation 1 |
| f19cddbd4cba | deadlines | 9 | 51 | 0 | 7 | 0 | schema 7 |
| f19cddbd4cba | required_documents | 22 | 62 | 0 | 4 | 3 | value_not_in_citation 1 |
| 58f13b9c2e87 | eligibility | 19 | 109 | 0 | 5 | 3 | value_not_in_citation 2 |
| 58f13b9c2e87 | deadlines | 10 | 55 | 0 | 3 | 0 | date_or_time_not_in_citation 3 |
| 58f13b9c2e87 | required_documents | 18 | 46 | 0 | 3 | 3 | - |
| a81e99fecea5 | eligibility | 22 | 173 | 0 | 8 | 8 | - |
| a81e99fecea5 | deadlines | 16 | 49 | 0 | 6 | 0 | schema 6 |
| a81e99fecea5 | required_documents | 35 | 62 | 0 | 3 | 3 | - |
| 136dfba9ee59 | eligibility | 28 | 600 | 1 | 0 | 0 | TimeoutError |
| 136dfba9ee59 | deadlines | 11 | 22 | 0 | 1 | 0 | schema 1 |
| 136dfba9ee59 | required_documents | 38 | 53 | 0 | 2 | 2 | - |
| d230e51e2805 | eligibility | 20 | 137 | 0 | 7 | 6 | duplicate 1 |
| d230e51e2805 | deadlines | 18 | 34 | 0 | 3 | 0 | schema 3 |
| d230e51e2805 | required_documents | 27 | 59 | 0 | 3 | 3 | - |
| 6b7142ab74f4 | eligibility | 20 | 204 | 0 | 9 | 7 | value_not_in_citation 2 |
| 6b7142ab74f4 | deadlines | 9 | 32 | 0 | 4 | 0 | schema 4 |
| 6b7142ab74f4 | required_documents | 22 | 44 | 0 | 1 | 1 | - |
| 84e9d0c8325c | eligibility | 22 | 191 | 0 | 8 | 2 | value_not_in_citation 6 |
| 84e9d0c8325c | deadlines | 16 | 54 | 0 | 6 | 0 | schema 6 |
| 84e9d0c8325c | required_documents | 35 | 124 | 0 | 11 | 5 | value_not_in_citation 6 |
| 594c3cb69c53 | eligibility | 20 | 163 | 0 | 6 | 3 | value_not_in_citation 3 |
| 594c3cb69c53 | deadlines | 8 | 28 | 0 | 2 | 0 | schema 2 |
| 594c3cb69c53 | required_documents | 22 | 100 | 0 | 6 | 5 | value_not_in_citation 1 |
| a13baaac55c8 | eligibility | 17 | 125 | 0 | 4 | 1 | value_not_in_citation 2, unknown_id 1 |
| a13baaac55c8 | deadlines | 30 | 39 | 0 | 1 | 0 | schema 1 |
| a13baaac55c8 | required_documents | 67 | 151 | 0 | 11 | 11 | - |
| 563042df9941 | eligibility | 8 | 105 | 0 | 4 | 4 | - |
| 563042df9941 | deadlines | 13 | 25 | 0 | 2 | 0 | schema 2 |
| 563042df9941 | required_documents | 31 | 68 | 0 | 3 | 3 | - |
| 4b0b9d8229c7 | deadlines | 14 | 82 | 0 | 12 | 0 | schema 12 |
| 4b0b9d8229c7 | required_documents | 14 | 33 | 0 | 2 | 2 | - |
| d40000275df6 | eligibility | 28 | 600 | 1 | 0 | 0 | TimeoutError |
| d40000275df6 | deadlines | 82 | 270 | 0 | 24 | 4 | date_or_time_not_in_citation 17, duplicate 3 |
| d40000275df6 | required_documents | 170 | 200 | 0 | 18 | 6 | value_not_in_citation 11, unknown_id 1 |
| 28ad40ea4b1f | eligibility | 7 | 120 | 0 | 7 | 7 | - |
| 28ad40ea4b1f | deadlines | 61 | 91 | 0 | 10 | 4 | date_or_time_not_in_citation 6 |
| 28ad40ea4b1f | required_documents | 105 | 116 | 0 | 15 | 2 | value_not_in_citation 13 |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
