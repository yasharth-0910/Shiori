# Phase 5 fix 3: eligibility proviso merge and 第73条 kind

Replay of the saved list-field traces (`data/cache/hybrid/trace_cmp_<model>.json`, one per model) through the current `core/shiori_core/extract/llm.py`. No model was started, no cloud call, no label, scorer, prompt, retrieval, deadlines code or `EXTRACTOR_VERSION` change; dev only (model-reviewed silver labels, D-41). Both columns replay the same saved proposals with fixes 1 and 2 on; "before" switches off only the two fix-3 functions, so the difference is fix 3 alone. The models' proposals are old saved answers, so this shows what the code change does to them, not what a new run would give. Every number is a fit to documents the prompts were tuned on.

- Change 1 (`_merge_provisos`): a sentence that starts with なお or ただし right after an eligibility item's last cited sentence is added to that item (text_ja joined with a line break, id added to citations). An item that cites only such a sentence is dropped (trace verdict `merged`). With no item before it the sentence stays as it was.
- Change 2 (`_kind`, D-71): an item whose text_ja starts with 予算決算及び会計令第73条 and holds 支出負担行為担当官が定める資格 gets kind other.

Rows: the saved traces cover 13 of the 14 labeled dev documents (5d75d4a67c71 was labeled after those runs). For Qwen3.5-9B, Gemma 4 E4B and Qwen3-Swallow-8B, 5d75d4a67c71 was run live twice (temperature 0, fix 3 off and on), so those three have 42 rows. The other five models have no usable GGUF in `models/`, so they stay at 39 rows (13 documents).

Item ids below are `doc8:cited ids:kind`; no document text.

## qwen35_9b

Documents: 14; list-field rows scored: 42 (eligibility 14). Includes 5d75d4a6 from a real run each way (`trace_cmp5dbefore_qwen35_9b.json`, `trace_cmp5d_qwen35_9b.json`): provisos merged 1, kind other set 2.

| count | before | after |
| --- | --- | --- |
| all list-field rows right | 10 of 42 | 14 of 42 |
| all list-field rows wrong value shown | 30 | 26 |
| all list-field rows not found | 2 | 2 |
| eligibility rows right | 1 of 14 | 5 of 14 |
| eligibility items: paired / label items / answer items | 55 / 84 / 76 | 57 / 84 / 71 |

Provisos merged: 9 (documents 136dfba9, 563042df, 58f13b9c, 594c3cb6, 6b7142ab, 84e9d0c8, a81e99fe, d230e51e, f19cddbd). Items set to kind other by the 第73条 rule: 4 (documents 136dfba9, 6b7142ab, f19cddbd). Rows whose right/wrong state changed: 4 (f19cddbd/eligibility, 84e9d0c8/eligibility, 563042df/eligibility, 5d75d4a6/eligibility).

Eligibility answer items that changed:

| before only | after only |
| --- | --- |
| 136dfba9:h_s46:legal<br>136dfba9:h_s54+h_s55:legal<br>563042df:h_s40:legal<br>58f13b9c:h_s40:legal<br>58f13b9c:h_s41:legal<br>594c3cb6:h_s39:legal<br>5d75d4a6:h_s34:legal<br>5d75d4a6:h_s35:legal<br>5d75d4a6:h_s38:legal<br>6b7142ab:h_s38:legal<br>6b7142ab:h_s42:legal<br>84e9d0c8:h_s42:legal<br>84e9d0c8:h_s43:other<br>a81e99fe:h_s42:legal<br>a81e99fe:h_s43:other<br>d230e51e:h_s40:legal<br>f19cddbd:h_s38:legal<br>f19cddbd:h_s39:other<br>f19cddbd:h_s43:legal | 136dfba9:h_s46+h_s47:legal<br>136dfba9:h_s54+h_s55:other<br>563042df:h_s40+h_s41:legal<br>58f13b9c:h_s40+h_s41:legal<br>594c3cb6:h_s39+h_s40:legal<br>5d75d4a6:h_s34+h_s35:legal<br>5d75d4a6:h_s38:other<br>6b7142ab:h_s42:other<br>84e9d0c8:h_s42+h_s43:legal<br>a81e99fe:h_s42+h_s43:legal<br>f19cddbd:h_s38+h_s39:legal<br>f19cddbd:h_s43:other |

## qwen35_4b

Documents: 13; list-field rows scored: 39 (eligibility 13).

| count | before | after |
| --- | --- | --- |
| all list-field rows right | 2 of 39 | 3 of 39 |
| all list-field rows wrong value shown | 36 | 35 |
| all list-field rows not found | 1 | 1 |
| eligibility rows right | 1 of 13 | 2 of 13 |
| eligibility items: paired / label items / answer items | 51 / 80 / 75 | 54 / 80 / 75 |

Provisos merged: 9 (documents 136dfba9, 563042df, 58f13b9c, 594c3cb6, 6b7142ab, 84e9d0c8, a81e99fe, d230e51e, f19cddbd). Items set to kind other by the 第73条 rule: 5 (documents 136dfba9, 594c3cb6, 6b7142ab, f19cddbd). Rows whose right/wrong state changed: 1 (136dfba9/eligibility).

Eligibility answer items that changed:

| before only | after only |
| --- | --- |
| 136dfba9:h_s46:legal<br>136dfba9:h_s54+h_s55:legal<br>563042df:h_s40:legal<br>58f13b9c:h_s40:legal<br>594c3cb6:h_s39:legal<br>594c3cb6:h_s44:legal<br>6b7142ab:h_s38:legal<br>6b7142ab:h_s42:legal<br>84e9d0c8:h_s42:legal<br>a81e99fe:h_s42:legal<br>d230e51e:h_s40:legal<br>f19cddbd:h_s38:legal<br>f19cddbd:h_s43+h_s39:unified_qualification<br>f19cddbd:h_s43:legal | 136dfba9:h_s46+h_s47:legal<br>136dfba9:h_s54+h_s55:other<br>563042df:h_s40+h_s41:legal<br>594c3cb6:h_s39+h_s40:legal<br>594c3cb6:h_s44:other<br>6b7142ab:h_s38+h_s39:legal<br>6b7142ab:h_s42:other<br>84e9d0c8:h_s42+h_s43:legal<br>a81e99fe:h_s42+h_s43:legal<br>d230e51e:h_s40+h_s41:legal<br>f19cddbd:h_s38+h_s39:legal<br>f19cddbd:h_s43+h_s39:other<br>f19cddbd:h_s43:other |

## gemma4_e4b

Documents: 14; list-field rows scored: 42 (eligibility 14). Includes 5d75d4a6 from a real run each way (`trace_cmp5dbefore_gemma4_e4b.json`, `trace_cmp5d_gemma4_e4b.json`): provisos merged 1, kind other set 1.

| count | before | after |
| --- | --- | --- |
| all list-field rows right | 11 of 42 | 13 of 42 |
| all list-field rows wrong value shown | 31 | 29 |
| all list-field rows not found | 0 | 0 |
| eligibility rows right | 3 of 14 | 5 of 14 |
| eligibility items: paired / label items / answer items | 53 / 84 / 69 | 56 / 84 / 66 |

Provisos merged: 9 (documents 136dfba9, 563042df, 58f13b9c, 594c3cb6, 6b7142ab, 84e9d0c8, a81e99fe, d230e51e, f19cddbd). Items set to kind other by the 第73条 rule: 2 (documents 6b7142ab, f19cddbd). Rows whose right/wrong state changed: 6 (f19cddbd/eligibility, 58f13b9c/eligibility, d230e51e/eligibility, 84e9d0c8/eligibility, 563042df/eligibility, 5d75d4a6/eligibility).

Eligibility answer items that changed:

| before only | after only |
| --- | --- |
| 136dfba9:h_s46:legal<br>563042df:h_s40:legal<br>58f13b9c:h_s40:legal<br>594c3cb6:h_s39:legal<br>594c3cb6:h_s40:legal<br>5d75d4a6:h_s34:legal<br>5d75d4a6:h_s38:legal<br>6b7142ab:h_s38:legal<br>6b7142ab:h_s42:legal<br>84e9d0c8:h_s42:legal<br>84e9d0c8:h_s43:legal<br>a81e99fe:h_s42:legal<br>a81e99fe:h_s43:legal<br>d230e51e:h_s40:legal<br>f19cddbd:h_s38:legal<br>f19cddbd:h_s43:legal | 136dfba9:h_s46+h_s47:legal<br>563042df:h_s40+h_s41:legal<br>58f13b9c:h_s40+h_s41:legal<br>594c3cb6:h_s39+h_s40:legal<br>5d75d4a6:h_s34+h_s35:legal<br>5d75d4a6:h_s38:other<br>6b7142ab:h_s38+h_s39:legal<br>6b7142ab:h_s42:other<br>84e9d0c8:h_s42+h_s43:legal<br>a81e99fe:h_s42+h_s43:legal<br>d230e51e:h_s40+h_s41:legal<br>f19cddbd:h_s38+h_s39:legal<br>f19cddbd:h_s43:other |

## qwen3_swallow_8b

Documents: 14; list-field rows scored: 42 (eligibility 14). Includes 5d75d4a6 from a real run each way (`trace_cmp5dbefore_qwen3_swallow_8b.json`, `trace_cmp5d_qwen3_swallow_8b.json`): provisos merged 1, kind other set 1.

| count | before | after |
| --- | --- | --- |
| all list-field rows right | 3 of 42 | 6 of 42 |
| all list-field rows wrong value shown | 30 | 27 |
| all list-field rows not found | 9 | 9 |
| eligibility rows right | 1 of 14 | 4 of 14 |
| eligibility items: paired / label items / answer items | 42 / 84 / 75 | 44 / 84 / 68 |

Provisos merged: 8 (documents 563042df, 58f13b9c, 594c3cb6, 6b7142ab, 84e9d0c8, a81e99fe, d230e51e, f19cddbd). Items set to kind other by the 第73条 rule: 3 (documents 6b7142ab, f19cddbd). Rows whose right/wrong state changed: 3 (f19cddbd/eligibility, 563042df/eligibility, 5d75d4a6/eligibility).

Eligibility answer items that changed:

| before only | after only |
| --- | --- |
| 563042df:h_s40:legal<br>58f13b9c:h_s40:legal<br>58f13b9c:h_s41:experience<br>594c3cb6:h_s39:experience<br>5d75d4a6:h_s34:legal<br>5d75d4a6:h_s35:legal<br>5d75d4a6:h_s38:legal<br>6b7142ab:h_s38:legal<br>6b7142ab:h_s39:legal<br>6b7142ab:h_s42:legal<br>84e9d0c8:h_s42:legal<br>84e9d0c8:h_s43:legal<br>a81e99fe:h_s42:legal<br>a81e99fe:h_s43:other<br>d230e51e:h_s40:legal<br>d230e51e:h_s41:other<br>f19cddbd:h_s38:legal<br>f19cddbd:h_s39:legal<br>f19cddbd:h_s43:legal | 563042df:h_s40+h_s41:legal<br>58f13b9c:h_s40+h_s41:legal<br>5d75d4a6:h_s34+h_s35:legal<br>5d75d4a6:h_s38:other<br>6b7142ab:h_s38+h_s39:legal<br>6b7142ab:h_s42:other<br>84e9d0c8:h_s42+h_s43:legal<br>a81e99fe:h_s42+h_s43:legal<br>d230e51e:h_s40+h_s41:legal<br>f19cddbd:h_s38+h_s39:legal<br>f19cddbd:h_s43:other |

## lfm25_12b_jp

Documents: 13; list-field rows scored: 39 (eligibility 13).

| count | before | after |
| --- | --- | --- |
| all list-field rows right | 1 of 39 | 1 of 39 |
| all list-field rows wrong value shown | 14 | 14 |
| all list-field rows not found | 24 | 24 |
| eligibility rows right | 1 of 13 | 1 of 13 |
| eligibility items: paired / label items / answer items | 5 / 80 / 31 | 7 / 80 / 30 |

Provisos merged: 1 (documents 58f13b9c). Items set to kind other by the 第73条 rule: 2 (documents 6b7142ab, f19cddbd). Rows whose right/wrong state changed: 0.

Eligibility answer items that changed:

| before only | after only |
| --- | --- |
| 58f13b9c:h_s36:suspension<br>58f13b9c:h_s37:suspension<br>6b7142ab:h_s42:suspension<br>f19cddbd:h_s43:suspension | 58f13b9c:h_s36+h_s37:suspension<br>6b7142ab:h_s42:other<br>f19cddbd:h_s43:other |

## lfm25_8b_a1b

Documents: 13; list-field rows scored: 39 (eligibility 13).

| count | before | after |
| --- | --- | --- |
| all list-field rows right | 3 of 39 | 3 of 39 |
| all list-field rows wrong value shown | 27 | 27 |
| all list-field rows not found | 9 | 9 |
| eligibility rows right | 1 of 13 | 1 of 13 |
| eligibility items: paired / label items / answer items | 8 / 80 / 40 | 11 / 80 / 37 |

Provisos merged: 5 (documents 136dfba9, 563042df, 6b7142ab, a13baaac, f19cddbd). Items set to kind other by the 第73条 rule: 2 (documents 594c3cb6, f19cddbd). Rows whose right/wrong state changed: 0.

Eligibility answer items that changed:

| before only | after only |
| --- | --- |
| 136dfba9:h_s46:experience<br>563042df:h_s40:legal<br>563042df:h_s41:legal<br>594c3cb6:h_s44:experience<br>6b7142ab:h_s38:unified_qualification<br>a13baaac:h_s38:legal<br>a13baaac:h_s39:legal<br>f19cddbd:h_s38:unified_qualification<br>f19cddbd:h_s39:other<br>f19cddbd:h_s43:suspension | 136dfba9:h_s46+h_s47:experience<br>563042df:h_s40+h_s41:legal<br>594c3cb6:h_s44:other<br>6b7142ab:h_s38+h_s39:unified_qualification<br>a13baaac:h_s38+h_s39:legal<br>f19cddbd:h_s38+h_s39:unified_qualification<br>f19cddbd:h_s43:other |

## nemotron_nano_9b_jp

Documents: 13; list-field rows scored: 39 (eligibility 13).

| count | before | after |
| --- | --- | --- |
| all list-field rows right | 3 of 39 | 3 of 39 |
| all list-field rows wrong value shown | 30 | 30 |
| all list-field rows not found | 6 | 6 |
| eligibility rows right | 1 of 13 | 1 of 13 |
| eligibility items: paired / label items / answer items | 26 / 80 / 45 | 25 / 80 / 41 |

Provisos merged: 8 (documents 563042df, 58f13b9c, 594c3cb6, 6b7142ab, 84e9d0c8, a81e99fe, d230e51e, f19cddbd). Items set to kind other by the 第73条 rule: 2 (documents 6b7142ab, d230e51e). Rows whose right/wrong state changed: 0.

Eligibility answer items that changed:

| before only | after only |
| --- | --- |
| 563042df:h_s40:legal<br>58f13b9c:h_s40:legal<br>58f13b9c:h_s41:other<br>594c3cb6:h_s39:legal<br>6b7142ab:h_s38:unified_qualification<br>6b7142ab:h_s42:unified_qualification<br>84e9d0c8:h_s42:legal<br>a81e99fe:h_s42:legal<br>a81e99fe:h_s43:other<br>d230e51e:h_s40:legal<br>d230e51e:h_s41:other<br>d230e51e:h_s45:legal<br>f19cddbd:h_s38:unified_qualification<br>f19cddbd:h_s39:legal | 563042df:h_s40+h_s41:legal<br>58f13b9c:h_s40+h_s41:legal<br>594c3cb6:h_s39+h_s40:legal<br>6b7142ab:h_s38+h_s39:unified_qualification<br>6b7142ab:h_s42:other<br>84e9d0c8:h_s42+h_s43:legal<br>a81e99fe:h_s42+h_s43:legal<br>d230e51e:h_s40+h_s41:legal<br>d230e51e:h_s45:other<br>f19cddbd:h_s38+h_s39:unified_qualification |

## sarashina22_3b

Documents: 13; list-field rows scored: 39 (eligibility 13).

| count | before | after |
| --- | --- | --- |
| all list-field rows right | 1 of 39 | 1 of 39 |
| all list-field rows wrong value shown | 0 | 0 |
| all list-field rows not found | 38 | 38 |
| eligibility rows right | 1 of 13 | 1 of 13 |
| eligibility items: paired / label items / answer items | 0 / 80 / 0 | 0 / 80 / 0 |

Provisos merged: 0 (documents none). Items set to kind other by the 第73条 rule: 0 (documents none). Rows whose right/wrong state changed: 0.

Eligibility answer items that changed:

| before only | after only |
| --- | --- |
| none | none |

## What I saw

Counts above come from this run of `uv run python -m eval.phase5_fix3_replay`. Why a changed item does or does not pair with its label item was not looked into beyond the counts.
