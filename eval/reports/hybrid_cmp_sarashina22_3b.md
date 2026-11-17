# Hybrid extractor: list fields (cmp_sarashina22_3b)

Rules for everything they answer, `sarashina2.2-3b-instruct-v0.1-Q4_K_M.gguf` through llama-server on 127.0.0.1 for eligibility, deadlines and required_documents. Split `dev`, 14 documents scored, extractor version 0.3.0, schema 1.0.0, 2026-11-17T20:30:04+00:00. Retrieval: sections whose heading holds a field cue plus 3 sentences each side, at most 7000 characters; one call per field; JSON-schema output; every item checked against its cited sentences.

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## The three list fields, hybrid against the rules extractor and the grouped bake-off

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| extractor | item precision | item recall | whole-field accuracy (value correct) | whole-field verified | dropped items (failed a check) | seconds per document | seconds per call |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid (rules + model) | - (0 of 0) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - (0 of 0) | 74 (model calls only) | 27 |
| rules only (0 items by design) | - (0 items given) | 0 of 187 (0%) | 1 of 39 (3%) | 1 of 39 (3%) | - | 0 | - |
| grouped bake-off, Qwen3.5-9B (all 23 fields in grouped calls, 5 pilot documents) | not measured | not measured | 1 of 12 (8%) | not measured | not measured | 419 to 1530 (all fields) | not measured |

Item precision = answer items paired one to one with a label item (eval.silver.compare.item_pairs, the agreement rule the harness uses) over answer items; recall = the same pairs over label items. Whole-field accuracy is the harness's value rule: every item must pair, so one extra or missing item makes the whole field wrong. The rules row counts the fields whose label is absent as correct. The bake-off row is from `eval/reports/local_labeler_bakeoff.md` (D-67): 5 pilot documents, different prompt, all fields in one grouped call, so it is a reference point and not the same denominator (39 fields here).

Calls: 38 calls (38 retried), 38 not found after the retry (HTTPError). Items proposed 0, kept 0; dropped by reason: none.

## By field

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| field | item precision | item recall | whole-field (value correct) | whole-field verified |
| --- | --- | --- | --- | --- |
| eligibility | - (0 of 0) | 0 of 80 (0%) | 1 of 13 (8%) | 1 of 13 (8%) |
| deadlines | - (0 of 0) | 0 of 42 (0%) | 0 of 13 (0%) | 0 of 13 (0%) |
| required_documents | - (0 of 0) | 0 of 65 (0%) | 0 of 13 (0%) | 0 of 13 (0%) |

## By document

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

| document | type | model seconds | items paired / label items / answer items | dropped items |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | notice | 17 | 0 / 8 / 0 | 0 |
| 58f13b9c2e87 | notice | 44 | 0 / 10 / 0 | 0 |
| a81e99fecea5 | notice | 72 | 0 / 18 / 0 | 0 |
| 136dfba9ee59 | notice | 38 | 0 / 9 / 0 | 0 |
| d230e51e2805 | notice | 58 | 0 / 11 / 0 | 0 |
| 6b7142ab74f4 | notice | 50 | 0 / 10 / 0 | 0 |
| 84e9d0c8325c | notice | 65 | 0 / 16 / 0 | 0 |
| 594c3cb69c53 | notice | 19 | 0 / 11 / 0 | 0 |
| a13baaac55c8 | notice | 18 | 0 / 17 / 0 | 0 |
| 563042df9941 | notice | 68 | 0 / 10 / 0 | 0 |
| 4b0b9d8229c7 | notice | 30 | 0 / 5 / 0 | 0 |
| d40000275df6 | bid_instructions | 432 | 0 / 37 / 0 | 0 |
| 28ad40ea4b1f | bid_instructions | 121 | 0 / 25 / 0 | 0 |
| 4c40bbd831fe | spec | 0 | 0 / 0 / 0 | 0 |

## Calls

| document | field | sentences sent | seconds | retries | items proposed | kept | dropped by reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | eligibility | 20 | 7 | 1 | 0 | 0 | HTTPError |
| f19cddbd4cba | deadlines | 9 | 5 | 1 | 0 | 0 | HTTPError |
| f19cddbd4cba | required_documents | 22 | 5 | 1 | 0 | 0 | HTTPError |
| 58f13b9c2e87 | eligibility | 19 | 3 | 1 | 0 | 0 | HTTPError |
| 58f13b9c2e87 | deadlines | 10 | 34 | 1 | 0 | 0 | HTTPError |
| 58f13b9c2e87 | required_documents | 18 | 7 | 1 | 0 | 0 | HTTPError |
| a81e99fecea5 | eligibility | 22 | 3 | 1 | 0 | 0 | HTTPError |
| a81e99fecea5 | deadlines | 16 | 63 | 1 | 0 | 0 | HTTPError |
| a81e99fecea5 | required_documents | 35 | 5 | 1 | 0 | 0 | HTTPError |
| 136dfba9ee59 | eligibility | 28 | 3 | 1 | 0 | 0 | HTTPError |
| 136dfba9ee59 | deadlines | 11 | 30 | 1 | 0 | 0 | HTTPError |
| 136dfba9ee59 | required_documents | 38 | 5 | 1 | 0 | 0 | HTTPError |
| d230e51e2805 | eligibility | 20 | 16 | 1 | 0 | 0 | HTTPError |
| d230e51e2805 | deadlines | 18 | 37 | 1 | 0 | 0 | HTTPError |
| d230e51e2805 | required_documents | 27 | 5 | 1 | 0 | 0 | HTTPError |
| 6b7142ab74f4 | eligibility | 20 | 6 | 1 | 0 | 0 | HTTPError |
| 6b7142ab74f4 | deadlines | 9 | 39 | 1 | 0 | 0 | HTTPError |
| 6b7142ab74f4 | required_documents | 22 | 5 | 1 | 0 | 0 | HTTPError |
| 84e9d0c8325c | eligibility | 22 | 4 | 1 | 0 | 0 | HTTPError |
| 84e9d0c8325c | deadlines | 16 | 56 | 1 | 0 | 0 | HTTPError |
| 84e9d0c8325c | required_documents | 35 | 5 | 1 | 0 | 0 | HTTPError |
| 594c3cb69c53 | eligibility | 20 | 5 | 1 | 0 | 0 | HTTPError |
| 594c3cb69c53 | deadlines | 8 | 2 | 1 | 0 | 0 | HTTPError |
| 594c3cb69c53 | required_documents | 22 | 11 | 1 | 0 | 0 | HTTPError |
| a13baaac55c8 | eligibility | 17 | 3 | 1 | 0 | 0 | HTTPError |
| a13baaac55c8 | deadlines | 30 | 6 | 1 | 0 | 0 | HTTPError |
| a13baaac55c8 | required_documents | 67 | 9 | 1 | 0 | 0 | HTTPError |
| 563042df9941 | eligibility | 8 | 53 | 1 | 0 | 0 | HTTPError |
| 563042df9941 | deadlines | 13 | 2 | 1 | 0 | 0 | HTTPError |
| 563042df9941 | required_documents | 31 | 13 | 1 | 0 | 0 | HTTPError |
| 4b0b9d8229c7 | deadlines | 14 | 29 | 1 | 0 | 0 | HTTPError |
| 4b0b9d8229c7 | required_documents | 14 | 2 | 1 | 0 | 0 | HTTPError |
| d40000275df6 | eligibility | 28 | 6 | 1 | 0 | 0 | HTTPError |
| d40000275df6 | deadlines | 82 | 395 | 1 | 0 | 0 | HTTPError |
| d40000275df6 | required_documents | 170 | 30 | 1 | 0 | 0 | HTTPError |
| 28ad40ea4b1f | eligibility | 7 | 90 | 1 | 0 | 0 | HTTPError |
| 28ad40ea4b1f | deadlines | 61 | 12 | 1 | 0 | 0 | HTTPError |
| 28ad40ea4b1f | required_documents | 105 | 18 | 1 | 0 | 0 | HTTPError |

## What this does not tell you

- Same documents for tuning and scoring, so the numbers are a fit, not a forecast. A hold-out of reviewed documents the prompt never saw is still needed (project_log.md, Phase 4).
- One run, temperature 0, one machine (MacBook Air M4). Seconds are not Windows 16 GB numbers.
- Documents that are not notice-like (specs) have no list fields and are not counted.
