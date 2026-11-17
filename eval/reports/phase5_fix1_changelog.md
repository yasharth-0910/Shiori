# Phase 5 fix 1: deadline date recovery and eligibility polarity

Replay of the saved Qwen3.5-9B and Gemma 4 E4B traces (`data/cache/hybrid/trace_cmp_*.json`) through the current `core/shiori_core/extract/llm.py`. No model was started, no cloud call, no label, scorer, prompt, retrieval or `EXTRACTOR_VERSION` change; dev only (14 documents, model-reviewed silver labels, D-41). The proposals are the models' saved answers, so this shows what the two code changes do to the same answers, not what a new run would give. Both models were tuned or labeled on these documents, so every number is a fit.

- Fix A (`_recover_date`, `_recovered`): a deadline with `kind` and `citations` but no `datetime` and no `relative_text` gets its date from the cited sentences (`spans_of`, i.e. `value_normalize.find_dates`/`find_times`) when they give exactly one distinct date for that kind (mail spans for `mail_arrival`, the others for any other kind). The result still goes through the old `_check` (date and time must be in the cited sentence). Two dates or none: dropped as `schema`, as before.
- Fix B (`_polarity`): an eligibility item whose `text_ja` keeps its negation (…ないこと, …でないこと, …ない者であること) is a requirement (docs/labeling_guide.md). The other half of the guide rule (negation stripped means disqualification) is not applied: a text without a negation is often a plain requirement, so the model's polarity stays.

## Qwen3.5-9B

Before-replay matches the saved run (`run_cmp_qwen35_9b.json`): yes (39 rows, 10 right). Calls whose retrieved ids differ from the trace: 0.

| list-field count | before | after |
| --- | --- | --- |
| rows scored | 39 | 39 |
| rows right (value correct) | 10 | 10 |
| rows wrong value shown | 27 | 27 |
| rows not found | 2 | 2 |
| eligibility: answer items paired / label items / answer items | 49 / 80 / 71 | 49 / 80 / 71 |
| deadlines: answer items paired / label items / answer items | 24 / 42 / 35 | 24 / 42 / 35 |
| required_documents: answer items paired / label items / answer items | 50 / 65 / 58 | 50 / 65 / 58 |
| eligibility: rows right of 13 | 1 | 1 |
| deadlines: rows right of 13 | 4 | 4 |
| required_documents: rows right of 13 | 5 | 5 |

Items recovered by fix A: 0 (in 0 calls, documents none). Eligibility polarity set by fix B: 0 items (in 0 calls, documents none). Rows whose right/wrong state changed: 0.

## Gemma 4 E4B

Before-replay matches the saved run (`run_cmp_gemma4_e4b.json`): yes (39 rows, 10 right). Calls whose retrieved ids differ from the trace: 0.

| list-field count | before | after |
| --- | --- | --- |
| rows scored | 39 | 39 |
| rows right (value correct) | 10 | 11 |
| rows wrong value shown | 22 | 28 |
| rows not found | 7 | 0 |
| eligibility: answer items paired / label items / answer items | 48 / 80 / 65 | 48 / 80 / 65 |
| deadlines: answer items paired / label items / answer items | 9 / 42 / 22 | 21 / 42 / 42 |
| required_documents: answer items paired / label items / answer items | 57 / 65 / 67 | 57 / 65 / 67 |
| eligibility: rows right of 13 | 3 | 3 |
| deadlines: rows right of 13 | 1 | 2 |
| required_documents: rows right of 13 | 6 | 6 |

Items recovered by fix A: 23 (in 8 calls, documents 136dfba9, 4b0b9d82, 563042df, 58f13b9c, 594c3cb6, 84e9d0c8, a81e99fe, f19cddbd). Eligibility polarity set by fix B: 1 items (in 1 calls, documents d4000027). Rows whose right/wrong state changed: 1 (f19cddbd4cba/deadlines).

## What I saw

Counts above come from this run of `uv run python -m eval.phase5_fix1_replay`. Anything not shown (for example why a recovered item still does not pair with its label item) was not looked into.
