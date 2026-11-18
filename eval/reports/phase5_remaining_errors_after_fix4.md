# Phase 5: list-field rows still wrong after fix 4

Read-only analysis of the saved traces and the current labels. No code, label, scorer, prompt, test split or `EXTRACTOR_VERSION` was changed, no model was started, no cloud call. Dev only, 14 documents, model-reviewed silver labels (D-41); both models were tuned or labeled on these documents, so every count is a fit, not a forecast. No document text in this file: doc id prefixes, sentence ids, field names, kinds, counts and the marker words the design review already uses (必着, 開札, なお).

## 1. What was counted

A row is one list field of one document (eligibility, deadlines, required_documents), 42 rows. It is right only when every answer item has a distinct partner in the label and the other way round (`eval/silver/agree.py` `item_same`). The saved proposals of both models were replayed through the current `core/shiori_core/extract/llm.py` (fixes 1 to 4 on) and scored with the unchanged scorer. This reproduces `phase5_summary_after_fix4.md` exactly: Qwen3.5-9B 15 right, 25 wrong value, 2 not found; Gemma 4 E4B 14 right, 28 wrong value, 0 not found. So 27 + 28 = 55 rows are listed in section 4.

One caveat carried over from that summary: the Qwen required_documents rows come from the old saved trace (5 right), not from the fix 2 run, which was never saved. The Qwen required_documents rows below may include one row that the fix 2 run had right.

Categories are the ones of `phase5_design_review.md`: label or convention (L), kind or value normalization (N), validator reads one sentence (V), retrieval or window (R), model (M), and other (O). Where the review put extra answer items with no label partner under label or convention (it cannot be told from here whether the label misses them), this report does the same, except where the cited sentence is plainly not a deadline (marked M).

**Primary cause rule.** Each wrong row has exactly one primary cause: the cause on the most items of the row. A tie goes to the earlier pipeline stage (R, then V, N, M, L, O), because that stage hides the later ones. Every other cause on the row is listed as `also`. Primary counts below add up to the number of wrong rows.

## 2. Counts per category and per model

Primary cause (rows):

| category | Qwen3.5-9B | Gemma 4 E4B | both |
| --- | --- | --- | --- |
| (L) label or convention | 8 | 11 | 19 |
| (N) kind or value normalization | 4 | 6 | 10 |
| (V) validator reads one sentence | 4 | 5 | 9 |
| (R) retrieval or window | 4 | 4 | 8 |
| (M) model | 7 | 2 | 9 |
| (O) other | 0 | 0 | 0 |
| all wrong rows | 27 | 28 | 55 |

Rows touched by the cause at all (primary or `also`):

| category | Qwen3.5-9B | Gemma 4 E4B |
| --- | --- | --- |
| (L) label or convention | 12 | 19 |
| (N) kind or value normalization | 8 | 10 |
| (V) validator reads one sentence | 6 | 6 |
| (R) retrieval or window | 4 | 4 |
| (M) model | 11 | 4 |
| (O) other | 2 | 0 |

By field (primary cause, rows):

| field | Qwen3.5-9B: L N V R M O | Gemma 4 E4B: L N V R M O |
| --- | --- | --- |
| eligibility | 4 0 2 3 0 0 (of 9) | 4 0 2 3 0 0 (of 9) |
| deadlines | 1 3 2 1 2 0 (of 9) | 2 5 3 1 0 0 (of 11) |
| required_documents | 3 1 0 0 5 0 (of 9) | 5 1 0 0 2 0 (of 8) |

## 3. Ranked: the 3 largest groups a deterministic rule could fix

A rule here is something code can check without a model and without a Japanese reader. Rows flipped are **measured**: the rule was applied in memory on the replayed answers (and on the labels where it says so), then the whole 42 rows were rescored, so a row that turns from right to wrong shows up as a loss. Nothing was written to the repo or to a label file. Ranked by rows flipped, both models added.

| rank | rule | rows it flips (Qwen / Gemma) | rows lost | what it needs |
| --- | --- | --- | --- | --- |
| 1 | **P: proviso text and copies.** (a) Label side: when a label item cites a なお or ただし sentence, its text_ja holds that sentence too (guide F-0076, what the code already does). (b) Code side: after `_merge_provisos`, drop an item identical in kind, text and citations to one already kept. | 3 / 3 (6 rows): eligibility 58f13b9c, d230e51e, 6b7142ab (Qwen); 58f13b9c, d230e51e, 594c3cb6 (Gemma) | 0 | 5 dev label items in 5 documents change (58f13b9c, 594c3cb6, 6b7142ab, a81e99fe, d230e51e); 9 other label items in 7 documents already include the proviso. Part (b) alone flips 0 rows; part (a) alone flips 1 Qwen and 3 Gemma rows. Relabeling dev after seeing the answers fits the labels to the extractor; the label change is mechanical, but it still needs Yasharth's call. |
| 2 | **K: deadline kind from the sentence's own cue, only when the model said `other`.** K1: cue 開札 gives bid_opening. K2: cue 入札書の受領期限 or 提出期限 on a notice whose rules-extractor submission_modes is electronic only gives electronic. | 1 / 2 (3 rows): deadlines 6b7142ab (Qwen, Gemma), 594c3cb6 (Gemma) | 0 with the label fix below, else K2 loses f19cddbd deadlines in both models | K2 only nets positive when the dev label of f19cddbd deadlines item 1 (kind other, same bid receipt wording that 6b7142ab labels electronic) is also set to electronic. K1 alone: 0 Qwen, 1 Gemma. The wider version in the design review (override any kind on the cue) was tried too and loses 594c3cb6 deadlines for Qwen, so it is not this rule. |
| 3 | **REL: drop a deadline item whose relative_text has no number in it.** | 1 / 0 (1 row): deadlines d230e51e (Qwen) | 0 | One example only. It is a guess from a single row, so treat it as the weakest of the three. |

Rows are on different fields, so the three do not overlap: all three applied, Qwen 15 + 3 + 1 + 1 = 20 of 42 and Gemma 14 + 3 + 2 = 19 of 42 (an estimate by addition; the K and REL parts were rescored together in one run, P was rescored separately).

Groups checked that flip **0 rows alone** (so they are not in the top three, even though they touch rows):

| rule | rows it touches (primary or also) | rows it flips alone | why |
| --- | --- | --- | --- |
| NV: validator reads the sentence before or after a cited one (design review 5.2) | 6 Qwen / 6 Gemma | 0 | every row it touches also has a kind, extra-item or retrieval cause. Measured for eligibility value_not_in_citation (0 gained, 0 lost on both models); for deadlines, reasoned from the per-row causes (not simulated). |
| DR: take the date from the cited sentence when the model's date is not in it | 1 (Qwen 58f13b9c deadlines) | 0 | the row also has an item not produced, a time in the next sentence and a 必着 outside the date span. |
| RT: retrieval or window change | 4 Qwen / 4 Gemma | not measurable here | a different window changes the prompt, so it needs a model run, see the time cost in section 6. |
| required_documents name boundary (trim or extend a name) | 4 Qwen / 4 Gemma | 0 | no rule found: both directions occur (answer shorter and answer longer), and the boundary is the open label question. |

## 4. Every wrong row

`also` lists the other causes on the row. `rule`: P, K1, K2, REL, NV, DR as in section 3, RT retrieval change, none = no deterministic rule found. `flips` names the rule that flips the row in the in-memory test. A row marked with a rule but empty `flips` would still be wrong after that rule, because of the `also` causes.

### Qwen3.5-9B (27 rows)

| doc | field | primary | also | rule | flips | what the row looks like |
| --- | --- | --- | --- | --- | --- | --- |
| 58f13b9c | eligibility | L | - | P | P | label text stops before the proviso it cites; answer includes it |
| a81e99fe | eligibility | R | - | RT | - | label sentence never sent (1 item) |
| 136dfba9 | eligibility | V | L | NV | - | suspension item dropped, its text starts in the sentence before the one cited; plus 1 extra item over 4 sentences |
| d230e51e | eligibility | L | O | P | P | same proviso label text; plus a second identical copy of the item left by the merge |
| 6b7142ab | eligibility | L | O | P | P | same proviso label text; plus an identical copy left by the merge |
| 594c3cb6 | eligibility | L | - | P | - | proviso label text; plus 1 extra item (h_s58), so P alone does not flip it |
| a13baaac | eligibility | V | L | none | - | item spans 3 sentences, answer took 2; kind other vs legal |
| d4000027 | eligibility | R | M | RT | - | 6 label items never sent, 7 sub-items outside the 3-sentence window; polarity read from the list header |
| 28ad40ea | eligibility | R | L,M | RT | - | 2 label items never sent (tie with 2 kind items, earlier stage wins); 1 not produced |
| 58f13b9c | deadlines | N | M,V | DR | - | all 3 items dropped: model wrote year 2024, sentence says 2022; also 1 item not produced, 1 time in next sentence, 必着 outside the date span |
| a81e99fe | deadlines | N | M | none | - | date range split into two single-date items; 2 items with the wrong kind |
| 136dfba9 | deadlines | V | N | NV | - | time sits in the next sentence (2 items), dropped; 1 item also needs kind electronic |
| d230e51e | deadlines | M | - | REL | REL | 1 extra relative_text item whose cited sentence is not a deadline (no number in it) |
| 6b7142ab | deadlines | N | - | K2 | K2 | kind other vs electronic on a bid receipt line; the same wording is labelled other in f19cddbd, so K2 needs that label fixed too |
| 84e9d0c8 | deadlines | M | N | none | - | 2 items not produced; 1 kind and citation difference |
| a13baaac | deadlines | R | V,N | RT | - | 1 label sentence never sent; the other item needs the 必着 sentence and kind mail_arrival |
| 563042df | deadlines | L | - | none | - | label says other, answer says electronic (label older than the electronic rule); no cue in the cited text a rule could use |
| 28ad40ea | deadlines | V | N | NV | - | 必着 sits in the next sentence (3 items); 1 item also has kind other for question |
| f19cddbd | required_documents | L | - | none | - | answer name shorter than label name (boundary) |
| 58f13b9c | required_documents | L | - | none | - | answer name shorter than label name (boundary) |
| 136dfba9 | required_documents | M | L | none | - | 1 item not produced; 1 extra item merging 5 sentences |
| 594c3cb6 | required_documents | M | - | none | - | 1 item not produced |
| 5d75d4a6 | required_documents | M | - | none | - | 2 items not produced |
| a13baaac | required_documents | M | - | none | - | 1 item not produced |
| 563042df | required_documents | L | - | none | - | answer name shorter than label name (boundary) |
| d4000027 | required_documents | N | - | none | - | 4 answer names hold the name plus a clause; trimming needs a boundary rule |
| 28ad40ea | required_documents | M | - | none | - | 5 items not produced, and 1 item dropped for citing an id outside the window |

### Gemma 4 E4B (28 rows)

| doc | field | primary | also | rule | flips | what the row looks like |
| --- | --- | --- | --- | --- | --- | --- |
| 58f13b9c | eligibility | L | - | P | P | proviso label text |
| a81e99fe | eligibility | R | - | RT | - | label sentence never sent (1 item) |
| 136dfba9 | eligibility | V | L | NV | - | 3 items dropped because their text starts in the sentence before the one cited; one of them also needs kind other |
| d230e51e | eligibility | L | - | P | P | proviso label text |
| 6b7142ab | eligibility | L | - | P | - | proviso label text; plus 1 extra item, so P alone does not flip it |
| 594c3cb6 | eligibility | L | - | P | P | proviso label text |
| a13baaac | eligibility | V | M,L | NV | - | 1 item dropped (text in 2 sentences), 1 not produced, 1 extra |
| d4000027 | eligibility | R | L | RT | - | 6 label items never sent, 7 sub-items outside the window; 1 kind item and 2 extra |
| 28ad40ea | eligibility | R | L,M | RT | - | 2 label items never sent (tie with 2 kind items, earlier stage wins) |
| 58f13b9c | deadlines | V | N | NV | - | 必着 after the date span (1 item), time in next sentence (1 item), 1 item dropped as duplicate by a key that ignores citations |
| a81e99fe | deadlines | N | - | none | - | date range dropped (no single date), 2 items with the wrong kind |
| 136dfba9 | deadlines | V | N | NV | - | time sits in the next sentence (2 items); 1 also needs kind electronic |
| 6b7142ab | deadlines | N | - | K2 | K2 | kind other vs electronic; needs the f19cddbd label fix as well |
| 84e9d0c8 | deadlines | N | - | none | - | date range dropped (no single date); 1 kind and citation difference |
| 594c3cb6 | deadlines | N | - | K1 | K1 | kind other where the sentence has the bid-opening cue |
| a13baaac | deadlines | R | V,N | RT | - | 1 label sentence never sent; the other item needs the 必着 sentence and kind mail_arrival |
| 563042df | deadlines | L | - | none | - | label says other, answer electronic (label older than the electronic rule) |
| 4b0b9d82 | deadlines | N | L | none | - | 3 items: answer kind mail_arrival, label question or other set by the heading sentence just before; plus 1 extra item |
| d4000027 | deadlines | L | - | none | - | 3 extra items (2 are planned dates), all 3 label items paired; whether the label misses them needs a native reader |
| 28ad40ea | deadlines | V | L | NV | - | 必着 in the next sentence (3 items); 3 extra items |
| f19cddbd | required_documents | L | - | none | - | answer name shorter than label name (boundary) |
| 58f13b9c | required_documents | L | - | none | - | answer name shorter than label name (boundary) |
| 6b7142ab | required_documents | L | - | none | - | 1 extra item |
| 5d75d4a6 | required_documents | M | L | none | - | 1 item not produced; 1 extra item |
| a13baaac | required_documents | N | - | none | - | answer name longer than label name (name plus a clause) |
| 563042df | required_documents | M | L | none | - | 1 item not produced (cited a different sentence); 1 extra |
| d4000027 | required_documents | L | N,L | none | - | 3 answer names shorter than label (boundary), 1 longer, 1 extra |
| 28ad40ea | required_documents | L | - | none | - | 1 extra item |

## 5. What stays after the three rules

- Qwen3.5-9B: 22 of 27 wrong rows have no flipping rule: R 4, V 4, N 3, M 6, L 5.
- Gemma 4 E4B: 23 of 28 wrong rows have no flipping rule: R 4, V 5, N 4, M 2, L 8.

The biggest block that no rule touches is label or convention and model (required_documents names, extra items, items not produced), then retrieval, which only a model run can measure.

## 6. What I did not do, and the time cost

- No model run. A retrieval or window change (group RT, 4 Qwen / 4 Gemma touch it) needs a new prompt per document, so it needs a run. The only timing in the repo is the fix 2 rerun of required_documents for Qwen, 862 s wall for 14 documents (`phase5_rescore_after_label_fix.md`); a three-field run of both models on 14 documents is longer than that, and I did not measure it.
- The measured flips are on saved answers (temperature 0, one run each). A new run can give different answers.
- Extra items: whether the label misses them or the model over-produced them needs a Japanese reader. They are counted under label or convention, as in the design review.

## 7. What I actually saw

- Replay of both models over 14 documents through current `llm.py` gave Qwen 42 rows, 15 right, 25 wrong, 2 not found, and Gemma 42 rows, 14 right, 28 wrong, 0 not found, matching `phase5_summary_after_fix4.md`. 0 calls had a moved window.
- Per row, the label items, the answer items, the check verdicts and the cited sentences' structure (length, date spans, marker positions) were printed to the terminal and read; the sentence text of the cited sentences was not copied into this file.
- Proviso census over the 14 label files: 9 label items cite a なお or ただし sentence and include it in text_ja (7 documents), 5 cite it and do not (5 documents).
- In-memory rescoring runs (42 rows each): P with and without the copy drop; K1, K2, K2 with the f19cddbd label change, and REL; the neighbour validator on eligibility; the wider cue-override version. Results as in section 3: the wider override lost 594c3cb6 deadlines (Qwen), K2 without the label change lost f19cddbd deadlines (both models).
- Files read: `phase5_design_review.md`, `phase5_summary_after_fix4.md`, `phase5_fix4_deadline_dupes.md`, the first 60 lines of `phase5_fix3_eligibility_proviso.md`, decisions D-71 and D-72, `llm.py` (checks, merge, cues, retrieve), `eval/hybrid.py` (`classify`, `subcause`), `eval/phase5_fix1_replay.py`, `eval/phase5_fix3_replay.py`. Scratch scripts were in the session scratchpad, outside the repo; nothing but this file was written into it.

Could not explain:
- Why the label text for 5 documents stops before the proviso it cites while 7 other documents include it. I read it as a label inconsistency, not a model error.
- Why Qwen wrote 2024 for dates the sentence gives as 2022 in 58f13b9c (a Reiwa-year conversion slip is my guess, not checked).
- Whether the extra items (all rows marked L with extras) are missing from the labels.
