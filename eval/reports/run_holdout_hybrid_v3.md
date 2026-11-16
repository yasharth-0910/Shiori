# Eval run holdout_hybrid_v3

Split `dev`, extractor `hybrid`, extractor version 0.3.0, schema 1.0.0, commit 2a52834a5ff3d42a112f7675b8ec8fea49cfac2d, 2026-11-16T13:29:17+00:00.

Scores are against model-reviewed silver labels, not human-verified ones (D-41). Only fields asked of the document's type are scored. No cloud call and no document text in this report.

Documents scored: 5 of 5 in the dev label set. Label lines reviewed by a model: 70 of 115 (61%).

| rate | count | out of |
| --- | --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) (all asked fields with a label) | 49 of 115 (43%) | |
| Value accuracy (citations ignored) (all asked fields with a label) | 49 of 115 (43%) | |
| Citation exists rate (fields shown as present) | 54 of 54 (100%) | |
| Value-in-citation rate (fields shown as present) | 52 of 54 (96%) | |
| Not-found rate (all asked fields with a label) | 61 of 115 (53%) | |
| Hallucination rate (shown, value not in the cited sentences) (fields shown as present) | 2 of 54 (4%) | |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) (all asked fields with a label) | 11 of 115 (10%) | |
| Over-abstention rate (label present, not found) (fields whose label is present) | 43 of 97 (44%) | |

## Tier 1 fields

| rate | count |
| --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) | 25 of 50 (50%) |
| Value accuracy (citations ignored) | 25 of 50 (50%) |
| Citation exists rate | 34 of 34 (100%) |
| Value-in-citation rate | 32 of 34 (94%) |
| Not-found rate | 16 of 50 (32%) |
| Hallucination rate (shown, value not in the cited sentences) | 2 of 34 (6%) |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) | 9 of 50 (18%) |
| Over-abstention rate (label present, not found) | 16 of 50 (32%) |

## By field type

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| list | 4 of 15 (27%) | 4 of 15 (27%) | 1 of 15 (7%) | 2 of 14 (14%) |
| structured | 44 of 80 (55%) | 44 of 80 (55%) | 40 of 80 (50%) | 0 of 40 (0%) |
| text | 1 of 20 (5%) | 1 of 20 (5%) | 20 of 20 (100%) | - (0 of 0) |

## By field

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| award_method | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| bid_bond | 5 of 5 (100%) | 5 of 5 (100%) | 0 of 5 (0%) | 0 of 5 (0%) |
| contact | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| contracting_officer | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| deadlines | 1 of 5 (20%) | 1 of 5 (20%) | 1 of 5 (20%) | 0 of 4 (0%) |
| delivery_deadline | 5 of 5 (100%) | 5 of 5 (100%) | 5 of 5 (100%) | - (0 of 0) |
| delivery_location | 1 of 5 (20%) | 1 of 5 (20%) | 5 of 5 (100%) | - (0 of 0) |
| eligibility | 0 of 5 (0%) | 0 of 5 (0%) | 0 of 5 (0%) | 2 of 5 (40%) |
| issuer_org | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| item_category | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| language_currency | 5 of 5 (100%) | 5 of 5 (100%) | 0 of 5 (0%) | 0 of 5 (0%) |
| notice_date | 5 of 5 (100%) | 5 of 5 (100%) | 0 of 5 (0%) | 0 of 5 (0%) |
| performance_bond | 5 of 5 (100%) | 5 of 5 (100%) | 0 of 5 (0%) | 0 of 5 (0%) |
| performance_period | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| procurement_type | 5 of 5 (100%) | 5 of 5 (100%) | 0 of 5 (0%) | 0 of 5 (0%) |
| required_documents | 3 of 5 (60%) | 3 of 5 (60%) | 0 of 5 (0%) | 0 of 5 (0%) |
| scope_summary | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| spec_access | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| submission_modes | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| tax_basis | 5 of 5 (100%) | 5 of 5 (100%) | 0 of 5 (0%) | 0 of 5 (0%) |
| title | 0 of 5 (0%) | 0 of 5 (0%) | 5 of 5 (100%) | - (0 of 0) |
| unified_qualification | 4 of 5 (80%) | 4 of 5 (80%) | 0 of 5 (0%) | 0 of 5 (0%) |
| wto_covered | 5 of 5 (100%) | 5 of 5 (100%) | 0 of 5 (0%) | 0 of 5 (0%) |

## Skipped (0): no label file

- none
