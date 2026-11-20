# Eval run portal_guard

Split `dev`, extractor `hybrid`, extractor version 0.3.0, schema 1.0.0, commit 5992991b85d64228eb3c5908d943d423dc45c378, 2026-11-20T22:53:21+00:00.

Scores are against model-reviewed silver labels, not human-verified ones (D-41). Only fields asked of the document's type are scored. No cloud call and no document text in this report.

Documents scored: 1 of 1 in the dev label set. Label lines reviewed by a model: 12 of 23 (52%).

| rate | count | out of |
| --- | --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) (all asked fields with a label) | 19 of 23 (83%) | |
| Value accuracy (citations ignored) (all asked fields with a label) | 19 of 23 (83%) | |
| Citation exists rate (fields shown as present) | 16 of 16 (100%) | |
| Value-in-citation rate (fields shown as present) | 16 of 16 (100%) | |
| Not-found rate (all asked fields with a label) | 6 of 23 (26%) | |
| Hallucination rate (shown, value not in the cited sentences) (fields shown as present) | 0 of 16 (0%) | |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) (all asked fields with a label) | 2 of 23 (9%) | |
| Over-abstention rate (label present, not found) (fields whose label is present) | 0 of 16 (0%) | |

## Tier 1 fields

| rate | count |
| --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) | 9 of 10 (90%) |
| Value accuracy (citations ignored) | 9 of 10 (90%) |
| Citation exists rate | 9 of 9 (100%) |
| Value-in-citation rate | 9 of 9 (100%) |
| Not-found rate | 0 of 10 (0%) |
| Hallucination rate (shown, value not in the cited sentences) | 0 of 9 (0%) |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) | 1 of 10 (10%) |
| Over-abstention rate (label present, not found) | 0 of 9 (0%) |

## By field type

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| list | 1 of 3 (33%) | 1 of 3 (33%) | 0 of 3 (0%) | 0 of 3 (0%) |
| structured | 16 of 16 (100%) | 16 of 16 (100%) | 4 of 16 (25%) | 0 of 11 (0%) |
| text | 2 of 4 (50%) | 2 of 4 (50%) | 2 of 4 (50%) | 0 of 2 (0%) |

## By field

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| award_method | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| bid_bond | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| contact | 1 of 1 (100%) | 1 of 1 (100%) | 1 of 1 (100%) | - (0 of 0) |
| contracting_officer | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| deadlines | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) |
| delivery_deadline | 1 of 1 (100%) | 1 of 1 (100%) | 1 of 1 (100%) | - (0 of 0) |
| delivery_location | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| eligibility | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| issuer_org | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| item_category | 1 of 1 (100%) | 1 of 1 (100%) | 1 of 1 (100%) | - (0 of 0) |
| language_currency | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| notice_date | 1 of 1 (100%) | 1 of 1 (100%) | 1 of 1 (100%) | - (0 of 0) |
| performance_bond | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| performance_period | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| procurement_type | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| required_documents | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) |
| scope_summary | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| spec_access | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | - (0 of 0) |
| submission_modes | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| tax_basis | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| title | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| unified_qualification | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| wto_covered | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |

## Skipped (0): no label file

- none
