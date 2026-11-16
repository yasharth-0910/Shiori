# Eval run dev_stub

Split `dev`, extractor `stub`, extractor version 0.3.0, schema 1.0.0, commit 03b48489c09acb1b3e7fb642c5f9f76ca305af17, 2026-11-16T10:50:08+00:00.

Scores are against model-reviewed silver labels, not human-verified ones (D-41). Only fields asked of the document's type are scored. No cloud call and no document text in this report.

Documents scored: 9 of 60 in the dev label set. Label lines reviewed by a model: 120 of 207 (58%).

| rate | count | out of |
| --- | --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) (all asked fields with a label) | 37 of 186 (20%) | |
| Value accuracy (citations ignored) (all asked fields with a label) | 37 of 186 (20%) | |
| Citation exists rate (fields shown as present) | - (0 of 0) | |
| Value-in-citation rate (fields shown as present) | - (0 of 0) | |
| Not-found rate (all asked fields with a label) | 186 of 186 (100%) | |
| Hallucination rate (shown, value not in the cited sentences) (fields shown as present) | - (0 of 0) | |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) (all asked fields with a label) | 0 of 186 (0%) | |
| Over-abstention rate (label present, not found) (fields whose label is present) | 132 of 132 (100%) | |

## Tier 1 fields

| rate | count |
| --- | --- |
| Verified field accuracy (correct and a cited sentence matches the label) | 10 of 80 (12%) |
| Value accuracy (citations ignored) | 10 of 80 (12%) |
| Citation exists rate | - (0 of 0) |
| Value-in-citation rate | - (0 of 0) |
| Not-found rate | 80 of 80 (100%) |
| Hallucination rate (shown, value not in the cited sentences) | - (0 of 0) |
| Wrong value shown (eval_protocol.md definition: shown but wrong, or label absent) | 0 of 80 (0%) |
| Over-abstention rate (label present, not found) | 64 of 64 (100%) |

## By field type

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| list | 1 of 24 (4%) | 1 of 24 (4%) | 24 of 24 (100%) | - (0 of 0) |
| structured | 32 of 126 (25%) | 32 of 126 (25%) | 126 of 126 (100%) | - (0 of 0) |
| text | 4 of 36 (11%) | 4 of 36 (11%) | 36 of 36 (100%) | - (0 of 0) |

## By field

| | verified accuracy | value accuracy | not found | hallucination |
| --- | --- | --- | --- | --- |
| award_method | 1 of 8 (12%) | 1 of 8 (12%) | 8 of 8 (100%) | - (0 of 0) |
| bid_bond | 3 of 8 (38%) | 3 of 8 (38%) | 8 of 8 (100%) | - (0 of 0) |
| contact | 2 of 8 (25%) | 2 of 8 (25%) | 8 of 8 (100%) | - (0 of 0) |
| contracting_officer | 3 of 8 (38%) | 3 of 8 (38%) | 8 of 8 (100%) | - (0 of 0) |
| deadlines | 0 of 8 (0%) | 0 of 8 (0%) | 8 of 8 (100%) | - (0 of 0) |
| delivery_deadline | 8 of 9 (89%) | 8 of 9 (89%) | 9 of 9 (100%) | - (0 of 0) |
| delivery_location | 4 of 9 (44%) | 4 of 9 (44%) | 9 of 9 (100%) | - (0 of 0) |
| eligibility | 1 of 8 (12%) | 1 of 8 (12%) | 8 of 8 (100%) | - (0 of 0) |
| issuer_org | 0 of 9 (0%) | 0 of 9 (0%) | 9 of 9 (100%) | - (0 of 0) |
| item_category | 3 of 6 (50%) | 3 of 6 (50%) | 6 of 6 (100%) | - (0 of 0) |
| language_currency | 2 of 8 (25%) | 2 of 8 (25%) | 8 of 8 (100%) | - (0 of 0) |
| notice_date | 2 of 6 (33%) | 2 of 6 (33%) | 6 of 6 (100%) | - (0 of 0) |
| performance_bond | 1 of 8 (12%) | 1 of 8 (12%) | 8 of 8 (100%) | - (0 of 0) |
| performance_period | 0 of 9 (0%) | 0 of 9 (0%) | 9 of 9 (100%) | - (0 of 0) |
| procurement_type | 0 of 8 (0%) | 0 of 8 (0%) | 8 of 8 (100%) | - (0 of 0) |
| required_documents | 0 of 8 (0%) | 0 of 8 (0%) | 8 of 8 (100%) | - (0 of 0) |
| scope_summary | 0 of 9 (0%) | 0 of 9 (0%) | 9 of 9 (100%) | - (0 of 0) |
| spec_access | 0 of 8 (0%) | 0 of 8 (0%) | 8 of 8 (100%) | - (0 of 0) |
| submission_modes | 1 of 8 (12%) | 1 of 8 (12%) | 8 of 8 (100%) | - (0 of 0) |
| tax_basis | 0 of 8 (0%) | 0 of 8 (0%) | 8 of 8 (100%) | - (0 of 0) |
| title | 0 of 9 (0%) | 0 of 9 (0%) | 9 of 9 (100%) | - (0 of 0) |
| unified_qualification | 3 of 8 (38%) | 3 of 8 (38%) | 8 of 8 (100%) | - (0 of 0) |
| wto_covered | 3 of 8 (38%) | 3 of 8 (38%) | 8 of 8 (100%) | - (0 of 0) |

## Skipped (51): no label file

- 01204a43ed1d
- 58f13b9c2e87
- a81e99fecea5
- d230e51e2805
- 6b7142ab74f4
- 594c3cb69c53
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
