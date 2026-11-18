# Phase 5 fix 1: why 21 Gemma 4 E4B deadline answers do not pair

Saved trace `data/cache/hybrid/trace_cmp_gemma4_e4b.json` replayed through the current `llm.py` (no model, no network, nothing changed), paired with the dev labels exactly as `eval.silver.compare.item_pairs` does (greedy, `agree.item_same`: kind, datetime, relative_text, flags and a shared cited sentence all equal). Dev only, 14 documents, model-reviewed silver labels (D-41), so "the label looks wrong" is only what code can see, not a Japanese reading. Item ids are `doc8:cited sentence ids:kind`; no document text.

Answer items 42, paired 21, unpaired 21.

## Counts per cause (first match in this order)

| cause | meaning | items |
| --- | --- | --- |
| duplicate | same item as an answer item that already paired (the label item is used up) | 0 |
| kind | only the kind differs from a label item on a shared sentence | 6 |
| flags | only the flags differ | 3 |
| date | only the datetime differs | 2 |
| several | two or more of kind, datetime, flags differ | 3 |
| no_label_on_sentence | no label item cites any sentence this answer cites | 7 |

## Items

### kind (6)

- `6b7142ab:h_s49:other` kind; answer other / label electronic; wording markers in the cited sentence [], in the next sentence ['開札']; labels with the same date (cited ids:kind) ['h_s49:electronic']; markers inside the answer's own date span [], 必着/消印 after the last date span []; markers in the label's cited sentences [], sentences only the label cites []; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags [], label flags []
- `594c3cb6:h_s49:other` kind; answer other / label bid_opening; wording markers in the cited sentence ['必着', '郵送', '開札'], in the next sentence []; labels with the same date (cited ids:kind) ['h_s49:bid_opening', 'h_s49:mail_arrival']; markers inside the answer's own date span [], 必着/消印 after the last date span []; markers in the label's cited sentences ['必着', '郵送', '開札'], sentences only the label cites []; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags [], label flags []
- `563042df:h_s49:electronic` kind; answer electronic / label other; wording markers in the cited sentence [], in the next sentence []; labels with the same date (cited ids:kind) ['h_s48+h_s49:other']; markers inside the answer's own date span [], 必着/消印 after the last date span []; markers in the label's cited sentences [], sentences only the label cites ['h_s48']; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags [], label flags []
- `4b0b9d82:h_s33:mail_arrival` kind; answer mail_arrival / label question; wording markers in the cited sentence ['必着'], in the next sentence ['質問']; labels with the same date (cited ids:kind) ['h_s32+h_s33:question']; markers inside the answer's own date span ['必着'], 必着/消印 after the last date span []; markers in the label's cited sentences ['必着', '質問'], sentences only the label cites ['h_s32']; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags ['arrival_required'], label flags ['arrival_required']
- `4b0b9d82:h_s37:mail_arrival` kind; answer mail_arrival / label other; wording markers in the cited sentence ['必着'], in the next sentence []; labels with the same date (cited ids:kind) ['h_s36+h_s37:other']; markers inside the answer's own date span ['必着'], 必着/消印 after the last date span []; markers in the label's cited sentences ['必着'], sentences only the label cites ['h_s36']; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags ['arrival_required'], label flags ['arrival_required']
- `4b0b9d82:h_s39:mail_arrival` kind; answer mail_arrival / label other; wording markers in the cited sentence ['必着'], in the next sentence []; labels with the same date (cited ids:kind) ['h_s38+h_s39:other']; markers inside the answer's own date span ['必着'], 必着/消印 after the last date span []; markers in the label's cited sentences ['必着'], sentences only the label cites ['h_s38']; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags ['arrival_required'], label flags ['arrival_required']

### flags (3)

- `58f13b9c:h_s49:mail_arrival` flags; answer mail_arrival / label mail_arrival; wording markers in the cited sentence ['必着', '郵送'], in the next sentence []; labels with the same date (cited ids:kind) ['h_s49:mail_arrival', 'h_s53:other']; markers inside the answer's own date span [], 必着/消印 after the last date span ['必着']; markers in the label's cited sentences ['必着', '郵送'], sentences only the label cites []; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags [], label flags ['arrival_required']
- `28ad40ea:p2_s24:other` flags; answer other / label other; wording markers in the cited sentence [], in the next sentence []; labels with the same date (cited ids:kind) ['p2_s24+p2_s26:other']; markers inside the answer's own date span [], 必着/消印 after the last date span []; markers in the label's cited sentences ['必着'], sentences only the label cites ['p2_s26']; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags [], label flags ['arrival_required']
- `28ad40ea:p3_s20:other` flags; answer other / label other; wording markers in the cited sentence [], in the next sentence []; labels with the same date (cited ids:kind) ['p3_s20+p3_s28:other']; markers inside the answer's own date span [], 必着/消印 after the last date span []; markers in the label's cited sentences ['必着', '郵送'], sentences only the label cites ['p3_s28']; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags [], label flags ['arrival_required']

### date (2)

- `58f13b9c:h_s51:bid_opening` datetime; answer bid_opening / label bid_opening; time only; wording markers in the cited sentence ['開札'], in the next sentence []; labels with the same date (cited ids:kind) ['h_s51+h_s52:bid_opening']; markers inside the answer's own date span [], 必着/消印 after the last date span []; label already paired by another answer: no; label datetime found in its own cited sentence: False; answer flags [], label flags []
- `136dfba9:h_s81:bid_opening` datetime; answer bid_opening / label bid_opening; time only; wording markers in the cited sentence ['開札'], in the next sentence []; labels with the same date (cited ids:kind) ['h_s81+h_s82:bid_opening']; markers inside the answer's own date span [], 必着/消印 after the last date span []; label already paired by another answer: no; label datetime found in its own cited sentence: False; answer flags [], label flags []

### several (3)

- `58f13b9c:h_s49:other` kind+flags; answer other / label mail_arrival; wording markers in the cited sentence ['必着', '郵送'], in the next sentence []; labels with the same date (cited ids:kind) ['h_s49:mail_arrival', 'h_s53:other']; markers inside the answer's own date span [], 必着/消印 after the last date span ['必着']; markers in the label's cited sentences ['必着', '郵送'], sentences only the label cites []; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags [], label flags ['arrival_required']
- `136dfba9:h_s79:other` kind+datetime; answer other / label electronic; time only; wording markers in the cited sentence [], in the next sentence []; labels with the same date (cited ids:kind) ['h_s79+h_s80:electronic']; markers inside the answer's own date span [], 必着/消印 after the last date span []; markers in the label's cited sentences [], sentences only the label cites ['h_s80']; label already paired by another answer: no; label datetime found in its own cited sentence: False; answer flags [], label flags []
- `a13baaac:h_s94:other` kind+flags; answer other / label mail_arrival; wording markers in the cited sentence [], in the next sentence ['必着']; labels with the same date (cited ids:kind) ['h_s94+h_s95:mail_arrival']; markers inside the answer's own date span [], 必着/消印 after the last date span []; markers in the label's cited sentences ['必着'], sentences only the label cites ['h_s95']; label already paired by another answer: no; label datetime found in its own cited sentence: True; answer flags [], label flags ['arrival_required']

### no_label_on_sentence (7)

- `4b0b9d82:h_s31:other` ; wording markers in the cited sentence [], in the next sentence ['質問']; labels with the same date (cited ids:kind) []; markers inside the answer's own date span [], 必着/消印 after the last date span []
- `d4000027:p3_s10:other` ; wording markers in the cited sentence [], in the next sentence ['質問']; labels with the same date (cited ids:kind) []; markers inside the answer's own date span [], 必着/消印 after the last date span []
- `d4000027:p3_s17:other` ; wording markers in the cited sentence [], in the next sentence []; labels with the same date (cited ids:kind) []; markers inside the answer's own date span [], 必着/消印 after the last date span []
- `d4000027:p3_s18:other` ; wording markers in the cited sentence [], in the next sentence []; labels with the same date (cited ids:kind) []; markers inside the answer's own date span [], 必着/消印 after the last date span []
- `28ad40ea:p1_s25:question` ; wording markers in the cited sentence ['質問'], in the next sentence ['質問']; labels with the same date (cited ids:kind) ['p2_s11+p2_s13:question']; markers inside the answer's own date span [], 必着/消印 after the last date span []
- `28ad40ea:p2_s18:bid_opening` ; wording markers in the cited sentence ['質問'], in the next sentence []; labels with the same date (cited ids:kind) []; markers inside the answer's own date span [], 必着/消印 after the last date span []
- `28ad40ea:p2_s18:other` ; wording markers in the cited sentence ['質問'], in the next sentence []; labels with the same date (cited ids:kind) []; markers inside the answer's own date span [], 必着/消印 after the last date span []
