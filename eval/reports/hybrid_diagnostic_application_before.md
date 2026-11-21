# Hybrid extractor: why label items were missed (application_before)

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

Measurement only: no prompt, retrieval window or check was changed for this table. One row per label item of the three list fields on the scored dev documents. Item ids are `<doc id prefix>/<field>#<n>`, n counting the label file's items from 1; only sentence ids are shown, no document text.

Order of the tests: a kept answer item that pairs with the label item (hit); else a dropped one that would have paired (c); else an answer item citing a shared sentence that does not pair (d); else a if none of the label item's sentences was sent, b if one was.

| field | label items | hit | a: not in window | b: not produced | c: dropped by a check | d: wrong value or kind | answer items with no label item |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eligibility | 84 | 61 | 9 | 1 | 1 | 12 | 8 |
| deadlines | 45 | 28 | 1 | 3 | 1 | 12 | 10 |
| required_documents | 69 | 58 | 0 | 4 | 0 | 7 | 9 |
| all | 198 | 147 | 10 | 8 | 2 | 31 | 27 |

## Category c by check

- eligibility: value_not_in_citation 1
- deadlines: date_or_time_not_in_citation 1
- required_documents: none

## Category d by sub-cause

Read side by side: the label item and the answer items that share a cited sentence with it. Cells: count (convention / real).

| sub-cause | eligibility | deadlines | required_documents | all |
| --- | --- | --- | --- | --- |
| d1 same sentence, different kind | 2 (2 / 0) | 7 (1 / 6) | 0 (0 / 0) | 9 (3 / 6) |
| d2 same sentence, different polarity | 2 (0 / 2) | 0 (0 / 0) | 0 (0 / 0) | 2 (0 / 2) |
| d3 different split of the same text | 1 (0 / 1) | 0 (0 / 0) | 7 (0 / 7) | 8 (0 / 8) |
| d4 wrong sentence (the answer item is built on another sentence) | 7 (0 / 7) | 0 (0 / 0) | 0 (0 / 0) | 7 (0 / 7) |
| d5 wrong value (datetime, flags or name) | 0 (0 / 0) | 5 (0 / 5) | 0 (0 / 0) | 5 (0 / 5) |
- d1 eligibility: `28ad40ea4b1f/eligibility#6` sentences p1_s18 (convention); `28ad40ea4b1f/eligibility#7` sentences p1_s19 (convention)
- d1 deadlines: `a81e99fecea5/deadlines#4` sentences h_s68 (real); `a81e99fecea5/deadlines#5` sentences h_s68, h_s85 (real); `136dfba9ee59/deadlines#1` sentences h_s79, h_s80 (real)
- d2 eligibility: `d40000275df6/eligibility#11` sentences p2_s17, p2_s18 (real); `d40000275df6/eligibility#12` sentences p2_s17, p3_s1 (real)
- d3 eligibility: `a13baaac55c8/eligibility#1` sentences h_s29, h_s30, h_s31 (real)
- d3 required_documents: `f19cddbd4cba/required_documents#2` sentences h_s55 (real); `58f13b9c2e87/required_documents#3` sentences h_s53 (real); `563042df9941/required_documents#1` sentences h_s34, h_s48 (real)
- d4 eligibility: `d40000275df6/eligibility#13` sentences p2_s17, p3_s2 (real); `d40000275df6/eligibility#14` sentences p2_s17, p3_s3 (real); `d40000275df6/eligibility#15` sentences p2_s17, p3_s4 (real)
- d5 deadlines: `58f13b9c2e87/deadlines#1` sentences h_s49 (real); `58f13b9c2e87/deadlines#3` sentences h_s51, h_s52 (real); `a81e99fecea5/deadlines#1` sentences h_s61 (real)

Convention or real error, with the reasoning:
- d1 kind, eligibility: convention. Whether a rule about a stated officer qualification (予算決算及び会計令第73条) or a tax arrears rule is `legal` or `other` is not settled by the field table, and the labels disagree with each other. d1 kind, deadlines: convention only when the label says `other` (those labels predate the rule that a bid receipt on an electronic notice is `electronic`); otherwise real, because the answer cited one sentence and missed the one with 到着 or 質問.
- d2 polarity: convention when the answer text keeps its negation (...ないこと): the guide says that is a requirement, and the older labels say disqualification. Real when the text names the bad state (暴力団... 者) under a header that says none of them may apply: the guide says disqualification.
- d3 split: real against the written rule (the なお or ただし sentence stays inside the 第70条 item with both ids), although the reader loses little. The label side is consistent with the guide.
- d4 wrong sentence: real. The label lists each item of an ア to ケ list with the header sentence and its own sentence; the answer made one item from the header only and none from the list items, so those label items are misses that share only the header sentence.
- d5 wrong value: real. The label's 必着 comes from a second sentence the answer did not cite; flags are read from the cited sentences only.
These readings are mine, not a native speaker's. The calls that need a Japanese reader are the legal-or-other split in d1 and the sentences behind d4.


## Examples (first three per field and category, spread over documents)

- eligibility, a (its sentence was not in the retrieved window): `a81e99fecea5/eligibility#8` sentences h_s82; `d40000275df6/eligibility#1` sentences p2_s4, p2_s5; `28ad40ea4b1f/eligibility#8` sentences p1_s20
- eligibility, b (in the window, but the model did not produce it): `28ad40ea4b1f/eligibility#1` sentences p1_s13
- eligibility, c (produced, then dropped by a verification check): `136dfba9ee59/eligibility#5` sentences h_s56, h_s57 (value_not_in_citation)
- eligibility, d (produced (kept or dropped) but the value or kind is wrong): `a13baaac55c8/eligibility#1` sentences h_s29, h_s30, h_s31 (d3 real); `d40000275df6/eligibility#11` sentences p2_s17, p2_s18 (d2 real); `28ad40ea4b1f/eligibility#6` sentences p1_s18 (d1 convention)
- deadlines, a (its sentence was not in the retrieved window): `a13baaac55c8/deadlines#2` sentences h_s106
- deadlines, b (in the window, but the model did not produce it): `58f13b9c2e87/deadlines#2` sentences h_s53; `84e9d0c8325c/deadlines#1` sentences h_s61, h_s62; `84e9d0c8325c/deadlines#2` sentences h_s64
- deadlines, c (produced, then dropped by a verification check): `136dfba9ee59/deadlines#2` sentences h_s81, h_s82 (date_or_time_not_in_citation)
- deadlines, d (produced (kept or dropped) but the value or kind is wrong): `58f13b9c2e87/deadlines#1` sentences h_s49 (d5 real); `a81e99fecea5/deadlines#1` sentences h_s61 (d5 real); `136dfba9ee59/deadlines#1` sentences h_s79, h_s80 (d1 real)
- required_documents, a (its sentence was not in the retrieved window): none
- required_documents, b (in the window, but the model did not produce it): `594c3cb69c53/required_documents#1` sentences h_s34; `5d75d4a67c71/required_documents#2` sentences h_s45; `a13baaac55c8/required_documents#7` sentences h_s63
- required_documents, c (produced, then dropped by a verification check): none
- required_documents, d (produced (kept or dropped) but the value or kind is wrong): `f19cddbd4cba/required_documents#2` sentences h_s55 (d3 real); `58f13b9c2e87/required_documents#3` sentences h_s53 (d3 real); `563042df9941/required_documents#1` sentences h_s34, h_s48 (d3 real)
