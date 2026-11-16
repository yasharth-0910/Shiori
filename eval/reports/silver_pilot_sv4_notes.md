## Day-1 gate, 2026-10-04: failed on the 90% bar; passed in substance (Yasharth, 2026-10-11, D-58)

The 5 pilot documents under sv4 in comparison mode (no label written). Local half 04:41 to 06:00 UTC; Gemini half from 07:01 UTC, after Gemini's quota day turned over at Pacific midnight (D-57: the first try at 04:41 UTC hit the daily cap of the Pacific day 2026-10-03).

| criterion | result | verdict |
| --- | --- | --- |
| Gemini sv4 matches at least 90% of labeled fields | 85 of 96 (89%); on the model-reviewed fields only 45 of 55 (82%). On the 4 documents also scored under sv3: 79 of 90 (sv3: 80 of 90) | **fail** |
| no new kind of schema, JSON or parse failure | Gemini: 0 shape problems, 0 repairs, 0 parse errors (8 HTTP 503 in 13 requests). Qwen: only "present with normalized empty" (seen in sv3), on 2 documents, all fixed by the repair; no truncation, no failed part | pass |
| Qwen sv4 no worse than sv3 on list fields | 1 of 12 under both; list items paired with a label item 22 of 48 (sv3: 13) | pass |

Gemini's 11 misses, by cause:
- **Old misses the sv4 rules did not fix (4):** 28ad40ea4b1f award_method absent (label best_value, F-0046) and spec_access absent (label see_other_document 別紙「仕様書」, F-0044), although both rules are now in the prompt; spec_access of f19cddbd4cba and 563042df9941 answered public (the field already called ambiguous in sv1).
- **Eligibility polarity (2):** 563042df9941 and 28ad40ea4b1f: Gemini marks the legal items `requirement` where the labels say `disqualification`. The sv4 rule lets polarity follow text_ja (negation kept: requirement; negation stripped: disqualification), so both forms can be right for the same fact, but agreement compares polarity exactly. Part of these misses may be the rule, not Gemini.
- **Near misses (3):** f19cddbd4cba eligibility (one item cites h_s38 where the label cites h_s38 and h_s39), f19cddbd4cba and 563042df9941 required_documents (a name without 「この公告に示した」; 提案書 split out as its own item).
- **Different citation (1):** 563042df9941 title: same text, cited at h_s26 in the body, the label cites h_s9 (portal metadata line). The sv4 title rule points to the 件名 line.
- **Different kind (1):** 563042df9941 deadlines: the 2026-09-09 12:00 item is `electronic` in sv4, `other` in the label.

Fixed by sv4 compared with sv3 (Gemini): f19cddbd4cba submission_modes, 563042df9941 scope_summary (F-0057 rule), 4b0b9d8229c7 deadlines. Gemini-vs-Qwen flags after repair: 27 of 96 fields (28%; sv3: 30 of 90, 33%).

### Decision of 2026-10-11 (D-58)

Yasharth judged the gate passed in substance and started the dev run: on the 4 documents also scored under sv3 Gemini matches 79 of 90 (sv3 80 of 90), no new failure kind appeared, Qwen's paired list items rose from 13 to 22 of 48, and Gemini-vs-Qwen disagreement fell from 33% to 28%. The 90% bar had no evidence behind it, and Gemini's misses become review items settled against the guide. PROMPT_VERSION sv4 is frozen until dev and test are labeled.

Recomputed with the new agreement rule `eligibility_negation` (a requirement whose text keeps the negation equals a disqualification without it): unchanged, Gemini 85 of 96, 79 of 90 on the shared documents, 45 of 55 on reviewed fields. 563042df9941's label pairs disqualification with the negation kept, which the rule leaves alone; on 28ad40ea4b1f polarity now matches but three items differ in kind and p1_s13 is missing. Replay of the rule on all 56 reviewed items: settles none, accepts none wrongly.
