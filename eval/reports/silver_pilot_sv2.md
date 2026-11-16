# Silver pilot, prompt sv2: comparison with the reviewed sv1 labels

Date: 2026-10-03 (UTC). Five open dev documents, `run --pilot --yes --max-calls 40`, then a local shadow run and one diagnostic Gemini request. Everything below the notes is rebuilt by `uv run python -m eval.silver report --pilot --notes eval/reports/silver_pilot_sv2_notes.md` (no API calls).

## What happened

- **Gemini's strict schema mode refused sv2 on 4 of 5 documents.** `responseJsonSchema` returned HTTP 400 INVALID_ARGUMENT for the 23-field schema (the three notices) and the 21-field one (bid instructions), and accepted the 6-field one (spec). One extra request with the 23-field schema and no document text got the same 400 with the message "Request contains an invalid argument", so the schema is the trigger. The keywords are the same as in the schema that worked; only the size differs (39 `anyOf` and depth 14, against 6 and 11). Google's docs warn that large schemas may be rejected; the message does not say which limit. No other schema variant was tried today.
- **Groq's strict mode accepted every grouping** (6 to 12 fields per request), but 4 of 19 parts came back `json_validate_failed`: the model's answer did not match the schema. The pipeline treats that as a final failure for the part, so two documents (563042df9941, 28ad40ea4b1f) have no complete Groq answer.
- **Result:** 1 of 5 documents resolved (4c40bbd831fe, spec: 5 accepted, 1 flagged). The 3 reviewed documents have no Gemini answer, so comparison mode has nothing to report.
- **No 503s today.** The new pause (a provider that uses up its backoff sits out the rest of the run) was not triggered.
- **Local shadow, Qwen3.5-9B:** on 28ad40ea4b1f (21 fields) both tries stopped at exactly 4,056 output tokens, the output cap for a 21-field request (`est_output` x 1.3), so the JSON was cut off. At temperature 0 the retry produced the same answer. On 4c40bbd831fe (6 fields) it answered in 194 s and agreed with Gemini on 4 of 6 fields and with Groq on 4 of 6 (Gemini and Groq: 5 of 6); no blocking-check or schema failures on either side. The two differences: issuer_org `和歌山県教育庁` (Gemini `和歌山県`, Groq absent; whether 教育庁 is an org is now an open question in `decisions.md`) and delivery_deadline `令和９年３月３１日` (p1_s16, p4_s16) where both cloud labelers said absent. Two documents, one of them failed: no conclusion about Qwen as a labeler.

## Proposals (not implemented)

**Gemini fix A: JSON mode without a strict schema.** Send `responseMimeType: application/json` without `responseJsonSchema`, describe the answer shape in the prompt (the field list and each `normalized` form are already there), and rely on our own checks (`schema_valid` and the rest), with one repair retry that sends back the answer and the failed checks. One request per document; two when the repair is needed. Risk: Gemini without a schema may leave keys out or use other shapes more often; our checks catch that, but each repair costs one of the 20 daily requests.

**Gemini fix B: field groups**, as Groq already has. The 6-field schema is accepted; anything between 7 and 20 fields is untested. Groups of at most 6 mean 4 requests per notice; at most 12, 2 per notice, if Google accepts that size.

**Groq: retry a `json_validate_failed` part once with its field group split in half.** Two smaller requests with the same document text. Smaller schemas probably fail less, but that is a guess: 4 failures are too few to tell whether size matters (the failed groups had 7 or 8 fields, the successful ones 6 to 12).

Dev-set quota days for each (the table in "Projection" below; token numbers scaled by the real / estimate ratios measured here):

| plan | Gemini days | Groq days | total days |
| --- | --- | --- | --- |
| Gemini fix A, no repairs, + Groq | 2 | 10 | 10 |
| Gemini fix A, a repair on every document, + Groq | 4 | 10 | 10 |
| Gemini fix B, groups of at most 12, + Groq | 4 | 10 | 10 |
| Gemini fix B, groups of at most 6, + Groq | 7 | 10 | 10 |
| any of the above, + Groq split retry at today's 21% failure rate | same | 14 | 14 |
| Gemini fix A + local model on open documents (Groq + local on restricted) | 2 to 4 | 5 | 5 |
| Gemini fix B (at most 6) + local model on open documents | 7 | 5 | 7 |

With Groq as the second voice, Groq's 200,000 tokens/day is the limit whatever Gemini does. With the local model as the second voice on open documents, Groq only labels the 23 restricted documents, and Gemini's requests decide. The local model then labels all 60 dev documents; at today's mean of 752 s per document that is about 12.5 hours on this Mac, but the mean mixes one 6-field answer (194 s) with one 21-field failure (two tries, 1,311 s). A notice-sized answer needs a larger output cap than 4,056 tokens first, and takes 10 minutes or more per try at 6 to 8 tokens/s.

## Decision needed

Which Gemini fix (A or B), whether to add the Groq split retry, and whether the second voice on open documents stays Groq or becomes the local model. Each changes the prompt, schema or chunking, so it gets a new PROMPT_VERSION (sv3).

Comparison mode: these documents already had labels, so nothing was written except this report (and the raw answer cache and usage ledger). Pseudo-gold = the existing labels: sv1 consensus lines plus the reviewer's answers (`claude_chat`, not human-verified). **These documents were used to build sv2, so their numbers are optimistic.** The documents labeled for real in the same run are the held-out check (below, without gold).

Blocking checks: schema_valid, citations_exist, value_in_citation, values_roundtrip, field_applicable, era_plausible, weekday_consistent.

## Reviewed documents (optimistic)

| document | fields asked | flagged sv1 | flagged sv2 | review items sv1 | review items sv2 | sv1 flags settled correctly | settled wrongly | settled, no gold | still flagged |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Fresh documents (held out, labeled for real)

- 4c40bbd831fe (spec): 1 of 6 asked fields flagged (17%); schema failures gemini 0, groq 0

## Documents without two complete answers

- f19cddbd4cba (notice): gemini failed, groq complete
- 563042df9941 (notice): gemini failed, groq failed
- 4b0b9d8229c7 (notice): gemini failed, groq complete
- 28ad40ea4b1f (bid_instructions): gemini failed, groq failed

## Providers

| labeler | schema accepted (fields per request) | schema rejected (fields) | output failed the schema (fields) | requests (ledger) | failures by outcome | 503s | tokens in / out per call, real | estimated | real / estimate | tokens per document, real |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemini | yes (6) | 21, 23 | - | 5 on 2026-10-03 | http_400 4 | 0 | 5,059 / 848 (n=1) | 6,997 / 1,320 | 0.72 / 0.64 | 5,907 (n=1) |
| groq | yes (6, 7, 8, 11, 12) | - | 4 of 19 requests (7, 7, 7, 8) | 23 on 2026-10-03 | http_400 4, http_429 4 | 0 | 5,089 / 1,127 (n=15) | 4,784 / 1,512 | 1.06 / 0.75 | 16,137 (n=3) |
| Qwen3.5-9B-Q4_K_M | yes (6) | - | - | local, no ledger quota | - | - | 4,954 / 921 (n=1) | 6,997 / 1,320 | 0.71 / 0.70 | 5,875 (n=1) |

Requests count every try of a labeling call on the run's day (kind `label`, failures included). Tokens per call are means over the requests that returned an answer; estimates are the plan's numbers for the same requests (`Part.est_in`, `est_output`). Gemini's output includes thinking tokens.

## Flag rate on the fresh documents

sv2, fresh documents resolved: 1 flagged of 6 asked fields (17%), 1 review items (flagged + spot-check). sv1 pilot: 36 of 69 (52%), 37 review items, on 3 notices (different documents and types, so a rough comparison).

## Local shadow (report only: no label, no flag)

| document | pair (A vs B) | fields asked | agree | agreement | would be flagged | blocking-check failures A / B | schema failures A / B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 28ad40ea4b1f | gemini vs groq | - | - | - | - | - | no complete answer from gemini (failed: bad_request: HTTP 400 INVALID_ARGUMENT), groq (failed: bad_request: HTTP 400 json_validate_failed) |
| 28ad40ea4b1f | gemini vs Qwen3.5-9B-Q4_K_M | - | - | - | - | - | no complete answer from gemini (failed: bad_request: HTTP 400 INVALID_ARGUMENT), Qwen3.5-9B-Q4_K_M (failed: invalid JSON) |
| 28ad40ea4b1f | groq vs Qwen3.5-9B-Q4_K_M | - | - | - | - | - | no complete answer from groq (failed: bad_request: HTTP 400 json_validate_failed), Qwen3.5-9B-Q4_K_M (failed: invalid JSON) |
| 4c40bbd831fe | gemini vs groq | 6 | 5 | 83% | 1 | 0 / 0 | 0 / 0 |
| 4c40bbd831fe | gemini vs Qwen3.5-9B-Q4_K_M | 6 | 4 | 67% | 2 | 0 / 0 | 0 / 0 |
| 4c40bbd831fe | groq vs Qwen3.5-9B-Q4_K_M | 6 | 4 | 67% | 2 | 0 / 0 | 0 / 0 |

Time per document:
- 28ad40ea4b1f gemini: 1 part(s), time not recorded (run before timing was added)
- 28ad40ea4b1f groq: 8 part(s), time not recorded (run before timing was added)
- 28ad40ea4b1f Qwen3.5-9B-Q4_K_M: 1 part(s), 1311 s (waits and retries included)
- 4c40bbd831fe gemini: 1 part(s), time not recorded (run before timing was added)
- 4c40bbd831fe groq: 3 part(s), time not recorded (run before timing was added)
- 4c40bbd831fe Qwen3.5-9B-Q4_K_M: 1 part(s), 194 s (waits and retries included)

## Projection for the full dev set

Dev set: 60 documents, 37 open, 23 restricted. Restricted documents never go to Gemini (D-44): their first slot is the local model, so every plan below needs a second voice for them.

| plan | Gemini requests | Gemini days (20/day) | Groq requests | Groq tokens (real-scaled) | Groq days | local model documents | local hours | days |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemini + Groq; Gemini as built: strict schema, 1 request per document (rejected on notices and bid instructions) | 36 | 2 | 294 (+ split retry: 418) | 1,919,806 (+ retry: 2,728,145) | 10 (+ retry: 14) | 23 | 4.8 | 10 (+ retry: 14) |
| Gemini + local on open documents (Groq + local on restricted); Gemini as built: strict schema, 1 request per document (rejected on notices and bid instructions) | 36 | 2 | 127 | 828,565 | 5 | 60 | 12.5 | 5 |
| Gemini + Groq; Gemini fix A: JSON mode, schema in the prompt, no repair needed | 36 | 2 | 294 (+ split retry: 418) | 1,919,806 (+ retry: 2,728,145) | 10 (+ retry: 14) | 23 | 4.8 | 10 (+ retry: 14) |
| Gemini + local on open documents (Groq + local on restricted); Gemini fix A: JSON mode, schema in the prompt, no repair needed | 36 | 2 | 127 | 828,565 | 5 | 60 | 12.5 | 5 |
| Gemini + Groq; Gemini fix A: JSON mode, every document needs its one repair retry | 72 | 4 | 294 (+ split retry: 418) | 1,919,806 (+ retry: 2,728,145) | 10 (+ retry: 14) | 23 | 4.8 | 10 (+ retry: 14) |
| Gemini + local on open documents (Groq + local on restricted); Gemini fix A: JSON mode, every document needs its one repair retry | 72 | 4 | 127 | 828,565 | 5 | 60 | 12.5 | 5 |
| Gemini + Groq; Gemini fix B: field groups of at most 12 (size not tested) | 68 | 4 | 294 (+ split retry: 418) | 1,919,806 (+ retry: 2,728,145) | 10 (+ retry: 14) | 23 | 4.8 | 10 (+ retry: 14) |
| Gemini + local on open documents (Groq + local on restricted); Gemini fix B: field groups of at most 12 (size not tested) | 68 | 4 | 127 | 828,565 | 5 | 60 | 12.5 | 5 |
| Gemini + Groq; Gemini fix B: field groups of at most 6 (the size Gemini accepted) | 132 | 7 | 294 (+ split retry: 418) | 1,919,806 (+ retry: 2,728,145) | 10 (+ retry: 14) | 23 | 4.8 | 10 (+ retry: 14) |
| Gemini + local on open documents (Groq + local on restricted); Gemini fix B: field groups of at most 6 (the size Gemini accepted) | 132 | 7 | 127 | 828,565 | 5 | 60 | 12.5 | 7 |

Days = the slower provider; providers run in parallel and each is capped per day. Groq days come from its 200,000 tokens/day cap with the estimate scaled by the measured ratio; Gemini days from its 20 requests/day (no token cap). Failed requests (503s, 400s) also count against Gemini's 20 and are not in these numbers. "+ retry" adds Groq's proposed split retry at the pilot's json_validate_failed rate (21% of parts). Local hours = documents x the shadow's mean time per document on this Mac.
