# Web import check (Gemini web chat, prompt sv4-web, D-104)

Counts only: item ids, doc id prefixes, field names. Schema 1.1.0.

## Per document

| doc | type | fields asked | passed | failed | advisory only | uncertain notes |
|---|---|---|---|---|---|---|
| 1bfaa824 | notice | 23 | 23 | 0 | 5 | 6 |
| 209ff219 | notice | 23 | 23 | 0 | 6 | 7 |
| 262e3a41 | notice | 23 | 21 | 2 | 4 | 5 |
| 427784e8 | bid_instructions | 21 | 19 | 2 | 10 | 6 |
| 44473a6e | notice | 23 | 22 | 1 | 11 | 7 |
| 7362dc8f | spec | 6 | 6 | 0 | 1 | 3 |
| 75a7ffe0 | spec | 6 | 6 | 0 | 2 | 3 |
| 84f65380 | notice | 23 | 23 | 0 | 2 | 4 |
| b66a3908 | bid_instructions | 21 | 20 | 1 | 6 | 4 |
| e8ca985b | bid_instructions | 21 | 21 | 0 | 2 | 6 |

## Per field (over the imported documents)

| field | asked | passed | failed |
|---|---|---|---|
| award_method | 8 | 8 | 0 |
| bid_bond | 8 | 8 | 0 |
| contact | 8 | 6 | 2 |
| contracting_officer | 8 | 8 | 0 |
| deadlines | 8 | 6 | 2 |
| delivery_deadline | 10 | 9 | 1 |
| delivery_location | 10 | 10 | 0 |
| eligibility | 8 | 8 | 0 |
| issuer_org | 10 | 10 | 0 |
| item_category | 5 | 5 | 0 |
| language_currency | 8 | 8 | 0 |
| notice_date | 5 | 5 | 0 |
| performance_bond | 8 | 8 | 0 |
| performance_period | 10 | 10 | 0 |
| procurement_type | 8 | 8 | 0 |
| required_documents | 8 | 8 | 0 |
| scope_summary | 10 | 10 | 0 |
| spec_access | 8 | 8 | 0 |
| submission_modes | 8 | 8 | 0 |
| tax_basis | 8 | 7 | 1 |
| title | 10 | 10 | 0 |
| unified_qualification | 8 | 8 | 0 |
| wto_covered | 8 | 8 | 0 |

## Failures (doc, field, check)

- 262e3a41 deadlines values_roundtrip
- 262e3a41 tax_basis values_roundtrip
- 427784e8 contact values_roundtrip
- 427784e8 deadlines values_roundtrip
- 44473a6e delivery_deadline weekday_consistent
- b66a3908 contact values_roundtrip

## Advisory checks that failed (do not stop a field)

- 1bfaa824 title heading_cue
- 1bfaa824 issuer_org heading_cue
- 1bfaa824 scope_summary heading_cue
- 1bfaa824 tax_basis heading_cue
- 1bfaa824 required_documents heading_cue
- 209ff219 issuer_org heading_cue
- 209ff219 scope_summary heading_cue
- 209ff219 performance_period heading_cue
- 209ff219 delivery_location heading_cue
- 209ff219 tax_basis heading_cue
- 209ff219 required_documents heading_cue
- 262e3a41 title heading_cue
- 262e3a41 issuer_org heading_cue
- 262e3a41 scope_summary heading_cue
- 262e3a41 required_documents heading_cue
- 427784e8 title heading_cue
- 427784e8 issuer_org heading_cue
- 427784e8 procurement_type heading_cue
- 427784e8 scope_summary heading_cue
- 427784e8 performance_period heading_cue
- 427784e8 delivery_location heading_cue
- 427784e8 eligibility heading_cue
- 427784e8 submission_modes heading_cue
- 427784e8 tax_basis heading_cue
- 427784e8 required_documents heading_cue
- 44473a6e title heading_cue
- 44473a6e issuer_org heading_cue
- 44473a6e contracting_officer heading_cue
- 44473a6e procurement_type heading_cue
- 44473a6e scope_summary heading_cue
- 44473a6e performance_period heading_cue
- 44473a6e eligibility heading_cue
- 44473a6e submission_modes heading_cue
- 44473a6e tax_basis heading_cue
- 44473a6e required_documents heading_cue
- 44473a6e spec_access heading_cue
- 7362dc8f issuer_org heading_cue
- 75a7ffe0 title heading_cue
- 75a7ffe0 scope_summary heading_cue
- 84f65380 title heading_cue
- 84f65380 required_documents heading_cue
- b66a3908 issuer_org heading_cue
- b66a3908 procurement_type heading_cue
- b66a3908 scope_summary heading_cue
- b66a3908 eligibility heading_cue
- b66a3908 tax_basis heading_cue
- b66a3908 required_documents heading_cue
- e8ca985b issuer_org heading_cue
- e8ca985b contact heading_cue

## Not imported

none
