# Document type rule against the manifest (D-92)

Documents with issuers in the test split are not read. Rows are the manifest doc_type, columns what the rule said. No text from any document is in this file.

| manifest \ rule | notice | bid_instructions | spec | (no text) |
|---|---|---|---|---|
| notice | 27 | 0 | 0 | 0 |
| bid_instructions | 4 | 38 | 0 | 1 |
| spec | 2 | 0 | 40 | 1 |
| draft_contract | 12 | 0 | 1 | 0 |
| evaluation_criteria | 7 | 2 | 0 | 0 |
| forms | 25 | 1 | 0 | 0 |
| other | 29 | 0 | 2 | 2 |
| qa | 12 | 5 | 0 | 0 |
| result | 12 | 0 | 0 | 0 |
| rfi_material | 0 | 0 | 1 | 0 |

Accuracy on the three named types: 105 of 113 (92.9%), of which 2 had no text layer on page 1 (the rule answers notice there, so it counts as wrong unless the document is a notice).
Skipped: {'test split': 159, 'not a PDF on disk': 136}.

## Wrong on the three named types (doc id prefix, manifest, rule, license)

- 2baf6023 bid_instructions -> notice (open)
- 6df340ac bid_instructions -> notice (restricted)
- 7c76af66 bid_instructions -> (no text) (unknown)
- 98485b73 bid_instructions -> notice (unknown)
- f468eeda bid_instructions -> notice (restricted)
- 12e3ac14 spec -> (no text) (restricted)
- 720e2a76 spec -> notice (restricted)
- aeedf544 spec -> notice (restricted)
