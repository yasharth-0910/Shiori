# Phase 5 fix 2: why Qwen3.5-9B skips required_documents items that were in its window

Dev only, 14 documents with labels (13 have a required_documents row), model-reviewed silver labels (D-41). Qwen3.5-9B was one of the labelers and the prompt was tuned on these documents, so every number is a fit, not a forecast. No cloud call, no network call, no test split, no label, scorer, matching rule or `EXTRACTOR_VERSION` change. No document text in this file: doc id prefixes, item indexes and counts only. The reading of what the skipped entries are is mine, not a native speaker's.

## 1. The 8 skipped items (category b), from the saved trace

Source: `data/cache/hybrid/trace_cmp_qwen35_9b.json`, classified with `eval.hybrid.classify`. Read-only, no model.

| doc | label item | position of its sentence in the window | what the model did with it |
| --- | --- | --- | --- |
| 136dfba9 | 0 | 26 of 38 | folded into another item that cites 4 sentences (its own and three more) |
| 594c3cb6 | 0 | 3 of 22 | folded into another item that cites 7 sentences |
| a13baaac | 6 | 31 of 67 | folded into another item that cites 3 sentences |
| 28ad40ea | 7 to 11 (5 items) | 47 to 51 of 105 | nothing: no proposal cites them |

Cause counts (8 items):

| cause | items | note |
| --- | --- | --- |
| model left out a run of entries in the middle of one flat numbered list (28ad40ea: it listed entries 1 to 6, skipped the next 5, resumed at the last one) | 5 | the list is one level, not split |
| model merged several documents into one item (the label has one item per document) | 3 | the sentence is cited, but by a multi-sentence item, so it counts as missed |
| late in a long window | 0 | positions run from 3 of 22 to 51 of 105, none in the last quarter of the window except 136dfba9 (26 of 38) |
| output cut at the token cap | 0 | `call_failed` is None in all 13 calls; a cut raises `Truncated`. Largest answer 9 items, cap is 2,048 tokens and 40 items |
| item split across list levels | 0 | the 5 skipped entries are siblings at one level |
| window cut at the 7,000 character budget | 0 | all 8 sentences were sent (they are in `retrieved`) |

So a bigger output cap or a chunked window would not have touched any of the 8. The two causes are the model's own behavior on a list. Not explained: why it skips exactly those 5 entries (they are the ones without a form number; I did not test that).

## 2. The change

One line added to the required_documents rules in `core/shiori_core/extract/llm.py` (`RULES["required_documents"]`): go through a numbered list in order, one item per entry, do not skip entries in the middle, do not merge several documents into one item. No other field's prompt, retrieval, cap or check changed.

## 3. Before and after (required_documents only, 13 rows)

Both are real Qwen3.5-9B runs I executed this session, same 14 documents, same script, `required_documents` only, one llama-server on 127.0.0.1:8792 each (pid 64675, then 64969, both stopped). The before run reproduced the saved trace exactly (50 hit, 8 b, 7 d).

| required_documents | before | after |
| --- | --- | --- |
| rows right | 5 of 13 | 6 of 13 |
| rows wrong value shown | 8 | 7 |
| rows not found | 0 | 0 |
| hallucination (shown, value not in citation) | 0 | 0 |
| label items hit | 50 of 65 | 56 of 65 |
| label items: b not produced | 8 | 2 |
| label items: d cut differently | 7 | 7 |
| label items: a or c | 0 | 0 |
| answer items kept / proposed | 58 / 59 | 65 / 66 |
| answer items dropped (unknown_id) | 1 | 1 |
| calls failed or retried | 0 | 0 |
| model seconds (13 calls), wall seconds | 660, 670 | 747, 751 |

Rows that changed: 136dfba9 wrong to right, 28ad40ea wrong to right (13 of 13 items hit, 14 proposed, 1 dropped as unknown_id), 6b7142ab right to wrong (the answer went from 2 to 4 items, the label has 2, so 2 extra items). Net 5 to 6. The 2 b items left are 594c3cb6 item 0 and a13baaac item 6 (still folded into a multi-sentence item). The 7 d items did not move.

## 4. What this does and does not show

- One run each at temperature 0. Not repeated, so I cannot say how much of the change is the prompt and how much is run-to-run noise from a different prompt length; the item count moved by 6 hits.
- It is a fit: the line was written after reading the 8 misses on these same 14 documents, and the label side is partly Qwen's own candidates.
- The line has a cost I saw once (6b7142ab, 2 extra items). I did not read those 2 items, so I cannot say if the label lacks them or the model over-produced.
- Calls got about 13% slower (660 to 747 s model time), mostly 28ad40ea (82 to 140 s), because it now lists 13 items instead of 8.

## 5. What I actually saw

Files read: `eval/reports/list_field_wrong_value_analysis.md`, `eval/reports/phase5_fix1_changelog.md` (head), `core/shiori_core/extract/llm.py`, `eval/hybrid.py` (classify, Server), `eval/run.py`, the saved Qwen trace (39 calls), the 14 dev label files, and `sentences.json` of 28ad40ea (first 70 characters of 9 sentences, read locally, not copied here). Two scratch scripts in the session scratchpad (outside the repo) did the counting and the runs; their JSON outputs are `fix2_before.json` and `fix2_after.json` there. Run times: 670 s and 751 s wall. `pgrep -x llama-server` returned nothing after each run.
