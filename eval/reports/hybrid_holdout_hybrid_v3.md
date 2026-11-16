# Hybrid extractor: list fields (holdout_hybrid_v3)

Rules for everything they answer, `Qwen3.5-9B-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 5 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-16T13:29:17+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | 49 of 61 (80%) | 49 of 60 (82%) | 4 of 15 (27%) | 4 of 15 (27%) | 11 of 72 (15%) | 95 (model calls only) | 32 |
| rules only (0 items by design) | - (0 items given) | 0 of 60 (0%) | 0 of 15 (0%) | 0 of 15 (0%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (15 fields here).

Calls: 15 calls (0 retried), 0 not found after the retry (none). Items proposed 72, kept 61; dropped by reason: date_or_time_not_in_citation 3, duplicate 8.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | 25 of 31 (81%) | 25 of 27 (93%) | 0 of 5 (0%) | 0 of 5 (0%) |
| deadlines | 12 of 17 (71%) | 12 of 19 (63%) | 1 of 5 (20%) | 1 of 5 (20%) |
| required_documents | 12 of 13 (92%) | 12 of 14 (86%) | 3 of 5 (60%) | 3 of 5 (60%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| 58f13b9c2e87 | notice | 61 | 6 / 10 / 8 | 3 |
| a81e99fecea5 | notice | 99 | 14 / 18 / 18 | 0 |
| d230e51e2805 | notice | 119 | 11 / 11 / 13 | 4 |
| 6b7142ab74f4 | notice | 109 | 8 / 10 / 11 | 4 |
| 594c3cb69c53 | notice | 89 | 10 / 11 / 11 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 58f13b9c2e87 | eligibility | 19 | 29 | 0 | 5 | 5 | - |
| 58f13b9c2e87 | deadlines | 10 | 20 | 0 | 3 | 0 | date_or_time_not_in_citation 3 |
| 58f13b9c2e87 | required_documents | 18 | 12 | 0 | 3 | 3 | - |
| a81e99fecea5 | eligibility | 22 | 41 | 0 | 8 | 8 | - |
| a81e99fecea5 | deadlines | 16 | 36 | 0 | 6 | 6 | - |
| a81e99fecea5 | required_documents | 35 | 22 | 0 | 4 | 4 | - |
| d230e51e2805 | eligibility | 20 | 68 | 0 | 10 | 6 | duplicate 4 |
| d230e51e2805 | deadlines | 18 | 36 | 0 | 5 | 5 | - |
| d230e51e2805 | required_documents | 27 | 14 | 0 | 2 | 2 | - |
| 6b7142ab74f4 | eligibility | 20 | 68 | 0 | 10 | 6 | duplicate 4 |
| 6b7142ab74f4 | deadlines | 9 | 25 | 0 | 3 | 3 | - |
| 6b7142ab74f4 | required_documents | 22 | 15 | 0 | 2 | 2 | - |
| 594c3cb69c53 | eligibility | 20 | 48 | 0 | 6 | 6 | - |
| 594c3cb69c53 | deadlines | 8 | 23 | 0 | 3 | 3 | - |
| 594c3cb69c53 | required_documents | 22 | 18 | 0 | 2 | 2 | - |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
