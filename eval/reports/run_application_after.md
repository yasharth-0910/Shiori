# Eval run application_after

Split `dev`, extractor `hybrid`, extractor version 0.3.0, schema 1.1.0, commit 40412021c08af3840dba2fcd33c24d88e47c238b, 2026-11-21T17:52:50+00:00.

Scores are against model-reviewed silver labels, not human-verified ones (D-41). Only fields asked of the document's type are scored. No cloud call and no document text in this report.

Documents scored: 15 of 60 in the dev label set. Label lines reviewed by a model: 202 of 345 (59%).

| rate | count | out of |
| --- | --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) (all asked fields with a label) | 226 of 324 (70%) | |
| Value accuracy (citations ignored) (all asked fields with a label) | 227 of 324 (70%) | |
| Citation exists rate (fields shown as present) | 203 of 203 (100%) | |
| Value-in-citation rate (fields shown as present) | 202 of 203 (100%) | |
| Not-found rate (all asked fields with a label) | 114 of 324 (35%) | |
| Hallucination rate (shown, value not in the cited sentences) (fields shown as present) | 1 of 203 (0%) | |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) (all asked fields with a label) | 26 of 324 (8%) | |
| Over-abstention rate (label present, not found) (fields whose label is present) | 47 of 250 (19%) | |

## Tier 1 fields

| rate | count |
| --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) | 107 of 140 (76%) |
| Value accuracy (citations ignored) | 108 of 140 (77%) |
| Citation exists rate | 114 of 114 (100%) |
| Value-in-citation rate | 113 of 114 (99%) |
| Not-found rate | 24 of 140 (17%) |
| Hallucination rate (shown, value not in the cited sentences) | 1 of 114 (1%) |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) | 18 of 140 (13%) |
| Over-abstention rate (label present, not found) | 9 of 123 (7%) |

## By field type

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| list | 16 of 42 (38%) | 16 of 42 (38%) | 3 of 42 (7%) | 1 of 39 (3%) |
| structured | 181 of 222 (82%) | 182 of 222 (82%) | 75 of 222 (34%) | 0 of 140 (0%) |
| text | 29 of 60 (48%) | 29 of 60 (48%) | 36 of 60 (60%) | 0 of 24 (0%) |

## By field

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| award_method | 12 of 14 (86%) | 12 of 14 (86%) | 3 of 14 (21%) | 0 of 11 (0%) |
| bid_bond | 14 of 14 (100%) | 14 of 14 (100%) | 3 of 14 (21%) | 0 of 11 (0%) |
| contact | 2 of 14 (14%) | 2 of 14 (14%) | 14 of 14 (100%) | - (0 of 0) |
| contracting_officer | 13 of 14 (93%) | 13 of 14 (93%) | 4 of 14 (29%) | 0 of 10 (0%) |
| deadlines | 2 of 14 (14%) | 2 of 14 (14%) | 2 of 14 (14%) | 0 of 12 (0%) |
| delivery_deadline | 13 of 15 (87%) | 13 of 15 (87%) | 15 of 15 (100%) | - (0 of 0) |
| delivery_location | 5 of 15 (33%) | 5 of 15 (33%) | 15 of 15 (100%) | - (0 of 0) |
| eligibility | 8 of 14 (57%) | 8 of 14 (57%) | 1 of 14 (7%) | 1 of 13 (8%) |
| issuer_org | 10 of 15 (67%) | 10 of 15 (67%) | 5 of 15 (33%) | 0 of 10 (0%) |
| item_category | 3 of 12 (25%) | 3 of 12 (25%) | 12 of 12 (100%) | - (0 of 0) |
| language_currency | 14 of 14 (100%) | 14 of 14 (100%) | 2 of 14 (14%) | 0 of 12 (0%) |
| notice_date | 12 of 12 (100%) | 12 of 12 (100%) | 2 of 12 (17%) | 0 of 10 (0%) |
| performance_bond | 14 of 14 (100%) | 14 of 14 (100%) | 1 of 14 (7%) | 0 of 13 (0%) |
| performance_period | 13 of 15 (87%) | 13 of 15 (87%) | 2 of 15 (13%) | 0 of 8 (0%) |
| procurement_type | 13 of 14 (93%) | 14 of 14 (100%) | 0 of 14 (0%) | 0 of 14 (0%) |
| required_documents | 6 of 14 (43%) | 6 of 14 (43%) | 0 of 14 (0%) | 0 of 14 (0%) |
| scope_summary | 0 of 15 (0%) | 0 of 15 (0%) | 15 of 15 (100%) | - (0 of 0) |
| spec_access | 6 of 14 (43%) | 6 of 14 (43%) | 8 of 14 (57%) | 0 of 4 (0%) |
| submission_modes | 12 of 14 (86%) | 12 of 14 (86%) | 2 of 14 (14%) | 0 of 12 (0%) |
| tax_basis | 14 of 14 (100%) | 14 of 14 (100%) | 0 of 14 (0%) | 0 of 14 (0%) |
| title | 14 of 15 (93%) | 14 of 15 (93%) | 1 of 15 (7%) | 0 of 14 (0%) |
| unified_qualification | 12 of 14 (86%) | 12 of 14 (86%) | 4 of 14 (29%) | 0 of 10 (0%) |
| wto_covered | 14 of 14 (100%) | 14 of 14 (100%) | 3 of 14 (21%) | 0 of 11 (0%) |

## Skipped (45): no label file

- 01204a43ed1d
- 5720c2903850
- 435d2881b52d
- fb1253a58b2d
- 5d76c6a061ac
- 6a44715085ac
- db5c1723dc2b
- a697e69a7db8
- a90497874108
- f08ea5aea45f
- 2edf2494bef1
- 3fc322cb5b33
- b16ad9882fbc
- e420f76b7182
- 82fe582369e6
- 08558fc7fe0a
- bf99e8ba6a15
- a11d233c84ad
- e81e9338bfca
- 01e953d899ad
- 99044e933212
- 2ed05ba95b66
- 070b894ee590
- 08ec571dc30e
- 53320d90cf87
- 34ea5d0b8aa6
- e56028078517
- a2728e6bb87e
- 081d27569eac
- 11ead9a54403
- 8869632bb85c
- aeedf544969c
- bb10715a6a3b
- 67e636608c55
- 6387bfc31c98
- 12f50d0602ce
- 94b7145f88e2
- 9b6a573a3652
- 870f1f2ec726
- f31471b231db
- 03406dd6af8d
- fd637c1deea1
- ae487875206f
- 7e591bba3e4f
- 720e2a764fa5
