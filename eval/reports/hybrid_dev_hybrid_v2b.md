# Hybrid extractor: list fields (dev_hybrid_v2b)

Rules for everything they answer, `Qwen3.5-9B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 9 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-16T12:38:38+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 54 of 79 (68%) | 54 of 127 (43%) | 6 of 24 (25%) | 6 of 24 (25%) | 9 of 88 (10%) | 106 (model calls only) | 42 |
| rules only (0 items by design) | - (0 items given) | 0 of 127 (0%) | 1 of 24 (4%) | 1 of 24 (4%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (24 fields here).

Calls: 23 calls (0 retried), 0 not found after the retry (none). Items proposed 88, kept 79; dropped by reason: date_or_time_not_in_citation 8, value_not_in_citation 1.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 24 of 40 (60%) | 24 of 53 (45%) | 1 of 8 (12%) | 1 of 8 (12%) |
| deadlines | 12 of 18 (67%) | 12 of 23 (52%) | 3 of 8 (38%) | 3 of 8 (38%) |
| required_documents | 18 of 21 (86%) | 18 of 51 (35%) | 2 of 8 (25%) | 2 of 8 (25%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 51 | 4 / 8 / 8 | 0 |
| 136dfba9ee59 | notice | 99 | 3 / 9 / 6 | 3 |
| 84e9d0c8325c | notice | 133 | 10 / 16 / 13 | 0 |
| a13baaac55c8 | notice | 82 | 5 / 17 / 7 | 0 |
| 563042df9941 | notice | 86 | 6 / 10 / 10 | 0 |
| 4b0b9d8229c7 | notice | 57 | 5 / 5 / 5 | 1 |
| d40000275df6 | bid_instructions | 253 | 9 / 37 / 13 | 5 |
| 28ad40ea4b1f | bid_instructions | 197 | 12 / 25 / 17 | 0 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 28 | 0 | 5 | 5 | - |
| f19cddbd4cba | deadlines | 9 | 17 | 0 | 2 | 2 | - |
| f19cddbd4cba | required_documents | 9 | 6 | 0 | 1 | 1 | - |
| 136dfba9ee59 | eligibility | 28 | 55 | 0 | 6 | 5 | value_not_in_citation 1 |
| 136dfba9ee59 | deadlines | 11 | 33 | 0 | 2 | 0 | date_or_time_not_in_citation 2 |
| 136dfba9ee59 | required_documents | 11 | 10 | 0 | 1 | 1 | - |
| 84e9d0c8325c | eligibility | 22 | 87 | 0 | 8 | 8 | - |
| 84e9d0c8325c | deadlines | 16 | 34 | 0 | 3 | 3 | - |
| 84e9d0c8325c | required_documents | 16 | 13 | 0 | 2 | 2 | - |
| a13baaac55c8 | eligibility | 17 | 44 | 0 | 4 | 4 | - |
| a13baaac55c8 | deadlines | 30 | 18 | 0 | 1 | 1 | - |
| a13baaac55c8 | required_documents | 30 | 19 | 0 | 2 | 2 | - |
| 563042df9941 | eligibility | 8 | 39 | 0 | 5 | 5 | - |
| 563042df9941 | deadlines | 13 | 34 | 0 | 3 | 3 | - |
| 563042df9941 | required_documents | 13 | 12 | 0 | 2 | 2 | - |
| 4b0b9d8229c7 | deadlines | 14 | 42 | 0 | 4 | 3 | date_or_time_not_in_citation 1 |
| 4b0b9d8229c7 | required_documents | 14 | 15 | 0 | 2 | 2 | - |
| d40000275df6 | eligibility | 28 | 92 | 0 | 7 | 7 | - |
| d40000275df6 | deadlines | 82 | 99 | 0 | 8 | 3 | date_or_time_not_in_citation 5 |
| d40000275df6 | required_documents | 100 | 62 | 0 | 3 | 3 | - |
| 28ad40ea4b1f | eligibility | 7 | 76 | 0 | 6 | 6 | - |
| 28ad40ea4b1f | deadlines | 61 | 52 | 0 | 3 | 3 | - |
| 28ad40ea4b1f | required_documents | 85 | 69 | 0 | 8 | 8 | - |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
