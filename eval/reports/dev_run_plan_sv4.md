# Dev run plan, prompt sv4

Date: 2026-10-03. No labeling call was made for this plan. Numbers come from `uv run python -m eval.silver plan --split dev` (estimates, no API calls), the label set (`data/eval/label_set.json`, metadata only for test) and the sv3 pilot (`eval/reports/silver_pilot_sv3.md`). Document ids below are ids only, no document text.

## What runs

| | documents | labelers | prompt |
| --- | --- | --- | --- |
| open (dev) | 37 | Gemini + local Qwen3.5-9B | sv4, one grouped request each |
| restricted (dev) | 23 | Groq + local Qwen3.5-9B (half-split retry on `json_validate_failed`) | sv4, Groq in field groups that fit 8,000 tokens per request |
| unknown (dev) | 0 | (would be Groq + local) | |

5 of the 37 open documents are the pilot documents (f19cddbd4cba, 563042df9941, 4b0b9d8229c7, 28ad40ea4b1f, 4c40bbd831fe). They already have labels, so they run in comparison mode: their sv4 answers are scored against the reviewed labels in `eval/reports/silver_pilot_sv4.md` and nothing is written. The other 55 documents (32 open, 23 restricted) get labels.

## Per provider

| provider | documents | requests (estimate) | estimated tokens in / out | days | notes |
| --- | --- | --- | --- | --- | --- |
| Gemini | 37 | 37 (one per document; 0 repairs in the sv3 pilot) | 377,863 / 112,440 | **2** at 20 requests/day; **6** at the sv3 pilot's 503 rate | the pilot needed 11 tries for 4 answers (7 HTTP 503): 2.75 requests per answer, 102 requests for 37 documents. No tokens/day cap. Today (UTC 2026-10-03) 17 of 20 are used, so the run starts on the next UTC day |
| Groq | 23 | 138 (20 documents need more than one request) | 749,653 / 179,760; about 929,000 with the sv2 real/estimate ratio (1.06 in, 0.75 out) | **5** at 200,000 tokens/day; **7** with the split retry | split retry at sv2's `json_validate_failed` rate (21% of parts): about 29 parts, 58 more requests, about 390,000 more tokens, 1.32 M in total. The largest document is about 108,000 estimated tokens, so a day holds 2 to 7 documents |
| local Qwen3.5-9B | 60 | 60 grouped requests + repairs | 636,675 / 167,400 (no quota) | **8.5 to 12 Mac hours** | 27.8 s per asked field in the sv3 pilot (2,502 s for 90 fields, one grouped request) x 1,095 asked fields = 8.5 h; repairs were needed on 2 of 4 documents at about 420 s each, which adds about 3.5 h if half the documents need one |

Days for the whole run = the slower cloud provider: **5 to 7 days**. The local model runs in the same command after the cloud queue, on this Mac.

## Review items (projection)

Accepted consensus fields are written; every flagged field is reviewed; a seeded 5% of accepted fields goes to review as the consensus spot-check. No single-source shortcut, on dev or test. Rates are the ones observed in the sv3 pilot (Gemini vs local, after repair): 30 of 90 fields over the 4 pilot documents (33%) and 11 of 21 on the one document labeled for real, 28ad40ea4b1f (52%). sv4's new rules target known mismatches, but their effect is not measured; the restricted documents' pair (Groq + local) was never measured. Items = asked x rate + 5% x asked x (1 - rate).

| split | documents | asked fields | at 33% | at 52% |
| --- | --- | --- | --- | --- |
| dev (the 55 new documents) | 55 | 999 | **366 items, 31 batches of 12** | **547 items, 46 batches** |
| test (for the end, frozen prompt) | 40 | 730 | **268 items, 23 batches** | **400 items, 34 batches** |
| both | 95 | 1,729 | 634 items, 54 batches | 947 items, 80 batches |

The 5 pilot documents add no review items (comparison mode). Batches can also close early at 25,000 characters, so the real batch count can be a little higher.

## Order and days

`run` works through side A's queue first (Gemini for open documents, Groq for restricted ones, in label-set order), then side B's (the local model, every selected document), then resolves every document whose two answers are complete. The quota guard aborts a run whose estimate passes a provider's daily budget (20 Gemini requests, 200,000 Groq tokens), so the dev set is run as one selection per day with `--docs`, not as `--split dev`. Proposed selections (label-set order, Groq packed under 195,000 estimated tokens a day):

| day | Gemini documents | Groq documents (estimated tokens) | local requests | Mac time |
| --- | --- | --- | --- | --- |
| 1, first run (gate) | the 5 pilot documents (comparison) | - | 5 | about 1 h |
| 1, second run | 15 open: 58f13b9c2e87, a81e99fecea5, 136dfba9ee59, d230e51e2805, 6b7142ab74f4, 84e9d0c8325c, 594c3cb69c53, 5d75d4a67c71, 5720c2903850, 435d2881b52d, fb1253a58b2d, a13baaac55c8, db5c1723dc2b, a697e69a7db8, a90497874108 | 01204a43ed1d, 5d76c6a061ac, 6a44715085ac (141k) | 18 | about 4 h |
| 2 | 17 open: f08ea5aea45f, 2edf2494bef1, 3fc322cb5b33, 82fe582369e6, 08558fc7fe0a, bf99e8ba6a15, a11d233c84ad, 01e953d899ad, d40000275df6, 53320d90cf87, e56028078517, 081d27569eac, 8869632bb85c, 12f50d0602ce, 870f1f2ec726, fd637c1deea1, 7e591bba3e4f | b16ad9882fbc, e420f76b7182, e81e9338bfca (192k) | 20 | about 4 h |
| 3 | leftovers after 503s | 99044e933212, 2ed05ba95b66, 070b894ee590 (151k) | 3 + leftovers | about 0.5 h + |
| 4 | leftovers | 08ec571dc30e, 34ea5d0b8aa6 (132k) | 2 + leftovers | |
| 5 | leftovers | a2728e6bb87e, 11ead9a54403, aeedf544969c, bb10715a6a3b, 67e636608c55 (193k) | 5 + leftovers | |
| 6 | leftovers | 6387bfc31c98, 94b7145f88e2, 9b6a573a3652, f31471b231db, 03406dd6af8d, ae487875206f, 720e2a764fa5 (120k) | 7 + leftovers | |
| 7 | spare day for 503s and split retries | | | |

Each day:

```
uv run python -m eval.silver plan --docs <the day's ids plus yesterday's leftovers>
uv run python -m eval.silver run --docs <same> --yes --max-calls 120
uv run python -m eval.silver status --split dev
```

`--max-calls` counts every try, 503 retries and local repairs included: 120 covers 20 Gemini tries, about 30 Groq requests with split halves and up to 2 local requests per document.

The gate: after the day 1 first run, `uv run python -m eval.silver report --docs f19cddbd4cba,563042df9941,4b0b9d8229c7,28ad40ea4b1f,4c40bbd831fe` writes `eval/reports/silver_pilot_sv4.md` with Gemini and Qwen under sv4 against the reviewed labels. Go on only if sv4 is not worse than sv3 on the same 4 documents (Gemini 80 of 90, Qwen 62 of 90; 4c40bbd831fe adds 6 fields under sv4).

## Resuming across days

- Every answer is cached per part in `data/cache/labeling/raw/<doc>/<provider>__<model>__sv4__0.3.0__1.0.0.json`, written after each part. A part that is `ok` is never asked again, so re-running the same `--docs` the next day costs only what is missing. The guard prices only the missing parts.
- A daily-quota 429 or the ledger reaching the day's requests or tokens stops that provider for the day; the other provider and the local model go on.
- A part that used up the backoff (5 tries on 503) is `provider_unavailable`: that provider pauses for the rest of the run and the part is retried by the next run. A `failed` part (invalid JSON after the repair, a bad request) is asked again only with `--retry-failed`.
- A document is resolved at the end of the run in which its second answer completes; `uv run python -m eval.silver resolve --docs <ids>` does the same from the cache alone. Reviewed lines are never replaced by a re-run.
- The local model labels every selected document even when its cloud answer is still missing, so Mac time is spent on the day the document is selected.

## Not decided, for Yasharth

- Whether to run the 5 pilot documents first as a gate (proposed above; it costs 5 Gemini requests and about 1 Mac hour).
- (Decided 2026-10-04, D-56: a capped provider now stops for the day and the run goes on, so a plain `run --split dev` replaces the daily `--docs` lists below.) The guard aborted rather than stopping at the cap, which is why the plan needed daily `--docs` lists. A guard that runs up to the daily budget and leaves the rest pending would allow `run --split dev` every day. Not changed.
