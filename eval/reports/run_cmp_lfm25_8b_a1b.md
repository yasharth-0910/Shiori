# Eval run cmp_lfm25_8b_a1b

Split `dev`, extractor `hybrid`, extractor version 0.3.0, schema 1.0.0, commit 828f1e6bf8d52027819f0ac5ee523b943082b062, 2026-11-17T20:12:38+00:00.

Scores are against model-reviewed silver labels, not human-verified ones (D-41). Only fields asked of the document's type are scored. No cloud call and no document text in this report.

Documents scored: 14 of 60 in the dev label set. Label lines reviewed by a model: 190 of 322 (59%).

| rate | count | out of |
| --- | --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) (all asked fields with a label) | 178 of 301 (59%) | |
| Value accuracy (citations ignored) (all asked fields with a label) | 179 of 301 (59%) | |
| Citation exists rate (fields shown as present) | 152 of 152 (100%) | |
| Value-in-citation rate (fields shown as present) | 152 of 152 (100%) | |
| Not-found rate (all asked fields with a label) | 142 of 301 (47%) | |
| Hallucination rate (shown, value not in the cited sentences) (fields shown as present) | 0 of 152 (0%) | |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) (all asked fields with a label) | 23 of 301 (8%) | |
| Over-abstention rate (label present, not found) (fields whose label is present) | 77 of 229 (34%) | |

## Tier 1 fields

| rate | count |
| --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) | 93 of 130 (72%) |
| Value accuracy (citations ignored) | 94 of 130 (72%) |
| Citation exists rate | 96 of 96 (100%) |
| Value-in-citation rate | 96 of 96 (100%) |
| Not-found rate | 32 of 130 (25%) |
| Hallucination rate (shown, value not in the cited sentences) | 0 of 96 (0%) |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) | 14 of 130 (11%) |
| Over-abstention rate (label present, not found) | 18 of 114 (16%) |

## By field type

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| list | 1 of 39 (3%) | 1 of 39 (3%) | 17 of 39 (44%) | 0 of 22 (0%) |
| structured | 172 of 206 (83%) | 173 of 206 (84%) | 69 of 206 (33%) | 0 of 130 (0%) |
| text | 5 of 56 (9%) | 5 of 56 (9%) | 56 of 56 (100%) | - (0 of 0) |

## By field

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| award_method | 11 of 13 (85%) | 11 of 13 (85%) | 3 of 13 (23%) | 0 of 10 (0%) |
| bid_bond | 13 of 13 (100%) | 13 of 13 (100%) | 3 of 13 (23%) | 0 of 10 (0%) |
| contact | 2 of 13 (15%) | 2 of 13 (15%) | 13 of 13 (100%) | - (0 of 0) |
| contracting_officer | 12 of 13 (92%) | 12 of 13 (92%) | 4 of 13 (31%) | 0 of 9 (0%) |
| deadlines | 0 of 13 (0%) | 0 of 13 (0%) | 11 of 13 (85%) | 0 of 2 (0%) |
| delivery_deadline | 13 of 14 (93%) | 13 of 14 (93%) | 14 of 14 (100%) | - (0 of 0) |
| delivery_location | 5 of 14 (36%) | 5 of 14 (36%) | 14 of 14 (100%) | - (0 of 0) |
| eligibility | 1 of 13 (8%) | 1 of 13 (8%) | 2 of 13 (15%) | 0 of 11 (0%) |
| issuer_org | 0 of 14 (0%) | 0 of 14 (0%) | 14 of 14 (100%) | - (0 of 0) |
| item_category | 3 of 11 (27%) | 3 of 11 (27%) | 11 of 11 (100%) | - (0 of 0) |
| language_currency | 13 of 13 (100%) | 13 of 13 (100%) | 2 of 13 (15%) | 0 of 11 (0%) |
| notice_date | 11 of 11 (100%) | 11 of 11 (100%) | 2 of 11 (18%) | 0 of 9 (0%) |
| performance_bond | 13 of 13 (100%) | 13 of 13 (100%) | 1 of 13 (8%) | 0 of 12 (0%) |
| performance_period | 13 of 14 (93%) | 13 of 14 (93%) | 1 of 14 (7%) | 0 of 8 (0%) |
| procurement_type | 12 of 13 (92%) | 13 of 13 (100%) | 0 of 13 (0%) | 0 of 13 (0%) |
| required_documents | 0 of 13 (0%) | 0 of 13 (0%) | 4 of 13 (31%) | 0 of 9 (0%) |
| scope_summary | 0 of 14 (0%) | 0 of 14 (0%) | 14 of 14 (100%) | - (0 of 0) |
| spec_access | 6 of 13 (46%) | 6 of 13 (46%) | 7 of 13 (54%) | 0 of 4 (0%) |
| submission_modes | 12 of 13 (92%) | 12 of 13 (92%) | 2 of 13 (15%) | 0 of 11 (0%) |
| tax_basis | 13 of 13 (100%) | 13 of 13 (100%) | 0 of 13 (0%) | 0 of 13 (0%) |
| title | 0 of 14 (0%) | 0 of 14 (0%) | 14 of 14 (100%) | - (0 of 0) |
| unified_qualification | 12 of 13 (92%) | 12 of 13 (92%) | 3 of 13 (23%) | 0 of 10 (0%) |
| wto_covered | 13 of 13 (100%) | 13 of 13 (100%) | 3 of 13 (23%) | 0 of 10 (0%) |

## Skipped (46): no label file

- 01204a43ed1d
- 5d75d4a67c71
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
