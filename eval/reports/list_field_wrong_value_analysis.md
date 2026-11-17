# Why the list fields show a wrong value: Qwen3.5-9B (27 of 39 rows) and Gemma 4 E4B (22 of 39 rows)

Read-only analysis. No code, label, decision log, test split, or `EXTRACTOR_VERSION` was changed. No model was started, no network call was made, and this file holds no document text: only doc id prefixes, field names, item ids and counts. Dev only, 14 documents, model-reviewed silver labels (D-41). Qwen3.5-9B was one of the labelers and the prompts were tuned on these documents with it, so every number here is a fit, not a forecast. The two Japanese-meaning calls (legal vs other, what counts as one item) are my reading, not a native speaker's.

## 1. Units, and how the counts were made

Two different units appear in the existing reports, and mixing them is the main source of confusion.

- **Rows**: one row per (document, field) in `run_*.json`. 39 rows = 14 documents x the list fields each has a label for. "Wrong value shown" means `pred == present` and the whole-list agreement rule failed. That rule (`eval/silver/compare.py:score` -> `agree`, list branch `_match`) needs every answer item to have a distinct partner in the label and the other way round. So **one missed label item, or one extra answer item, makes the whole row wrong.**
- **Label items**: one per item in the label files (187 across the three fields). The `hybrid_diagnostic_*.md` tables count these.

The rows are 27 wrong / 10 right / 3 not found (Qwen) and 22 wrong / 10 right / 8 not found (Gemma). Not-found rows are not "wrong value shown", so they are outside the 27 and 22.

How I got per-row causes: the diagnostic `.md` files only list 3 examples per cause. I wrote a scratch script (outside the repo, in the session scratchpad) that loads the saved traces `data/cache/hybrid/trace_cmp_*.json`, calls the repo's own `eval.hybrid.classify` the same way `--diagnose` does, and joins the result to the `records` in `run_cmp_*.json`. Nothing was written into the repo. Checks that it matches the existing reports:

- Qwen: wrong rows 27, a/b/c/d = 10/12/2/40, answer items with no label item 41. Same as the diagnostic.
- Gemma: wrong rows 22, a/b/c/d = 10/2/3/58, extra answer items 40. Same as the diagnostic.
- Every one of the 27 and 22 wrong rows has at least one non-hit label item or one extra answer item (0 unexplained). No right row has either.

## 2. One correction to the Gemma diagnostic (a mislabeled cause)

Gemma's `d5 wrong value` on deadlines is 29 label items. **24 of those are not wrong values.** In the trace, Gemma proposed 90 deadline items; 55 were dropped with verdict `schema`. 53 of those 55 have no `datetime` key at all (just `kind` and `citations`), 2 have `datetime` null with `relative_text` null. `DeadlineItem` requires exactly one of the two, so they fail validation in `read_items` before any check runs. `classify` only reports category c when the dropped item would pair with the label, and an item with no datetime can never pair, so it falls through to d and then `subcause` files it as d5. I call this token `S` below. The remaining 5 d5 items on Gemma are real (flags or datetime differ on kept items). Qwen has 0 schema drops.

These 24 `S` items sit in the 7 deadline rows where Gemma kept nothing, so they show up as "not found", not in the 22. They do explain why Gemma's deadline hit rate is 9 of 42.

## 3. Causes, counted

Token key: `a` sentence not in the retrieved window; `b` in the window but the model did not produce it; `c` produced then dropped by a check; `S` dropped by schema (Gemma only); `d1c` kind differs, convention; `d1r` kind differs, real; `d2c` / `d2r` polarity differs, convention / real; `d3` same text cut differently; `d4` answer built on a different sentence; `d5` datetime or flags differ on a kept item; `X` kept answer item that pairs with no label item and is not the mate of a missed label item.

### 3a. Label items missed, by cause (Qwen / Gemma)

| cause | eligibility | deadlines | required_documents | all | missed by both with the same cause (item-level) |
| --- | --- | --- | --- | --- | --- |
| a not in window | 9 / 9 | 1 / 1 | 0 / 0 | 10 / 10 | 10 (9 elig, 1 deadl) |
| b not produced | 1 / 1 | 3 / 0 | 8 / 1 | 12 / 2 | 0 |
| c dropped by a check | 1 / 3 | 1 / 0 | 0 / 0 | 2 / 3 | 1 (elig) |
| S dropped by schema | 0 / 0 | 0 / 24 | 0 / 0 | 0 / 24 | 0 (Gemma only) |
| d1 kind, convention | 5 / 6 | 1 / 1 | 0 / 0 | 6 / 7 | 5 elig |
| d1 kind, real | 0 / 0 | 7 / 2 | 0 / 0 | 7 / 2 | 2 deadl |
| d2 polarity, convention | 3 / 3 | 0 / 0 | 0 / 0 | 3 / 3 | 3 elig |
| d2 polarity, real | 2 / 0 | 0 / 0 | 0 / 0 | 2 / 0 | 0 |
| d3 different split | 3 / 3 | 0 / 0 | 7 / 7 | 10 / 10 | 5 (2 elig, 3 req) |
| d4 wrong sentence | 7 / 7 | 0 / 0 | 0 / 0 | 7 / 7 | 7 (elig) |
| d5 wrong value | 0 / 0 | 5 / 5 | 0 / 0 | 5 / 5 | 2 deadl |
| **label items not hit** | 31 / 32 | 18 / 33 | 15 / 8 | 64 / 73 | |

Totals: Qwen 123 hit of 187, Gemma 114 of 187.

### 3b. Extra answer items with no label item (X), not tied to a missed label item

| | eligibility | deadlines | required_documents | all |
| --- | --- | --- | --- | --- |
| Qwen | 7 | 1 | 1 | 9 |
| Gemma | 5 | 6 | 4 | 15 |

Of the other extras (41 for Qwen, 40 for Gemma in the diagnostic), the rest are the answer-side half of a d item: the kept item that shares a sentence with a missed label item. Those are the same defect as the d item, not a separate cause (Qwen 32, Gemma 25).

Shapes of the X items I could check without reading text. Cited sentence already used by a matched label item ("dupsent"): Qwen 6 (2 answer text inside the label text, 2 label text inside the answer text, 2 unrelated), Gemma 4 (1 inside, 3 unrelated). Cited sentence that no label item cites ("nolabel"): Qwen 3, Gemma 11; 4 of the 14 are next to a labeled sentence, the rest are far from any.

### 3c. Wrong rows, by cause (rows touched; a row can touch several)

| | Qwen elig | Qwen deadl | Qwen req | Qwen all | Gemma elig | Gemma deadl | Gemma req | Gemma all |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| wrong rows | 12 | 7 | 8 | **27** | 10 | 5 | 7 | **22** |
| a | 3 | 1 | 0 | 4 | 3 | 1 | 0 | 4 |
| b | 1 | 1 | 4 | 6 | 1 | 0 | 1 | 2 |
| c | 1 | 0 | 0 | 1 | 2 | 0 | 0 | 2 |
| d1 convention | 4 | 1 | 0 | 5 | 5 | 1 | 0 | 6 |
| d1 real | 0 | 5 | 0 | 5 | 0 | 2 | 0 | 2 |
| d2 convention | 2 | 0 | 0 | 2 | 2 | 0 | 0 | 2 |
| d2 real | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| d3 | 3 | 0 | 4 | 7 | 3 | 0 | 4 | 7 |
| d4 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 1 |
| d5 | 0 | 2 | 0 | 2 | 0 | 2 | 0 | 2 |
| X extras | 7 | 1 | 1 | 9 | 5 | 2 | 4 | 11 |

Rows whose only cause is a single token (these are the rows a single fix flips): Qwen: d3 5, b 3, extras 5 (3 dupsent + 2 nolabel), d1 convention 1, d1 real 1 = 15 rows. Gemma: d3 3, extras 5, d1 real 1 = 9 rows. The other 12 (Qwen) and 13 (Gemma) rows have two or more causes at once, which is why fixing one cause often repairs few rows.

## 4. Shared causes: what points at the pipeline

- **Wrong in both models: 19 rows** (10 eligibility, 6 required_documents, 3 deadlines). Qwen-only 8, Gemma-only 3. 14 of the 19 share at least one cause token; 8 have exactly the same cause set.
- **Label items missed by both: 50** (28 eligibility, 18 deadlines, 4 required_documents). With the same cause in both: 35 (27 eligibility, 5 deadlines, 3 required_documents). The 13 "different cause" deadline items are Gemma's `S` drops over items Qwen also missed for other reasons.
- **Fully shared (pipeline, not model):** a (10 of 10 items, same ids in both models, the window is model-independent), d4 (7 of 7), d1 convention in eligibility (5 shared of 5/6), d2 convention (3 of 3), the 10 d3 items per model (5 shared; the other 5 are the same defect on different items).
- **Mostly shared:** eligibility overall. 28 of 31 / 32 missed eligibility items are missed by both.
- **Model-specific:** b on required_documents and deadlines (Qwen omits 12 items, Gemma 2), c on eligibility (Gemma 3, Qwen 1), S (Gemma 24), d1 real on deadlines (Qwen 7, Gemma 2), d5 on deadlines kept items (5 and 5 but on different items, only 2 shared), d2 real (Qwen 2).

So on eligibility the failure is almost all pipeline or label (retrieval a, list structure d4, convention d1/d2, split d3). On required_documents it is split (d3) for both plus omissions for Qwen. On deadlines the two models fail differently.

## 5. Cause, pipeline part, smallest fix, ranked by rows repaired

"Rows repaired" is an upper bound from my replay: a row counts only if every cause on that row is covered by the fixes up to that point. It does not predict what a rerun gives. Standalone = rows whose only causes are this fix's. Incremental = added rows when applied in this order (Qwen / Gemma). The order is by standalone rows then incremental value, and it is not unique.

| rank | cause | label items (Q/G) | rows standalone (Q/G) | rows incremental (Q/G) | points at | smallest fix to try |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | X extra answer items | 9 / 15 answer items | 5 / 5 | 5 / 5 | matching against the label, or the label itself (cannot tell which without Japanese) | First look at these 10 rows with a Japanese reader to see if the label lacks the item or the extractor over-produced. No code change before that. If over-production, dedupe an answer item whose text sits inside another item that shares its citation (3 of the 10 dupsent items). |
| 2 | d3 same text cut differently | 10 / 10 | 5 / 3 | 5 / 4 | matching against the label (plus normalization of item boundaries) | In `item_same` for text fields, treat two items as the same when one text contains the other and the citations overlap. This is two-directional: answer text inside the label text (Qwen 6, Gemma 8) and label text inside the answer text (Qwen 4, Gemma 2). It changes the metric, so it needs a `docs/decisions.md` entry before use. The pipeline-side alternative is merging contained items, which only covers the first direction. |
| 3 | d1 / d2 convention (legal vs other, requirement vs disqualification) | 9 / 10 | 1 / 0 | 4 / 3 | the label itself (labels disagree with each other) and the kind rule in `field_schema.md` | Decide the line in `field_schema.md` and relabel the 5 to 6 items, or accept either value in `item_same`. Alone it fixes almost nothing (1 / 0) because those rows also carry d3 or extras. |
| 4 | d1 real and d5 on deadlines | 14 / 7 | 3 / 1 | 3 / 3 | kind or polarity (kind assigned from one sentence, the 到着 or 質問 sentence not cited) and normalization (flags read from cited sentences only) | Derive `kind` in code from the cited wording, and read flags from the cited sentence plus its neighbour. Qwen answers `bid_in_person` where the label says `electronic` or `mail_arrival` in 5 of the 7 d1 items; the deterministic kind check is the smaller change. |
| 5 | b model did not produce | 12 / 2 | 3 / 0 | 5 / 1 | model (Qwen only; Gemma finds all but 1 of the 8 required_documents items) | Not a pipeline fix. A second pass on required_documents asking for items not yet listed, or use the model that finds them. Skip until ranks 1 to 4 are settled. |
| 6 | c dropped by a check | 2 / 3 | 0 / 0 | 1 / 2 | value check (`value_not_in_citation`, `date_or_time_not_in_citation`) | Read the 5 dropped items to see if the check is too strict. Too few to act on. |
| 7 | a sentence not in the window | 10 / 10 | 0 / 0 | 3 / 3 | retrieval | Widen the window for eligibility headers in the 4 documents (a81e99, d40000 and 28ad40 are in the diagnostic examples). Zero rows flip on their own because each of these rows also has d1, d4, or X causes. |
| 8 | d4 list header only, d2 real | 9 / 7 | 0 / 0 | 1 / 1 | retrieval plus prompt (ア to ケ lists) | Expand a list header into one item per sub-item sentence. 7 label items in one document (d40000), both models. One row. |
| not in the 22 | S schema drop | 0 / 24 | n/a | n/a | model output vs `DeadlineItem` validation | Fill `datetime` in code from the cited sentence (`spans_of` already finds dates) when the model returns only kind and citations. This would turn Gemma's 7 not-found deadline rows into shown rows; it does not reduce the 22 and I cannot say how many would then be right. |

All eight together cover all 27 and 22 rows by construction, which is only a restatement that every wrong row has a cause. The first four fixes together cover 17 of 27 (Qwen) and 15 of 22 (Gemma) rows on the upper bound.

## 6. Rows that may be label or scoring mismatches, not extractor errors

Listed separately and not fixed.

- **d1 convention in eligibility, 5 (Qwen) / 6 (Gemma) label items.** Answer `legal` vs label `other` or the reverse. The diagnostic itself says the labels disagree with each other. One Gemma item is `other` vs `certification`, which is not a legal/other case; `subcause` files any text-field kind mismatch as "convention", so this one is not backed by the written reasoning. Item ids are in the diagnostic files (d1 eligibility examples) and in my replay, not repeated here.
- **d2 polarity convention, 3 items per model.** Answer says `requirement` where the label says `disqualification` and the answer text keeps its negation. The diagnostic says the guide calls that a requirement and the older labels say disqualification, so these are label-vs-guide conflicts. The 2 Qwen `d2 real` items are different (bad state named under a "none may apply" header).
- **d1 convention in deadlines, 1 item per model**, label `other` where the answer says `mail_arrival` or `electronic`. The diagnostic says those labels predate the electronic-notice rule.
- **d3 where the label is the shorter one** (Qwen 4, Gemma 2, all required_documents): the answer contains the whole label text plus more. This is the reverse of what the diagnostic text describes for d3 ("the なお or ただし sentence stays inside the item"), so it reads as a granularity difference, which could be either side. I labeled all 10 per model as "real" in the table only because the diagnostic does.
- **X extras with no label item (14 answer items, 3 dupsent "unrelated")**, and the 10 rows that fail only because of an extra item. If the label is missing an item, these are label mistakes. I cannot tell from ids alone.
- **Greedy pairing and an all-or-nothing row rule.** One extra item flips a row, so the 10 X-only rows (5 per model) are partly a property of the metric, not only of the extractor.

## 7. What I actually saw

Files read in full: `eval/reports/hybrid_diagnostic_cmp_qwen35_9b.md`, `hybrid_diagnostic_cmp_gemma4_e4b.md`, `model_compare_list_fields.md`, `run_cmp_qwen35_9b.md` (first 60 lines). Files read by script: `run_cmp_qwen35_9b.json` and `run_cmp_gemma4_e4b.json` (the 39 list-field records each), `data/cache/hybrid/trace_cmp_qwen35_9b.json` and `trace_cmp_gemma4_e4b.json` (39 calls each), and the dev label files under `data/eval/dev/labels/` and `data/eval_private/dev/labels/` for the 14 documents (item structure, citations, kinds, flags; no text printed). Code read: `eval/hybrid.py` (classify, subcause, write_diagnostic), `eval/run.py`, `eval/silver/compare.py` (`score`), `eval/silver/agree.py` (list rule), `core/shiori_core/extract/llm.py` (`read_items`, `_check`, `_deadline_when`), `core/shiori_core/fields.py` (`DeadlineItem`).

Counts reproduced: Qwen 27 wrong, 10 right, 3 not found; Gemma 22 wrong, 10 right, 8 not found; diagnostic totals match for a, b, c, d, and extras on both models.

Could not explain:
- Why 10 rows fail only through extra answer items (5 per model). The label might lack the item, or the model over-produced. Needs a Japanese reader on those rows.
- Why Gemma emits no `datetime` on 53 deadline proposals (the trace holds the parsed-from-JSON item, not the raw model string, so I cannot see if it was an empty string or a missing key beyond "no key").
- Why Qwen omits 8 required_documents items that are in its window (category b) while Gemma finds them. I did not read the prompts or model output text.
- The Gemma `other` vs `certification` kind item, which the diagnostic counts as convention without a written reason.

The scratch script is at `/private/tmp/claude-501/-Users-yasharthsingh--claude-spares-spare-J9Vhjx/efaac7fe-3624-4e88-a32b-81ecabb40eb8/scratchpad/an.py`, outside the repo.
