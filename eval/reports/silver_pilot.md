# Silver labeling pilot (prompt sv1, extractor 0.3.0)

Date: 2026-10-02 (UTC). Five open dev documents. Prompt, schema and thresholds were not tuned.
The only code change was in the plan printer (it crashed on a provider with no tokens/day cap).

## Status

| document | type | state |
| --- | --- | --- |
| f19cddbd4cba | notice | both providers, resolved |
| 563042df9941 | notice | both providers, resolved |
| 4b0b9d8229c7 | notice | both providers, resolved |
| 28ad40ea4b1f | bid_instructions | **not labeled**: Gemini 503 on every try, then the 20 requests/day cap |
| 4c40bbd831fe | spec | **not labeled**: same |

Everything below is about the 3 resolved documents (69 field decisions). The 2 missing documents have
no results from either provider (Groq is only called after Gemini answers). Re-run tomorrow:
`uv run python -m eval.silver run --pilot --yes --max-calls 20 --retry-failed` (the plan prints 2 Gemini calls plus the Groq calls for the 2 documents).

With 3 documents, every rate here is a rough indication, not a measurement.

## 503 count, reconciled (added 2026-10-03)

The ledger (`data/cache/labeling/usage.jsonl`) has 20 Gemini requests on 2026-10-02 (UTC): 3 ok and 17 failed.
sv1's ledger recorded only ok or not ok, so the split comes from the times and the code path:

| run (UTC) | failed | ok |
| --- | --- | --- |
| 16:06-16:07 | 3 (503) | 1 |
| 16:09-16:12 | 10 (503) | 1 |
| 16:16-16:19 | 3 (503) + 1 (429 daily quota, 16:19:18) | 1 |

The last failure is a 429: the ledger's `daily_block` line has the same second, and sv1 wrote that line only when a 429
said the daily quota was spent. So: **16 HTTP 503 and 1 HTTP 429**, 17 failures. This text said "17, all HTTP 503" in
three places; 13 is the count at the end of the second run. Not in the ledger: the diagnostic request and the three
probes mentioned below were made outside it, so Google may have seen 21 to 24 requests that day. sv2 records every
request with its outcome (D-46).

## Per provider

| | gemini-3.8-flash | groq gpt-oss-120b |
| --- | --- | --- |
| requests made | 20 | 5 |
| successful | 3 | 5 |
| failed | 17: 16 HTTP 503 "high demand", 1 HTTP 429 daily quota (see "503 count, reconciled") | 0 |
| JSON-mode / schema acceptance | 3 of 3 answers accepted by the API | 5 of 5 accepted by the API |
| answers that parsed as JSON | 3 of 3 | 5 of 5 |
| input tokens, actual (successful calls) | 10,075 (3,358 per call) | 14,666 (2,933 per call) |
| output tokens, actual | 9,090 (3,030 per call) | 12,886 (2,577 per call) |
| plan estimate per call (5-doc plan) | 5,359 in, 2,904 out | 3,388 in, 2,920 out |
| documents needing a split | 0 of 3 | 2 of 3 (4 of 5 in the plan) |
| time used | 12.4 min across the calls, mostly the 503 retries | 9.7 min (the 8,000 tokens/min cap paces it) |
| quota left today (UTC) | **0 of 20 requests** | 995 of 1,000 requests; 172,448 of 200,000 tokens (27,552 used) |

Gemini daily requests: **20 of 20 used**. 17 of them failed: 16 were 503s and the 20th was the daily-quota 429 (corrected 2026-10-03, see below). I counted failed requests as used
(our ledger does), but Google may not count a 503 against the quota; I did not verify that. A tiny
diagnostic request returned the same 503 body ("This model is currently experiencing high demand"), so the
fault was Google's, not the request. Three later probes (done outside the ledger) returned 200 on the
first try, so the outage lasted a few minutes at most. The pipeline retries a 503 once per chunk and then
gives up on that chunk, which is how 17 failed requests went on 4 chunks across 3 runs.

Groq: the Zero Data Retention setting is on, as you said. Strict JSON schema mode accepted the schema on all
5 calls. The failures on the Groq side were all inside the JSON (see checks below), not at the API.

Plan estimates were not far off on output (Gemini +4%, Groq -12%) and high on Gemini input (-37%).
The Groq estimate of input is about 13% high.

## Fields

Counts are per field across the 3 documents. "Agreed" = both labelers agree and no blocking check failed
(accepted as silver). "Disagreed" = the two answers differ. "Blocked" = they agree but a blocking check
failed. "Both absent + cue" = both said absent but a heading cue for the field is in the document.
Flagged = disagreed + blocked + cue.

| field | agreed (of which absent) | disagreed | blocked | both absent + cue | flagged |
| --- | --- | --- | --- | --- | --- |
| title | 2 (0) | 1 | 0 | 0 | 1 |
| issuer_org | 2 (0) | 1 | 0 | 0 | 1 |
| contracting_officer | 1 (1) | 2 | 0 | 0 | 2 |
| notice_date | 1 (1) | 2 | 0 | 0 | 2 |
| procurement_type | 1 (0) | 2 | 0 | 0 | 2 |
| award_method | 2 (0) | 1 | 0 | 0 | 1 |
| item_category | 3 (2) | 0 | 0 | 0 | 0 |
| scope_summary | 2 (0) | 1 | 0 | 0 | 1 |
| performance_period | 0 | 3 | 0 | 0 | 3 |
| delivery_deadline | 2 (2) | 1 | 0 | 0 | 1 |
| delivery_location | 2 (1) | 0 | 1 | 0 | 1 |
| eligibility | 1 (1) | 2 | 0 | 0 | 2 |
| unified_qualification | 2 (1) | 1 | 0 | 0 | 1 |
| deadlines | 0 | 3 | 0 | 0 | 3 |
| submission_modes | 2 (1) | 1 | 0 | 0 | 1 |
| bid_bond | 3 (1) | 0 | 0 | 0 | 0 |
| performance_bond | 3 (1) | 0 | 0 | 0 | 0 |
| tax_basis | 1 (0) | 1 | 1 | 0 | 2 |
| language_currency | 0 | 1 | 2 | 0 | 3 |
| required_documents | 0 | 3 | 0 | 0 | 3 |
| contact | 0 | 2 | 0 | 1 | 3 |
| wto_covered | 3 (1) | 0 | 0 | 0 | 0 |
| spec_access | 0 | 2 | 1 | 0 | 3 |
| **overall (69)** | **33 (13)** | **30** | **5** | **1** | **36** |

Notes on reading this:
- Agreement is 48% of decisions, and 13 of the 33 agreements are both-absent. Of the 20 both-present
  agreements, none has been checked by a reader of Japanese yet.
- Six fields never agreed in any of the 3 documents: performance_period, deadlines, required_documents,
  language_currency, contact, spec_access. The list fields (deadlines, eligibility, required_documents) disagree on item sets.
- Several "disagreed" fields differ only in a sub-value (performance_period: same Japanese quote and end date,
  Groq adds `relative_text`, Gemini leaves it null). Strict equality on `normalized` flags these. Not changed.

## Automatic checks that failed

Blocking failures, counted over the 69 decisions (sides, so up to 2 per decision): 17 total.

| check | count | notes |
| --- | --- | --- |
| schema_valid | 14 | all but 2 from Groq |
| value_in_citation | 2 | both Groq |
| values_roundtrip | 1 | Groq |

Within `schema_valid` (open documents only, so all examples are public notices):
1. **Groq returned `normalized: null` for a list field** (5 times: deadlines, eligibility, procurement_type, tax_basis).
   Example: 4b0b9d8229c7 `deadlines`, B failed schema_valid (normalized is not a JSON object). Groq cited
   h_s31, h_s33, h_s35, h_s37 but gave no items.
2. **Chunk answers disagreed in a split document** (5 times, all Groq, since only Groq splits).
   Example: f19cddbd4cba `procurement_type`: chunk 1 cited h_s5, Gemini cited h_s24 (answer value agrees: 一般競争入札).
   Example: 563042df9941 `language_currency`: Groq's second chunk answered present with no citation.
3. **`see_other_document` shape** (3 times, Gemini twice, Groq once): `normalized` must be `{"ref": ...}`.
   Example: 563042df9941 `scope_summary`, Gemini answered 入札説明書による。 (see_other_document) and the schema
   rejected the shape.

Other checks:
- `value_in_citation` (Groq): 563042df9941 `contracting_officer`, Groq joined the two sentences with `; ` so the
  value is not a substring of the cited text. 563042df9941 `tax_basis`, Groq's quote contains text that is not
  in citation h_s35 verbatim.
- `values_roundtrip` (Groq): f19cddbd4cba `deadlines`.
- Non-blocking `heading_cue` fired 17 times, 11 of them on Gemini, including correct answers such as the title
  and issuer_org of 4b0b9d8229c7 (cue not in the cited sentence). It is probably too strict for those two
  fields; I left it.

## The 5 most interesting disagreements

1. **issuer_org, 4b0b9d8229c7**
   A (Gemini): 和歌山県. B (Groq): the whole sentence 和歌山県は、エビデンスに基づく行政を推進するとともに、...を実施しています。
   Source h_s2: 和歌山県は、エビデンスに基づく行政を推進するとともに、全国にデータ利活用の重要性・有用性を発信するため、平成29（2017）年度より「和歌山県データを利活用した公募型研究事業」を実施しています。
   Groq's English was "Wakayama Prefecture is the issuing organization." (it understood, but did not narrow the span).
2. **spec_access, f19cddbd4cba**
   A: present/public, cites h_s47 (入札説明書の交付方法 電子調達システム及び上記３の(1)の場所にて公告日より交付する。).
   B: see_other_document -> bid_instructions, cites h_s33 (調達案件の仕様等 入札説明書及び仕様書による。).
   Both are defensible; they answer different questions (how the instructions are handed out vs where specs are).
3. **scope_summary, 563042df9941**
   A: see_other_document, cites h_s28 (入札説明書による。). B: present, cites h_s26 (令和８年度 国立研究開発法人によるイノベーションシステム構築に関する調査).
   B looks right as a title-like summary; A copied a "see the instructions" line. A's answer also failed the schema.
4. **contracting_officer, f19cddbd4cba**
   Source h_s26 支出負担行為担当官 / h_s27 出入国在留管理庁次長　内藤惣一郎.
   A: title 支出負担行為担当官 出入国在留管理庁次長, name 内藤惣一郎. B: title 支出負担行為担当官, name 出入国在留管理庁次長 内藤惣一郎.
   Both quote the same sentences; the split between title and name differs. I read A as the better split, but this is a Japanese-reading call for the reviewer.
5. **notice_date, f19cddbd4cba**
   A: present, 令和８年８月28日 -> 2026-08-28, cites h_s25. B: absent. h_s25 is a line containing only that date (full-width and half-width digits mixed). Groq missed a bare date line; the same happened in 563042df9941 (令和08年08月19日).

## Does gpt-oss-120b handle the Japanese?

As far as the disagreements show, yes for reading. It cites the right sentences, quotes them verbatim, and its
English glosses in the examples above were sensible. I can't verify meaning myself, so this is a judgment
from the quotes, not a check. Where it is weaker is following the output contract: it emits `normalized: null` for list fields,
skips bare lines with a date, answers absent for `required_documents` (3 of 3 documents; Gemini found items in all 3),
returns whole sentences where a short name is wanted (issuer_org), and gave inconsistent answers between chunks of
the same document. These look like instruction-following and long-context limits more than Japanese comprehension.
Three documents are too few to rule out a Japanese problem.

## Quota projection for the full dev set (37 open documents, real token numbers)

Plan for the remaining open dev documents: Gemini 34 calls (+3 cached), Groq 106 calls (+5 cached), of which 30 documents need a split on Groq.

- Gemini: 34 calls at 20 requests per day = 2 days. Real tokens are no constraint (about 114k input at 3,358 per call).
  The 503 episode shows the day count assumes no retries: 16 of the day's 20 requests went on 503s, and 1 more was the 429 that ended the day.
- Groq: plan estimate is 688k tokens (357k in + 331k out) = 4 days at 200,000 tokens/day. With the real
  average of 5,510 tokens per call, 106 calls is about 584k tokens = 3 days. The 8,000 tokens/min cap makes
  it about 73 minutes of pure waiting per 100k tokens, i.e. 10 minutes for the 5 pilot calls.
- Overall: 3 to 4 days for the whole dev set, limited by Groq.

## Groq token cuts, ranked by saving (not applied)

Output is 47% of Groq tokens, input 53%. These are estimates, not measured.

1. **Do not ask Groq for `reason` and `value_en`** (output tokens, maybe 20 to 25% of its output, about 10 to 12% of total).
   `reason` stays in the raw cache only and is never exported. Needs a prompt/schema version bump.
2. **Skip fields the document type can't have** in the prompt for Groq (input; the plan already marks these rule-absent,
   but the prompt still lists all 23). Perhaps 5 to 10% of input.
3. **Shorten `FIELD_HELP`** (input, repeated in every chunk of a split document; maybe 5 to 8% of input, bigger on split documents).
4. **Avoid splits** by raising `request_cap` use: 30 of 37 documents split on Groq, and each split repeats the system prompt and help text.
   Not possible while the 8,000 tokens/min / per-request cap holds, so the saving is only what 3 removes.
5. **Cut the list-field retry waste**: Groq's `normalized: null` answers cost full output tokens and still end up flagged. Fixing the contract
   (for example by showing a one-line example in the schema description) would reduce flags more than tokens.

Cut 5 is a prompt change that would also lift agreement, which you asked me not to do yet.

## Review export

Exported from the 3 resolved documents after this report was written. See the command output for paths and item counts.
