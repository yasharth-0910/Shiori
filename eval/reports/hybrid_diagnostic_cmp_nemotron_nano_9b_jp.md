# Hybrid extractor: why label items were missed (cmp_nemotron_nano_9b_jp)

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

Measurement only: no prompt, retrieval window or check was changed for this table. One row per label item of the three list fields on the scored dev documents. Item ids are `<doc id prefix>/<field>#<n>`, n counting the label file's items from 1; only sentence ids are shown, no document text.

Order of the tests: a kept answer item that pairs with the label item (hit); else a dropped one that would have paired (c); else an answer item citing a shared sentence that does not pair (d); else a if none of the label item's sentences was sent, b if one was.

| field | label items | hit | a: not in window | b: not produced | c: dropped by a check | d: wrong value or kind | answer items with no label item |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eligibility | 80 | 24 | 9 | 26 | 2 | 19 | 21 |
| deadlines | 42 | 3 | 1 | 10 | 1 | 27 | 5 |
| required_documents | 65 | 35 | 0 | 18 | 0 | 12 | 14 |
| all | 187 | 62 | 10 | 54 | 3 | 58 | 40 |

## Category c by check

- eligibility: value_not_in_citation 2
- deadlines: date_or_time_not_in_citation 1
- required_documents: none

## Category d by sub-cause

Read side by side: the label item and the answer items that share a cited sentence with it. Cells: count (convention / real).

| sub-cause | eligibility | deadlines | required_documents | all |
| --- | --- | --- | --- | --- |
| d1 same sentence, different kind | 5 (5 / 0) | 1 (0 / 1) | 0 (0 / 0) | 6 (5 / 1) |
| d2 same sentence, different polarity | 1 (1 / 0) | 0 (0 / 0) | 0 (0 / 0) | 1 (1 / 0) |
| d3 different split of the same text | 6 (0 / 6) | 0 (0 / 0) | 5 (0 / 5) | 11 (0 / 11) |
| d4 wrong sentence (the answer item is built on another sentence) | 7 (0 / 7) | 0 (0 / 0) | 7 (0 / 7) | 14 (0 / 14) |
| d5 wrong value (datetime, flags or name) | 0 (0 / 0) | 26 (0 / 26) | 0 (0 / 0) | 26 (0 / 26) |
- d1 eligibility: `f19cddbd4cba/eligibility#2` sentences h_s40 (convention); `d230e51e2805/eligibility#4` sentences h_s44 (convention); `6b7142ab74f4/eligibility#1` sentences h_s38, h_s39 (convention)
- d1 deadlines: `28ad40ea4b1f/deadlines#1` sentences p2_s11, p2_s13 (real)
- d2 eligibility: `563042df9941/eligibility#4` sentences h_s44 (convention)
- d3 eligibility: `f19cddbd4cba/eligibility#1` sentences h_s38, h_s39 (real); `d230e51e2805/eligibility#5` sentences h_s45 (real); `a13baaac55c8/eligibility#1` sentences h_s29, h_s30, h_s31 (real)
- d3 required_documents: `58f13b9c2e87/required_documents#3` sentences h_s53 (real); `563042df9941/required_documents#1` sentences h_s34, h_s48 (real); `d40000275df6/required_documents#11` sentences p6_s1 (real)
- d4 eligibility: `58f13b9c2e87/eligibility#2` sentences h_s42 (real); `84e9d0c8325c/eligibility#2` sentences h_s44 (real); `84e9d0c8325c/eligibility#3` sentences h_s45 (real)
- d4 required_documents: `d40000275df6/required_documents#5` sentences p5_s18 (real); `d40000275df6/required_documents#6` sentences p5_s19 (real); `d40000275df6/required_documents#7` sentences p5_s20 (real)
- d5 deadlines: `f19cddbd4cba/deadlines#1` sentences h_s49 (real); `f19cddbd4cba/deadlines#2` sentences h_s50 (real); `a81e99fecea5/deadlines#1` sentences h_s61 (real)

Convention or real error, with the reasoning:
- d1 kind, eligibility: convention. Whether a rule about a stated officer qualification (予算決算及び会計令第73条) or a tax arrears rule is `legal` or `other` is not settled by the field table, and the labels disagree with each other. d1 kind, deadlines: convention only when the label says `other` (those labels predate the rule that a bid receipt on an electronic notice is `electronic`); otherwise real, because the answer cited one sentence and missed the one with 到着 or 質問.
- d2 polarity: convention when the answer text keeps its negation (...ないこと): the guide says that is a requirement, and the older labels say disqualification. Real when the text names the bad state (暴力団... 者) under a header that says none of them may apply: the guide says disqualification.
- d3 split: real against the written rule (the なお or ただし sentence stays inside the 第70条 item with both ids), although the reader loses little. The label side is consistent with the guide.
- d4 wrong sentence: real. The label lists each item of an ア to ケ list with the header sentence and its own sentence; the answer made one item from the header only and none from the list items, so those label items are misses that share only the header sentence.
- d5 wrong value: real. The label's 必着 comes from a second sentence the answer did not cite; flags are read from the cited sentences only.
These readings are mine, not a native speaker's. The calls that need a Japanese reader are the legal-or-other split in d1 and the sentences behind d4.


## Examples (first three per field and category, spread over documents)

- eligibility, a (its sentence was not in the retrieved window): `a81e99fecea5/eligibility#8` sentences h_s82; `d40000275df6/eligibility#1` sentences p2_s4, p2_s5; `28ad40ea4b1f/eligibility#8` sentences p1_s20
- eligibility, b (in the window, but the model did not produce it): `f19cddbd4cba/eligibility#4` sentences h_s43; `58f13b9c2e87/eligibility#3` sentences h_s43; `136dfba9ee59/eligibility#1` sentences h_s46, h_s47, h_s48, h_s49, h_s50
- eligibility, c (produced, then dropped by a verification check): `a13baaac55c8/eligibility#3` sentences h_s33, h_s34 (value_not_in_citation); `a13baaac55c8/eligibility#4` sentences h_s35, h_s36 (value_not_in_citation)
- eligibility, d (produced (kept or dropped) but the value or kind is wrong): `f19cddbd4cba/eligibility#1` sentences h_s38, h_s39 (d3 real); `58f13b9c2e87/eligibility#2` sentences h_s42 (d4 real); `d230e51e2805/eligibility#4` sentences h_s44 (d1 convention)
- deadlines, a (its sentence was not in the retrieved window): `a13baaac55c8/deadlines#2` sentences h_s106
- deadlines, b (in the window, but the model did not produce it): `58f13b9c2e87/deadlines#1` sentences h_s49; `d230e51e2805/deadlines#2` sentences h_s58; `594c3cb69c53/deadlines#1` sentences h_s48
- deadlines, c (produced, then dropped by a verification check): `58f13b9c2e87/deadlines#3` sentences h_s51, h_s52 (date_or_time_not_in_citation)
- deadlines, d (produced (kept or dropped) but the value or kind is wrong): `f19cddbd4cba/deadlines#1` sentences h_s49 (d5 real); `a81e99fecea5/deadlines#1` sentences h_s61 (d5 real); `136dfba9ee59/deadlines#1` sentences h_s79, h_s80 (d5 real)
- required_documents, a (its sentence was not in the retrieved window): none
- required_documents, b (in the window, but the model did not produce it): `f19cddbd4cba/required_documents#2` sentences h_s55; `a81e99fecea5/required_documents#1` sentences h_s39; `6b7142ab74f4/required_documents#2` sentences h_s54
- required_documents, c (produced, then dropped by a verification check): none
- required_documents, d (produced (kept or dropped) but the value or kind is wrong): `58f13b9c2e87/required_documents#3` sentences h_s53 (d3 real); `563042df9941/required_documents#1` sentences h_s34, h_s48 (d3 real); `d40000275df6/required_documents#5` sentences p5_s18 (d4 real)
