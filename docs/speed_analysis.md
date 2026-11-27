# Where extraction model time goes, and what could cut it

Date: 2026-11-26. Analysis only. No source file, prompt, threshold or `EXTRACTOR_VERSION` (0.3.0) was changed. The analysis used recorded answers and made no model call. Later the same day, with go-ahead, the baseline was recorded twice more on the local llama-server (section 4). No cloud call was made.

## Short answer

- **Two identical runs differ by up to 20% in total seconds (1,938.6 s and 2,335.1 s of server time).** Smaller slices differ more: one field group by up to 38%, one call by up to 2.3 times. So every saving is judged in tokens and calls first. Seconds are only an estimate.
- Token counts, call counts and answers did not move between those runs.
- Model calls are almost all of extraction time: 1,906.6 s of 1,908 s logged for the 15 labeled dev documents. Mean 127.1 s per document, median 121.6 s, range 24.7 to 325.8 s.
- Writing output is about two thirds of model time, reading prompts about one third (a fit, see Method).
- No option that cuts the time of a first run is guaranteed to leave output unchanged. Only reusing a stored result on a repeat run is.
- Speculative decoding (option 2) was tested on 2026-11-27 and 28. It changed 2 of 56 answers, so it is class C and is not adopted (section 6, D-122).
- The scalar fallback took 245 s (12.9%) and added nothing to the final output on these 15 documents. On a separate 50-document cache it did keep answers (19 answers on 6 documents), so removing it would change output.
- The 15 dev documents are the set the prompts were tuned on. Any option marked "might change output" needs evidence from outside them before it ships (D-96).

## Method

Sources:

- `data/cache/audit_baseline/` (recorded answers and wall seconds per request, Qwen3.5-9B Q4_K_M, bundled llama-server b12651, Mac).
- `data/cache/audit_repeat/` (the two repeat recordings with llama-server's log, used in section 4 and for option 7).
- `data/cache/hybrid/server.log` (24 requests with llama-server's own timings; a different run, used only as a cross-check).
- `models/Qwen3.5-9B-Q4_K_M.silver.log` (labeling run, different prompt; used only as evidence about prompt caching).
- `data/cache/gemini_compare/lists_cache/` and `scalars_report.md` (50 documents).

`baseline.py compare` was run first: 75 of 75 outputs identical, 0 requests missing from the cache. So the recorded answers match the current code.

Prompts were rebuilt by replaying each document. Tokens were counted with `llama-tokenize` (vocabulary only, no inference) on a hand-built chat template (system, user, empty think block). The template was an assumption at first, since the recorded baseline has no token counts. The repeat runs confirmed it: the server's prompt counts match on all 56 calls, and its output counts are 1 or 2 tokens higher per call (13,082 against 13,023 in total). Sections 1 to 3 use the tokenizer counts.

Costs per token come from a least-squares fit of seconds against prompt and output tokens over the 56 calls (R2 0.96):

| | seconds per token | tokens per second |
|---|---|---|
| prompt | 0.0095 | about 105 |
| output | 0.099 | about 10 |

All "estimated seconds" below use these two rates and are divided by 15 documents. They are estimates, not measurements. Speed varies between runs on the same machine: the repeat runs measured 99.2 and 76.1 prompt tokens per second, and 10.1 and 8.7 output tokens per second. The hybrid log shows 67 and 6.7, so seconds saved could be about 1.5 times larger on a slower run. Savings of different options overlap and must not be added up.

## 1. Calls, tokens and share of time

| group | calls | seconds | share | mean s per call | s per document (/15) | prompt tokens (mean) | output tokens (mean) |
|---|---|---|---|---|---|---|---|
| eligibility | 13 | 694.2 | 36.4% | 53.4 | 46.3 | 13,759 (1,058) | 5,915 (455) |
| required_documents | 14 | 503.8 | 26.4% | 36.0 | 33.6 | 21,955 (1,568) | 2,824 (202) |
| deadlines | 14 | 463.6 | 24.3% | 33.1 | 30.9 | 15,658 (1,118) | 3,555 (254) |
| scalars | 15 | 245.0 | 12.9% | 16.3 | 16.3 | 20,996 (1,400) | 729 (49) |
| total | 56 | 1,906.6 | 100% | 34.0 | 127.1 | 72,368 | 13,023 |

Eligibility is output-heavy (about 585 of its seconds are output by the fit). The scalar call is prompt-heavy (about 200 s prompt, 72 s output).

Cross-check from the hybrid log: 301 s prompt and 725 s output (29% and 71%).

No call was truncated, retried or failed.

### Per document

Each cell is seconds / prompt tokens / output tokens.

| doc | type | calls | eligibility | deadlines | required_documents | scalars | total s |
|---|---|---|---|---|---|---|---|
| 136dfba9 | notice | 4 | 30.7 / 1001 / 403 | 12.7 / 789 / 124 | 14.0 / 1080 / 94 | 15.1 / 1034 / 112 | 72.5 |
| 28ad40ea | bid_instructions | 4 | 46.9 / 666 / 494 | 55.9 / 2021 / 342 | 87.9 / 2939 / 573 | 18.2 / 1614 / 45 | 208.9 |
| 4b0b9d82 | notice | 3 | no call | 26.2 / 810 / 225 | 9.2 / 546 / 58 | 16.2 / 1295 / 60 | 51.6 |
| 4c40bbd8 | spec | 1 | no call | no call | no call | 24.7 / 2885 / 35 | 24.7 |
| 563042df | notice | 4 | 29.9 / 637 / 293 | 24.3 / 824 / 229 | 15.8 / 1104 / 82 | 17.1 / 1120 / 85 | 87.1 |
| 58f13b9c | notice | 4 | 36.5 / 1107 / 316 | 25.2 / 931 / 219 | 15.3 / 963 / 84 | 9.5 / 1093 / 27 | 86.5 |
| 594c3cb6 | notice | 4 | 46.6 / 1266 / 404 | 23.6 / 870 / 211 | 17.2 / 1204 / 80 | 10.1 / 1145 / 27 | 97.5 |
| 5d75d4a6 | notice | 4 | 55.9 / 1057 / 456 | 41.9 / 815 / 407 | 13.8 / 1003 / 57 | 14.2 / 1230 / 35 | 125.8 |
| 6b7142ab | notice | 4 | 74.6 / 1206 / 679 | 24.4 / 871 / 212 | 25.0 / 1144 / 146 | 10.3 / 1093 / 27 | 134.3 |
| 84e9d0c8 | notice | 4 | 60.5 / 1096 / 498 | 28.0 / 906 / 229 | 23.0 / 1198 / 120 | 10.1 / 1042 / 27 | 121.6 |
| a13baaac | notice | 4 | 39.0 / 893 / 288 | 14.5 / 1314 / 58 | 73.9 / 1867 / 441 | 33.9 / 1737 / 123 | 161.2 |
| a81e99fe | notice | 4 | 66.7 / 1098 / 500 | 44.3 / 904 / 360 | 27.3 / 1195 / 120 | 10.8 / 1026 / 27 | 149.2 |
| d230e51e | notice | 4 | 80.2 / 1125 / 662 | 48.7 / 982 / 360 | 16.8 / 1038 / 64 | 12.3 / 1126 / 27 | 158.0 |
| d4000027 | bid_instructions | 4 | 80.6 / 1471 / 610 | 69.6 / 2770 / 435 | 148.1 / 5600 / 843 | 27.6 / 2427 / 37 | 325.8 |
| f19cddbd | notice | 4 | 46.2 / 1136 / 312 | 24.1 / 851 / 144 | 16.6 / 1074 / 62 | 15.0 / 1129 / 35 | 102.0 |

The "no call" cells are correct behaviour: no sentence was retrieved (4b0b9d82 eligibility), or the field does not apply to the document type (4c40bbd8, a spec).

### What the output tokens are

| part of the output | tokens | share of 13,023 |
|---|---|---|
| copied Japanese text (`text_ja`, `name_ja`, scalar `value_ja`) | 3,770 | 29% |
| of which eligibility `text_ja` | 2,880 | 22% |
| citation id lists (list fields) | 1,905 | 15% |
| whitespace (output minus the same JSON written compactly) | 2,814 | 22% |
| of which newlines and indentation | 1,313 | 10% |
| repeated items in the list answers | 943 | 7% |

These parts overlap (an item that repeats another also contains text, ids and spaces). The model formats some answers over many lines: 11 of 14 deadline answers and all 15 scalar answers.

## 2. Calls that were settled already, or did not reach the output

### Settled by rules

- List fields: 0 of 41 calls. Rules never answer eligibility, deadlines or required_documents.
- Scalar call: rules answers are already left out of the request field by field (`have` in `sidecar/__main__.py`). 58 field requests were made over 15 calls. `scope_summary`, `delivery_deadline` and `delivery_location` were asked on all 15 documents because rules answered none of them here, so the call was never skipped.
- "Skip when rules hold a value" is therefore already done. Note that `have` counts any rules answer, whether or not it later passes the checks.

### Calls that added nothing to the final output

| calls | seconds | why |
|---|---|---|
| 15 scalar calls | 245.0 | 55 of 58 field requests were answered null. The other 3 failed a check (`schema_valid`, `portal_window_date`, `unknown_id`). |
| deadlines, 136dfba9 | 12.7 | 2 items proposed, both dropped (`date_or_time_not_in_citation`) |
| deadlines, 58f13b9c | 25.2 | 3 items proposed, all dropped (same reason) |
| 17 calls | 283.0 | 14.9% of model time, 18.9 s per document |

None of this is knowable before the call from what the code holds today. Every deadline call had at least one date in its retrieved sentences, and a deadline may also be a `relative_text`, so no list call can be proved useless in advance.

D-95 records an earlier dev run where the fallback moved one row to right (136dfba9 `performance_period`). In the recorded baseline that document's non-null answer was dropped by `schema_valid`, and nothing was kept.

Dropped items inside calls that did produce output: eligibility 11 duplicates and 1 value not in its citation (10 more items were merged, not lost); deadlines 10 failed the date or time check (5 of those are in the two empty calls), 2 duplicates and 2 same-sentence copies; required_documents 1 unknown id.

### The 50-document cache

`lists_cache/` (run of 2026-11-21, one run, not scored against labels for scalars, 15 of the 50 are in the dev list and 0 in test):

| document type | documents | total seconds | scalar seconds | documents with a kept scalar answer | answers kept |
|---|---|---|---|---|---|
| notice | 16 | 2,082 | 406 | 3 | 11 |
| bid_instructions | 17 | 3,363 | 527 | 0 | 0 |
| spec | 17 | 455 | 443 | 3 | 8 |
| all | 50 | 5,900 | 1,376 (23.3%) | 6 | 19 |

Here "seconds" includes reading the PDF. Scalar seconds are total minus the time up to the end of the list calls.

`scalars_report.md` (prompt variant B2, the shipped wording per D-95) compares rules alone with rules plus fallback against Gemini on 50 documents. Agreeing answers: title 28 to 33, issuer_org 10 to 13, contracting_officer 0 to 3, scope_summary 0 to 5, delivery_location 0 to 1 (plus 1 differing), performance_period 21 to 21 (differing 1 to 2), delivery_deadline 3 to 3, notice_date 11 to 11. It also passed 19 answers. Gemini is silver, not ground truth (D-96). The cache stores only a count per document, so which fields were kept in `lists_cache/` is not known.

## 3. Shared prefix and prompt caching

### Is caching used today?

Yes. `llm.Client.complete` sends `"cache_prompt": True` (`core/shiori_core/extract/llm.py:211`). The app starts llama-server with `-c 16384 -np 1` and no other cache flag (`app/electron/llama.ts:50`). One slot means each request can only reuse what that slot or a saved checkpoint still holds.

### How much is shared inside one document

| from, to | identical leading tokens |
|---|---|
| list call to list call | 75 (system prompt and template; they differ from the field name on) |
| list call to scalar call | 23 (the system prompts differ) |
| sum over the 56 calls | 2,347 of 72,368 prompt tokens (3.2%) |

The 3.2% counts only text shared with an earlier call of the same document. It is not what the server reused (next part).

### What the server reused

In both repeat runs the server reused **8,663 of 72,368 prompt tokens (12.0%)**, the same number on every call in both runs. That is 578 tokens per document. At least 6,580 of the 8,663 are more than any earlier call of the same document shares, so they came from earlier documents.

Across documents, calls for the same field start with the same system prompt, field rules and example, sometimes followed by identical sentence tokens.

| group | calls | longest start shared with an earlier same-field call, tokens per call | sum | reused by the server | shared but not reused |
|---|---|---|---|---|---|
| eligibility | 13 | 0 (first call), then 382 to 672 | 4,911 | 1,547 | 3,364 |
| deadlines | 14 | 0 (first call), then 564 to 593 | 7,412 | 4,386 | 3,096 |
| required_documents | 14 | 0 (first call), then 299 to 336 | 3,975 | 980 | 3,065 |
| scalars | 15 | 0 to 442 | 4,746 | 1,750 | 2,996 |
| total | 56 | | 21,044 | 8,663 | 12,521 |

The last column is summed call by call and never below zero, so it can differ a little from sum minus reused.

The hybrid log, from a different run, shows 0 to 437 tokens per request, 4,610 of 24,807 (19%).

The qualifier from `eval/silver/pipeline.py:173` matters: Qwen3.5 is a hybrid model, so llama-server restores a cached prompt only from a saved checkpoint (about 512 tokens before the end of a prompt, per that comment). Reuse does not reach the full length of the common prefix.

### Repeated sentences that are not cached

The four calls send 1,885 sentence lines, of which 1,313 are distinct (30% repeats). In tokens: 48,914 sent, 32,290 distinct. They cannot be reused today because they come after the field-specific rules.

A document-first prompt can reuse a lot with this model: in the labeling log, 58 of 59 requests reused more than 500 tokens, 243,925 of 306,694 prompt tokens (80%). That run shared a whole document between calls. Extraction shares only retrieved windows.

### Where prompt tokens go

| part | tokens | share |
|---|---|---|
| sentence lines | 48,914 | 68% |
| of which the `[id] ` markers | 11,731 | 16% |
| field rules, examples, labels | about 15,600 | 22% |
| system prompt and template | about 7,800 | 11% |

The last row is what remains of 72,368 after sentence lines and field text.

## 4. Repeat runs

The unchanged `baseline.py record` was run twice into `data/cache/audit_repeat/`, with llama-server's log kept. Mac on AC power, Low Power Mode off, same server command as the app.

### Did anything but time change?

| comparison | model answers | `full/` files | `rules/` files |
|---|---|---|---|
| run1 vs run2 | 56 of 56 identical | 15 of 15 byte-identical | 60 of 60 byte-identical |
| old baseline vs run1 | 56 of 56 identical | 15 of 15 | 60 of 60 |
| old baseline vs run2 | 56 of 56 identical | 15 of 15 | 60 of 60 |

No answer was truncated and no request was missing. Calls (56), prompt tokens, reused tokens and output tokens were the same in both runs.

### Server timings

| run | group | calls | prompt tokens (reused) | prompt s | tokens/s | output tokens | output s | tokens/s | total s |
|---|---|---|---|---|---|---|---|---|---|
| 1 | eligibility | 13 | 13,759 (1,547) | 127.9 | 95.5 | 5,928 | 589.7 | 10.1 | 717.5 |
| 1 | required_documents | 14 | 21,955 (980) | 215.1 | 97.5 | 2,838 | 285.9 | 9.9 | 501.0 |
| 1 | deadlines | 14 | 15,658 (4,386) | 111.4 | 101.2 | 3,569 | 354.9 | 10.1 | 466.3 |
| 1 | scalars | 15 | 20,996 (1,750) | 188.0 | 102.4 | 747 | 65.6 | 11.4 | 253.6 |
| 1 | all | 56 | 72,368 (8,663) | 642.4 | 99.2 | 13,082 | 1,296.1 | 10.1 | 1,938.6 |
| 2 | eligibility | 13 | 13,759 (1,547) | 160.8 | 76.0 | 5,928 | 675.2 | 8.8 | 836.0 |
| 2 | required_documents | 14 | 21,955 (980) | 262.8 | 79.8 | 2,838 | 322.9 | 8.8 | 585.7 |
| 2 | deadlines | 14 | 15,658 (4,386) | 149.9 | 75.2 | 3,569 | 412.6 | 8.7 | 562.5 |
| 2 | scalars | 15 | 20,996 (1,750) | 263.3 | 73.1 | 747 | 87.6 | 8.5 | 350.9 |
| 2 | all | 56 | 72,368 (8,663) | 836.7 | 76.1 | 13,082 | 1,498.3 | 8.7 | 2,335.1 |

| measure | run1 | run2 | old baseline |
|---|---|---|---|
| total model seconds | 1,938.6 (server) | 2,335.1 (server) | 1,906.6 (client wall) |
| mean per document, s | 129.2 | 155.7 | 127.1 |
| median per document, s | 134.0 | 149.5 | 121.6 |
| prompt / output share of server time | 33% / 67% | 36% / 64% | not recorded |
| model load, s | 3.63 | 1.92 | not recorded |
| time outside the server, 15 documents, s | 8.8 | 8.6 | not recorded |

### How far identical runs differ

| slice | slower over faster |
|---|---|
| all 56 calls | 1.20 |
| one field group | 1.17 to 1.38 |
| one document | 1.04 to 2.12 |
| one call | up to 2.34 (37 of 56 calls differ by more than 20%) |

The cause was not found. No sleep event or thermal warning was seen. The load average was 53 when run1 ended, a browser played a video during run2, and about 3.5 GB of swap was in use afterwards. The first calls of run1 reached about 170 prompt and 16 output tokens per second, which may be the idle speed; no quiet-machine run was made.

## 5. Options, ranked

Classes:

- **A, cannot change output** by construction.
- **B, should not change output**: same prompt and sampling, different computation. Temperature 0 does not guarantee identical floating point results, so it must be shown.
- **C, might change output**: prompt, schema, grammar, retrieval or which calls run.

The ranking weighs saving, risk and the evidence behind it.

The calls and tokens column is what to judge a saving by. Seconds are estimates from the fit, and two identical runs differ by up to 20% in total. Tokens are prompt or output tokens per document, from the 15 dev documents. Prompt counts include tokens the server already reuses, unless marked.

| rank | option | class | saved per document: calls and tokens | estimated seconds per document | risk to output |
|---|---|---|---|---|---|
| 1 | Reuse the stored result when the same file is opened again | A | repeat only: 3.7 calls, 4,825 prompt (4,247 not reused today), 868 output | 127 s on a repeat, 0 on a first run | none if keyed correctly |
| 2 | Draft output from text already in the prompt (llama.cpp ngram speculative decoding) | C (was B; section 6) | no calls or tokens; speed per token only | measured on 15 documents: 7.4% less time, smaller than the 17.7% between two unflagged runs | changed 2 of 56 answers; one field of one document became not found |
| 3 | Compact JSON, no whitespace | C | up to 188 output (newlines and indentation only: 88) | up to 19 s (9 s) | low to medium |
| 4 | Short sentence ids (`[46]` for `[p1_s9]`) | C | 144 prompt, 43 output | about 5.6 s | medium |
| 5 | Stop repeated items | C | up to 63 output | up to 6 s | medium |
| 6 | Skip the scalar call for bid_instructions | C | 0.13 calls, 269 prompt, 5 output on dev; 0.34 calls on the 50-document set (no token counts there) | 3 s on dev (2 of 15 documents), 10.5 s averaged over the 50-document set, about 31 s on each such document | low on the evidence held (0 of 17 kept), unproven |
| 7 | Better reuse of each field's fixed start (one slot per field, or cache flags) | B | 0 to 835 prompt tokens that are not reused today, no calls | 0 to about 8 s, from the second document on | numeric drift; memory |
| 8 | Eligibility returns ids only, code copies the text | C | up to 192 output | up to 19 s | high |
| 9 | Document sentences first, shared by all calls | C | 0 to 1,108 prompt; today's reuse (578) could be partly lost | 0 to 11 s | high |
| 10 | Remove the whole scalar fallback | C | 1 call, 1,400 prompt (1,283 not reused), 49 output | 16 s on dev, 27.5 s on the 50 documents | loses answers, shown |
| 11 | Skip the scalar call when only the three never-found fields are asked | C | 0.4 calls, 435 prompt (335 not reused), 11 output | about 4 s on dev | loses answers |
| 12 | Shorter rules and examples | C | about 520 prompt if halved, part of it reused today | about 5 s if halved | medium to high |
| 13 | Smaller retrieval window or budget | C | about 150 to 310 prompt (worked back from the seconds) | 1.4 to 2.9 s | medium to high |
| 14 | One merged call for the three list fields | C | 1.7 calls, about 840 prompt (worked back from the seconds) | about 8 s | very high, not recommended |
| 15 | Server flags (threads, batch sizes, flash attention) | B | no calls or tokens; speed per token only | unknown | numeric drift |

### Notes on each

1. **Stored results.** Within one app session the sidecar already returns the existing job for the same bytes (`Worker.submit`). Across restarts everything is recomputed because the Library is in memory only (already on the roadmap). The key must cover the file hash, model hash, extractor version, prompts, schema and server version. A stored result holds document text, so it needs a privacy decision first.

2. **Speculative drafting.** A simple count on the recorded tokens: 8,418 of 13,023 output tokens (65%) equal the token that followed the latest earlier occurrence of the same 2 tokens in the prompt or output (66% with 3). The ceiling assumes drafted tokens cost nothing, which is false. The bundled binary contains `--spec-type` and `--spec-ngram-*` options; whether they work well, or at all, with this hybrid model (which may need checkpoint rollback after a rejected draft) was not tested. This is not llama.cpp's own matching algorithm. Tested afterwards, see section 6.

3. **Compact JSON.** 2,814 tokens. The request uses `response_format` with a JSON schema, which lets the model add whitespace. Forcing compact output needs a different grammar. The tokens that follow are then chosen from a different history, so content can differ. Prompt example answers are already written without newlines.

4. **Short ids.** Measured by renumbering: markers 11,731 to 9,578 tokens, output 13,023 to 12,385. Needs a map back to real ids; the citation check stays the same.

5. **Repeated items.** 16 repeats (11 eligibility, 5 deadlines), 943 tokens. The code already drops them, but the model has already spent the time. Only a prompt or grammar change stops it.

6. **bid_instructions scalar skip.** These are the slowest documents (about 167 s of list calls each in the 50-document run). Evidence is one run of 17 documents plus 2 dev documents with nothing kept. One kept answer on a new document would be lost.

7. **Fixed start reuse.** Corrected after the repeat runs. The first version counted 75 shared tokens per document (3.2%) and put the upper bound at about 1,000 more. The server already reuses 8,663 tokens (12.0%, 578 per document), much of it across documents. What is left, if every call reused its whole shared start with an earlier same-field call, is 12,521 tokens, 835 per document (635 without the scalar call): about 8 s at the fitted rate, 8 to 11 s at the two measured prompt rates. The real saving is likely lower, because this model restores only from checkpoints. Reuse by field today is uneven: deadlines gets 4,386 of 7,412, required_documents 980 of 3,975. With `-np 4` the context splits to 4,096 tokens per slot, but the largest prompt here is 5,600, so `-c` would have to grow. Memory use on a 16 GB machine is unmeasured. Flags such as `--cache-ram` and `--ctx-checkpoints` exist in the binary and may do the same with one slot. Judge it by the server's reused token count, which repeated exactly between runs.

8. **Eligibility ids only.** 2,880 tokens. `text_ja` is often only part of its sentences (no leading number, one clause), so copying whole sentences changes values. required_documents cannot use this: `name_ja` is a name inside a sentence.

9. **Document first.** Ideal case saves the 16,624 repeated sentence tokens. Checkpoint placement can use that up (three later calls times about 512 tokens is about the same size), hence 0. Each call would also read sentences it does not see today.

10. **Remove the fallback.** Largest single call to remove, and the only option here with direct evidence that it loses answers (50-document table above).

11. **Three-field skip.** 6 dev calls, 63 s. `scope_summary` had 5 agreeing answers on the 50 documents, so this is not free.

12. **Fixed text.** All field rules and examples are about 15,600 tokens, about 10 s per document in total. Some of this wording was added to fix specific errors (for example the required_documents line, Phase 5 fix 2).

13. **Retrieval.** Checked without a model: how many sentences cited in the baseline output would still be sent. This is a necessary condition only, not proof of the same answer.

| setting | cited sentences no longer sent (eligibility of 86, deadlines of 57, required_documents of 117) | saving per document |
|---|---|---|
| budget 4,000 characters (now 7,000) | 0, 0, 0 | 1.4 s |
| budget 3,000 | 0, 0, 2 | 1.9 s |
| window 2 (now 3) | 5, 1, 6 | 2.9 s |
| window 1 | 12, 4, 10 | not recommended |

    D-69 widened retrieval because items were being missed, and the 7,000 budget may matter on longer documents than these.

14. **Merged list call.** Saves repeated sentences, not output. D-69 cites D-67: grouped local calls (a different prompt covering many fields) got at most 1 of 12 list fields right.

15. **Server flags.** Nothing in the cache compares them.

Not a time saving: the document is only marked done after the scalar call. Showing it as ready after the list calls would bring "done" forward by about 16 s with the same values. It changes app behaviour, not model time.

## 6. Speculative decoding test

Run on 2026-11-27 and 28 with the bundled llama-server b12651 and the same model, on the Mac. All work is in `data/cache/spec_ngram/` (a copy of the baseline folder, gitignored). The only change between old and new is the server flags. New means:

    --spec-type ngram-map-k --spec-ngram-map-k-size-n 3 --spec-ngram-map-k-size-m 8

The server starts with them, serves requests and logs a draft acceptance rate. No new draft model is needed.

### One call

The slowest list call (d4000027 `required_documents`, 5,600 prompt tokens, 844 output tokens), a fresh server for each run. Every one of the 14 runs, all configs, returned the recorded answer.

Screening, one run each. The AC rows and the battery rows cannot be compared.

| flags | output tokens/s | power |
|---|---|---|
| none | 15.83 | AC |
| `ngram-simple`, defaults | 14.19 | AC |
| `ngram-simple`, sizes 3 and 8 | 19.14 | AC |
| `ngram-map-k`, sizes 3 and 8 | 20.09 | AC |
| `ngram-map-k4v`, sizes 3 and 8 | 10.68 | battery, Low Power Mode |
| `ngram-mod`, defaults | 5.93 | battery, Low Power Mode |
| `ngram-mod`, match 3, min 2, max 8 | 10.61 | battery, Low Power Mode |
| `ngram-cache`, defaults | 12.28 | battery, Low Power Mode |

`ngram-map-k` was chosen from this one call. Then old and new alternated three times on battery in Low Power Mode:

| | old | new |
|---|---|---|
| output tokens/s | 6.02, 6.12, 6.17 | 12.12, 12.08, 12.08 |
| output s | 140.2, 137.9, 136.9 | 69.7, 69.9, 69.9 |
| whole call s | 222.9, 218.0, 217.0 | 149.3, 150.1, 149.8 |

The whole call took 31 to 33% less time. This was not alternated on AC.

### 15 documents

Order: old1, new2, old2, new3, all on AC with Low Power Mode off (power sampled every 30 s). A further flagged run, new1, ran first, partly on battery: its answers count, its seconds do not.

| run | calls | prompt tokens | output tokens | prompt s | output s | total s | answers differing from baseline |
|---|---|---|---|---|---|---|---|
| old1 | 56 | 72,368 | 13,082 | 525.0 | 1,054.8 | 1,579.8 | 0 |
| new2 | 56 | 72,369 | 14,465 | 590.3 | 972.7 | 1,563.0 | 2 |
| old2 | 56 | 72,368 | 13,082 | 608.2 | 1,250.7 | 1,858.9 | 0 |
| new3 | 56 | 72,369 | 14,465 | 615.0 | 1,005.7 | 1,620.8 | 2 |

The one extra prompt token comes from how the count is derived from the log when an answer is cut off. Each flagged run drafted 8,111 tokens and accepted 5,913.

Mean of the two runs by field group:

| group | calls | prompt tokens old / new | output tokens old / new | seconds old / new |
|---|---|---|---|---|
| eligibility | 13 | 13,759 / 13,760 | 5,928 / 7,311 | 635.4 / 556.8 |
| required_documents | 14 | 21,955 / 21,955 | 2,838 / 2,838 | 436.3 / 424.1 |
| deadlines | 14 | 15,658 / 15,658 | 3,569 / 3,569 | 417.4 / 364.3 |
| scalars | 15 | 20,996 / 20,996 | 747 / 747 | 230.3 / 246.8 |
| all | 56 | 72,368 / 72,369 | 13,082 / 14,465 | 1,719.4 / 1,591.9 |

### Answers

new1, new2 and new3 differ on the same two eligibility requests. old1 and old2 match the baseline on all 56. Each other flagged answer matches the baseline.

| document, request | change | in the 3 flagged runs | final output |
|---|---|---|---|
| d230e51e, `5b28002d` | answer went from 663 output tokens to the 2,048 cap and was cut off | cut off in all 3 | eligibility goes from 5 items to not found; 5 cited sentences drop out; translation requests 36 to 31 |
| f19cddbd, `f42888b1` | item 5 of 5 has a different `kind` and `text_ja` | the same new answer in all 3 | unchanged |

The other 14 `full/` files and all 60 `rules/` files are byte-identical to the baseline. Why the answers change was not found.

### Speed

| measure | old1, old2 | new2, new3 |
|---|---|---|
| total s | 1,579.8, 1,858.9 (17.7% apart) | 1,563.0, 1,620.8 (3.7% apart) |
| total s without the two differing calls | 1,481.8, 1,747.6 | 1,446.7, 1,502.8 |
| output tokens/s without the two differing calls | 12.44, 10.45 | 13.84, 13.35 |
| prompt tokens/s | 121.34, 104.74 | 107.91, 103.58 |

On the mean, new took 7.4% less total time (8.7% without the differing calls). That is smaller than the gap between the two unflagged runs, and new3 was 2.6% slower in total than old1. Output without the differing calls was faster in both new runs than in both old runs, by 7 to 32% between pairs. A whole-run saving is not shown.

### Result

By the rule in the next section, a difference moves the option to class C. It is not adopted (D-122). Not done: the other six configs on 15 documents, eval scoring, another machine, Windows.

Scripts: `smoke.py` (one call), `run.py` (full recordings), `compare.py` (answer diff and totals), `diffs.py` (structure of each difference), `table.py` (per group totals and spread).

## How to prove an option did not change output

**Important limit of the baseline compare.** The replay key hashes only system text, user text, schema and max tokens. It does not cover llama-server flags, other request body fields (`cache_prompt` and the like) or a `grammar` field added inside the client. For options 2, 7 and 15, `compare` would pass without testing anything.

Judge a saving first by calls, prompt tokens, reused tokens and output tokens from the server log: these were identical between two unchanged runs. Seconds differed by up to 20% in total, so a timing claim needs old and new runs alternated several times on a quiet machine. Options 2 and 15 change no counts, so seconds are their only measure.

| class | proof |
|---|---|
| A | `baseline.py compare` (75 of 75). Plus a test that a stored result equals a fresh one and that any key part changing forces a new run. |
| B | Two unchanged recordings were identical (section 4), so on this Mac and server build a difference points to the change. Record into a copy of the baseline folder at the same depth (`record` refuses to overwrite, and the server command is hard-coded in `start_llama`, so flags go into the copy). Diff `full/*.json` and the `answer` strings, ignoring `seconds`. Any difference moves the option to class C. |
| C | New recording and diff, read every difference. Then `SHIORI_SCALARS=1 uv run python -m eval.run --split dev --extractor hybrid` with no row moving from right to wrong. Then evidence outside the 15 dev documents (D-96), at least the 50-document Gemini comparisons. |

Two traps:

- `eval.gemini_list_compare` resumes from `lists_cache/`, keyed by document only. Move that cache aside (do not delete it) or old answers will be reused.
- `eval.hybrid` starts the `llama-server` on the PATH, while the baseline used the bundled b12651. Compare like with like.

Never use the test split for any of this.

## Measurements that need a new model call (not run)

1. Speed on a quiet machine, and why identical runs differ.
2. Whether answers stay identical on another machine or server build.
3. Speculative decoding: done for `ngram-map-k` on this Mac (section 6). Still open: the other configs on 15 documents, and the cause of the changed answers.
4. Cache hits and speed with one slot per field or the cache flags; peak memory with a larger `-c` or `-np`.
5. Compact JSON grammar: speed and answer differences.
6. Document-first prompt: real reuse on this model with retrieved windows.
7. Which scalar fields the shipped fallback keeps on documents outside dev (the cache stores counts only).
8. Translation time. The 15 documents queue 466 translation requests (5 to 53 each) after extraction. The baseline stubs them, so their model time is unknown and not in any number above. It may be a large part of what the user waits for.
9. Windows 16 GB, CPU only. Every number here is from a Mac; the split between prompt and output may differ a lot.
10. Time to first answer and model load time in the app (model load took 3.63 s and 1.92 s in the repeat runs and about 6 s in the hybrid log, once per session; time to first answer in the app is not measured).
