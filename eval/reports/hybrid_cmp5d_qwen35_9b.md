# Hybrid extractor: list fields (cmp5d_qwen35_9b)

Rules for everything they answer, `Qwen3.5-9B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 1 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-18T12:36:24+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 9 of 12 (75%) | 9 of 11 (82%) | 1 of 3 (33%) | 1 of 3 (33%) | 4 of 16 (25%) | 196 (model calls only) | 65 |
| rules only (0 items by design) | - (0 items given) | 0 of 11 (0%) | 0 of 3 (0%) | 0 of 3 (0%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (3 fields here).

Calls: 3 calls (0 retried), 0 not found after the retry (none). Items proposed 16, kept 12; dropped by reason: duplicate 3.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 4 of 4 (100%) | 4 of 4 (100%) | 1 of 1 (100%) | 1 of 1 (100%) |
| deadlines | 3 of 6 (50%) | 3 of 3 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| required_documents | 2 of 2 (100%) | 2 of 4 (50%) | 0 of 1 (0%) | 0 of 1 (0%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| 5d75d4a67c71 | notice | 196 | 9 / 11 / 12 | 3 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5d75d4a67c71 | eligibility | 19 | 90 | 0 | 8 | 4 | duplicate 3 |
| 5d75d4a67c71 | deadlines | 9 | 80 | 0 | 6 | 6 | - |
| 5d75d4a67c71 | required_documents | 20 | 27 | 0 | 2 | 2 | - |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
