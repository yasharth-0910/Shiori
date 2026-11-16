# Eval run dev_hybrid_2docs

Split `dev`, extractor `hybrid`, extractor version 0.3.0, schema 1.0.0, commit 78fac4186849dd10c78dce65309052db33a5a6b9, 2026-11-16T11:11:36+00:00.

Scores are against model-reviewed silver labels, not human-verified ones (D-41). Only fields asked of the document's type are scored. No cloud call and no document text in this report.

Documents scored: 2 of 2 in the dev label set. Label lines reviewed by a model: 28 of 46 (61%).

| rate | count | out of |
| --- | --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) (all asked fields with a label) | 20 of 46 (43%) | |
| Value accuracy (citations ignored) (all asked fields with a label) | 20 of 46 (43%) | |
| Citation exists rate (fields shown as present) | 19 of 19 (100%) | |
| Value-in-citation rate (fields shown as present) | 19 of 19 (100%) | |
| Not-found rate (all asked fields with a label) | 27 of 46 (59%) | |
| Hallucination rate (shown, value not in the cited sentences) (fields shown as present) | 0 of 19 (0%) | |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) (all asked fields with a label) | 4 of 46 (9%) | |
| Over-abstention rate (label present, not found) (fields whose label is present) | 16 of 35 (46%) | |

## Tier 1 fields

| rate | count |
| --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) | 10 of 20 (50%) |
| Value accuracy (citations ignored) | 10 of 20 (50%) |
| Citation exists rate | 14 of 14 (100%) |
| Value-in-citation rate | 14 of 14 (100%) |
| Not-found rate | 6 of 20 (30%) |
| Hallucination rate (shown, value not in the cited sentences) | 0 of 14 (0%) |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) | 4 of 20 (20%) |
| Over-abstention rate (label present, not found) | 4 of 18 (22%) |

## By field type

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| list | 0 of 6 (0%) | 0 of 6 (0%) | 2 of 6 (33%) | 0 of 4 (0%) |
| structured | 20 of 32 (62%) | 20 of 32 (62%) | 17 of 32 (53%) | 0 of 15 (0%) |
| text | 0 of 8 (0%) | 0 of 8 (0%) | 8 of 8 (100%) | - (0 of 0) |

## By field

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| award_method | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| bid_bond | 2 of 2 (100%) | 2 of 2 (100%) | 0 of 2 (0%) | 0 of 2 (0%) |
| contact | 1 of 2 (50%) | 1 of 2 (50%) | 2 of 2 (100%) | - (0 of 0) |
| contracting_officer | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| deadlines | 0 of 2 (0%) | 0 of 2 (0%) | 0 of 2 (0%) | 0 of 2 (0%) |
| delivery_deadline | 2 of 2 (100%) | 2 of 2 (100%) | 2 of 2 (100%) | - (0 of 0) |
| delivery_location | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| eligibility | 0 of 2 (0%) | 0 of 2 (0%) | 0 of 2 (0%) | 0 of 2 (0%) |
| issuer_org | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| item_category | 1 of 2 (50%) | 1 of 2 (50%) | 2 of 2 (100%) | - (0 of 0) |
| language_currency | 2 of 2 (100%) | 2 of 2 (100%) | 0 of 2 (0%) | 0 of 2 (0%) |
| notice_date | 2 of 2 (100%) | 2 of 2 (100%) | 1 of 2 (50%) | 0 of 1 (0%) |
| performance_bond | 2 of 2 (100%) | 2 of 2 (100%) | 0 of 2 (0%) | 0 of 2 (0%) |
| performance_period | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| procurement_type | 2 of 2 (100%) | 2 of 2 (100%) | 0 of 2 (0%) | 0 of 2 (0%) |
| required_documents | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| scope_summary | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| spec_access | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| submission_modes | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| tax_basis | 2 of 2 (100%) | 2 of 2 (100%) | 0 of 2 (0%) | 0 of 2 (0%) |
| title | 0 of 2 (0%) | 0 of 2 (0%) | 2 of 2 (100%) | - (0 of 0) |
| unified_qualification | 2 of 2 (100%) | 2 of 2 (100%) | 0 of 2 (0%) | 0 of 2 (0%) |
| wto_covered | 2 of 2 (100%) | 2 of 2 (100%) | 0 of 2 (0%) | 0 of 2 (0%) |

## Skipped (0): no label file

- none
