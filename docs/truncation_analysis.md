# Cut-off model answers in the recorded runs

Date: 2026-11-28. Analysis only, from files already on disk. No model call, no cloud call, no code or cache change. `EXTRACTOR_VERSION` stays 0.3.0.

"Cut off" means the request stopped because it hit its output cap (`max_tokens`; finish reason `length` or `MAX_TOKENS`).

## How a cut-off is stored

| recording | what is kept |
|---|---|
| app recordings (`audit_baseline`, `audit_repeat`, `spec_ngram` replay files) | `{"truncated": true, "seconds": ...}` in place of `answer` |
| llama-server logs | no finish reason; seen as an output token count equal to the cap (the `truncated = 0` in these logs is a different thing and is 0 everywhere read) |
| `hybrid/trace_*.json` | `call_failed: "Truncated"` on the call; no token count |
| `gemini_compare/lists_cache/` | a `truncated` list of field names per document |
| `scalar_probe/`, `models/feasibility_raw.jsonl` | `finish_reason` / `finish` |
| `labeling/raw/` | chunk with `truncated: true`, `tokens_out_cut`, `error`; a cut repair request shows as `repair.failed` |
| `labeling/usage.jsonl` | no finish reason; a cut request is logged as `ok`, seen only by output tokens equal to the cap |
| labeling answers from before the cut-off check (prompt sv2) | `error: "invalid JSON"`; the cut is known from `eval/reports/silver_pilot_sv2.md` and `docs/decisions.md` (under D-50) |

## What the app does with a cut answer

`core/shiori_core/extract/llm.py`: the client raises `Truncated` and throws the text away (line 233). No repair, no salvage of finished items, no second request (lines 649 to 652; 831 to 832 for the scalar call).

- List call cut: that field is not found. The app sends a "none" event for it, the same as for a field with no answer.
- Scalar call cut (by the code; none recorded): every field asked in that call is not found.

The labeling pipeline (`eval/silver/pipeline.py`) also drops the text: the part is `failed`. If the cut request was a repair request, the first answer is kept. A cut Groq part may be split in two on a later run (D-59).

## App recordings without extra server flags

Shipped model, bundled llama-server, 15 dev documents, 56 requests per full run.

| recording | requests | cut off | final fields lost |
|---|---|---|---|
| `audit_baseline` | 56 | 0 | 0 |
| `audit_repeat/run1` | 56 | 0 | 0 |
| `audit_repeat/run2` | 56 | 0 | 0 |
| `spec_ngram/old1` | 56 | 0 | 0 |
| `spec_ngram/old2` | 56 | 0 | 0 |
| `spec_ngram` one-call runs without flags | 4 | 0 | 0 |
| total | 284 | 0 | 0 |

The largest output in the server logs of `run1`, `run2`, `old1` and `old2` was 844 tokens, against a cap of 2,048 for list calls. `spec_ngram/replay`, `full` and `rules` are byte-identical copies of the baseline and are not counted. `audit_baseline` keeps no server log.

## Flagged runs (ngram speculative decoding), listed separately

| recording | requests | cut off | field group | document | output tokens | app result | final fields lost |
|---|---|---|---|---|---|---|---|
| `new1` | 56 | 1 | eligibility | d230e51e | 2,048 | not found | 1 |
| `new2` | 56 | 1 | eligibility | d230e51e | 2,048 | not found | 1 |
| `new3` | 56 | 1 | eligibility | d230e51e | 2,048 | not found | 1 |
| one-call runs with flags | 10 | 0 | required_documents | d4000027 | 844 | answer kept | 0 |
| total | 178 | 3 | | | | | 3 (one field of one document, three times) |

All three are request `5b28002d`. Without flags it wrote 663 tokens (replay count) and the final output held 5 eligibility items. In each flagged run the final output has eligibility absent with 0 items, and translation requests go from 36 to 31. No other final field differs from the baseline.

## Older caches: extraction runs

| recording | requests counted | cut off | final fields lost |
|---|---|---|---|
| `hybrid/trace_*.json`, 25 traces | 694 calls with an answer (734 calls; 40 got none after HTTP or timeout errors) | 5 | 5 |
| hybrid reports with no trace file (`hybrid_dev_hybrid`, `_2docs`, `_2docs_b`, `_v2`) | 56 | 0 (reports show no failed call) | 0 |
| `gemini_compare` scalar report, variants B, B2, S | 150 | 0 | 0 |
| `gemini_compare/lists_cache`, 50 documents | not stored | 0 | 0 |
| `scalar_probe/` | 45 | 0 | 0 |
| `models/feasibility_raw.jsonl` | 57 with an answer (2 HTTP errors) | 0 | 0 |

The 5 cut calls are all in model comparison runs with models the app does not ship:

| run | model | field | document | output tokens | result |
|---|---|---|---|---|---|
| `cmp_qwen3_swallow_8b` | Qwen3-Swallow-8B | eligibility | 136dfba9 | not recorded | not found |
| `cmp_lfm25_12b_jp` | LFM2.5-1.2B-JP | eligibility | d230e51e | not recorded | not found |
| `cmp_lfm25_12b_jp` | LFM2.5-1.2B-JP | eligibility | 594c3cb6 | not recorded | not found |
| `cmp_lfm25_12b_jp` | LFM2.5-1.2B-JP | deadlines | d4000027 | not recorded | not found |
| `cmp_lfm25_12b_jp` | LFM2.5-1.2B-JP | deadlines | 28ad40ea | not recorded | not found |

The cap for these list calls is 2,048 in the current code. The traces do not store it. All had 0 retries.

Traces not named after another model (456 calls, including `cmp_qwen35_9b`) have 0 cut calls.

## Older caches: labeling (`data/cache/labeling/`)

These are labeler candidates for the silver labels, not app output. Prompts, caps (set per request) and most models differ from the app. `labeling.bak-holdout/` is a strict subset (88 raw files identical, ledger lines all present) and is not counted again.

10 of 231 answered requests in the ledger were cut off.

| model | cut / answered requests |
|---|---|
| LFM2.5-1.2B-JP (local) | 4 / 7 |
| LFM2.5-8B-A1B (local) | 1 / 9 |
| Qwen3-Swallow-8B (local) | 1 / 8 |
| Qwen3.5-9B (local) | 2 / 130 |
| NVIDIA Nemotron 9B Japanese (local) | 0 / 1 |
| gpt-oss-120b (Groq) | 2 / 50 |
| gemini-3.8-flash | 0 / 26 |

| document | model, prompt | requests | field group | output tokens (= cap) | what the pipeline did | labeler field answers lost |
|---|---|---|---|---|---|---|
| 28ad40ea | LFM2.5-1.2B, sv4 | 1 | all, 21 fields (set A) | 8,192 | part failed | 21 |
| 4b0b9d82 | LFM2.5-1.2B, sv4 | 1 | all, 23 fields (set B) | 8,192 | part failed | 23 |
| f19cddbd | LFM2.5-1.2B, sv4 | 1 | all, 23 fields (set B) | 8,192 | part failed | 23 |
| 563042df | LFM2.5-1.2B, sv4 | 1 (repair) | all, 23 fields (set B) | 8,192 | repair dropped, first answer kept | 0 |
| 28ad40ea | Qwen3-Swallow-8B, sv4 | 1 | all, 21 fields (set A) | 8,192 | part failed | 21 |
| 4c40bbd8 | LFM2.5-8B, sv4 | 1 | set C | 8,192 | part failed | 6 |
| 6a447150 | gpt-oss-120b, sv4, part index 1 | 1 | set D | 1,716 | part failed; no later split recorded | 6 |
| b16ad988 | gpt-oss-120b, sv4, part index 2 | 1 | set D | 1,716 | part failed; no later split recorded | 6 |
| 28ad40ea | Qwen3.5-9B, sv2 | 2 (same request twice) | all, 21 fields (set A) | 4,056 | recorded as invalid JSON, part failed | 21 |
| total | | 10 | | | | 127 |

- Set B: title, issuer_org, contracting_officer, notice_date, procurement_type, award_method, item_category, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility, unified_qualification, deadlines, submission_modes, bid_bond, performance_bond, tax_basis, language_currency, required_documents, contact, wto_covered, spec_access.
- Set A: set B without notice_date and item_category.
- Set C: title, issuer_org, scope_summary, performance_period, delivery_deadline, delivery_location.
- Set D: item_category, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility.
- 563042df: the kept first answer had shape errors in deadlines, delivery_deadline, notice_date, performance_period and submission_modes, which the cut repair did not fix.

"Field answers lost" counts one labeler's answers. No app field is involved. 6a447150 and b16ad988 have no dev label file and no resolved record. The other documents in the table have dev label files; whether a lost candidate would have changed any label was not checked.

## Final fields lost, by recording set

| set | cut requests | final app fields lost |
|---|---|---|
| unflagged app recordings | 0 | 0 |
| flagged (ngram) runs | 3 | 3 |
| older extraction runs (comparison models only) | 5 | 5 |
| older labeling cache | 10 | none (127 labeler field answers) |

"Lost" means the field ended as not found. It does not say the cut answer was right or would have passed the checks.

## Cut off but still valid JSON

None found. No stored answer is both marked cut off (or at a known cap) and parseable. All stored answers in the app replay files parse as JSON.

This cannot be ruled out for the cut requests themselves: the code discards the text of a cut answer, so none of the recordings listed holds it.

## Not determined

- Whether any discarded cut answer was valid JSON, or held complete items.
- Four Groq sv2 failures (`json_validate_failed`; 28ad40ea part indexes 2 and 5, 563042df part indexes 1 and 2) may be cut-offs or schema slips. The error text was not kept.
- Labeling requests with no recorded cap (some sv1 and sv2 ones): a cut there is visible only if the answer failed and something else records why. The ledger stores no finish reason.
- Output token counts of the 5 cut hybrid calls.
- The number of requests behind the 50-document list run.
- Translation requests: stubbed in the app recordings, and no finish reason was found for real ones.
- Gemini web-chat replies and the chat reference batches have no finish reason.
- Runs whose cache or log was later overwritten.
- Why the flagged answer ran to the cap.

## Conclusion

For the shipped model with the app's extraction requests, no recorded unflagged request was cut off: 0 of 284 in the app recordings, and 0 in the older extraction traces of that model. The only recorded cut-offs with it in extraction are the 3 ngram ones, all the same request. On these sets, truncation in the app is a side effect of the ngram flags.

It is not only that in general. Without any such flag, 15 requests were cut off in older runs: 5 extraction calls by two other models, and 10 labeling requests (8 local, 2 Groq), 2 of them by Qwen3.5-9B under an older, lower cap and a 21-field request. So it depends on model, cap and request size.

The evidence is narrow: mostly the 15 labeled dev documents, plus a 50-document list run, on one Mac. It says nothing about longer documents or other machines.
