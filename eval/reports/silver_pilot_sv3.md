# Silver pilot, prompt sv3

Date: 2026-10-03 (UTC). Four open dev documents: 28ad40ea4b1f labeled for real, f19cddbd4cba, 563042df9941 and 4b0b9d8229c7 in comparison mode (no labels written). Everything below these notes is rebuilt by `uv run python -m eval.silver report --docs 28ad40ea4b1f,f19cddbd4cba,563042df9941,4b0b9d8229c7 --notes eval/reports/silver_pilot_sv3_notes.md` (no API calls).

## What happened

- **How it ran.** `run --docs <the 4> --yes --max-calls 12`. Gemini went first and hit HTTP 503 seven times (f19cddbd4cba answered on the 5th try, 4b0b9d8229c7 on the 2nd, 28ad40ea4b1f on the 3rd), so 11 of the 12 calls went on Gemini and the local model got one document (f19cddbd4cba) before the cap. The backoff never ran out, so the pause did not trigger. The other three local answers were made with `shadow` (local only, same prompt, same raw cache, no cloud call), and the documents were resolved with a second `run ... --max-calls 1` that found everything cached: the ledger did not change. No Groq call was made. Gemini used 17 of its 20 requests today (6 before this pilot).
- **Gemini in JSON mode works.** 4 of 4 answers had the right shape as first sent; no repair request was needed. The 21- and 23-field documents that strict mode refused in sv2 are labeled. Against the existing labels Gemini matches 62 of 69 fields. Two of its 7 mismatches are worth a look before blaming Gemini: on f19cddbd4cba it answers issuer_org `出入国在留管理庁` where the sv1 consensus label says `法務省`; the current guide (a 〇〇庁 that issues in its own name is the org) and the reviewed contact label of the same document (F-0038, org `出入国在留管理庁`) agree with Gemini, so the old label may be the one that is out of date. spec_access (2 mismatches) is the field the sv1 report already called ambiguous: Gemini says public (handed out from the portal), the labels say see_other_document (入札説明書による).
- **The local model never ran out of room.** One part per document at an 8,192-token cap, 481 to 724 s each, no truncation, no invalid JSON. 28ad40ea4b1f, which was cut off at 4,056 tokens twice in sv2, needed 2,197 tokens.
- **But on two documents Qwen left most values empty.** On 28ad40ea4b1f it marked 11 structured or list fields present and gave `normalized: null` for 9 of them; on 4b0b9d8229c7, 3 of 5. On f19cddbd4cba and 563042df9941 it did not happen at all, and Gemini never did it (0 of 49). The strict schema allows null there (null is right when a field is absent), so llama-server's grammar cannot stop it. This is the same failure Groq showed in sv1. It explains most of 28ad40ea4b1f's flags: 9 of its 13 flagged fields have Qwen failing `schema_valid`, and it is also why the review export has no C (union) candidate: on every flagged list field Qwen's side has no items. It also pulls down Qwen's scores below (list fields 1 of 9).
- **Flag rate.** 28ad40ea4b1f: 13 of 21 fields flagged (62%), 14 review items with the spot-check. Over the 4 documents Gemini and Qwen agree on 57 of 90 fields (63%). With Qwen's empty values fixed, the rate would be lower, by how much is not measured.

## Proposal (implemented as D-52, results in the last section)

Give the local model the same shape check and one repair request as Gemini. Both are already written; run on Qwen's 28ad40ea4b1f answer, `checks.shape_errors` finds exactly the 9 empty values. It costs Mac time only (one more request on a document with problems, about 10 minutes), no quota, and treats both labelers the same way: shape is repaired, content is not. The alternative, a schema that forbids null for present fields, needs conditional schemas that neither llama-server's grammar nor Groq's strict mode is known to support.

## Follow-up, same day: local repair (D-52)

- **The repair ran on the cached answers only.** `repair --docs <the 4>`: two repair requests on this Mac, no cloud call, no full re-run. f19cddbd4cba and 563042df9941 had no shape problems (no request). 4b0b9d8229c7: 3 of 3 fields fixed (416 s). 28ad40ea4b1f: 4 of 9 fixed (421 s); eligibility, deadlines, submission_modes, required_documents and contact still have `normalized` null, so the repair helps but does not cure it. No field outside the problem list changed its answer.
- **Effect is small.** Qwen against the labels: 47 to 49 of 68. Gemini-vs-Qwen agreement: 57 to 62 of 90 (63% to 69%), flags 34 to 31. 28ad40ea4b1f: 13 to 12 flags, 14 review items either way. Of its 4 fixed fields only language_currency became a consensus; procurement_type now fails a content check (value_in_citation), award_method is a status disagreement, and on tax_basis Gemini's own answer fails values_roundtrip.
- **Field counts are now 68, not 69.** issuer_org of f19cddbd4cba was reopened (the sv1 label 法務省 against Gemini sv3's 出入国在留管理庁, review item F-0055), so it is no longer a label and drops out of every comparison. That removes one Gemini and one Qwen mismatch and one Groq sv1 match.
- **Single-source rule (projection only).** It would settle 4 of the 31 flagged items: 563042df9941 item_category (Gemini absent; matches the label) and on 28ad40ea4b1f scope_summary (Gemini see_other_document), required_documents and contact. One checkable item is not evidence that the rule is safe.

## Second follow-up: review imported, local labeler sv3-l1 (D-53)

- **Labels changed since the sections below "After local repair" were first written.** The batch-01 and batch-02 answers are imported (F-0039 held back), issuer_org of f19cddbd4cba is reviewed (F-0055), scope_summary of 563042df9941 was reopened and answered see_other_document (F-0057), and the NUM-6 converter now reads 28ad40ea4b1f p6_s10 as tax included, so Gemini's tax_basis there no longer fails values_roundtrip. The tables are rebuilt from the current labels, so some numbers differ from the bullets above.
- **sv3-l1 did not move the accuracy.** Qwen against the labels of all 4 documents: 62 of 90 under sv3 (after repair) and under sv3-l1; list fields 1 of 12 both. Gemini-vs-Qwen agreement 62 to 59 of 90, flags 30 to 31.
- **The empty values are mostly gone.** Asked alone, Qwen still first answers list fields with `normalized` null, but after the plain repair message 10 of 11 such answers have a value (the D-52 message: 7 of 12); one of the 10, 28ad40ea4b1f deadlines, then breaks another form rule (exactly one of datetime and relative_text). Of two answers marked present with no citations, f19cddbd4cba eligibility stayed broken and 563042df9941 eligibility was turned into see_other_document, which the label (present, 5 items) says is wrong. On 28ad40ea4b1f eligibility and required_documents now have 8 and 12 items where sv3 had none. The list fields still fail because the list rule needs every item to pair: required_documents pairs 14 of 19 label items (sv3: 0), eligibility 4 of 18 (sv3: 8), deadlines 3 of 11 (sv3: 5).
- **The prompt cache works, after one change.** The document prefix is byte-identical (llama-server's LCP similarity 0.96 between calls), but Qwen3.5 is a hybrid model: llama-server restores a cached prompt only from a checkpoint it saves about 512 tokens before the end of a prompt. With the grouped call first that checkpoint lay past the shared document and only 1,440 tokens were reused; with the grouped call last, later calls take 2,578 to 6,928 tokens from the cache and spend 7.5 to 12.7 s on the prompt (first call 20 to 88 s).
- **Cost.** 7 to 9 local requests per document (5 parts plus repairs); 432 to 511 s on the three notices (sv3: 697 to 897 s), 1,285 s on 28ad40ea4b1f (sv3 with repair: 1,021 s).

## Reviewed documents: each labeler against the existing labels

Comparison mode: these documents already had labels, so nothing was written for them. The labels are sv1 consensus lines plus the reviewer's answers (`claude_chat`, a model in chat, not human-verified). **They came from Gemini and Groq plus that review, which slightly favors Gemini** (and Groq's sv1 row), and the documents were used to write the labeling guide, so every number here is optimistic. The local model's answers are shown as first sent (after repair: the last section). Match = the consensus agreement rule (status, enums and dates exact; text fuzzy with overlapping citations; the active relaxations): the answer would have been accepted beside the label. Mismatches name the review item id when the label came from the review, `consensus` when it was an sv1 consensus line.

| labeler | list | structured | text | all fields |
| --- | --- | --- | --- | --- |
| gemini | 6 of 9 | 45 of 48 | 11 of 12 | 62 of 69 (90%) |
| Qwen3.5-9B-Q4_K_M | 1 of 9 | 38 of 48 | 9 of 12 | 48 of 69 (70%) |
| groq (sv1, reference) | 1 of 9 | 37 of 48 | 8 of 12 | 46 of 69 (67%) |

- gemini, mismatches (7): f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 scope_summary (F-0057), 563042 required_documents (F-0034), 563042 spec_access (F-0011), 4b0b9d deadlines (F-0001)
- Qwen3.5-9B-Q4_K_M, mismatches (21): f19cdd delivery_location (consensus), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 contracting_officer (F-0020), 563042 notice_date (F-0022), 563042 item_category (consensus), 563042 scope_summary (F-0057), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 4b0b9d title (F-0018), 4b0b9d procurement_type (F-0013), 4b0b9d performance_period (F-0025), 4b0b9d deadlines (F-0001), 4b0b9d required_documents (F-0033), 4b0b9d contact (F-0036), 4b0b9d spec_access (F-0010)
- groq (sv1, reference), mismatches (23): f19cdd issuer_org (F-0055), f19cdd notice_date (F-0023), f19cdd performance_period (F-0027), f19cdd delivery_deadline (F-0028), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), f19cdd contact (F-0038), 563042 scope_summary (F-0057), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 563042 spec_access (F-0011), 4b0b9d title (F-0018), 4b0b9d issuer_org (F-0019), 4b0b9d procurement_type (F-0013), 4b0b9d deadlines (F-0001), 4b0b9d tax_basis (F-0008), 4b0b9d language_currency (F-0030), 4b0b9d required_documents (F-0033), 4b0b9d spec_access (F-0010)

## Gemini (JSON mode, one repair request)

| document | requests | answer valid as first sent | repair | problems before / after repair | tokens in / out | state |
| --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | 5 | yes | - | - | 4881 / 3895 | ok |
| 563042df9941 | 1 | yes | - | - | 5169 / 4017 | ok |
| 4b0b9d8229c7 | 2 | yes | - | - | 4336 / 2868 | ok |
| 28ad40ea4b1f | 3 | yes | - | - | 8472 / 4858 | ok |

## Local model (field groups under 60% of the output cap)

| document | model | fields | parts | output cap per part | time | tokens out | truncated parts | JSON failures | state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | Qwen3.5-9B-Q4_K_M | 23 | 1 | 8192 | 697 s | 3,016 | 0 | 0 | complete |
| 563042df9941 | Qwen3.5-9B-Q4_K_M | 23 | 1 | 8192 | 724 s | 3,339 | 0 | 0 | complete |
| 4b0b9d8229c7 | Qwen3.5-9B-Q4_K_M | 23 | 1 | 8192 | 481 s | 2,044 | 0 | 0 | complete |
| 28ad40ea4b1f | Qwen3.5-9B-Q4_K_M | 21 | 1 | 8192 | 600 s | 2,197 | 0 | 0 | complete |

## Gemini and the local model: agreement and flags

| document | mode | fields asked | agree | agreement | flagged | review items (flagged + spot-check) |
| --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | comparison | 23 | 19 | 83% | 5 | 6 |
| 563042df9941 | comparison | 23 | 14 | 61% | 9 | 10 |
| 4b0b9d8229c7 | comparison | 23 | 16 | 70% | 7 | 8 |
| 28ad40ea4b1f | labeled | 21 | 8 | 38% | 13 | 14 |
| all | | 90 | 57 | 63% | 34 | |

## Projection for the full dev set

Dev set: 60 documents (37 open: Gemini + local; 23 restricted: Groq + local), 1095 asked fields.

| labeler | documents | requests | tokens | days | notes |
| --- | --- | --- | --- | --- | --- |
| Gemini (JSON mode) | 37 | 37 | no daily token cap | 2 without failed requests; 6 at this pilot's failure rate (7 of 11 tries) | one request per document plus repairs at this pilot's rate (0% of answers); documents needing two field groups: 0 |
| Groq | 23 | 131 (+ about 55 split-retry requests) | 861,640 (with the split retry: 1,224,435) | 5; 7 with the split retry | plan estimate scaled by the sv2 real / estimate ratio (1.06 in, 0.75 out); split retry at sv2's json_validate_failed rate (21% of parts), each failure costing two more requests of about the same size |
| local model | 60 | 60 (one part each in the plan) | runs on this Mac | 8.5 Mac hours | this pilot's time per asked field (28 s, n=4 documents) x 1095 asked fields |

Days = the slower cloud provider: **5 to 7**. The local model runs beside them on this Mac.

Review items, at the flag rate of the document labeled for real (62%): about **699**; at the Gemini-vs-local flag rate over all pilot documents (38%): about **448**. Both include the 5% consensus spot-check of accepted fields. The restricted documents' pair is Groq + local, which this pilot did not measure.

## After local repair

The local model's answers got the same shape check and one repair request as Gemini's (D-52), run on the cached answers: repair requests only, no full re-run. The sections above show the local answers as first sent.

### The repair, per document

| document | fields with shape problems | fixed by the repair | still failing | other fields whose answer changed | kept | repair time | repair tokens in / out |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | 0 | - | - | - | - | no request | - |
| 563042df9941 | 0 | - | - | - | - | no request | - |
| 4b0b9d8229c7 | 3 | 3 | - | - | repair | 415.9 s | 6345 / 2360 |
| 28ad40ea4b1f | 9 | 4 | contact, deadlines, eligibility, required_documents, submission_modes | - | repair | 421.1 s | 10648 / 2252 |

### The local model against the existing labels, before and after

| labeler | list | structured | text | all fields |
| --- | --- | --- | --- | --- |
| Qwen3.5-9B-Q4_K_M, as first sent | 1 of 9 | 38 of 48 | 9 of 12 | 48 of 69 (70%) |
| Qwen3.5-9B-Q4_K_M, after repair | 1 of 9 | 40 of 48 | 9 of 12 | 50 of 69 (72%) |

- Qwen3.5-9B-Q4_K_M, as first sent, mismatches (21): f19cdd delivery_location (consensus), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 contracting_officer (F-0020), 563042 notice_date (F-0022), 563042 item_category (consensus), 563042 scope_summary (F-0057), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 4b0b9d title (F-0018), 4b0b9d procurement_type (F-0013), 4b0b9d performance_period (F-0025), 4b0b9d deadlines (F-0001), 4b0b9d required_documents (F-0033), 4b0b9d contact (F-0036), 4b0b9d spec_access (F-0010)
- Qwen3.5-9B-Q4_K_M, after repair, mismatches (19): f19cdd delivery_location (consensus), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 contracting_officer (F-0020), 563042 notice_date (F-0022), 563042 item_category (consensus), 563042 scope_summary (F-0057), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 4b0b9d title (F-0018), 4b0b9d performance_period (F-0025), 4b0b9d deadlines (F-0001), 4b0b9d required_documents (F-0033), 4b0b9d spec_access (F-0010)

### Gemini and the local model, before and after

| document | mode | fields asked | agree (first sent / after repair) | flagged | review items (flagged + spot-check) | single-source rule would settle | flagged left with the rule |
| --- | --- | --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | comparison | 23 | 19 / 19 | 5 / 5 | 6 / 6 | 0 | 5 |
| 563042df9941 | comparison | 23 | 14 / 14 | 9 / 9 | 10 / 10 | 1 | 8 |
| 4b0b9d8229c7 | comparison | 23 | 16 / 18 | 7 / 5 | 8 / 6 | 0 | 5 |
| 28ad40ea4b1f | labeled | 21 | 8 / 11 | 13 / 11 | 14 / 13 | 3 | 8 |
| all | | 90 | 57 (63%) / 62 (69%) | 34 / 30 | | 4 | 26 |

### Single-source rule (projection only, not implemented)

The rule: for a flagged tier 2 field, when Gemini passes every blocking check and the local model's answer still fails one after its repair, accept Gemini's answer as `silver_single`, with a 10% spot-check into review. Tier 1 fields (deadlines, submission_modes, bid_bond, performance_bond, eligibility, unified_qualification, tax_basis, spec_access, procurement_type, award_method) are never settled this way. Settled after repair:

- 563042df9941 (comparison): item_category (Gemini: absent, matches the label)
- 28ad40ea4b1f (labeled): scope_summary (Gemini: see_other_document, matches the label), required_documents (Gemini: present, matches the label), contact (Gemini: present, matches the label)

Where a label exists, Gemini's answer matches it on 4 of 4 items the rule would settle.

### Review items for the full dev set

1095 asked fields. Review items = flagged fields left + 10% of the settled ones + the 5% consensus spot-check of the accepted ones, at the pilot's rates. The rates are Gemini + local; the restricted documents get Groq + local, not measured here, and the rule as written names Gemini.

| flag rate from | first sent: flag rate, review items | after repair: flag rate, review items | after repair with the single-source rule: settled, review items |
| --- | --- | --- | --- |
| the document labeled for real | 62%, 699 | 52%, **600** | 14% of asked fields, **459** |
| all pilot documents (Gemini vs local) | 38%, 448 | 33%, **402** | 4% of asked fields, **358** |

## Local labeler sv3-l1

The local labeler's own prompt version `sv3-l1` (D-53): the same system prompt in every call, the document before the fields, list fields and contact asked one per call, a plain repair message, llama-server's prompt cache on. Gemini stays at `sv3` (cached). The pending sv4 guide rules are not in it. Scored on every document that has labels: the 28ad40ea4b1f labels were reviewed from Gemini's and Qwen's sv3 answers, which favors those answers.

### Against the labels

| labeler | list | structured | text | all fields |
| --- | --- | --- | --- | --- |
| gemini (sv3, reference) | 8 of 12 | 57 of 62 | 15 of 16 | 80 of 90 (89%) |
| Qwen3.5-9B-Q4_K_M sv3 (after repair) | 1 of 12 | 51 of 62 | 10 of 16 | 62 of 90 (69%) |
| Qwen3.5-9B-Q4_K_M sv3-l1 | 1 of 12 | 51 of 62 | 10 of 16 | 62 of 90 (69%) |

- gemini (sv3, reference), mismatches (10): f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 scope_summary (F-0057), 563042 required_documents (F-0034), 563042 spec_access (F-0011), 4b0b9d deadlines (F-0001), 28ad40 award_method (F-0046), 28ad40 eligibility (F-0042), 28ad40 spec_access (F-0044)
- Qwen3.5-9B-Q4_K_M sv3 (after repair), mismatches (28): f19cdd delivery_location (consensus), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), f19cdd spec_access (F-0012), 563042 contracting_officer (F-0020), 563042 notice_date (F-0022), 563042 item_category (consensus), 563042 scope_summary (F-0057), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 4b0b9d title (F-0018), 4b0b9d performance_period (F-0025), 4b0b9d deadlines (F-0001), 4b0b9d required_documents (F-0033), 4b0b9d spec_access (F-0010), 28ad40 title (F-0047), 28ad40 issuer_org (F-0048), 28ad40 scope_summary (F-0049), 28ad40 eligibility (F-0042), 28ad40 deadlines (F-0040), 28ad40 submission_modes (F-0041), 28ad40 required_documents (F-0052), 28ad40 contact (F-0053), 28ad40 spec_access (F-0044)
- Qwen3.5-9B-Q4_K_M sv3-l1, mismatches (28): f19cdd delivery_location (consensus), f19cdd eligibility (F-0006), f19cdd deadlines (F-0003), f19cdd submission_modes (F-0004), f19cdd required_documents (F-0035), 563042 notice_date (F-0022), 563042 item_category (consensus), 563042 scope_summary (F-0057), 563042 performance_period (F-0026), 563042 eligibility (F-0005), 563042 deadlines (F-0002), 563042 required_documents (F-0034), 4b0b9d title (F-0018), 4b0b9d performance_period (F-0025), 4b0b9d delivery_deadline (consensus), 4b0b9d deadlines (F-0001), 4b0b9d required_documents (F-0033), 4b0b9d spec_access (F-0010), 28ad40 title (F-0047), 28ad40 issuer_org (F-0048), 28ad40 scope_summary (F-0049), 28ad40 performance_period (F-0054), 28ad40 eligibility (F-0042), 28ad40 deadlines (F-0040), 28ad40 submission_modes (F-0041), 28ad40 required_documents (F-0052), 28ad40 contact (F-0053), 28ad40 spec_access (F-0044)

List fields and contact, document by document:

| field | kind | sv3 matches | sv3-l1 matches |
| --- | --- | --- | --- |
| eligibility | list | 1 of 4 (misses f19cdd, 563042, 28ad40) | 1 of 4 (misses f19cdd, 563042, 28ad40) |
| deadlines | list | 0 of 4 (misses f19cdd, 563042, 4b0b9d, 28ad40) | 0 of 4 (misses f19cdd, 563042, 4b0b9d, 28ad40) |
| required_documents | list | 0 of 4 (misses f19cdd, 563042, 4b0b9d, 28ad40) | 0 of 4 (misses f19cdd, 563042, 4b0b9d, 28ad40) |
| contact | structured | 3 of 4 (misses 28ad40) | 3 of 4 (misses 28ad40) |

List items: a list field matches only when every item pairs (agree.item_same: same kind, dates and flags, overlapping citations, similar text), so a near miss scores like an empty answer. Items given and paired, summed over the documents:

| field | label items | sv3: items given, paired with a label item | sv3-l1: items given, paired |
| --- | --- | --- | --- |
| eligibility | 18 | 10, 8 | 8, 4 |
| deadlines | 11 | 8, 5 | 13, 3 |
| required_documents | 19 | 1, 0 | 15, 14 |

### Gemini and the local model

| document | fields asked | agree (sv3 / sv3-l1) | flagged (sv3 / sv3-l1) | flag rate (sv3 / sv3-l1) | single-source rule would settle (sv3-l1) |
| --- | --- | --- | --- | --- | --- |
| f19cddbd4cba | 23 | 19 / 17 | 5 / 6 | 22% / 26% | - |
| 563042df9941 | 23 | 14 / 15 | 9 / 8 | 39% / 35% | item_category |
| 4b0b9d8229c7 | 23 | 18 / 17 | 5 / 6 | 22% / 26% | - |
| 28ad40ea4b1f | 21 | 11 / 10 | 11 / 11 | 52% / 52% | - |
| all | 90 | 62 (69%) / 59 (66%) | 30 / 31 | 33% / 34% | 1 |

### Cost and the prompt cache

| document | sv3: requests, time | sv3-l1: requests, time | first request: prompt tokens processed, ms | later requests: tokens taken from the cache, tokens processed, ms (mean) |
| --- | --- | --- | --- | --- |
| f19cddbd4cba | 1, 697 s | 8, 511 s | 3407, 52961 | 3146, 505, 8336 |
| 563042df9941 | 1, 724 s | 8, 448 s | 2225, 27853 | 3404, 493, 7501 |
| 4b0b9d8229c7 | 2, 897 s | 7, 432 s | 1442, 20139 | 2578, 520, 8676 |
| 28ad40ea4b1f | 2, 1021 s | 9, 1285 s | 5625, 88349 | 6928, 713, 12701 |

### Review items, dev and test (projection only)

Rates from the 4 documents above (Gemini vs local): flag rate 33% (sv3), 34% (sv3-l1); the rule settles 1% of asked fields. Test is always fully reviewed: every one of its 730 asked fields is a review item (in brackets: the test items at the flag rate, for comparison). Review items = flagged fields left + 10% of the settled ones + the 5% consensus spot-check.

| scenario | dev documents | dev asked fields | dev review items | test review items | total |
| --- | --- | --- | --- | --- | --- |
| (a) sv3 as now | 60 | 1095 | **402** | 730 (268) | **1132** |
| (b) sv3-l1 | 60 | 1095 | **413** | 730 (275) | **1143** |
| (c) sv3-l1 + single-source rule on dev tier 2 fields | 60 | 1095 | **402** | 730 (275) | **1132** |
| (d) as (c), dev cut to 40 documents, stratified | 40 | 730 | **268** | 730 (275) | **998** |
