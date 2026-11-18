# Hybrid extractor: why label items were missed (cmp5d_gemma4_e4b)

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

Measurement only: no prompt, retrieval window or check was changed for this table. One row per label item of the three list fields on the scored dev documents. Item ids are `<doc id prefix>/<field>#<n>`, n counting the label file's items from 1; only sentence ids are shown, no document text.

Order of the tests: a kept answer item that pairs with the label item (hit); else a dropped one that would have paired (c); else an answer item citing a shared sentence that does not pair (d); else a if none of the label item's sentences was sent, b if one was.

| field | label items | hit | a: not in window | b: not produced | c: dropped by a check | d: wrong value or kind | answer items with no label item |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eligibility | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| deadlines | 3 | 3 | 0 | 0 | 0 | 0 | 3 |
| required_documents | 4 | 3 | 0 | 1 | 0 | 0 | 1 |
| all | 11 | 10 | 0 | 1 | 0 | 0 | 4 |

## Category c by check

- eligibility: none
- deadlines: none
- required_documents: none

## Category d by sub-cause

Read side by side: the label item and the answer items that share a cited sentence with it. Cells: count (convention / real).

| sub-cause | eligibility | deadlines | required_documents | all |
| --- | --- | --- | --- | --- |
| d1 same sentence, different kind | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) |
| d2 same sentence, different polarity | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) |
| d3 different split of the same text | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) |
| d4 wrong sentence (the answer item is built on another sentence) | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) |
| d5 wrong value (datetime, flags or name) | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) | 0 (0 / 0) |

Convention or real error, with the reasoning:
- d1 kind, eligibility: convention. Whether a rule about a stated officer qualification (予算決算及び会計令第73条) or a tax arrears rule is `legal` or `other` is not settled by the field table, and the labels disagree with each other. d1 kind, deadlines: convention only when the label says `other` (those labels predate the rule that a bid receipt on an electronic notice is `electronic`); otherwise real, because the answer cited one sentence and missed the one with 到着 or 質問.
- d2 polarity: convention when the answer text keeps its negation (...ないこと): the guide says that is a requirement, and the older labels say disqualification. Real when the text names the bad state (暴力団... 者) under a header that says none of them may apply: the guide says disqualification.
- d3 split: real against the written rule (the なお or ただし sentence stays inside the 第70条 item with both ids), although the reader loses little. The label side is consistent with the guide.
- d4 wrong sentence: real. The label lists each item of an ア to ケ list with the header sentence and its own sentence; the answer made one item from the header only and none from the list items, so those label items are misses that share only the header sentence.
- d5 wrong value: real. The label's 必着 comes from a second sentence the answer did not cite; flags are read from the cited sentences only.
These readings are mine, not a native speaker's. The calls that need a Japanese reader are the legal-or-other split in d1 and the sentences behind d4.


## Examples (first three per field and category, spread over documents)

- eligibility, a (its sentence was not in the retrieved window): none
- eligibility, b (in the window, but the model did not produce it): none
- eligibility, c (produced, then dropped by a verification check): none
- eligibility, d (produced (kept or dropped) but the value or kind is wrong): none
- deadlines, a (its sentence was not in the retrieved window): none
- deadlines, b (in the window, but the model did not produce it): none
- deadlines, c (produced, then dropped by a verification check): none
- deadlines, d (produced (kept or dropped) but the value or kind is wrong): none
- required_documents, a (its sentence was not in the retrieved window): none
- required_documents, b (in the window, but the model did not produce it): `5d75d4a67c71/required_documents#4` sentences h_s54
- required_documents, c (produced, then dropped by a verification check): none
- required_documents, d (produced (kept or dropped) but the value or kind is wrong): none
