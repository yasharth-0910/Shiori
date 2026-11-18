# Phase 5 design review: why list-field verified accuracy stays at 26 to 28%

Read-only review. No code, label, prompt, scorer, test split or `EXTRACTOR_VERSION` was changed, no model was started and no network call was made. This file holds doc id prefixes, sentence ids, field names, kinds and counts only, no document text. Dev only, 14 documents, model-reviewed silver labels (D-41). Qwen3.5-9B helped make these labels and the prompts were tuned on these documents, so every number is a fit, not a forecast. The calls on what counts as a convention are my reading of the written guide, not a native speaker's.

## 1. What was counted

The unit is the **row**: one (document, list field) with a label, 39 rows (13 eligibility, 13 deadlines, 13 required_documents). A row is right only when every answer item has a distinct partner in the label and the other way round (`eval/silver/agree.py`, `_match` with `item_same`). One missed or one extra item makes the whole row wrong.

State used for each model, the latest one that exists:

| | right | wrong value shown | not found | not right (rows to explain) |
| --- | --- | --- | --- | --- |
| Qwen3.5-9B, saved trace replayed through current `llm.py`, required_documents taken from the fix 2 run | 11 | 26 | 2 | 28 |
| Gemma 4 E4B, saved trace replayed through current `llm.py` (fix 1 on) | 11 | 28 | 0 | 28 |

11 of 39 is 28%. Before the two fixes both models were at 10 of 39 (26%). The replay reproduces `phase5_fix1_changelog.md` exactly (Qwen 10 / 27 / 2, Gemma 11 / 28 / 0, 0 calls with a different window). The Qwen required_documents rows come from `fix2_after.json` (6 right, 7 wrong, 0 not found); that run kept per-document counts but no trace, so its items are counted, not inspected (see section 7). `model_compare_list_fields.md` says 3 not found for Qwen; the third is 4b0b9d82 eligibility, where the label is absent, nothing was extracted, and the row counts as right.

How each label item got a cause: `eval.hybrid.classify` gives a, b, c, d per label item as in the diagnostics; I then split c and d by what the trace and the label show (citations, which sentence each side cites, distance between them, marker words such as 必着 or 開札 in those sentences, the guide rules). Extra answer items with no label partner were added as their own items. A row's categories are the union over its items.

## 2. The five categories, and how many rows each explains

| category | what it means here | Qwen items | Qwen rows touched | Qwen rows where it is the only cause | Qwen rows, equal share | Gemma items | Gemma rows touched | Gemma only cause | Gemma equal share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| (1) label or convention, needs a native reader | legal vs other kind, polarity labels older than the guide rule, deadline `other` labels older than the electronic rule, where a document name starts and ends, and answer items the label does not have (the label may be missing them) | 22 (12 convention, 10 extra) | 16 | 11 | 13.5 | 31 (15 convention, 16 extra) | 19 | 8 | 13.3 |
| (2) retrieval and window | the label's sentence was never sent (a), or the item's sub-item sentence was outside the window and the model answered with the list header (d4) | 17 | 4 | 0 | 1.8 | 17 | 4 | 0 | 2.0 |
| (3) value and kind normalization | deadline kind the code could set (`electronic` on an electronic notice, 開札 or 必着 in the item's own span), deadlines dropped for having no date, a dedupe-key drop, and required_documents names longer than the label's | 8 | 5 | 2 | 3.2 | 13 | 10 | 3 | 5.8 |
| (4) the validator reads each cited sentence on its own | the item's time, 必着, or proviso sits in the sentence next to the one cited, or the text spans two sentences and only one was cited; also 5 items whose deciding sentence is 2 to 17 sentences away | 13 (7 next sentence, 5 far, 1 spans 3 sentences) | 10 | 2 | 5.5 | 17 (11 next sentence, 5 far, 1 spans 5 sentences) | 11 | 0 | 4.9 |
| (5) the model | in the window but not produced (b), polarity read from a header, a kind with no wording behind it | 9 | 7 | 2 | 4.0 | 5 | 5 | 0 | 2.0 |
| all | | 69 | 28 rows | 17 rows have one category, 11 have two or more | 28.0 | 83 | 28 rows | 11 one, 17 two or more | 28.0 |

"Equal share" splits each row evenly over its categories, so the column adds up to the 28 rows. "Only cause" is the number of rows that fixing that category alone could flip (an upper bound: the row's items would also have to pair after the fix).

Some items need two fixes at once (Qwen 136dfba9 deadlines: time in the next sentence and kind `electronic`; six Gemma deadline items: no date and a kind or neighbour problem). They are counted under each category they need, so the item column adds up to more than the number of distinct items (Qwen 69 for 68 items, Gemma 83 for 77).

### Sub-causes behind the table

| sub-cause | category | Qwen | Gemma |
| --- | --- | --- | --- |
| extra answer item with no label item | (1) | 10 | 16 |
| eligibility kind legal vs other (or other vs certification) | (1) | 5 | 6 |
| eligibility polarity: answer keeps the negation and says requirement, older label says disqualification | (1) | 3 | 3 |
| required_documents name boundary, answer shorter than label | (1) | 3 | 5 |
| deadline label `other` older than the electronic rule | (1) | 1 | 1 |
| a: label sentence outside the window (same 10 items for both models) | (2) | 10 | 10 |
| d4: list header cited, sub-item sentence outside the window (all d40000) | (2) | 7 | 7 |
| deadline kind `electronic` on an electronic notice, model said bid_in_person or other | (3) | 3 | 3 |
| deadline kind readable from the item's own span (開札, 必着, 郵送) | (3) | 1 | 2 |
| deadline with no datetime, not recovered by fix 1 (schema) | (3) | 0 | 5 |
| dropped by the dedupe key | (3) | 0 | 1 |
| required_documents name longer than label (answer holds the name plus a clause) | (3) | 4 | 2 |
| deadline time or 必着 in the next sentence | (4) | 4 | 6 |
| eligibility text spans the previous sentence, only one cited, dropped as value_not_in_citation | (4) | 1 | 3 |
| eligibility なお/ただし proviso sentence left out of the item (guide F-0076) | (4) | 2 | 2 |
| deciding sentence 2 to 17 away, another section | (4) | 5 | 5 |
| item spans 3 or more sentences, answer took part of it | (4) | 1 | 1 |
| b: in the window, not produced | (5) | 6 | 2 |
| d2 real: polarity from a header (d40000) | (5) | 2 | 0 |
| deadline kind with no wording behind it | (5) | 1 | 3 |

The 10 category a items and the 7 d4 items are the same ids in both models; `model_compare_list_fields.md` shows a = 10 for 7 of the 8 models. Retrieval is model independent.

## 3. Qwen3.5-9B: the 28 rows that are not right

Numbers are items per category.

| row | state | categories |
| --- | --- | --- |
| f19cddbd eligibility | wrong | (1) 2, (4) 1 |
| f19cddbd required_documents | wrong | (1) 1 |
| 58f13b9c eligibility | wrong | (1) 1 extra |
| 58f13b9c deadlines | not found | (3) 1, (4) 1, (5) 1 |
| 58f13b9c required_documents | wrong | (1) 1 |
| a81e99fe eligibility | wrong | (1) 1 extra, (2) 1 |
| a81e99fe deadlines | wrong | (3) 1, (4) 1 far, (5) 1 |
| 136dfba9 eligibility | wrong | (1) 2, (4) 1 |
| 136dfba9 deadlines | not found | (3) 1, (4) 2 |
| d230e51e eligibility | wrong | (1) 1 extra |
| d230e51e deadlines | wrong | (1) 1 extra |
| 6b7142ab eligibility | wrong | (1) 2 |
| 6b7142ab deadlines | wrong | (3) 1 |
| 6b7142ab required_documents | wrong | (1) 2 extra (fix 2 run) |
| 84e9d0c8 eligibility | wrong | (1) 1 extra |
| 84e9d0c8 deadlines | wrong | (4) 1 far, (5) 2 |
| 594c3cb6 eligibility | wrong | (1) 1 extra |
| 594c3cb6 required_documents | wrong | (5) 1 |
| a13baaac eligibility | wrong | (4) 1 (spans 3 sentences) |
| a13baaac deadlines | wrong | (2) 1, (4) 1 |
| a13baaac required_documents | wrong | (5) 1 |
| 563042df eligibility | wrong | (1) 2, (4) 1 |
| 563042df deadlines | wrong | (1) 1 |
| 563042df required_documents | wrong | (1) 1 |
| d4000027 eligibility | wrong | (2) 13, (5) 2 |
| d4000027 required_documents | wrong | (3) 4 |
| 28ad40ea eligibility | wrong | (1) 2, (2) 2, (5) 1 |
| 28ad40ea deadlines | wrong | (4) 3 far |

## 4. Why the score does not move

1. **Half the failing rows fail only on category (1).** 11 of Qwen's 28 (8 of Gemma's) have nothing else wrong: 6 fail only on extra items the label does not have, 4 only on convention items, 1 on both. No change to retrieval, checks or model can flip them, because the disagreement is about what the label should say.
2. **The rest carry several causes at once.** 11 Qwen rows have two or more categories, so each fix repairs items but not rows. Fix 1 recovered 23 Gemma deadline items and flipped 1 row. Fix 2 raised required_documents items hit from 50 to 56 of 65 and moved rows from 5 to 6 (one row went right to wrong on 2 extra items).
3. **Ceiling without category (1).** If every pipeline and model cause were fixed and the labels stayed as they are, Qwen could reach 11 + 12 = 23 of 39 (59%), Gemma 11 + 9 = 20 of 39 (51%). If everything except the model were fixed, Qwen reaches 32 of 39, Gemma 34 of 39. Category (1) is the largest single block, and the model is not.
4. **Two guide rules are in the prompt and still missed.** The prompt already says that the なお/ただし minors proviso stays inside the item and that a bid receipt deadline on an electronic notice is `electronic` (`llm.py` `RULES`). Both models still miss them: 2 proviso items each, 3 `electronic` items each. The `electronic` rule needs a fact about the whole notice that the model cannot see in a deadlines window, and the same prompt also says to use `other` when the sentence does not say how bids are received.
5. **The pipeline treats an item as one sentence.** The segmenter often splits one line in two (date, then time or 必着 on the next line; a 第70条 sentence, then its なお proviso). The labels cite both sentences, the model usually cites one, and the code reads only what is cited: `_deadline_when` needs the time inside the date's own span in the same sentence, flags come from cited sentences only, and `value_in_citation` checks the cited text only. That gives 7 (Qwen) and 11 (Gemma) items, all next-sentence cases, in the same rows as other causes.

## 5. Three changes most likely to raise the score without making the scorer more lenient

Row gains below are upper bounds from this replay (a row counts only when every item on it is covered), on the same 14 documents the gains were derived from.

### 5.1 Settle the label conventions and the extra items (category 1)

What: (a) apply the written guide rules to the dev labels mechanically where code can check them: the 3 polarity labels per model that contradict F-0042 (negation kept means requirement; checked: all 3 keep the negation in their own `text_ja` and say disqualification) and the 1 deadline `other` label that predates the electronic rule, applied to every label item, hit or not, not only the ones the extractor disagrees with; (b) have a native reader, who does not see the model's answers, write the legal vs other line and the document-name boundary line into `docs/field_schema.md` and then decide the 10 (Qwen) and 16 (Gemma) extra answer items: missing from the label, or over-produced. Record it as a `docs/decisions.md` entry under the eval protocol. The scorer and the matching rule stay as they are.

Gain: up to 11 Qwen rows and 8 Gemma rows alone (4 and 2 of them from (a) and the two written lines, the rest from the extra items). It is the only change whose upper bound is above 5 rows.

Risk: relabeling dev after reading the extractor's answers fits the labels to the extractor. The reader may also side with the label, and then the gain is 0. A relabel can turn rows that are right now into wrong ones, which is why the rule has to go over every item. It needs a native reader, so it cannot be done here. The test split must not be touched. It improves the measurement, not the app: the app gives the same answers after it.

### 5.2 Let the validator read the sentence next to a cited one (category 4)

What: in `core/shiori_core/extract/llm.py` `_check` and `_deadline_when`, look at the sentence right before and right after each cited sentence, in the same section. For deadlines, take a time, 必着 or 消印有効 from the next sentence only when that sentence has no date of its own and the item's own date span has no time. For eligibility, accept a text that spans the previous or next sentence, and add a following なお/ただし sentence about 未成年者, 被保佐人 or 被補助人 (guide F-0076). In each case, add the neighbour's id to the item's citations, so the highlight covers it and the evidence check still runs on cited text only.

Gain: 7 Qwen items and 11 Gemma items. No row flips on this alone. Together with 5.3: Qwen 2 rows (136dfba9 deadlines, 6b7142ab deadlines), Gemma 4 rows. Together with 5.1 and 5.3: Qwen 16, Gemma 15.

Risk: it loosens the D-69 rule that a time must sit in its date's span, written for the 594c3cb6 case where a mail time in brackets passed for the bid time. A neighbour can hold the time of a different deadline. Keep the "no date of its own" condition and recheck 594c3cb6 and the hallucination count (0 now) on a rerun. The 5 far items are not covered, since that would mean linking a general clause to a date many sentences away.

### 5.3 Set the deadline kind and the missing date in code (category 3, deadlines)

What: after the checks, set `kind` from wording instead of trusting the model where the wording is certain. Use `electronic` when the rules extractor's `submission_modes` for the notice is electronic only and the cited sentence names the bid receipt (受領期限, 入札書の提出); use `bid_opening` when 開札 is in the item's own span; use `mail_arrival` when 必着 or 郵送 is in the item's own span (`spans_of` already gives the span). Extend fix 1's date recovery to the next sentence from 5.2, for Gemma's 5 deadlines still dropped as `schema`.

Gain: Qwen 4 items, Gemma 11. Alone: Qwen 1 row (6b7142ab deadlines), Gemma 2 rows (6b7142ab, 594c3cb6 deadlines). With 5.2: Qwen 2, Gemma 4.

Risk: the kind then depends on `submission_modes` (12 of 13 right on dev, `rules_v4_side_by_side.md`), so its errors pass on to deadlines. It overrides the model on a field the prompt describes two ways (`other` when the sentence is silent, `electronic` on an electronic notice), so the prompt and the code must say the same thing afterwards. The required_documents names that are too long (4 Qwen items, all d40000) are not in this change: trimming a name needs a boundary rule, which is part of 5.1.

### Not in the top three

- Retrieval (category 2): 17 items, but 0 rows flip on it alone, and 13 of the items are in one document (d40000, a lettered list running past the 3-sentence window). With 5.2 and 5.3 it adds 1 Qwen row (a13baaac deadlines) and 1 Gemma row.
- Model (category 5): 9 Qwen items, 2 rows alone (594c3cb6 and a13baaac required_documents, items merged into a multi-sentence item even after fix 2). Gemma: 5 items, 0 rows alone.

## 6. Order and what to measure

5.2 and 5.3 change only `llm.py`, can be checked by replaying the saved traces like fix 1, and need no model run to see the item counts. 5.1 needs the native reader and a decision entry first. Every gain above is a fit to these 14 documents; the only fair check is a rerun on documents nobody tuned on, which do not exist yet for the list fields.

## 7. What I actually saw

Files read in full: `eval/reports/list_field_wrong_value_analysis.md`, `phase5_fix1_changelog.md`, `phase5_fix1_unpaired_deadlines.md`, `phase5_fix2_required_documents.md`, `model_compare_list_fields.md`; `docs/project_log.md` (Phase 3 tail to Phase 5); `docs/labeling_guide.md` (lines 88 to 135); `docs/field_schema.md` (deadline kinds, by grep). Code read: `core/shiori_core/extract/llm.py` (`RULES`, `retrieve`, `spans_of`, `_deadline_when`, `_recover_date`, `_polarity`, `_check`, `read_items`, `_recovered`, `extract_lists`), `core/shiori_core/extract/rules.py` (`value_in_citation`), `eval/hybrid.py` (`subcause`, `classify`), `eval/silver/agree.py` (`similar`, `_match`, `item_same`, `_negation_form`, `agree`), `eval/phase5_fix1_replay.py`, the uncommitted diff of `llm.py` (the fix 2 prompt line) and `eval/phase5_fix1_unpaired.py`.

Data read by scratch scripts in the session scratchpad (outside the repo, nothing written into it): `data/cache/hybrid/trace_cmp_qwen35_9b.json` and `trace_cmp_gemma4_e4b.json` (39 calls each), replayed through `eval.phase5_fix1_replay.after_outputs` and scored with its `score`; the 14 dev label files through `eval.run.read_labels`; each document's sentences through `eval.documents.load_sentences`, for sentence order, section titles and marker words only, nothing printed; and `fix2_after.json` from the fix 2 session's scratchpad (per-document counts).

Counts reproduced: Qwen 10 right / 27 wrong / 2 not found before fix 2, Gemma 11 / 28 / 0 after fix 1, 0 calls with a moved window; category a = 10 items for both, the same ids; d4 = 7 items, all d40000, with the label-only sentence outside the window in 7 of 7; Qwen required_documents after fix 2: 6 right, 2 b, 7 d.

Could not explain:
- The 10 Qwen and 16 Gemma extra answer items: whether the label is missing them or the model over-produced. That needs a Japanese reader.
- The 2 extra items on Qwen 6b7142ab required_documents after fix 2. The fix 2 run kept no trace, so they are counted, not looked at. I also assumed the 7 required_documents d items after fix 2 are the same items as before; the per-document counts match (f19cddbd 1, 58f13b9c 1, 563042df 1, d40000 4), but I did not compare them item by item.
- Why both models ignore the proviso rule that is already in the prompt.
- Why 5 Gemma deadline items still have no date after fix 1 (the cited sentences give zero or two dates; I did not check which).
- The 5 far items per model (label cites a sentence 2 to 17 away, in another section): I counted them under (4), but whether a general clause that far away belongs to a given date is also a reading call.
- Whether the 2 d40000 polarity items (d2 real) are a model error or a label reading of the list header.
