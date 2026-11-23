# v0.1 milestone report, test split (v0_1)

Run 2026-11-23 20:00 to 2026-11-23 20:17 UTC, extractor 0.3.0, schema 1.1.0, commit 7e0879951019360111743a0d8b0bb120f0d9e808, pipeline: rules + local `Qwen3.5-9B-Q4_K_M.gguf` through llama-server on 127.0.0.1 (`eval.hybrid`, the same code the app ships). 10 labeled test documents, one run, no cloud call. Frozen by D-109.

Scores are against model-reviewed silver labels (D-41), not human-verified ones, and Qwen3.5-9B was one of the two labelers (D-50), so it leans optimistic. Every number is given twice: all items, and without the 5 label lines whose note says "settled by rule, native check pending" (D-105 to D-107). No document text in this report.

## Freeze evidence

`git status --short core/ eval/ docs/` before the model started (empty means clean). Lines here are the run's own new files, nothing under `core/`:

```
M docs/decisions.md
?? eval/milestone.py
```

Same command after the model stopped:

```
M docs/decisions.md
?? eval/milestone.py
```

SHA-256 over every .py file in core/ and eval/ and the test label files: before `c633620305a41a14`, after `c633620305a41a14`, identical.

`git diff --stat HEAD -- core/` before the run: empty (core/ matches the last commit).

Settled-by-rule label lines found: 5 (1bfaa8243f97 spec_access, 262e3a41d23a spec_access, 44473a6e7b5e delivery_deadline, e8ca985baaa7 contact, e8ca985baaa7 procurement_type).

## Headline

| rate | all items | without the 5 settled |
|---|---|---|
| Verified field accuracy (headline) | 82 of 190 (43%) | 81 of 185 (44%) |
| Value accuracy (citations ignored) | 82 of 190 (43%) | 81 of 185 (44%) |
| Citation precision (predicted cites in the label's cites) | 136 of 155 (88%) | 136 of 155 (88%) |
| Citation recall (label cites that were predicted) | 136 of 356 (38%) | 136 of 350 (39%) |
| Not found (answer absent) | 127 of 190 (67%) | 122 of 185 (66%) |
| Wrong value shown (shown but wrong, or label absent) | 23 of 190 (12%) | 23 of 185 (12%) |
| Hallucination (shown, value not in cited sentences) | 0 of 63 (0%) | 0 of 63 (0%) |
| Over-abstention (label present, not found) | 63 of 126 (50%) | 61 of 124 (49%) |

## By field

| | verified (all)| verified (w/o 5) | not found (all)| not found (w/o 5) |
|---|---|---|---|---|
| award_method | 2 of 8 (25%) | 2 of 8 (25%) | 6 of 8 (75%) | 6 of 8 (75%) |
| bid_bond | 3 of 8 (38%) | 3 of 8 (38%) | 6 of 8 (75%) | 6 of 8 (75%) |
| contact | 0 of 8 (0%) | 0 of 7 (0%) | 8 of 8 (100%) | 7 of 7 (100%) |
| contracting_officer | 6 of 8 (75%) | 6 of 8 (75%) | 5 of 8 (62%) | 5 of 8 (62%) |
| deadlines | 1 of 8 (12%) | 1 of 8 (12%) | 1 of 8 (12%) | 1 of 8 (12%) |
| delivery_deadline | 9 of 10 (90%) | 9 of 9 (100%) | 10 of 10 (100%) | 9 of 9 (100%) |
| delivery_location | 4 of 10 (40%) | 4 of 10 (40%) | 10 of 10 (100%) | 10 of 10 (100%) |
| eligibility | 2 of 8 (25%) | 2 of 8 (25%) | 1 of 8 (12%) | 1 of 8 (12%) |
| issuer_org | 2 of 10 (20%) | 2 of 10 (20%) | 9 of 10 (90%) | 9 of 10 (90%) |
| item_category | 2 of 5 (40%) | 2 of 5 (40%) | 5 of 5 (100%) | 5 of 5 (100%) |
| language_currency | 8 of 8 (100%) | 8 of 8 (100%) | 5 of 8 (62%) | 5 of 8 (62%) |
| notice_date | 5 of 5 (100%) | 5 of 5 (100%) | 0 of 5 (0%) | 0 of 5 (0%) |
| performance_bond | 3 of 8 (38%) | 3 of 8 (38%) | 6 of 8 (75%) | 6 of 8 (75%) |
| performance_period | 1 of 10 (10%) | 1 of 10 (10%) | 10 of 10 (100%) | 10 of 10 (100%) |
| procurement_type | 4 of 8 (50%) | 3 of 7 (43%) | 5 of 8 (62%) | 4 of 7 (57%) |
| required_documents | 1 of 8 (12%) | 1 of 8 (12%) | 1 of 8 (12%) | 1 of 8 (12%) |
| scope_summary | 0 of 10 (0%) | 0 of 10 (0%) | 10 of 10 (100%) | 10 of 10 (100%) |
| spec_access | 1 of 8 (12%) | 1 of 6 (17%) | 8 of 8 (100%) | 6 of 6 (100%) |
| submission_modes | 0 of 8 (0%) | 0 of 8 (0%) | 5 of 8 (62%) | 5 of 8 (62%) |
| tax_basis | 8 of 8 (100%) | 8 of 8 (100%) | 1 of 8 (12%) | 1 of 8 (12%) |
| title | 5 of 10 (50%) | 5 of 10 (50%) | 4 of 10 (40%) | 4 of 10 (40%) |
| unified_qualification | 7 of 8 (88%) | 7 of 8 (88%) | 5 of 8 (62%) | 5 of 8 (62%) |
| wto_covered | 8 of 8 (100%) | 8 of 8 (100%) | 6 of 8 (75%) | 6 of 8 (75%) |

## Not found by document type

Not found counts every asked field whose answer was absent, including fields whose label is absent too.

| | verified (all)| verified (w/o 5) | not found (all)| not found (w/o 5) |
|---|---|---|---|---|
| bid_instructions (3 docs) | 28 of 63 (44%) | 27 of 61 (44%) | 51 of 63 (81%) | 49 of 61 (80%) |
| notice (5 docs) | 47 of 115 (41%) | 47 of 112 (42%) | 65 of 115 (57%) | 62 of 112 (55%) |
| spec (2 docs) | 7 of 12 (58%) | 7 of 12 (58%) | 11 of 12 (92%) | 11 of 12 (92%) |

## By document

| document | type | verified (all) | seconds, whole document | seconds, model calls only | seconds, loading sentences |
|---|---|---|---|---|---|
| 1bfaa8243f97 | notice | 10 of 23 (43%) | 100 | 100 | 0 |
| 209ff2190e47 | notice | 11 of 23 (48%) | 204 | 197 | 0 |
| 262e3a41d23a | notice | 12 of 23 (52%) | 130 | 130 | 0 |
| 427784e8a916 | bid_instructions | 6 of 21 (29%) | 212 | 212 | 0 |
| 44473a6e7b5e | notice | 6 of 23 (26%) | 131 | 131 | 0 |
| 7362dc8f3628 | spec | 3 of 6 (50%) | 0 | 0 | 0 |
| 75a7ffe05c5b | spec | 4 of 6 (67%) | 0 | 0 | 0 |
| 84f6538008a9 | notice | 8 of 23 (35%) | 94 | 94 | 0 |
| b66a39082840 | bid_instructions | 8 of 21 (38%) | 119 | 119 | 0 |
| e8ca985baaa7 | bid_instructions | 14 of 21 (67%) | 48 | 48 | 0 |

Time per document: mean 104 s, median 119 s, max 212 s; total 1038 s. Seconds are from one MacBook Air M4, not the Windows 16 GB machine.
Peak memory (getrusage, bytes to MiB): this process 85 MiB; llama-server (largest waited-for child) 7042 MiB. Memory of the model is mapped, so treat these as rough.

## Wrong Verified answers

A Verified answer is a field shown as present. Listed: shown and not Verified-correct (wrong value, label absent, or right value with no cited sentence in common with the label). Cause is a mechanical category, not a diagnosis.

| document | field | cause category | one of the 5 settled |
|---|---|---|---|
| 209ff2190e47 | eligibility | value differs from the label | no |
| 209ff2190e47 | unified_qualification | value differs from the label | no |
| 209ff2190e47 | deadlines | value differs from the label | no |
| 209ff2190e47 | submission_modes | value differs from the label | no |
| 209ff2190e47 | required_documents | value differs from the label | no |
| 84f6538008a9 | eligibility | value differs from the label | no |
| 84f6538008a9 | deadlines | value differs from the label | no |
| 1bfaa8243f97 | title | value differs from the label | no |
| 1bfaa8243f97 | deadlines | value differs from the label | no |
| 1bfaa8243f97 | submission_modes | value differs from the label | no |
| 262e3a41d23a | eligibility | value differs from the label | no |
| 262e3a41d23a | deadlines | value differs from the label | no |
| 262e3a41d23a | required_documents | value differs from the label | no |
| 44473a6e7b5e | eligibility | value differs from the label | no |
| 44473a6e7b5e | deadlines | value differs from the label | no |
| 44473a6e7b5e | required_documents | value differs from the label | no |
| e8ca985baaa7 | submission_modes | value differs from the label | no |
| e8ca985baaa7 | required_documents | value differs from the label | no |
| b66a39082840 | eligibility | value differs from the label | no |
| b66a39082840 | required_documents | value differs from the label | no |
| 427784e8a916 | eligibility | value differs from the label | no |
| 427784e8a916 | deadlines | value differs from the label | no |
| 427784e8a916 | required_documents | value differs from the label | no |

Count: 23 of 190 asked fields (23 without the 5 settled).

## What this does not tell you

- Silver labels, 10 documents, one run, one machine. Small n: a single field moves a rate by several points.
- The 5 settled items wait for a native reader; the second column shows what they change.
- Item-level precision and recall for the three list fields are in the dev reports only; here a list field counts as one field (every item must pair).

## Breakdown of the 190 fields (added after the run)

Computed from this report's own tables (verified and not found per field, and the Wrong Verified answers list) plus the status of each test label line (present, absent, see_other_document; read only, counts only). No re-run, no model call. The run did not save per-field predictions (the partial file holds document ids and a record count only), so nothing here comes from the model's raw answers.

How the parts are derived per field: shown = asked minus not found; shown wrong = rows in the Wrong Verified answers list; shown fully right = shown minus shown wrong; Not found correct = verified minus shown fully right (label says absent, answer absent); Not found over-abstained = not found minus Not found correct minus see_other_document (label has a value, answer absent); the last column is Not found where the label says "see other document", which the scorer does not count as a match.

| field | asked | shown, fully right | shown, wrong | Not found, correct | Not found, over-abstained | Not found, label says see other document |
|---|---|---|---|---|---|---|
| award_method | 8 | 2 | 0 | 0 | 5 | 1 |
| bid_bond | 8 | 2 | 0 | 1 | 2 | 3 |
| contact | 8 | 0 | 0 | 0 | 8 | 0 |
| contracting_officer | 8 | 3 | 0 | 3 | 2 | 0 |
| deadlines | 8 | 1 | 6 | 0 | 1 | 0 |
| delivery_deadline | 10 | 0 | 0 | 9 | 1 | 0 |
| delivery_location | 10 | 0 | 0 | 4 | 4 | 2 |
| eligibility | 8 | 1 | 6 | 1 | 0 | 0 |
| issuer_org | 10 | 1 | 0 | 1 | 8 | 0 |
| item_category | 5 | 0 | 0 | 2 | 3 | 0 |
| language_currency | 8 | 3 | 0 | 5 | 0 | 0 |
| notice_date | 5 | 5 | 0 | 0 | 0 | 0 |
| performance_bond | 8 | 2 | 0 | 1 | 2 | 3 |
| performance_period | 10 | 0 | 0 | 1 | 8 | 1 |
| procurement_type | 8 | 3 | 0 | 1 | 4 | 0 |
| required_documents | 8 | 1 | 6 | 0 | 1 | 0 |
| scope_summary | 10 | 0 | 0 | 0 | 3 | 7 |
| spec_access | 8 | 0 | 0 | 1 | 2 | 5 |
| submission_modes | 8 | 0 | 3 | 0 | 5 | 0 |
| tax_basis | 8 | 7 | 0 | 1 | 0 | 0 |
| title | 10 | 5 | 1 | 0 | 4 | 0 |
| unified_qualification | 8 | 2 | 1 | 5 | 0 | 0 |
| wto_covered | 8 | 2 | 0 | 6 | 0 | 0 |
| total | 190 | 40 | 23 | 42 | 63 | 22 |

Totals, all 190 asked fields:

| part | count |
|---|---|
| Shown, fully right (value matches, cited sentence in common with the label) | 40 |
| Shown, wrong | 23 |
| Shown, total | 63 |
| Not found, correct (label absent, answer absent) | 42 |
| Not found, over-abstained (label has a value) | 63 |
| Not found, label says see other document | 22 |
| Not found, total | 127 |
| All asked | 190 |

Reproducing the 82: 40 shown fully right + 42 Not found correct = 82 of 190 (43%). The other 108 = 23 shown wrong + 63 over-abstained + 22 see other document. The 63 over-abstained matches "63 of 126" in the headline table and the 23 matches "Wrong value shown".

Partly right (list fields): not measured here. Scoring is all or nothing per field: a list field is right only when every item pairs, so a list that got some items right is counted in "shown, wrong". Of the 23 shown wrong, 18 are in the three list fields (eligibility 6, deadlines 6, required_documents 6); the other 5 are submission_modes 3, title 1, unified_qualification 1. How many of those 18 were partly right cannot be recovered without the saved predictions, and re-running was out of scope. Verified on a list field means each shown item is cited, not that the list is complete.

All numbers above are for all items (190). The "without the 5 settled" figures are in the Headline table: 81 of 185 (44%).
