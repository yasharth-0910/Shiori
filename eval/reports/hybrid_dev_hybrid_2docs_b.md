# Hybrid extractor: list fields (dev_hybrid_2docs_b)

Rules for everything they answer, `Qwen3.5-9B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 2 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-16T11:14:21+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on, and the examples in the prompt come from documents of this set. The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on, and the examples in the prompt come from documents of this set. The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 9 of 17 (53%) | 9 of 19 (47%) | 0 of 6 (0%) | 0 of 6 (0%) | 0 of 17 (0%) | 56 (model calls only) | 19 |
| rules only (0 items by design) | - (0 items given) | 0 of 19 (0%) | 0 of 6 (0%) | 0 of 6 (0%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (6 fields here).

Calls: 6 calls, 0 failed (none). Items proposed 17, kept 17; dropped by reason: none.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on, and the examples in the prompt come from documents of this set. The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 5 of 10 (50%) | 5 of 10 (50%) | 0 of 2 (0%) | 0 of 2 (0%) |
| deadlines | 3 of 5 (60%) | 3 of 5 (60%) | 0 of 2 (0%) | 0 of 2 (0%) |
| required_documents | 1 of 2 (50%) | 1 of 4 (25%) | 0 of 2 (0%) | 0 of 2 (0%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on, and the examples in the prompt come from documents of this set. The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| 136dfba9ee59 | notice | 51 | 4 / 9 / 8 | 0 |
| 563042df9941 | notice | 61 | 5 / 10 / 9 | 0 |

## Calls

| document | field | sentences sent | seconds | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- |
| 136dfba9ee59 | eligibility | 28 | 33 | 5 | 5 | - |
| 136dfba9ee59 | deadlines | 11 | 13 | 2 | 2 | - |
| 136dfba9ee59 | required_documents | 11 | 5 | 1 | 1 | - |
| 563042df9941 | eligibility | 8 | 27 | 5 | 5 | - |
| 563042df9941 | deadlines | 13 | 27 | 3 | 3 | - |
| 563042df9941 | required_documents | 13 | 8 | 1 | 1 | - |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
