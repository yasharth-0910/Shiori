# Phase 5: list-field rescore after the dev label fix (9deb37d)

Dev only. Model-reviewed silver labels (D-41), so every number is a score against silver labels, and both models were tuned or labeled on these documents, so it is a fit. No label, extractor, prompt, scorer, split or `EXTRACTOR_VERSION` change, no network call. No document text in this file: doc id prefixes, field names and counts only.

## Result

On the 13 documents that were scored before, the label fix moved **no list-field row** for either model: Qwen3.5-9B 11 of 39 before and after, Gemma 4 E4B 11 of 39 before and after. The new document `5d75d4a67c71` adds 3 rows, and both models get 0 of 3 right on it. With it: 11 of 42 for both.

## How it was done

- Saved outputs: `data/cache/hybrid/trace_cmp_<model>.json` (13 documents x 3 fields) replayed through the current `core/shiori_core/extract/llm.py` with a fake model, as in `eval.phase5_fix1_replay`. Calls whose retrieved ids differ from the trace: 0.
- Two parts could not come from saved outputs, so I ran the models (local only, one llama-server at a time on 127.0.0.1:8792, stopped after each, no calls failed):
  - Qwen3.5-9B: required_documents on the 13 documents (the fix 2 prompt, whose answers were never saved) plus all three fields on `5d75d4a67c71`. 862 s wall. Eligibility and deadlines for the 13 documents stay from the saved trace, as their prompts did not change.
  - Gemma 4 E4B: all three fields on `5d75d4a67c71` only. 85 s wall.
  - The Qwen required_documents rerun gave 6 of 13, matching the fix 2 report's after number, which is how the 11 of 39 baseline is reproduced.
- Scorer: `eval.run.evaluate` and `eval.hybrid.item_totals`, unchanged. A row is verified when its value is right.
- Before labels: dev label directory with the two modified files taken from `9deb37d^` and the new file removed. After labels: the working tree (`9deb37d`). The same outputs are scored against both, so any change is the labels alone.
- Scripts are in the session scratchpad, outside the repo. They did not use `eval.run`, so no `run_*.json` or `hybrid_*.md` files were written.

## Counts per model

| | Qwen before | Qwen after | Gemma before | Gemma after |
| --- | --- | --- | --- | --- |
| rows verified, 13 documents (of 39) | 11 | 11 | 11 | 11 |
| eligibility rows right (of 13) | 1 | 1 | 3 | 3 |
| deadlines rows right (of 13) | 4 | 4 | 2 | 2 |
| required_documents rows right (of 13) | 6 | 6 | 6 | 6 |
| eligibility items paired / label items / answer items | 49 / 80 / 71 | 52 / 80 / 71 | 48 / 80 / 65 | 51 / 80 / 65 |
| deadlines items paired / label items / answer items | 24 / 42 / 35 | 24 / 42 / 35 | 21 / 42 / 42 | 21 / 42 / 42 |
| required_documents items paired / label items / answer items | 56 / 65 / 65 | 56 / 65 / 65 | 57 / 65 / 67 | 57 / 65 / 67 |

## With and without `5d75d4a67c71`

It has no old label file, so "before" does not exist for it; it counts only in the "after" labels.

| after labels | Qwen without | Qwen with | Gemma without | Gemma with |
| --- | --- | --- | --- | --- |
| rows verified | 11 of 39 | 11 of 42 | 11 of 39 | 11 of 42 |
| eligibility rows right | 1 of 13 | 1 of 14 | 3 of 13 | 3 of 14 |
| deadlines rows right | 4 of 13 | 4 of 14 | 2 of 13 | 2 of 14 |
| required_documents rows right | 6 of 13 | 6 of 14 | 6 of 13 | 6 of 14 |

On `5d75d4a67c71` alone (items paired / label items / answer items):

| field | Qwen | Gemma |
| --- | --- | --- |
| eligibility | 3 / 4 / 5 | 2 / 4 / 4 |
| deadlines | 3 / 3 / 6 | 3 / 3 / 6 |
| required_documents | 2 / 4 / 2 | 3 / 4 / 4 |

Rows are 0 of 3 for both, because a row needs the whole item list to match. Both models extra-answer on deadlines (6 answer items against 3 label items); I did not look at why.

## Rows that changed: label changed, extractor unchanged

Rows whose verified state changed: **0** for both models.

Label lines changed in `9deb37d` (field and counts only):

| doc | field | what changed |
| --- | --- | --- |
| `563042df` | eligibility | 3 items from polarity `disqualification` to `requirement` (2 of kind `legal`, 1 of kind `suspension`) |
| `f19cddbd` | eligibility | 2 items from `disqualification` to `requirement` (both kind `legal`) |
| `5d75d4a6` | all 23 fields | new label file |

Effect of those 5 label items on the same outputs:

- Eligibility items paired rose by 3 for both models (Qwen 49 to 52, Gemma 48 to 51). So 3 of the 5 corrected items now pair with an answer item and 2 did not.
- The eligibility rows of `563042df` and `f19cddbd` were wrong before and are still wrong for both models. At least one other item in each list still fails to match. I did not look at which or why.
- No deadlines or required_documents label changed in these two files.

Rows changed because the extractor changed: none in this report.

## What I saw

- Counts above come from the scratch scripts' output on this run: Qwen old13 11/39, new13 11/39, newdoc 0/3, new14 11/42; Gemma old13 11/39, new13 11/39, newdoc 0/3, new14 11/42. Failed calls: none in either run. `pgrep -x llama-server` returned nothing afterwards.
- Read: `eval/run.py`, `eval/phase5_fix1_replay.py`, `eval/hybrid.py`, the fix 1 and fix 2 reports, both saved traces, the three label files changed by `9deb37d` (field, status, kind, polarity only).
- Not looked into: why the two eligibility rows stay wrong, why both models give 6 deadline items on `5d75d4a67c71`. One run each at temperature 0, not repeated.
