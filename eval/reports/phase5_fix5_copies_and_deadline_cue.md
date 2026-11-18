# Phase 5 fix 5: merged-proviso copies and the bid receipt cue (D-73)

Replay of the saved list-field proposals (`data/cache/hybrid/trace_cmp_<model>.json`, 13 documents, and `trace_cmp5d_<model>.json`, the 14th, `5d75d4a67c71`) through `core/shiori_core/extract/llm.py`. No model was started, no cloud call. Scored with the unchanged `eval.run` scorer against the current dev labels (the corrected ones, commit `4719503`). Prompt text, labels, scorer, test splits and `EXTRACTOR_VERSION` untouched. Dev only, model-reviewed silver labels (D-41); both models were tuned or labeled on these documents, so every number is a fit. No document text in this file: doc id prefixes, fields and counts only.

Rules (D-73):
- Rule 1: after the proviso merge, an eligibility item with the same polarity as a merged item, and the same text or citations inside the merged item's, is dropped.
- Rule 2: a deadline the model gave kind other, on a sentence whose first cue is 入札書の受領期限 or 入札書の提出期限, becomes electronic when the rules extractor reads the notice as electronic only (guide line 124). Other kinds are never changed.

"Before" is the code at HEAD (neither rule). The other rows switch one rule off in the current code. Each variant replays the same proposals, so only the rules differ. Calls with a moved retrieval window: 0 in every run.

## Rows right of 42 (all three list fields)

| | before | rule 1 only | rule 2 only | both |
| --- | --- | --- | --- | --- |
| Qwen3.5-9B | 15 | 17 | 17 | 19 |
| Gemma 4 E4B | 16 | 16 | 18 | 18 |

Wrong value shown / not found, both rules: Qwen 21 / 2 (before 25 / 2), Gemma 24 / 0 (before 26 / 0).

## Rows that changed (no row lost in any variant, for either model)

| model | rule | rows gained | rows lost |
| --- | --- | --- | --- |
| Qwen3.5-9B | 1 | 6b7142ab eligibility, d230e51e eligibility | none |
| Qwen3.5-9B | 2 | 6b7142ab deadlines, f19cddbd deadlines | none |
| Gemma 4 E4B | 1 | none | none |
| Gemma 4 E4B | 2 | 6b7142ab deadlines, f19cddbd deadlines | none |

Both rules stay: neither nets negative for either model.

## Notes

- Why rule 1 gains nothing for Gemma: its eligibility rows with a proviso have no second copy (the corrected labels already fixed those rows, so they were right before). The two Qwen rows had an identical second item after the merge (d230e51e, 6b7142ab).
- 5d75d4a67c71 is not replayed from the proposals. Its saved run keeps only the items the old code kept, with the proviso already merged. Rule 1 therefore cannot fire there. Rule 2 was applied to its kept deadline items before the D-72 same-sentence drop, followed by the duplicate key the real pipeline applies after the kind change. The row stays as it was for both models.
- The earlier measurement in `phase5_remaining_errors_after_fix4.md` (K2 lost f19cddbd deadlines) was before the f19cddbd4cba label was corrected to electronic; with the corrected label the same rule gains that row.
- Saved answers (temperature 0, one run each) were replayed, so a fresh model run can give other answers. The three required_documents rows of Qwen come from the old trace as before.

## What I actually saw

- `uv run pytest tests/test_llm_extract.py`: 33 passed (7 new). Full suite: 776 passed. `ruff check .`: all checks passed. `ruff format`: no changes left. `pyright`: 0 errors.
- The replay printed the rows right per variant exactly as in the table above, 0 moved windows, and the gained/lost lists above for both models.
- Scratch scripts and the HEAD copy of `llm.py` used for "before" were in the session scratchpad, outside the repo.
