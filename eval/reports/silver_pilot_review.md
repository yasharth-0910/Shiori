# Pilot review: provider stats, mapping recovery, agreement replay (sv2 work)

Inputs: 37 answered items of the sv1 pilot (`pilot-all.txt`; F-0022 is unanswered), the exported batches the reviewer saw, and the sv1 raw answers in the cache. Field types: 4 text, 25 structured, 8 list. Three documents, so every rate below is a rough indication. The reviewer is `claude_chat` (a model in chat), so "right" means "what the reviewer chose", not verified truth. Rebuild: `uv run python -m eval.silver replay --out eval/reports/silver_pilot_review.md`.

## Which provider was A and which B

The pilot export did not record it. `resolve()` builds the candidates in `SLOTS` order (gemini, groq; unchanged since the pilot commit 56a3a79) and labels them A, B. Check: every candidate shown in the batches is compared with the one rebuilt from each provider's cached sv1 answer (status, value, citations).

- A=gemini, B=groq: 34 (F-0001, F-0002, F-0003, F-0004, F-0005, F-0006, F-0007, F-0008, F-0009, F-0010, F-0011, F-0012, F-0013, F-0014, F-0015, F-0018, F-0019, F-0020, F-0021, F-0022, F-0023, F-0024, F-0025, F-0026, F-0027, F-0028, F-0029, F-0030, F-0032, F-0033, F-0034, F-0035, F-0036, F-0038)
- A=groq, B=gemini: 0 (-)
- inconclusive: 4 (F-0016, F-0017, F-0031, F-0037)

A side counts as evidence when it matches one provider's rebuilt candidate and not the other's: first by value and citations; where that cannot tell, by quote and citations. Inconclusive items are ones where A and B were the same answer (consensus spot-checks, both absent), so the order cannot be seen. `export/mapping.json` records A = gemini, B = groq for every pilot item.

## How often each provider's candidate was right when shown

Right = the reviewer accepted it, or the reviewer's final answer is the same answer (status, value; English text and item order ignored). Spot-check items count for both.

| provider | field type | shown | right | right % | right (items) | wrong (items) |
| --- | --- | --- | --- | --- | --- | --- |
| gemini | list | 8 | 7 | 88% | F-0001, F-0002, F-0003, F-0005, F-0006, F-0033, F-0034 | F-0035 |
| gemini | structured | 25 | 20 | 80% | F-0004, F-0007, F-0009, F-0010, F-0013, F-0014, F-0016, F-0017, F-0020, F-0021, F-0023, F-0026, F-0027, F-0028, F-0030, F-0031, F-0032, F-0036, F-0037, F-0038 | F-0008, F-0011, F-0012, F-0015, F-0025 |
| gemini | text | 4 | 2 | 50% | F-0018, F-0019 | F-0024, F-0029 |
| groq | list | 8 | 0 | 0% | - | F-0001, F-0002, F-0003, F-0005, F-0006, F-0033, F-0034, F-0035 |
| groq | structured | 25 | 9 | 36% | F-0009, F-0012, F-0015, F-0016, F-0017, F-0025, F-0031, F-0032, F-0037 | F-0004, F-0007, F-0008, F-0010, F-0011, F-0013, F-0014, F-0020, F-0021, F-0023, F-0026, F-0027, F-0028, F-0030, F-0036, F-0038 |
| groq | text | 4 | 1 | 25% | F-0024 | F-0018, F-0019, F-0029 |

- gemini: right 29 of 37 shown (78%)
- groq: right 10 of 37 shown (27%)

Note: on F-0029 (and Gemini's F-0024) the shown candidate was a see_other_document text field whose ref the sv1 parser had dropped (the step-0 bug), so it counts as wrong here; the reviewer's note on F-0029 says both candidates had the right content. "Same answer" compares status and value only, so a candidate with the right normalized value but an unusable quote (Groq's F-0009, an ellipsis) counts as right.

## Agreement relaxations, replayed

Each rule is replayed alone on top of the baseline (sv2 parsing, chunk merging and the cue fix, sv1 agreement). Settled = the field would have been accepted without review. A rule passes when it settles at least one item correctly that the baseline does not, and never settles an item wrongly (accepting a candidate the reviewer rejected or replaced). Status, enum, date and amount comparisons are never loosened.

| rule | what it does | settles correctly (new) | settles wrongly | passes |
| --- | --- | --- | --- | --- |
| baseline | sv2 parsing, merging and cue fix; sv1 agreement | F-0009, F-0014, F-0016, F-0017, F-0031, F-0032, F-0037 | - | - |
| list_items_by_citation | list items pair by citation overlap and their enum and date parts; item text similarity is not required | - | - | no |
| officer_concat | contracting_officer compares title + name as one string | F-0021 | - | yes |
| contact_concat | contact compares phone digits, email and org + department as one string | F-0036 | - | yes |
| uq_category_normalized | unified_qualification compares grades exactly and the category without brackets, quotes and list punctuation | F-0007 | - | yes |
| period_relative_optional | performance_period compares relative_text only when both set it (start and end stay exact) | F-0026 | F-0025 | no |
| text_without_citation_overlap | text fields with the same value agree even when they cite different sentences | - | - | no |
| eligibility_negation | an eligibility item with polarity requirement whose text_ja keeps the negation (…ないこと, …ではないこと, …がない者であること) equals the same condition with polarity disqualification and the negation stripped | - | - | no |
| ACTIVE (contact_concat, eligibility_negation, officer_concat, uq_category_normalized) | the rules switched on, together, on top of the baseline | F-0007, F-0021, F-0036 | - | - |

## Every review round, on the candidates as shown

Reviewed items with a frozen batch: 56 (F-0001 to F-0057).

| rule | active | settles correctly (new) | settles wrongly | reviewed items of its field |
| --- | --- | --- | --- | --- |
| list_items_by_citation | no | - | - | all |
| officer_concat | yes | F-0020, F-0021 | - | all |
| contact_concat | yes | F-0036 | - | all |
| uq_category_normalized | yes | F-0007 | - | all |
| period_relative_optional | no | F-0026 | F-0025 | all |
| text_without_citation_overlap | no | F-0048 | - | all |
| eligibility_negation | yes | - | - | F-0005, F-0006, F-0042 |
