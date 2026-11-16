# Hybrid extractor: why label items were missed (dev_hybrid_v2)

**Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

Measurement only: no prompt, retrieval window or check was changed for this table. One row per label item of the three list fields on the scored dev documents. Item ids are `<doc id prefix>/<field>#<n>`, n counting the label file's items from 1; only sentence ids are shown, no document text.

Order of the tests: a kept answer item that pairs with the label item (hit); else a dropped one that would have paired (c); else an answer item citing a shared sentence that does not pair (d); else a if none of the label item's sentences was sent, b if one was.

| field | label items | hit | a: not in window | b: not produced | c: dropped by a check | d: produced, value or kind wrong | answer items with no label item |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eligibility | 53 | 24 | 8 | 1 | 1 | 19 | 16 |
| deadlines | 23 | 12 | 1 | 2 | 1 | 7 | 6 |
| required_documents | 51 | 18 | 32 | 0 | 0 | 1 | 3 |
| all | 127 | 54 | 41 | 3 | 2 | 27 | 25 |

## Category c by check

- eligibility: value_not_in_citation 1
- deadlines: date_or_time_not_in_citation 1
- required_documents: none

## Examples (first three per field and category, spread over documents)

- eligibility, a (its sentence was not in the retrieved window): `d40000275df6/eligibility#1` sentences p2_s4, p2_s5; `28ad40ea4b1f/eligibility#8` sentences p1_s20; `d40000275df6/eligibility#2` sentences p2_s6
- eligibility, b (in the window, but the model did not produce it): `28ad40ea4b1f/eligibility#1` sentences p1_s13
- eligibility, c (produced, then dropped by a verification check): `136dfba9ee59/eligibility#5` sentences h_s56, h_s57 (value_not_in_citation)
- eligibility, d (produced (kept or dropped) but the value or kind is wrong): `f19cddbd4cba/eligibility#1` sentences h_s38, h_s39 (differs in polarity, text_ja); `136dfba9ee59/eligibility#4` sentences h_s54, h_s55 (differs in kind); `a13baaac55c8/eligibility#1` sentences h_s29, h_s30, h_s31 (differs in kind, text_ja)
- deadlines, a (its sentence was not in the retrieved window): `a13baaac55c8/deadlines#2` sentences h_s106
- deadlines, b (in the window, but the model did not produce it): `84e9d0c8325c/deadlines#1` sentences h_s61, h_s62; `84e9d0c8325c/deadlines#2` sentences h_s64
- deadlines, c (produced, then dropped by a verification check): `136dfba9ee59/deadlines#2` sentences h_s81, h_s82 (date_or_time_not_in_citation)
- deadlines, d (produced (kept or dropped) but the value or kind is wrong): `136dfba9ee59/deadlines#1` sentences h_s79, h_s80 (differs in kind (answer was date_or_time_not_in_citation)); `84e9d0c8325c/deadlines#4` sentences h_s68, h_s85 (differs in kind); `a13baaac55c8/deadlines#1` sentences h_s94, h_s95 (differs in kind, flags)
- required_documents, a (its sentence was not in the retrieved window): `f19cddbd4cba/required_documents#2` sentences h_s55; `136dfba9ee59/required_documents#1` sentences h_s87; `84e9d0c8325c/required_documents#1` sentences h_s39
- required_documents, b (in the window, but the model did not produce it): none
- required_documents, c (produced, then dropped by a verification check): none
- required_documents, d (produced (kept or dropped) but the value or kind is wrong): `84e9d0c8325c/required_documents#3` sentences h_s65, h_s81 (differs in name_ja)
