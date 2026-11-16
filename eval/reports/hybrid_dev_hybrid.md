# Hybrid extractor: list fields (dev_hybrid)

Rules for everything they answer, `Qwen3.5-9B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 9 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-16T11:30:43+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on, and the examples in the prompt come from documents of this set. The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on, and the examples in the prompt come from documents of this set. The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 55 of 78 (71%) | 55 of 127 (43%) | 5 of 24 (21%) | 5 of 24 (21%) | 10 of 88 (11%) | 107 (model calls only) | 42 |
| rules only (0 items by design) | - (0 items given) | 0 of 127 (0%) | 1 of 24 (4%) | 1 of 24 (4%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (24 fields here).

Calls: 23 calls, 0 failed (none). Items proposed 88, kept 78; dropped by reason: date_not_in_citation 5, duplicate 1, schema 2, value_not_in_citation 2.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on, and the examples in the prompt come from documents of this set. The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 26 of 40 (65%) | 26 of 53 (49%) | 1 of 8 (12%) | 1 of 8 (12%) |
| deadlines | 14 of 21 (67%) | 14 of 23 (61%) | 3 of 8 (38%) | 3 of 8 (38%) |
| required_documents | 15 of 17 (88%) | 15 of 51 (29%) | 1 of 8 (12%) | 1 of 8 (12%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on, and the examples in the prompt come from documents of this set. The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 74 | 4 / 8 / 8 | 0 |
| 136dfba9ee59 | notice | 81 | 4 / 9 / 8 | 0 |
| 84e9d0c8325c | notice | 132 | 10 / 16 / 11 | 4 |
| a13baaac55c8 | notice | 96 | 5 / 17 / 7 | 1 |
| 563042df9941 | notice | 83 | 5 / 10 / 9 | 0 |
| 4b0b9d8229c7 | notice | 58 | 5 / 5 / 5 | 1 |
| d40000275df6 | bid_instructions | 261 | 8 / 37 / 12 | 4 |
| 28ad40ea4b1f | bid_instructions | 179 | 14 / 25 / 18 | 0 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 43 | 5 | 5 | - |
| f19cddbd4cba | deadlines | 9 | 23 | 2 | 2 | - |
| f19cddbd4cba | required_documents | 9 | 8 | 1 | 1 | - |
| 136dfba9ee59 | eligibility | 28 | 54 | 5 | 5 | - |
| 136dfba9ee59 | deadlines | 11 | 19 | 2 | 2 | - |
| 136dfba9ee59 | required_documents | 11 | 8 | 1 | 1 | - |
| 84e9d0c8325c | eligibility | 22 | 69 | 8 | 8 | - |
| 84e9d0c8325c | deadlines | 16 | 51 | 5 | 3 | schema 1, duplicate 1 |
| 84e9d0c8325c | required_documents | 16 | 11 | 2 | 0 | value_not_in_citation 2 |
| a13baaac55c8 | eligibility | 17 | 46 | 4 | 4 | - |
| a13baaac55c8 | deadlines | 30 | 27 | 2 | 1 | schema 1 |
| a13baaac55c8 | required_documents | 30 | 23 | 2 | 2 | - |
| 563042df9941 | eligibility | 8 | 41 | 5 | 5 | - |
| 563042df9941 | deadlines | 13 | 33 | 3 | 3 | - |
| 563042df9941 | required_documents | 13 | 9 | 1 | 1 | - |
| 4b0b9d8229c7 | deadlines | 14 | 47 | 4 | 3 | date_not_in_citation 1 |
| 4b0b9d8229c7 | required_documents | 14 | 11 | 2 | 2 | - |
| d40000275df6 | eligibility | 28 | 94 | 7 | 7 | - |
| d40000275df6 | deadlines | 82 | 102 | 7 | 3 | date_not_in_citation 4 |
| d40000275df6 | required_documents | 100 | 64 | 2 | 2 | - |
| 28ad40ea4b1f | eligibility | 7 | 69 | 6 | 6 | - |
| 28ad40ea4b1f | deadlines | 61 | 58 | 4 | 4 | - |
| 28ad40ea4b1f | required_documents | 85 | 53 | 8 | 8 | - |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
