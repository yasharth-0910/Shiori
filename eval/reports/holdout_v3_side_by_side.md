# Hold-out score of the frozen hybrid extractor (holdout_hybrid_v3, holdout_rules)

One scoring run each, 2026-11-16, on five open dev documents: 58f13b9c, a81e99fe, d230e51e, 6b7142ab, 594c3cb6. Freeze record `hybrid_freeze_dev_hybrid_v3.md`; all five file hashes matched before the run. No prompt, cue, rule, label or code was changed. No cloud call. Source reports: `run_holdout_hybrid_v3.md`, `hybrid_holdout_hybrid_v3.md`, `hybrid_diagnostic_holdout_hybrid_v3.md`, `run_holdout_rules.md`; dev-9 figures from `run_dev_hybrid_v3.md`, `run_dev_rules.md`, `hybrid_dev_hybrid_v3.md`, `hybrid_diagnostic_dev_hybrid_v3.md`.

## Read this first

- Five open notices only (no bid_instructions, no spec). The dev-9 set has 6 notices, 2 bid_instructions and 1 spec, so the two columns are not the same mix. Seconds per document are not comparable for that reason (the two bid_instructions documents took 417 and 185 s).
- Labels were reviewed by model reviewers (D-41), not by a person who reads Japanese.
- Candidates came from Gemini and Qwen3.5-9B, and Qwen3.5-9B is also the extractor's model, so the hold-out leans toward the extractor (D-50).
- n is small (5 documents, 115 field slots, 60 list label items). Every rate carries its counts; differences of a few items are noise.
- The prompts and cues were tuned on the dev-9. The hold-out documents were not used for that, but they are open dev documents of the same kind and sources.

## Verified accuracy, dev-9 next to hold-out

| group | rules dev-9 | rules hold-out | hybrid dev-9 | hybrid hold-out |
| --- | --- | --- | --- | --- |
| all fields, verified | 84 of 186 (45%) | 45 of 115 (39%) | 89 of 186 (48%) | 49 of 115 (43%) |
| tier 1, verified | 42 of 80 (52%) | 24 of 50 (48%) | 45 of 80 (56%) | 25 of 50 (50%) |
| 8 rules fields, verified | 61 of 62 (98%) | 39 of 40 (98%) | 61 of 62 (98%) | 39 of 40 (98%) |
| 3 list fields, verified (whole field) | 1 of 24 (4%) | 0 of 15 (0%) | 6 of 24 (25%) | 4 of 15 (27%) |

Per field, verified accuracy:

| field | rules dev-9 | rules hold-out | hybrid dev-9 | hybrid hold-out |
| --- | --- | --- | --- | --- |
| notice_date | 6 of 6 (100%) | 5 of 5 (100%) | 6 of 6 (100%) | 5 of 5 (100%) |
| procurement_type | 7 of 8 (88%) | 5 of 5 (100%) | 7 of 8 (88%) | 5 of 5 (100%) |
| bid_bond | 8 of 8 (100%) | 5 of 5 (100%) | 8 of 8 (100%) | 5 of 5 (100%) |
| performance_bond | 8 of 8 (100%) | 5 of 5 (100%) | 8 of 8 (100%) | 5 of 5 (100%) |
| tax_basis | 8 of 8 (100%) | 5 of 5 (100%) | 8 of 8 (100%) | 5 of 5 (100%) |
| unified_qualification | 8 of 8 (100%) | 4 of 5 (80%) | 8 of 8 (100%) | 4 of 5 (80%) |
| language_currency | 8 of 8 (100%) | 5 of 5 (100%) | 8 of 8 (100%) | 5 of 5 (100%) |
| wto_covered | 8 of 8 (100%) | 5 of 5 (100%) | 8 of 8 (100%) | 5 of 5 (100%) |
| eligibility | 1 of 8 (12%) | 0 of 5 (0%) | 1 of 8 (12%) | 0 of 5 (0%) |
| deadlines | 0 of 8 (0%) | 0 of 5 (0%) | 3 of 8 (38%) | 1 of 5 (20%) |
| required_documents | 0 of 8 (0%) | 0 of 5 (0%) | 2 of 8 (25%) | 3 of 5 (60%) |

The 8 rules fields are the ones in `RULES` in `rules.py`. The hybrid and rules columns are identical for them by design (the hybrid only adds the three list fields).

## List fields: item precision, item recall, whole field

| field | dev-9 precision | hold-out precision | dev-9 recall | hold-out recall | dev-9 whole-field | hold-out whole-field |
| --- | --- | --- | --- | --- | --- | --- |
| eligibility | 24 of 40 (60%) | 25 of 31 (81%) | 24 of 53 (45%) | 25 of 27 (93%) | 1 of 8 | 0 of 5 |
| deadlines | 12 of 18 (67%) | 12 of 17 (71%) | 12 of 23 (52%) | 12 of 19 (63%) | 3 of 8 | 1 of 5 |
| required_documents | 38 of 45 (84%) | 12 of 13 (92%) | 38 of 51 (75%) | 12 of 14 (86%) | 2 of 8 | 3 of 5 |
| all three | 74 of 103 (72%) | 49 of 61 (80%) | 74 of 127 (58%) | 49 of 60 (82%) | 6 of 24 (25%) | 4 of 15 (27%) |

Note: the hold-out documents mostly have short, simple eligibility lists (27 items over 5 documents against 53 over 8). Rules-only gets 0 of 15 on the list fields on the hold-out (1 of 24 on dev-9).

## Cost and drops

| | dev-9 | hold-out |
| --- | --- | --- |
| dropped items (failed a check) | 10 of 113 (9%) | 11 of 72 (15%) |
| drop reasons | date_or_time_not_in_citation 8, unknown_id 1, value_not_in_citation 1 | date_or_time_not_in_citation 3, duplicate 8 |
| seconds per document (model calls) | 130 (9 documents, 2 long) | 95 (5 notices) |
| seconds per call | 51 | 32 |
| calls retried / not found after retry | 0 / 0 | 0 / 0 |

Hold-out wrong value shown (hybrid): 11 of 115; hallucination 2 of 54 (both eligibility; dev-9: 17 of 186 and 0 of 70). Rules: 1 of 115 and 0 of 40. The 2 value-in-citation misses are in eligibility; I did not open them further (no tuning).

## Miss categories (a to d)

Order of tests: hit, then c (dropped by a check), then d (answer shares a cited sentence but does not pair), then a (no label sentence sent) or b (sent, not produced).

| | dev-9 (127 label items) | hold-out (60 label items) |
| --- | --- | --- |
| hit | 74 (58%) | 49 (82%) |
| a: not in window | 9 | 1 |
| b: not produced | 10 | 2 |
| c: dropped by a check | 2 | 0 |
| d: wrong value or kind | 32 | 8 |
| answer items with no label item | 29 | 12 |

By field (hit / a / b / c / d):

| field | dev-9 | hold-out |
| --- | --- | --- |
| eligibility | 24 / 8 / 1 / 1 / 19 of 53 | 25 / 1 / 0 / 0 / 1 of 27 |
| deadlines | 12 / 1 / 2 / 1 / 7 of 23 | 12 / 0 / 1 / 0 / 6 of 19 |
| required_documents | 38 / 0 / 7 / 0 / 6 of 51 | 12 / 0 / 1 / 0 / 1 of 14 |

Hold-out category d, from the diagnostic: 4 d1 (1 convention, 3 real, all deadlines kind except one eligibility), 1 d3 real (required_documents), 3 d5 real (deadlines datetime or flags). Same labels as the written readings in the diagnostic; these are my readings, not a native speaker's. Deadlines is the weak field on the hold-out: 1 of 5 whole-field, 6 of 19 label items in category d.

Caveat on how these counts were made: `eval.hybrid --diagnose holdout_hybrid_v3` counts every labeled dev document, including the nine dev-9 documents, which have no trace in this run, so its file shows 187 label items and 128 in category a. All of those extra items are dev-9 items with no answer, so the hold-out counts above are the diagnostic's counts minus the dev-9 counts (127 items, a 53 / 23 / 51 for the three fields). The subtraction reproduces the per-field totals (27, 19, 14) and the 49 hits exactly. The file `hybrid_diagnostic_holdout_hybrid_v3.md` itself is therefore not a clean hold-out table; use this one. I did not edit the code.

## What the numbers say (no tuning follows from them)

- Rules fields: 39 of 40 on the hold-out against 61 of 62 on dev-9; one miss (unified_qualification). They held up.
- List fields: precision and recall are higher on the hold-out than on dev-9, but whole-field accuracy is about the same (4 of 15 against 6 of 24), because one extra or missing item makes a field wrong. Part of the gap in recall is the document mix (no bid_instructions here), not generalization.
- Overall verified accuracy is 43% (hybrid) against 39% (rules) on the hold-out; 48% against 45% on dev-9. Most of the remaining slots are text and structured fields no extractor answers yet (title, scope_summary, issuer_org and similar: not found in all 5 documents).
