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

## Why the 5 rows stay wrong: per row

Source for the first four rows: the saved traces replayed through the current `llm.py`, scored against the current labels with `eval.hybrid.classify` (no model). Sentence ids are within each document. Cause categories: **label** (label granularity or convention), **kind** (kind or value normalization), **validator** (answer item dropped by a check), **model** (the answer item is missing or cut differently). Where a mismatch can be read two ways I give both and do not pick; I read no Japanese meaning into any of them.

| row | label item that does not pair | what differs | cause |
| --- | --- | --- | --- |
| `563042df` eligibility, Qwen | item 0 (kind `legal`, cites `h_s40` + `h_s41`) | answer has one item citing `h_s40` only; no item cites `h_s41`. The other 4 label items hit | model (item cut: the label item spans 2 sentences); label granularity is the other reading |
| `563042df` eligibility, Gemma | item 0 (same) | same as Qwen | same |
| `f19cddbd` eligibility, Qwen | item 0 (`legal`, cites `h_s38` + `h_s39`) | answer has an item citing `h_s38` only, plus a separate `other` item citing `h_s39`; neither pairs | model (cut per sentence); label granularity is the other reading |
| `f19cddbd` eligibility, Qwen | item 3 (`other`, cites `h_s43`) | the answer item on `h_s43` has kind `legal`; the sentence is the same | kind (legal versus other, the open question logged 2026-11-18, guide has no line) |
| `f19cddbd` eligibility, Gemma | item 0 (same as Qwen) | answer has an item citing `h_s38` only; no item cites `h_s39` | model (item cut) |
| `f19cddbd` eligibility, Gemma | item 3 (same as Qwen) | kind `legal` on the `h_s43` item | kind |
| `5d75d4a67c71` eligibility, Qwen | item 3 (`other`, cites `h_s38`) | answer item on `h_s38` has kind `legal`. Label item 0 (cites `h_s34` + `h_s35`) pairs, but the answer also has a separate `h_s35` item that pairs with nothing (5 kept, 3 duplicates dropped) | kind (1); the extra item is the same per-sentence cut as above (model) |
| `5d75d4a67c71` eligibility, Gemma | item 0 (`h_s34` + `h_s35`) | answer item cites `h_s34` only | model (item cut) |
| `5d75d4a67c71` eligibility, Gemma | item 3 (`other`, `h_s38`) | kind `legal` | kind |
| `5d75d4a67c71` deadlines, Qwen | none: 3 of 3 label items pair | 3 extra answer items (6 against 3), see the deadline paragraph | model (extra items) |
| `5d75d4a67c71` deadlines, Gemma | none: 3 of 3 pair | same 3 extra items | model (extra items) |
| `5d75d4a67c71` required_documents, Qwen | item 1 (cites `h_s45`) and item 3 (cites `h_s54`) | 2 answer items: one cites `h_s32`, `h_s46`, `h_s54` together, one cites `h_s51`. Nothing cites `h_s45`; `h_s54` is inside the merged item | model (2: one entry left out, one folded into another item; the pattern of fix 2) |
| `5d75d4a67c71` required_documents, Gemma | item 3 (cites `h_s54`) | no answer item cites `h_s54`. Also an extra item citing `h_s29` alone | model (1, plus 1 extra item) |

Counts per cause, non-pairing label items over all 10 rows (the 4 earlier rows, plus the new document's 3 fields for 2 models); 12 items: model 8 (earlier 4, new 4: Gemma eligibility 1, Gemma required_documents 1, Qwen required_documents 2), kind 4 (earlier 2, new 2: `h_s38` once per model), validator 0, label 0 as sole cause. Answer items with no label partner, not counted above: 3 deadline items per model (6), plus 1 eligibility item for Qwen (new document), 1 required_documents item for Gemma. The label granularity reading (label item spans 2 sentences) stays an alternative for the item-cut cases, not decided. In the new document Qwen's duplicate check dropped 3 eligibility items; that is the validator working as designed and caused no miss.

Deadline rows of `5d75d4a67c71`: is the set of 6 answer items an in-person and electronic pair per date? **Per date, yes there are two items, but not always in-person and electronic.** Both models give the identical 6 items. For each of the 3 label dates the answer holds two items with the same datetime and the same cited sentence: dates 1 and 2 (`h_s45`, `h_s46`) are kind `other` plus kind `electronic`; date 3 (`h_s47`) is kind `bid_opening` plus kind `electronic`. The label holds one of each pair: `other` for date 1, `electronic` for date 2, `bid_opening` for date 3. So the pattern is "label kind plus an extra `electronic` copy" on every date, and on date 2 the extra is `other`. The model is adding a second kind per date, which `docs/labeling_guide.md` line 123 (a bid receipt on an electronic notice is kind electronic) does not ask for on the bid-opening date. I did not check what the three sentences say, and `other` is not shown to mean in-person, so whether two receiving modes exist per date is not established. Why the label has `other` for date 1 while the guide rule says electronic: not looked into.

Rerun for these rows: both models, local only, temperature 0, answers saved to the session scratchpad (`newdoc_<model>.json`), no call failed, no llama-server left running. The item counts match the earlier run (Qwen 3/4/5, 3/3/6, 2/4/2; Gemma 2/4/4, 3/3/6, 3/4/4), so the earlier scores stand.

## What I saw

- Counts above come from the scratch scripts' output on this run: Qwen old13 11/39, new13 11/39, newdoc 0/3, new14 11/42; Gemma old13 11/39, new13 11/39, newdoc 0/3, new14 11/42. Failed calls: none in either run. `pgrep -x llama-server` returned nothing afterwards.
- Read: `eval/run.py`, `eval/phase5_fix1_replay.py`, `eval/hybrid.py`, the fix 1 and fix 2 reports, both saved traces, the three label files changed by `9deb37d` (field, status, kind, polarity only).
- Not looked into: why the two eligibility rows stay wrong, why both models give 6 deadline items on `5d75d4a67c71`. One run each at temperature 0, not repeated.
