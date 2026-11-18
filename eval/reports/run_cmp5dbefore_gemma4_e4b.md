# Eval run cmp5dbefore_gemma4_e4b

Split `dev`, extractor `hybrid`, extractor version 0.3.0, schema 1.0.0, commit 6827bfff4780a57237f0a34a3a23b94ee598f514, 2026-11-18T12:46:16+00:00.

Scores are against model-reviewed silver labels, not human-verified ones (D-41). Only fields asked of the document's type are scored. No cloud call and no document text in this report.

Documents scored: 1 of 1 in the dev label set. Label lines reviewed by a model: 12 of 23 (52%).

| rate | count | out of |
| --- | --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) (all asked fields with a label) | 9 of 23 (39%) | |
| Value accuracy (citations ignored) (all asked fields with a label) | 9 of 23 (39%) | |
| Citation exists rate (fields shown as present) | 13 of 13 (100%) | |
| Value-in-citation rate (fields shown as present) | 13 of 13 (100%) | |
| Not-found rate (all asked fields with a label) | 10 of 23 (43%) | |
| Hallucination rate (shown, value not in the cited sentences) (fields shown as present) | 0 of 13 (0%) | |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) (all asked fields with a label) | 4 of 23 (17%) | |
| Over-abstention rate (label present, not found) (fields whose label is present) | 8 of 21 (38%) | |

## Tier 1 fields

| rate | count |
| --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) | 5 of 10 (50%) |
| Value accuracy (citations ignored) | 5 of 10 (50%) |
| Citation exists rate | 8 of 8 (100%) |
| Value-in-citation rate | 8 of 8 (100%) |
| Not-found rate | 2 of 10 (20%) |
| Hallucination rate (shown, value not in the cited sentences) | 0 of 8 (0%) |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) | 3 of 10 (30%) |
| Over-abstention rate (label present, not found) | 1 of 9 (11%) |

## By field type

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| list | 0 of 3 (0%) | 0 of 3 (0%) | 0 of 3 (0%) | 0 of 3 (0%) |
| structured | 9 of 16 (56%) | 9 of 16 (56%) | 6 of 16 (38%) | 0 of 10 (0%) |
| text | 0 of 4 (0%) | 0 of 4 (0%) | 4 of 4 (100%) | - (0 of 0) |

## By field

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| award_method | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| bid_bond | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| contact | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| contracting_officer | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| deadlines | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) |
| delivery_deadline | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| delivery_location | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| eligibility | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) |
| issuer_org | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| item_category | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| language_currency | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| notice_date | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| performance_bond | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| performance_period | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| procurement_type | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| required_documents | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) |
| scope_summary | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| spec_access | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| submission_modes | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) | 0 of 1 (0%) |
| tax_basis | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |
| title | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| unified_qualification | 0 of 1 (0%) | 0 of 1 (0%) | 1 of 1 (100%) | - (0 of 0) |
| wto_covered | 1 of 1 (100%) | 1 of 1 (100%) | 0 of 1 (0%) | 0 of 1 (0%) |

## Skipped (0): no label file

- none
