# Coverage of the rules extractor (no model)

- date: 2026-11-20
- git commit: b31617c33178cc7e7e0328a6ba08971a13c9aa0f
- documents processed: 224 of 224 PDFs read
- skipped: {'issuer in test split': 159, 'not a PDF on disk': 136}
- failures: 0

Test-split issuers are not opened. Counts only; no document text. A cell is found/applicable: a field counts only for documents whose manifest doc_type it applies to, and found means the rules gave a verified answer. `-` means the field never applies to that group.

## Overall

| field | found | applicable | rate |
|---|---|---|---|
| title | 64 | 113 | 57% |
| issuer_org | 25 | 113 | 22% |
| contracting_officer | 1 | 70 | 1% |
| notice_date | 25 | 27 | 93% |
| procurement_type | 45 | 70 | 64% |
| award_method | 7 | 70 | 10% |
| item_category | 0 | 27 | 0% |
| scope_summary | 0 | 113 | 0% |
| performance_period | 55 | 113 | 49% |
| delivery_deadline | 4 | 113 | 4% |
| delivery_location | 0 | 113 | 0% |
| eligibility | 0 | 70 | 0% |
| unified_qualification | 4 | 70 | 6% |
| deadlines | 0 | 70 | 0% |
| submission_modes | 24 | 70 | 34% |
| bid_bond | 13 | 70 | 19% |
| performance_bond | 18 | 70 | 26% |
| tax_basis | 43 | 70 | 61% |
| language_currency | 23 | 70 | 33% |
| required_documents | 0 | 70 | 0% |
| contact | 0 | 70 | 0% |
| wto_covered | 0 | 70 | 0% |
| spec_access | 2 | 70 | 3% |

## Per document type (manifest)

| doc type | docs | title | issuer_org | contracting_officer | notice_date | procurement_type | award_method | item_category | scope_summary | performance_period | delivery_deadline | delivery_location | eligibility | unified_qualification | deadlines | submission_modes | bid_bond | performance_bond | tax_basis | language_currency | required_documents | contact | wto_covered | spec_access |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bid_instructions | 43 | 27/43 | 1/43 | 1/43 | - | 24/43 | 2/43 | - | 0/43 | 17/43 | 1/43 | 0/43 | 0/43 | 4/43 | 0/43 | 16/43 | 3/43 | 9/43 | 24/43 | 13/43 | 0/43 | 0/43 | 0/43 | 1/43 |
| draft_contract | 13 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| evaluation_criteria | 9 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| forms | 26 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| notice | 27 | 12/27 | 22/27 | 0/27 | 25/27 | 21/27 | 5/27 | 0/27 | 0/27 | 19/27 | 1/27 | 0/27 | 0/27 | 0/27 | 0/27 | 8/27 | 10/27 | 9/27 | 19/27 | 10/27 | 0/27 | 0/27 | 0/27 | 1/27 |
| other | 33 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| qa | 17 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| result | 12 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| rfi_material | 1 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| spec | 43 | 25/43 | 2/43 | - | - | - | - | - | 0/43 | 19/43 | 2/43 | 0/43 | - | - | - | - | - | - | - | - | - | - | - | - |

## Per issuer

| issuer | docs | title | issuer_org | contracting_officer | notice_date | procurement_type | award_method | item_category | scope_summary | performance_period | delivery_deadline | delivery_location | eligibility | unified_qualification | deadlines | submission_modes | bid_bond | performance_bond | tax_basis | language_currency | required_documents | contact | wto_covered | spec_access |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| デジタル庁 | 34 | 9/16 | 3/16 | 1/8 | - | 0/8 | 0/8 | - | 0/16 | 5/16 | 0/16 | 0/16 | 0/8 | 4/8 | 0/8 | 0/8 | 0/8 | 0/8 | 1/8 | 1/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| 八王子市 | 32 | 10/18 | 0/18 | 0/13 | 0/1 | 8/13 | 0/13 | 0/1 | 0/18 | 4/18 | 0/18 | 0/18 | 0/13 | 0/13 | 0/13 | 5/13 | 0/13 | 0/13 | 5/13 | 0/13 | 0/13 | 0/13 | 0/13 | 0/13 |
| 和歌山県 | 34 | 11/17 | 1/17 | 0/9 | 1/1 | 8/9 | 0/9 | 0/1 | 0/17 | 14/17 | 0/17 | 0/17 | 0/9 | 0/9 | 0/9 | 6/9 | 2/9 | 8/9 | 8/9 | 6/9 | 0/9 | 0/9 | 0/9 | 0/9 |
| 奈良市 | 27 | 3/11 | 4/11 | 0/6 | 4/5 | 5/6 | 3/6 | 0/5 | 0/11 | 7/11 | 0/11 | 0/11 | 0/6 | 0/6 | 0/6 | 1/6 | 0/6 | 0/6 | 3/6 | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 |
| 富山市 | 1 | 0/1 | 0/1 | 0/1 | - | 0/1 | 0/1 | - | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 1/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| 川口市 | 2 | 1/2 | 0/2 | 0/1 | - | 0/1 | 0/1 | - | 0/2 | 0/2 | 0/2 | 0/2 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| 新潟県 | 15 | 4/8 | 0/8 | 0/5 | 3/3 | 1/5 | 4/5 | 0/3 | 0/8 | 2/8 | 3/8 | 0/8 | 0/5 | 0/5 | 0/5 | 2/5 | 4/5 | 0/5 | 5/5 | 0/5 | 0/5 | 0/5 | 0/5 | 1/5 |
| 旭川市 | 32 | 16/19 | 6/19 | 0/12 | 6/6 | 11/12 | 0/12 | 0/6 | 0/19 | 9/19 | 1/19 | 0/19 | 0/12 | 0/12 | 0/12 | 2/12 | 0/12 | 5/12 | 8/12 | 11/12 | 0/12 | 0/12 | 0/12 | 1/12 |
| 松江市 | 1 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| 横須賀市 | 2 | 1/2 | 0/2 | 0/1 | - | 0/1 | 0/1 | - | 0/2 | 1/2 | 0/2 | 0/2 | 0/1 | 0/1 | 0/1 | 1/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| 郡山市 | 41 | 9/17 | 9/17 | 0/12 | 9/9 | 12/12 | 0/12 | 0/9 | 0/17 | 13/17 | 0/17 | 0/17 | 0/12 | 0/12 | 0/12 | 4/12 | 5/12 | 5/12 | 11/12 | 5/12 | 0/12 | 0/12 | 0/12 | 0/12 |
| 金沢市 | 2 | 0/2 | 2/2 | 0/2 | 2/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 | 2/2 | 2/2 | 0/2 | 2/2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| 鹿児島市 | 1 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |

## 10 issuers with the lowest found rate: title

| issuer | found | applicable | rate | not found (doc id prefixes, first 10) |
|---|---|---|---|---|
| 金沢市 | 0 | 2 | 0% | 6c7ed844, d43dd5c2 |
| 富山市 | 0 | 1 | 0% | 7c76af66 |
| 奈良市 | 3 | 11 | 27% | 94521ecf, 314ec6bd, d4560236, cc3c1c34, 43e3356b, fd2cdc49, d2d48af7, 1185ff98 |
| 新潟県 | 4 | 8 | 50% | b16ad988, 67e63660, 94b7145f, f31471b2 |
| 川口市 | 1 | 2 | 50% | 98485b73 |
| 横須賀市 | 1 | 2 | 50% | ab5e74f1 |
| 郡山市 | 9 | 17 | 53% | 6b1d5a3c, 6bed5f04, c665449c, 6df62fa3, 1d5b1d3c, 88d80c6c, c8145351, 7887110a |
| 八王子市 | 10 | 18 | 56% | c74468a3, 2fd6e787, 1dc8e791, 6df340ac, 3df71c9c, 70ddd714, cfddd49a, f468eeda |
| デジタル庁 | 9 | 16 | 56% | c8448fb9, 2baf6023, 6af28f88, 22e6f85e, 756d17c8, 8a00ce8d, e7418476 |
| 和歌山県 | 11 | 17 | 65% | 2f2f5bd3, 081d2756, 12f50d06, 7e591bba, e5602807, 53320d90 |

## 10 issuers with the lowest found rate: issuer_org

| issuer | found | applicable | rate | not found (doc id prefixes, first 10) |
|---|---|---|---|---|
| 八王子市 | 0 | 18 | 0% | c74468a3, 12e3ac14, 2fd6e787, 1dc8e791, 6df340ac, b7fbcfe4, ac58cfb9, c170ca96, 1b0397f3, 7677f1e5 |
| 新潟県 | 0 | 8 | 0% | b16ad988, 67e63660, 9463d23d, 070b894e, 94b7145f, 4397a109, 99044e93, f31471b2 |
| 川口市 | 0 | 2 | 0% | 98485b73, d360751d |
| 横須賀市 | 0 | 2 | 0% | ab5e74f1, d97dc236 |
| 富山市 | 0 | 1 | 0% | 7c76af66 |
| 和歌山県 | 1 | 17 | 6% | 081d2756, 12f50d06, 28ad40ea, 870f1f2e, d4000027, 4c40bbd8, e71b351a, 7e591bba, e5602807, cd1a1936 |
| デジタル庁 | 3 | 16 | 19% | 10be3ae3, c8448fb9, 2baf6023, b04d58bd, 6af28f88, cca048bc, 22e6f85e, d69caea0, 8a00ce8d, d4be5408 |
| 旭川市 | 6 | 19 | 32% | 03406dd6, aeedf544, 11ead9a5, 08ec571d, 6387bfc3, 2ed05ba9, 9b6a573a, a2728e6b, bb10715a, 34ea5d0b |
| 奈良市 | 4 | 11 | 36% | faef6e6a, d4560236, 0d2192b6, fd2cdc49, 9744e5f8, d2d48af7, 1185ff98 |
| 郡山市 | 9 | 17 | 53% | a6d28ef4, af51a0ac, 6bed5f04, c665449c, c9b8a031, 63a52ed6, 6df62fa3, 1d5b1d3c |

## 10 issuers with the lowest found rate: notice_date

| issuer | found | applicable | rate | not found (doc id prefixes, first 10) |
|---|---|---|---|---|
| 八王子市 | 0 | 1 | 0% | c74468a3 |
| 奈良市 | 4 | 5 | 80% | d2d48af7 |
| 郡山市 | 9 | 9 | 100% |  |
| 旭川市 | 6 | 6 | 100% |  |
| 新潟県 | 3 | 3 | 100% |  |
| 金沢市 | 2 | 2 | 100% |  |
| 和歌山県 | 1 | 1 | 100% |  |

## Failures (documents that could not be read)

none
