# Phase 5 summary after fix 4

Dev only, model-reviewed silver labels (D-41). Both models were tuned or labeled on these documents, so every number is a fit, not a forecast. No code, label, scorer, prompt, split or `EXTRACTOR_VERSION` change, no model run, no cloud call. Doc id prefixes, field names and counts only, no document text.

## Table: all list rows right, per model, per step

A row is one list field (eligibility, deadlines, required_documents) of one document. 42 rows = 14 labeled dev documents. The 14th document, `5d75d4a67c71`, was labeled after the work started, so the early steps were scored on 39 rows (13 documents). One row is 2.6 points of 39 and 2.4 points of 42. Movement is in percentage points, from the step above, on the denominator shown.

| step | Qwen3.5-9B rows right | move | Gemma 4 E4B rows right | move | source |
| --- | --- | --- | --- | --- | --- |
| start of Phase 5 | 10 of 39 (25.6%) | | 10 of 39 (25.6%) | | `phase5_design_review.md` |
| after fix 1 (deadline date recovery, polarity) | 10 of 39 (25.6%) | 0.0 | 11 of 39 (28.2%) | +2.6 | `phase5_fix1_changelog.md` |
| after fix 2 (required_documents prompt line) | 11 of 39 (28.2%) | +2.6 | 11 of 39 (28.2%) | 0.0 | `phase5_design_review.md`, `phase5_rescore_after_label_fix.md` |
| label fix `9deb37d`, not a code step | 11 of 39, 11 of 42 (26.2%) | 0.0 | 11 of 39, 11 of 42 (26.2%) | 0.0 | `phase5_rescore_after_label_fix.md` |
| after fix 3 (proviso merge, 第73条 kind) | 14 of 42 (33.3%) | +9.5 (see note 1) | 13 of 42 (31.0%) | +4.8 | `phase5_fix3_eligibility_proviso.md` |
| after fix 4 (same-sentence deadline copies) | 15 of 42 (35.7%) | +2.4 | 14 of 42 (33.3%) | +2.4 | rescored from saved traces, this report |

Fix 3 moves are taken inside its own report, before to after on the same proposals and 42 rows (Qwen 10 to 14, Gemma 11 to 13). Chaining from the 11 of 42 line instead would read +7.1 for Qwen and +4.8 for Gemma; the two differ for Qwen, see note 1.

## Fix 4 rescore (new in this report)

Method: the saved proposals of both models were replayed through the current `core/shiori_core/extract/llm.py` the way `eval.phase5_fix3_replay` does (13 documents from `trace_cmp_<model>.json`), and for `5d75d4a67c71` the kept deadline items of `trace_cmp5d_<model>.json` were passed through `_drop_same_sentence_copies` or not. Scored with the unchanged `eval.run` / `eval.hybrid` scorer against the same labels. The script was a scratch file outside the repo, nothing was written to the repo but this report. The no-fix-4 side reproduced the fix 3 report exactly (Qwen 14 of 42, Gemma 13 of 42), so the two sides differ by fix 4 alone.

| | Qwen before | Qwen after | Gemma before | Gemma after |
| --- | --- | --- | --- | --- |
| all list rows right (of 42) | 14 | 15 | 13 | 14 |
| wrong value shown | 26 | 25 | 29 | 28 |
| not found | 2 | 2 | 0 | 0 |
| deadlines rows right (of 14) | 4 | 5 | 2 | 3 |
| deadlines items paired / label items / answer items | 27 / 45 / 41 | 27 / 45 / 38 | 24 / 45 / 48 | 24 / 45 / 45 |
| rows whose state changed | | `5d75d4a6` deadlines, wrong to right | | `5d75d4a6` deadlines, wrong to right |

The 3 dropped copies per model are the 6-to-3 rows in `phase5_fix4_deadline_dupes.md`. No other row moved.

## Notes and steps I cannot reproduce without a model run

1. **Qwen after fix 3 and fix 4 does not include fix 2's gain.** The fix 3 replay reads Qwen's required_documents from the old saved trace, where it has 5 right rows, not 6. The fix 2 answers were real runs and were never saved to the repo, so a cumulative fix 1 to 4 figure for Qwen needs a required_documents model run (the fix 2 rerun cost 862 s wall for Qwen, per `phase5_rescore_after_label_fix.md`, including the new document). Because of that, Qwen's 14 and 15 may each be 1 row too low, and the chained fix 3 move (+7.1 from 11 of 42) mixes two code states. Gemma is not affected, fix 2 changed nothing for it.
2. **Start of Phase 5 and fixes 1 and 2 on 42 rows: not reproducible.** `5d75d4a67c71` had no label then, and its rows under the earlier code need a model run on that document. Those steps are shown on 39 rows, as reported. The label-fix report scored the new document at 0 of 3 for both models with fixes 1 and 2 on, which is where the 11 of 42 comes from.
3. **The fix 3 and fix 4 rows for the 5d75 document are one real run each (temperature 0), not repeated.** Fix 3 and fix 4 are replays of saved answers, not new model runs, so they show what the code does to those answers, not what a fresh run gives.
4. The 39-row and 42-row percentages are not directly comparable, because the new document adds 3 rows, all 0 right at first.

## Phase 5 exit criterion

Exit (docs/roadmap.md): two consecutive changes give under 1 point of improvement.

**Not met.** The last two code changes moved the score by more than 1 point each, for both models: fix 3 by +9.5 (Qwen) and +4.8 (Gemma), fix 4 by +2.4 for both. One row is worth 2.4 points on 42, so any change that flips one row is already over 1 point; only a change that flips none would count as under 1. The only zero moves so far are fix 1 for Qwen and fix 2 for Gemma, and neither pair is consecutive (fix 1 moves Gemma, fix 2 moves Qwen). Also, both models are well below the ceiling set by the design review (`phase5_design_review.md`: Qwen at most 23 of 39 with the labels as they are), so the cheap fixes are not yet exhausted by that measure either.

## What I saw

- Read: `phase5_fix1_changelog.md`, `phase5_fix2_required_documents.md` (head), `phase5_fix3_eligibility_proviso.md`, `phase5_rescore_after_label_fix.md`, `phase5_design_review.md` (grep for the baseline and ceiling lines), `phase5_fix4_deadline_dupes.md`, `eval/phase5_fix1_replay.py`, `eval/phase5_fix3_replay.py`.
- Ran, no model and no network: the scratch rescore. Output lines: Qwen 14 of 42 to 15 of 42 (wrong 26 to 25, not found 2, deadlines rows 4 to 5, flipped row `5d75d4a6` deadlines); Gemma 13 of 42 to 14 of 42 (wrong 29 to 28, not found 0, deadlines rows 2 to 3, flipped row `5d75d4a6` deadlines).
- Not looked into: why the other 27 (Qwen) and 28 (Gemma) rows stay wrong, beyond what the design review already records.
