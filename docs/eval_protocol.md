# Eval protocol

How quality is measured. The point is that every number in a README, report, or interview answer can be traced back and defended.

## Splits

Documents are split by **issuing organization**, not randomly.

Why: one ministry reuses the same notice template for years. If its documents land in both train and test, the model just memorizes the template and the test score looks great but means nothing for unseen agencies. Splitting by organization tests what actually matters: a new agency's documents.

| Split | Share of orgs | Used for |
|---|---|---|
| train | ~60% | LoRA training data, few-shot examples |
| dev | ~20% | all iteration: prompts, thresholds, model choice |
| test | ~20% | milestone reports only |

Rules:
- The split assignment lives in `data/eval/splits.json` (org -> split), is committed, and is frozen (D-40): `tests/test_splits.py` fails if any org changes. The constraint checks are in `data/eval/splits.md`. The documents to label are in `data/eval/label_set.json` (60 dev, 40 test). Never move an org between splits without a decision entry.
- Test labels live in `data/eval/test/` and `data/eval_private/test/` (see Labels). Claude Code never edits them and never looks at test outputs while tuning.
- Test is run at most once per milestone (end of Phase 4, end of Phase 6, release). Each run is logged in decisions.md.

## Labels

One JSONL file per document, **one line per field per document** (all 23 v1 fields, exactly once; field list in `field_schema.md`):

- `data/eval/<split>/labels/<doc_id>.jsonl` for documents with `license_class` `open`. Committed.
- `data/eval_private/<split>/labels/<doc_id>.jsonl` for `restricted` and `unknown` documents. Gitignored, same layout (D-24). Labels hold source text (`value_ja`), and D-22 forbids redistributing text from these documents.
- `<split>` is the one `data/eval/splits.json` gives the document's org (frozen, D-40).

The harness reads both directories. `tests/test_eval_labels.py` fails if a label file in `data/eval/` belongs to a non-open document. The same split applies to translation pairs (`translation/`).

```json
{"doc_id": "2f2f5bd3...", "extractor_version": "0.3.0", "schema_version": "1.0.0",
 "field": "deadlines", "status": "present", "value_ja": null,
 "normalized": {"items": [
   {"kind": "bid_in_person", "datetime": "2026-10-27T14:00:00+09:00", "citations": ["p3_s30"]},
   {"kind": "mail_arrival", "datetime": "2026-10-26T17:00:00+09:00",
    "flags": ["arrival_required"], "citations": ["p3_s31"]}]},
 "value_en": "In person 27 Oct 2026 14:00; mail must arrive by 26 Oct 17:00",
 "citations": ["p3_s30", "p3_s31"],
 "provenance": {
   "pre_labelers": [{"provider": "...", "model": "...", "date": "2026-10-05", "prompt_version": "sv4"},
                    {"provider": "...", "model": "...", "date": "2026-10-05", "prompt_version": "sv4"}],
   "agreement": true,
   "auto_checks": [{"name": "citations_exist", "passed": true},
                   {"name": "date_roundtrip", "passed": true}],
   "reviewed_by": null, "review_note": null, "final_state": "silver_consensus"}}
```

(Sentence ids and values above are illustrative.)

Fields of a line:
- `field`, `status` (`present`, `absent`, `see_other_document`), `value_ja`, `normalized`, `value_en`, `citations`: as in `field_schema.md`. `absent` lines have no value and no citations. `see_other_document` lines carry `normalized: {"ref": {...}}` and the pointing sentence. Absent is labeled explicitly, including for fields that do not apply to the document's type, so hallucination can be measured.
- `citations`: Japanese sentence ids only, every sentence that supports the value; for list fields the union of the items' citations. English Summary sentences are never cited.
- `extractor_version`, `schema_version`: labels are tied to sentence ids (extractor) and field definitions (schema). The validator and the harness refuse mismatches. If the extractor changes, a migration script remaps IDs by text overlap and flags anything it can't remap; a schema change needs a decision entry and a relabel plan (D-39).
- `provenance`: see below.

### Provenance and label states

| `final_state` | what it means | allowed `reviewed_by` |
|---|---|---|
| `silver_unreviewed` | pre-labeled, maybe checked by Yasharth with the heading cues | null, `yasharth` |
| `silver_consensus` | two or more pre-labelers agree (`agreement` true), nobody reviewed it | null, `yasharth` |
| `silver_model_reviewed` | a model reviewed it, in chat or in a Claude Code review session | `claude_chat`, `claude_code` |
| `human_audited` | a native speaker reviewed it | `native_speaker` |

`prompt_version` is the version of the labeling prompt that made the pre-labels (`sv1` to `sv4`); since D-54 each `pre_labelers` entry also records its own labeler's version (`sv4`, or `sv4-l1` for the local model's focused calls), so a label whose labelers ran different versions says so, `reviewed_choice` says which candidate a reviewer took (a provider name, `union` for candidate C of a list field, or `custom`; null when not reviewed), and `labeler_overlap` is true when a local model contributed to the label: it voted in the consensus, or its answer was shown to the reviewer (D-45, D-50). Since sv3 the local Qwen3.5-9B is the second labeler on every document, so it is excluded from the Phase 4 model comparison or reported separately and clearly marked; the other models are reported with and without overlap lines. `agreement` is true when all pre-labelers gave the same normalized value, false when they differ, and null when there are fewer than two (it is set exactly when there are two or more). `auto_checks` record the code checks that ran, by name, with the result. `review_note` is free text: what was checked, what was doubtful.

**Only `native_speaker` review produces `human_audited`.** Yasharth reads at beginner level, so his check goes in `review_note` and does not change the state. Nothing except `human_audited` may be called human-verified in a report, README or write-up (D-41). Headline scores on silver labels are reported as scores against silver labels.

### How labels get made (given limited Japanese)

1. Pre-label with two labelers (public documents; provider terms recorded first, D-42): a cloud model (Gemini for open documents, Groq for restricted and unknown ones, which never go to Gemini) and the local Qwen3.5-9B (D-50). Each model and date goes into `pre_labelers`. Silver labels from cloud models are not LoRA targets until D-10 is resolved.
2. Auto checks in code: citations exist and are Japanese, normalized values re-run through the converters on the cited sentences, `value_ja` appears in its citations, the English Summary agrees where there is one (`en_summary_agrees`). Set `agreement`.
3. A model reviews disagreements and failed checks, state `silver_model_reviewed`: in a chat (`claude_chat`) or in a separate Claude Code session that follows `docs/review_session.md` and writes an answers file (`claude_code`, D-55). Either way it is a model review, not a human one. Items the reviewer could not decide confidently carry a note starting `UNSURE:`; import holds them (`answers/held-unsure.md`) for a second review instead of importing them. `calibrate` compares two reviewers' answer files for the same batch (agreement rate and every difference side by side); agreement between two model reviewers measures consistency, not correctness.
4. Yasharth checks fields using signals that don't need fluent Japanese, and records it in `review_note`:
   - heading cues from field_schema.md appear in or above the cited sentence
   - dates and amounts: run the normalizers himself and confirm the numbers match; weekday mismatches (D-38) are decided from context and noted
   - the English Summary on WTO notices, where present (D-26)
   - for OCR sentences, the page crop beside the text: OCR changes digits and eras (令和8年 read as 令和6年)
5. A native speaker reviews a sample (open question). Only that review gives `human_audited`.
6. Free-text fields (eligibility, scope) get extra care: these are where pre-labels are most likely wrong.

### Silver pipeline in short

`uv run python -m eval.silver plan` prices a run, `run --yes --max-calls N` labels, `export` / `import --reviewer claude_chat|claude_code` move doubtful fields through a model review. A field is accepted (`silver_consensus`) when both labelers agree and no blocking auto check fails; otherwise it is flagged. A seeded 5% of accepted fields is reviewed too, to estimate the silver error rate. Rules, thresholds and checks: D-43; provider policy: D-44, D-50; sv2 changes: D-46; sv3 (Gemini JSON mode with one shape repair, the local model as second labeler, Groq's half-split retry): D-49 to D-51; sv4 (one prompt and one grouped request for every labeler, per-labeler prompt versions): D-54; review in Claude Code: D-55. A Gemini repair request only fixes the answer's shape, never its content, so both labelers face the content checks on equal terms. A consensus later found doubtful can be reopened as a review item (`reopen`).

How a field is written when the facts are clear but the shape is not (officer title vs name, contact org vs department, which date is the notice date, quoting) is fixed in `docs/labeling_guide.md`; the same text goes into the labeling prompt, and the guide also prints the answer forms generated from `fields.py`.

A new prompt version is judged on documents that already have labels in comparison mode: each labeler's answers are scored field by field against those labels with the consensus agreement rule, by field type, and nothing is written. Those labels came from the earlier labelers plus a model review, so the comparison favors the labelers that made them, and the documents were used to write the guide; the numbers are optimistic and the report says so. Agreement may only be loosened by a rule that the replay of past reviews shows never accepts a wrong candidate (D-47, `uv run python -m eval.silver replay`); statuses, enums, dates and amounts are always compared exactly. In the review export, candidates are A and B without provider names (`export/mapping.json` keeps them), and list fields also get C, the union of both; a reopened item may show a third labeler's answer as C. `review-stats` reports how often each provider's candidate was right when shown.

### Validator

`uv run python -m eval.validate_labels [files]` checks every label file (default: all under `data/eval/` and `data/eval_private/`): each line against the schema and status rules; one line per field; `extractor_version` and `schema_version`; every citation exists in the document's sentences and is Japanese; a field outside the document type's `applies_to` is absent; normalized dates, times, arrival flags, rates, tax wording, category codes, grades, phone and email are readable in the cited sentences (the converters are re-run); and the D-24 path rule plus the split directory. It exits 1 on any error and prints field names and rule names, never document text.

## Metrics

Computed per field and overall (macro average over fields).

| Metric | Definition |
|---|---|
| **Verified field accuracy** (headline) | share of fields where the prediction is correct **and** at least one citation matches a gold citation. Absent gold + `not_found` prediction counts as correct |
| Value accuracy | value correct, ignoring citations |
| Citation precision | predicted citations that are in the gold set / all predicted citations |
| Citation recall | gold citations that were predicted / all gold citations |
| Hallucination rate | fields where gold is `absent` (including fields that do not apply to the document's type) but the system showed a `verified` value, plus fields shown as `verified` with a wrong value |
| Over-abstention rate | fields where gold is `present` but the system said `not_found` |
| Verifier false rejects | correct model outputs that the verifier rejected (tunes verifier strictness) |
| Latency | seconds per document, and per page, per machine |
| Peak RAM | whole app, per machine |

How "correct" is decided:
- dates, datetimes, amounts, enums, bools: exact match on the normalized value
- short text (title, org, location): normalized string match on `value_ja`, or fuzzy match above a set threshold (record the threshold)
- list fields (eligibility, required documents): item-level precision and recall, items matched by citation overlap plus text similarity; report F1
- `value_en` quality is not scored automatically for structured fields; it's spot-checked

Hallucination rate matters more than raw accuracy. A system that says "not found" too often is annoying; a system that shows a wrong deadline with a highlight is dangerous.

## Hover translation quality

Separate small benchmark: ~300 sentences from dev documents with reference translations.

- chrF via `sacrebleu`
- COMET (`Unbabel/wmt22-comet-da`) as the main number
- Plus a glossary consistency check: does the output use the section 5 renderings for terms that appear in the source

COMET models download from Hugging Face; that's a dev-time dependency and fine.

## Reports

Every run writes `eval/reports/<YYYY-MM-DD>_<config-name>/`:
- `report.json`: all metrics, per-field breakdowns, config, model file hash, prompt version, extractor version, git commit hash (read via `git rev-parse`, never created)
- `report.md`: human-readable summary and the 20 worst errors with sentence text
- `errors.jsonl`: every error, for Phase 5 categorization

Reports are never overwritten. Comparing two runs: `uv run python -m eval.compare <dir1> <dir2>`.

## Model benchmark table (Phase 4)

Each candidate gets one row:

| Model | Params | Quant | File size | License | Verified acc (dev) | Halluc. rate | Latency Mac | Latency Win CPU | Peak RAM |
|---|---|---|---|---|---|---|---|---|---|

Same prompts, same retrieval, same candidates per field for every model, so the comparison is fair. Then a second pass where each model gets its own tuned prompt, reported separately.
