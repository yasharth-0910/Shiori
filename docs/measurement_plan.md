# Measurement plan

Written 2026-11-28. Analysis only: no model call, no cloud call, no scoring run, no label file changed. Counts, doc id prefixes and field names only, no document text. It extends `docs/eval_protocol.md`; where the two differ, the protocol stays in force until a decision entry changes it.

## 1. What is labeled today

### Words used here

- **Label row:** one line of a label file, one field of one document. Every file has 23.
- **Scored row:** a label row whose field applies to the document's type (23 for a notice or tender page, 21 for bid instructions, 6 for a spec). `eval.run` and `eval.milestone` score only these.
- **Reviewed:** `final_state` is `silver_model_reviewed` or `human_audited`. Consensus rows are not reviewed.

### Rows by provenance state

| | dev | test | outside both |
|---|---|---|---|
| documents in `label_set.json` | 60 | 40 | 419 (of 519 in the manifest) |
| documents with a label file | 15 | 10 | 0 |
| documents without one: open / restricted | 22 / 23 | 20 / 10 | not planned |
| label rows | 345 | 230 | 0 |
| silver unreviewed | 21 | 40 | 0 |
| accepted consensus | 122 | 107 | 0 |
| model reviewed | 202 (claude_code 152, claude_chat 50) | 83 (claude_code 83) | 0 |
| human audited (native speaker) | 0 | 0 | 0 |
| **scored rows** | **324** | **190** | 0 |
| scored: present | 250 | 126 | 0 |
| scored: absent | 43 | 42 | 0 |
| scored: see_other_document | 31 | 22 | 0 |
| held-unsure, still open | 0 | 0 | 0 |

Notes:

- All 21 and 40 silver unreviewed rows are `absent` lines for fields that do not apply to the document's type. No pre-labeler made them and nothing scores them.
- `held-unsure.json` is empty. The 2 dev items listed in `held-unsure.md` and the 2 test items in `held-roundtrip.md` all have reviewed label rows.
- 5 test rows carry "settled by rule, native check pending" (D-105 to D-107). A 4-line dev relabel to kind `application` is written but not imported (open question in `decisions.md`).
- All 25 labeled documents are `open`. `data/eval_private/` does not exist, so no restricted document has a label file.
- One restricted dev document (`01204a43`) has 10 consensus rows in the labeling cache and no label file. It is not counted.
- The 419 documents outside the label set by org split: train 221, dev orgs 79, test orgs 119.
- Labeler overlap (the local Qwen voted or was shown): 250 of 345 dev rows, and all 190 scored test rows. A "without overlap" test score is therefore not possible.
- `52bba5f9` (open, bid instructions, in the test label set) is excluded from test labeling and test runs (D-102). Test has at most 39 eligible documents.
- The v0.1 test run has happened (D-109, `eval/reports/test_milestone_v0_1.md`): 10 documents, 190 scored rows.

### Scored rows still to be had

Computed from document types in `label_set.json`.

| | documents | scored rows |
|---|---|---|
| dev, labeled now | 15 | 324 |
| dev, all open | 37 | 752 |
| dev, all (needs the 23 restricted) | 60 | 1095 |
| test, labeled now | 10 | 190 |
| test, all eligible open | 29 | 555 |
| test, all eligible (needs the 10 restricted) | 39 | 709 |

## 2. Resolution: how small a change can be read

### One row at most 0.5 points

One row is worth `100 / N` points. `100 / N <= 0.5` gives `N >= 200`.

| rows scored | N now | one row | enough? |
|---|---|---|---|
| dev, all fields | 324 | 0.31 | yes |
| test, all fields | 190 | 0.53 | no, 10 short (one more notice or bid instructions) |
| dev, tier 1 | 140 | 0.71 | no, 60 short |
| test, tier 1 | 80 | 1.25 | no, 120 short |
| dev, three list fields | 42 | 2.38 | no, 158 short |
| one field, dev | at most 15 | 6.7 or more | no, would need 200 documents |

The 200 rows apply to each rate that is reported on its own. Per-field rates will not reach it, so report them as counts and never gate on them.

### Smallest gain a paired bootstrap over documents can read

A and B are scored on the same rows. Each row gives `d = correct_B - correct_A`, which is -1, 0 or +1.

- `N` rows in `n` documents, `m = N / n` rows per document.
- `pi`: share of rows where A and B differ in correctness (discordant rows).
- `delta`: net gain, the mean of `d`. Always `delta <= pi`.
- `Var(d) = pi - delta^2`.
- Rows in one document are not independent. Design effect `D = 1 + (m - 1) * rho`, where `rho` is the within-document correlation of `d`.
- `SE(delta) = sqrt((pi - delta^2) * D / N)`.
- Two-sided 5% level, 80% power: `k = 1.960 + 0.842 = 2.802`, `k^2 = 7.849`.
- Set `delta = k * SE` and solve: `delta = k * sqrt(pi * D / (N + k^2 * D))`.

**Assumptions, none of them measured:** `pi = 0.10` and `rho = 0.05` as the central case; normal approximation to the bootstrap; documents of equal size (they are not: a spec has 6 rows); labels taken as correct.

Worked, central case:

| case | N, n | m | D | sum | gain |
|---|---|---|---|---|---|
| dev now | 324, 15 | 21.6 | 1 + 20.6 x 0.05 = 2.030 | 2.802 x sqrt(0.203 / 339.9) | **6.8 points** (22 rows) |
| test now | 190, 10 | 19.0 | 1.900 | 2.802 x sqrt(0.190 / 204.9) | **8.5 points** (16 rows) |
| dev, all open | 752, 37 | 20.3 | 1.966 | 2.802 x sqrt(0.197 / 767.4) | 4.5 points |
| dev, all | 1095, 60 | 18.3 | 1.863 | 2.802 x sqrt(0.186 / 1109.6) | 3.6 points |
| test, eligible open | 555, 29 | 19.1 | 1.907 | 2.802 x sqrt(0.191 / 570.0) | 5.1 points |
| test, all eligible | 709, 39 | 18.2 | 1.859 | 2.802 x sqrt(0.186 / 723.6) | 4.5 points |

Sensitivity, in points. "n/a" means the gain would exceed `pi`, so 80% power cannot be reached with that few differing rows.

| pi, rho | dev now | test now | dev all | test all eligible open |
|---|---|---|---|---|
| 0.05, 0.00 | 3.4 | 4.5 | 1.9 | 2.6 |
| 0.05, 0.05 | 4.8 | n/a | 2.6 | 3.6 |
| 0.10, 0.00 | 4.9 | 6.3 | 2.7 | 3.7 |
| **0.10, 0.05** | **6.8** | **8.5** | **3.6** | **5.1** |
| 0.10, 0.15 | 9.5 | n/a | 5.0 | 7.1 |
| 0.20, 0.05 | 9.7 | 12.1 | 5.1 | 7.2 |
| 0.20, 0.15 | 13.4 | 16.3 | 7.1 | 10.0 |

With 10 to 15 documents a percentile bootstrap tends to give intervals that are too narrow. Using t quantiles with `n - 1` degrees of freedom in place of 2.802 gives `k` about 3.01 for 15 documents and 3.15 for 10, so read the "now" columns as roughly 7 to 12% too optimistic.

The list fields alone (42 dev rows) cannot be read at all in the central case: the formula asks for 13 points from rows of which only 10% differ.

After the first real paired comparison, replace the assumed `pi` and `rho` with the measured ones and redo this table.

## 3. Native reader sheet, rebuilt

### What exists

The repo has earlier sheets in `data/cache/audit/` (gitignored):

| file | rows | documents | distinct field labels | verdict cells filled |
|---|---|---|---|---|
| `readers_audit_v2.csv` / `.xlsx` | 43 | 14 | 13 | no answers (some Not found rows hold printed prompts) |
| `readers_audit_v2_styled.xlsx` | 45 | 14 | 14 | no answers (same) |
| `readers_audit_v3_styled.xlsx` | 40 plus 3 not-found | 14 | 13 | none |

The sheet described in the task (58 rows, about 13 documents, 4 of 23 fields, many near-duplicate boilerplate rows) matches none of these. It is not in the repo, or it is an export kept elsewhere. The spec below does not depend on its content. Send the export if its rows should be carried over.

### Spec

**Purpose:** measure how often the silver labels are wrong. It audits labels, not a model.

**Source rows:** scored rows of dev and test label files whose document is `open`. Run `uv run python -m eval.silver webcheck --docs <ids>` on every document before the sheet leaves the machine (D-111). Test verdicts are reported as counts only and never used to change a rule or a prompt (D-96). Label corrections to test files are made by Yasharth through the import step.

**Unit:** one scalar field of one document, or one item of a list field.

**One row per distinct pattern:**

1. Make a matching copy of the cited sentences: NFKC, whitespace removed, leading item numbering removed, each digit run replaced by `#`.
2. Within one field and one status, cluster rows whose copies have character 3-gram Jaccard similarity of 0.85 or more (a starting value, check it by eye on the first build).
3. Keep one row per cluster, picked by the seed. Record the cluster size.

The sheet shows the original text, never the matching copy.

**How rows are picked:** seed `20261128`.

1. Strata: field x document type (notice or tender page, bid instructions, spec).
2. Quota per field: 8 for each of the 10 tier 1 fields, 6 for each of the other 13. That is 158 rows, so that at least 150 are decided after some Unsure answers.
3. Inside a field, round robin over document types, taking from the least used document first.
4. At most 1 absent row per field, shown with keyword candidate sentences (D-81).
5. A field with fewer distinct patterns than its quota gives all it has. The rest is redistributed to tier 1 fields. The build report lists each shortfall.

Supply today, scored rows in dev plus test (before dedupe): between 17 (`notice_date`) and 25 (`title`, `issuer_org`, `scope_summary` and the other fields every type has) per field. `delivery_deadline` has only 3 rows that are not absent, so it will fall short. Distinct pattern counts were not computed. If 150 cannot be reached, label more open documents first. Do not add near-duplicates.

**Columns shown:**

| column | content |
|---|---|
| No | row number |
| Document | Japanese title and 8-character id prefix |
| Field | field name and one plain-English line saying what it means |
| Japanese source sentence(s) | original text with section path and sentence id |
| Our English answer | value in plain English, no JSON |
| Is the value correct? | Yes / No / Unsure |
| Is this the right sentence for this field? | Yes / No / Unsure |
| Is something missing from this answer? | Yes / No / Unsure |
| Correct English | if No |
| Correct Japanese | if wrong |
| Comment | optional |

**Not shown** (so the reader is not primed): split, label state, model or provider names, agreement. These go in a key file next to the sheet, with doc id, field, item index, cluster size, stratum, inclusion weight and the label file's SHA-256.

**Size:** the old instructions estimate 30 to 45 minutes for about 45 rows, so 158 rows is about 2 to 2.5 hours. Split into 3 tabs.

**Scoring the audit:**

- A row **disagrees** if any of: value No, sentence No, missing Yes.
- A row is **decided** if it disagrees, or all three answers are clean (Yes, Yes, No). Anything else is Unsure.
- Disagreement rate = disagreeing / decided. Report it with a 95% Wilson interval and the Unsure count.
- Because the sample is stratified and deduplicated, also report the rate weighted by cluster size and inclusion probability.
- Only a native speaker's review counts (D-41). A label line becomes `human_audited` only if all of it was reviewed, so a list line needs every item.

At 150 decided rows, under 5% means at most 7 disagreements (4.7%). The 95% interval at 7 of 150 is 2.3% to 9.3%. If the requirement were that the upper bound be under 5%, at most 2 disagreements would pass (upper bound 4.7%). The gate in section 6 uses the point estimate.

## 4. Who can verify which field

"Code" means the value can be checked by code or by eye with no Japanese. Code can show that a value appears in the cited sentence. It cannot show that it is the right sentence: a correct date under the wrong deadline kind passes. On OCR pages, compare digits and eras with the page crop.

| field | checkable without a reader | needs the reader |
|---|---|---|
| `notice_date` | date conversion and match | that it is the notice date |
| `delivery_deadline` | date | that it is the delivery deadline |
| `performance_period` | start and end dates | `relative_text`, which period it is |
| `deadlines` | datetimes, weekday check | kind, arrival flags, missing items |
| `item_category` | code digits | little: heading cue by eye |
| `bid_bond`, `performance_bond` | rate digits | required, waived, provisos |
| `contact` | phone and email copied exactly | organization, department, which office |
| `unified_qualification` | grade letters A to D | category, region, whether it is the national qualification |
| `tax_basis` | digits such as 100分の10 found | whether bids include or exclude tax |
| `language_currency` | fixed wording matched by eye | unusual wording |
| `title` | string match under a heading cue | whether it is the right line |
| `issuer_org` | string match | which body is the issuer |
| `contracting_officer` | string match | title against name, which person |
| `delivery_location` | string match | whether it is the place of delivery |
| `procurement_type` | fixed term found | negation, mixed wording |
| `award_method` | fixed term found | which method applies |
| `wto_covered` | cue found | negation |
| `submission_modes` | cue words found | allowed against forbidden |
| `spec_access` | cue found | the mode |
| `scope_summary` | nothing useful | all of it |
| `eligibility` | citations exist | items, kind, polarity, missing items |
| `required_documents` | names appear in the citation | item boundaries, missing items |

So: `notice_date`, `delivery_deadline` and `item_category` are close to fully checkable, once the heading is checked by eye. Six more (`performance_period`, `deadlines`, `bid_bond`, `performance_bond`, `contact`, `unified_qualification`) have a checkable part. The rest need the reader. Section numbers are not a v1 field: they appear in section paths and citations, which code checks.

## 5. Measurement protocol

### Metrics

All over scored rows, all three counts printed with their denominators.

| metric | definition (as `eval/run.py` computes it) |
|---|---|
| **Accuracy** (headline: verified field accuracy) | value correct and, when the label is not absent, at least one cited sentence in common. Absent label plus not found is correct |
| **Wrong-answer rate** | answers shown as `present` that are wrong, or whose label is absent, over scored rows |
| Wrong pointer count | `see_other_document` answers that are wrong. The code's wrong-answer rate does not include them, so report this count beside it |
| **Citation pass rate** | shown answers whose citations exist and whose value check is not False, over shown answers |
| Also reported | over-abstention, citation precision and recall, tier 1 accuracy, per-field counts |

Every report gives two versions where possible: all rows and without `labeler_overlap` rows (not possible for test today, section 1). It also splits reviewed rows from consensus rows. Every score on silver labels is called that (D-41).

### Paired bootstrap

1. Same documents, same label files (same SHA-256), same extractor and schema versions for A and B.
2. Resample documents with replacement, 10,000 times, seed `20261128`. A drawn document brings all its rows for both A and B.
3. Each resample: `delta = (sum correct_B - sum correct_A) / sum rows`. Do the same for the wrong-answer rate.
4. Report the point estimate, the 2.5 and 97.5 percentiles, and the number of rows that flipped in each direction.
5. A **gain** is claimed only if the lower bound is above 0. Otherwise report "no measurable difference" and the smallest readable gain from section 2.

`eval/bootstrap.py` does this for two saved dev reports: `uv run python -m eval.bootstrap <run_A.json> <run_B.json>`. It does not enforce all of step 1: run reports store no label file hashes, so it only refuses a row whose label status differs, and a changed label value or citation passes. Check the label files by hand until the reports carry hashes. It also does not split by `labeler_overlap` or reviewed rows, and does not check the other no-go conditions below.

### No-go conditions

A change is not adopted if any of these holds:

1. Citation pass rate below 100% of shown answers.
2. More wrong answers than the baseline (count, including wrong pointers), whatever accuracy does.
3. Any new wrong deadline.
4. The upper bound of the accuracy difference is below 0.
5. A rule change whose only example comes from the 15 dev documents (D-96).

A comparison is void, not just failed, if documents, label files, versions or settings differ between A and B, or if labels changed between the two runs.

### When test may run

- Only at a milestone: the end of Phase 6, then release. The Phase 4 / v0.1 run is used up (D-109).
- A decision entry is written **before** the run: what is frozen, which pipeline, which documents, which gates passed.
- Freeze evidence as in `eval.milestone`: clean tree under `core/` and `eval/`, one digest before and after, no overwrite of a report.
- Once. If a bug shows, stop and write it down. No fix and re-run to move a number (D-109).
- Nothing is tuned on test output afterwards. `52bba5f9` is skipped (D-102).
- The 10 documents already run once are reported separately from the unseen ones.
- Test labels are finished and frozen before any candidate model produces output on a test document.

## 6. LoRA go / no-go gates

All must pass. Status is as of 2026-11-28.

| # | gate | status now | pass? |
|---|---|---|---|
| 1 | all 29 eligible open test documents reviewed, at least 400 reviewed rows | 10 documents labeled, 190 scored rows, 83 reviewed | no |
| 2 | all 37 open dev documents reviewed, at least 600 reviewed rows | 15 documents labeled, 324 scored rows, 202 reviewed | no |
| 3 | native audit of at least 150 rows, under 5% disagreement | 0 rows | no |
| 4 | the last two rule changes each moved dev verified accuracy by under 2 points | D-108: 1 row of 324 (0.3 points). No measurement over all scored rows was found for the change before it. Rules are frozen (D-109) | not established |
| 5 | at least 2 fields where the model misreads a correct sentence | not established. List-field errors were sorted in the Phase 5 reports, but no native reader confirmed a misread | not established |

How each is read:

- **Open documents only:** gates 1 and 2 cover open documents (Yasharth, 2026-11-28). Restricted documents are not needed, so D-111 is not in the way. The task said 40 test and 60 dev documents; test is 29 because 30 are open and D-102 excludes `52bba5f9`. No replacement document is added.
- **Gates 1 and 2:** only reviewed scored rows count (`silver_model_reviewed` or `human_audited`). Consensus rows do not, until someone reviews them (Yasharth, 2026-11-28). `eval.silver reopen` turns an accepted consensus row back into a review item.
- **Gate 4:** measured over all scored dev rows, each change on its own. It is a stop rule on the point estimate, not a significance test: 2 points is below what section 2 says can be detected.
- **Gate 5:** the cited sentence is the label's sentence, the extracted text is right, the model's value is wrong, and the label is confirmed by code (dates, amounts) or by the native reader.

Reviewed share needed to reach the row gates:

| gate | open scored rows | reviewed share needed | today's share |
|---|---|---|---|
| dev, 600 reviewed rows | 752 | 80% | 62% |
| test, 400 reviewed rows | 555 | 72% | 44% |

At today's share this would give about 469 dev and 242 test reviewed rows, so both fall short unless consensus rows are reviewed.

What the gates no longer cover:

| | dev | test |
|---|---|---|
| restricted documents left out | 23 | 10 |
| of those, specs / bid instructions | 10 of 15 / 8 of 15 | 4 of 10 / 4 of 10 |
| orgs with no document left | 2 of 8 | 1 of 8 |
| documents with OCR pages left out | 3 of 3 | none exist |

So a result under these gates says nothing about OCR pages or those orgs, and much less about specs on dev. The section 2 figures that apply are the open ones: about 4.5 points on dev and 5.1 on test in the central case.

### Training data

D-125. Training targets come only from filtered Qwen self-distillation:

- **Documents:** open license only (Yasharth, 2026-11-28), new ones in neither the dev nor the test label set, from agencies that are not in dev or test. Restricted and unknown documents are not used. Today that means 88 open documents from 12 of the train orgs (54 notices, 8 specs, 8 bid instructions, so 70 of a type that has fields, plus 18 of other types) or newly collected open documents from agencies assigned to train by a decision entry. Check each id with `webcheck` when building the set.
- **Split by issuing agency:** the training set's own validation part holds out whole agencies too.
- **Targets:** the local Qwen's own answers.
- **Filters:** citations exist and are Japanese, the value appears in the cited sentence, normalized values convert again from that sentence, and no conflict with a deterministic rule.
- **Never:** Gemini or Groq outputs, web chat outputs, silver labels, or dev and test documents, either as targets or inside a filter.

A limit to settle before Phase 6 starts: gate 5 asks for places where the model misreads a correct sentence, and self-distillation teaches the model its own answers. The filters above remove errors that code can catch. A misread that passes them is trained back in. Before training, name for each gate 5 field the filter that would reject the misread. If no such filter exists, a LoRA is not expected to fix that field, and that is a no-go for it.

## Open questions

None open. Before any trained weights are shared, record the attribution or other terms of the open sources used for training (not checked here).
