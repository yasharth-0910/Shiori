# Silver pilot, prompt sv4

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

## Reviewed documents: each labeler against the existing labels

Comparison mode: these documents already had labels, so nothing was written for them. The labels are sv1 consensus lines plus the reviewer's answers (`claude_chat`, a model in chat, not human-verified). **They came from Gemini and Groq plus that review, which slightly favors Gemini** (and Groq's sv1 row), and the documents were used to write the labeling guide, so every number here is optimistic. The local model's answers are shown as first sent (after repair: the last section). Match = the consensus agreement rule (status, enums and dates exact; text fuzzy with overlapping citations; the active relaxations): the answer would have been accepted beside the label. Mismatches name the review item id when the label came from the review, `consensus` when it was an sv1 consensus line.

| labeler | list | structured | text | all fields |
| --- | --- | --- | --- | --- |
| gemini | 6 of 12 | 60 of 64 | 19 of 20 | 85 of 96 (89%) |
| Qwen3.5-9B-Q4_K_M | 1 of 12 | 48 of 64 | 12 of 20 | 61 of 96 (64%) |
| groq (sv1, reference) | 1 of 9 | 37 of 48 | 8 of 12 | 46 of 69 (67%) |

- gemini, mismatches (11): f19cdd eligibility (F-0006), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 title (consensus), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 563042 spec_access (F-0011), 28ad40 award_method (F-0046), 28ad40 eligibility (F-0042), 28ad40 spec_access (F-0044)
- Qwen3.5-9B-Q4_K_M, mismatches (35): f19cdd scope_summary (consensus), f19cdd delivery_location (consensus), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 title (consensus), 563042 contracting_officer (F-0020), 563042 notice_date (F-0022), 563042 item_category (consensus), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 563042 spec_access (F-0011), 4b0b9d title (F-0018), 4b0b9d procurement_type (F-0013), 4b0b9d award_method (F-0015), 4b0b9d performance_period (F-0025), 4b0b9d deadlines (F-0001), 4b0b9d tax_basis (F-0008), 4b0b9d required_documents (F-0033), 4b0b9d contact (F-0036), 4b0b9d spec_access (F-0010), 28ad40 title (F-0047), 28ad40 issuer_org (F-0048), 28ad40 procurement_type (F-0045), 28ad40 award_method (F-0046), 28ad40 performance_period (F-0054), 28ad40 eligibility (F-0042), 28ad40 deadlines (F-0040), 28ad40 required_documents (F-0052), 28ad40 contact (F-0053), 4c40bb issuer_org (F-0039), 4c40bb delivery_location (consensus)
- groq (sv1, reference), mismatches (23): f19cdd issuer_org (F-0055), f19cdd notice_date (F-0023), f19cdd performance_period (F-0027), f19cdd delivery_deadline (F-0028), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), f19cdd contact (F-0038), 563042 scope_summary (F-0057), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 563042 spec_access (F-0011), 4b0b9d title (F-0018), 4b0b9d issuer_org (F-0019), 4b0b9d procurement_type (F-0013), 4b0b9d deadlines (F-0001), 4b0b9d tax_basis (F-0008), 4b0b9d language_currency (F-0030), 4b0b9d required_documents (F-0033), 4b0b9d spec_access (F-0010)

## Gemini (JSON mode, one repair request)

| document | requests | answer valid as first sent | repair | problems before / after repair | tokens in / out | state |
| --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | 5 | yes | - | - | 5254 / 3800 | ok |
| 563042df9941 | 3 | yes | - | - | 5542 / 3840 | ok |
| 4b0b9d8229c7 | 2 | yes | - | - | 4709 / 2629 | ok |
| 28ad40ea4b1f | 2 | yes | - | - | 8845 / 4186 | ok |
| 4c40bbd831fe | 1 | yes | - | - | 5437 / 970 | ok |

## Local model (field groups under 60% of the output cap)

| document | model | fields | parts | output cap per part | time | tokens out | truncated parts | JSON failures | state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | Qwen3.5-9B-Q4_K_M | 23 | 1 | 8192 | 419 s | 3,011 | 0 | 0 | complete |
| 563042df9941 | Qwen3.5-9B-Q4_K_M | 23 | 1 | 8192 | 490 s | 2,996 | 0 | 0 | complete |
| 4b0b9d8229c7 | Qwen3.5-9B-Q4_K_M | 23 | 1 | 8192 | 729 s | 4,309 | 0 | 0 | complete |
| 28ad40ea4b1f | Qwen3.5-9B-Q4_K_M | 21 | 1 | 8192 | 1530 s | 8,097 | 0 | 0 | complete |
| 4c40bbd831fe | Qwen3.5-9B-Q4_K_M | 6 | 1 | 8192 | 223 s | 702 | 0 | 0 | complete |

## Gemini and the local model: agreement and flags

| document | mode | fields asked | agree | agreement | flagged | review items (flagged + spot-check) |
| --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | comparison | 23 | 19 | 83% | 4 | 5 |
| 563042df9941 | comparison | 23 | 17 | 74% | 6 | 7 |
| 4b0b9d8229c7 | comparison | 23 | 14 | 61% | 9 | 10 |
| 28ad40ea4b1f | comparison | 21 | 11 | 52% | 10 | 11 |
| 4c40bbd831fe | comparison | 6 | 4 | 67% | 2 | 2 |
| all | | 96 | 65 | 68% | 31 | |

## Projection for the full dev set

Dev set: 60 documents (37 open: Gemini + local; 23 restricted: Groq + local), 1095 asked fields.

| labeler | documents | requests | tokens | days | notes |
| --- | --- | --- | --- | --- | --- |
| Gemini (JSON mode) | 37 | 37 | no daily token cap | 2 without failed requests; 5 at this pilot's failure rate (8 of 13 tries) | one request per document plus repairs at this pilot's rate (0% of answers); documents needing two field groups: 0 |
| Groq | 23 | 108 (+ about 45 split-retry requests) | 724,421 (with the split retry: 1,029,440) | 4; 6 with the split retry | plan estimate scaled by the sv2 real / estimate ratio (1.06 in, 0.75 out); split retry at sv2's json_validate_failed rate (21% of parts), each failure costing two more requests of about the same size |
| local model | 60 | 60 (one part each in the plan) | runs on this Mac | 10.7 Mac hours | this pilot's time per asked field (35 s, n=5 documents) x 1095 asked fields |

Days = the slower cloud provider: **4 to 6**. The local model runs beside them on this Mac.

Review items, at the flag rate of the document labeled for real (?): about **?**; at the Gemini-vs-local flag rate over all pilot documents (32%): about **391**. Both include the 5% consensus spot-check of accepted fields. The restricted documents' pair is Groq + local, which this pilot did not measure.

## After local repair

The local model's answers got the same shape check and one repair request as Gemini's (D-52), run on the cached answers: repair requests only, no full re-run. The sections above show the local answers as first sent.

### The repair, per document

| document | fields with shape problems | fixed by the repair | still failing | other fields whose answer changed | kept | repair time | repair tokens in / out |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | 0 | - | - | - | - | no request | - |
| 563042df9941 | 0 | - | - | - | - | no request | - |
| 4b0b9d8229c7 | 6 | 6 | - | - | repair | - s | - / - |
| 28ad40ea4b1f | 2 | 2 | - | - | repair | - s | - / - |
| 4c40bbd831fe | 0 | - | - | - | - | no request | - |

### The local model against the existing labels, before and after

| labeler | list | structured | text | all fields |
| --- | --- | --- | --- | --- |
| Qwen3.5-9B-Q4_K_M, as first sent | 1 of 12 | 48 of 64 | 12 of 20 | 61 of 96 (64%) |
| Qwen3.5-9B-Q4_K_M, after repair | 1 of 12 | 54 of 64 | 12 of 20 | 67 of 96 (70%) |

- Qwen3.5-9B-Q4_K_M, as first sent, mismatches (35): f19cdd scope_summary (consensus), f19cdd delivery_location (consensus), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 title (consensus), 563042 contracting_officer (F-0020), 563042 notice_date (F-0022), 563042 item_category (consensus), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 563042 spec_access (F-0011), 4b0b9d title (F-0018), 4b0b9d procurement_type (F-0013), 4b0b9d award_method (F-0015), 4b0b9d performance_period (F-0025), 4b0b9d deadlines (F-0001), 4b0b9d tax_basis (F-0008), 4b0b9d required_documents (F-0033), 4b0b9d contact (F-0036), 4b0b9d spec_access (F-0010), 28ad40 title (F-0047), 28ad40 issuer_org (F-0048), 28ad40 procurement_type (F-0045), 28ad40 award_method (F-0046), 28ad40 performance_period (F-0054), 28ad40 eligibility (F-0042), 28ad40 deadlines (F-0040), 28ad40 required_documents (F-0052), 28ad40 contact (F-0053), 4c40bb issuer_org (F-0039), 4c40bb delivery_location (consensus)
- Qwen3.5-9B-Q4_K_M, after repair, mismatches (29): f19cdd scope_summary (consensus), f19cdd delivery_location (consensus), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 title (consensus), 563042 contracting_officer (F-0020), 563042 notice_date (F-0022), 563042 item_category (consensus), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 563042 spec_access (F-0011), 4b0b9d title (F-0018), 4b0b9d award_method (F-0015), 4b0b9d performance_period (F-0025), 4b0b9d deadlines (F-0001), 4b0b9d required_documents (F-0033), 28ad40 title (F-0047), 28ad40 issuer_org (F-0048), 28ad40 performance_period (F-0054), 28ad40 eligibility (F-0042), 28ad40 deadlines (F-0040), 28ad40 required_documents (F-0052), 28ad40 contact (F-0053), 4c40bb issuer_org (F-0039), 4c40bb delivery_location (consensus)

### Gemini and the local model, before and after

| document | mode | fields asked | agree (first sent / after repair) | flagged | review items (flagged + spot-check) | single-source rule would settle | flagged left with the rule |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | comparison | 23 | 19 / 19 | 4 / 4 | 5 / 5 | 0 | 4 |
| 563042df9941 | comparison | 23 | 17 / 17 | 6 / 6 | 7 / 7 | 1 | 5 |
| 4b0b9d8229c7 | comparison | 23 | 14 / 18 | 9 / 5 | 10 / 6 | 0 | 5 |
| 28ad40ea4b1f | comparison | 21 | 11 / 12 | 10 / 10 | 11 / 11 | 0 | 10 |
| 4c40bbd831fe | comparison | 6 | 4 / 4 | 2 / 2 | 2 / 2 | 0 | 2 |
| all | | 96 | 65 (68%) / 70 (73%) | 31 / 27 | | 1 | 26 |

### Single-source rule (projection only, not implemented)

The rule: for a flagged tier 2 field, when Gemini passes every blocking check and the local model's answer still fails one after its repair, accept Gemini's answer as `silver_single`, with a 10% spot-check into review. Tier 1 fields (deadlines, submission_modes, bid_bond, performance_bond, eligibility, unified_qualification, tax_basis, spec_access, procurement_type, award_method) are never settled this way. Settled after repair:

- 563042df9941 (comparison): item_category (Gemini: absent, matches the label)

Where a label exists, Gemini's answer matches it on 1 of 1 items the rule would settle.

### Review items for the full dev set

1095 asked fields. Review items = flagged fields left + 10% of the settled ones + the 5% consensus spot-check of the accepted ones, at the pilot's rates. The rates are Gemini + local; the restricted documents get Groq + local, not measured here, and the rule as written names Gemini.

| flag rate from | first sent: flag rate, review items | after repair: flag rate, review items | after repair with the single-source rule: settled, review items |
| --- | --- | --- | --- |
| all pilot documents (Gemini vs local) | 32%, 391 | 28%, **347** | 1% of asked fields, **337** |
