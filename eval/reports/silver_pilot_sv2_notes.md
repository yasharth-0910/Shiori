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
