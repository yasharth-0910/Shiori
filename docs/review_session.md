# Review session (Claude Code adjudicating export batches)

Instructions for a **separate** Claude Code session whose only job is to answer review batches written by `uv run python -m eval.silver export`. Yasharth starts the session, points it at this file and names one batch, for example `data/cache/labeling/export/batch-03.md`. The session's answers are imported by Yasharth with `--reviewer claude_code`, which gives `final_state` `silver_model_reviewed`, never `human_audited` (D-41, D-55).

Why a separate session: the session that builds the pipeline knows which labeler is which and what the code expects. The reviewer should see only what the batch shows (candidates A, B, C without provider names) plus the guide, so its answers measure the labels and not the pipeline.

## Read first, in this order

1. `docs/labeling_guide.md`, all of it: the rules between the `prompt` markers are the conventions every answer follows, and the examples show how they were applied.
2. The header of the batch file: the answer format (accept A, accept B, accept C, absent, custom) and the field forms used in the batch.
3. When a field's meaning is unclear: `docs/field_schema.md` (field definitions and heading cues) and `docs/japanese_rules.md` (dates, eras, tax wording, eligibility negation).

## How to answer

- Answer every item in the batch, one line per item, in the batch's format, and nothing else in the file. Item ids are `F-0001` style.
- Each item shows why it was flagged, the candidates with their automatic checks, and the cited sentences with two neighbours on each side. When that is not enough context, print the whole document (read-only): `uv run python -m eval.silver show <doc id prefix>`. A custom answer may cite any Japanese sentence id of the document.
- custom answers: `value_ja` is copied exactly from a cited sentence (no ellipsis, no rewording); `cites` lists every sentence that supports the value; `normalized` follows the field's form in the header; see_other_document always carries `normalized={"ref":{...}}`. Never put ` | ` inside a value.
- Write `note=` in plain English: which sentence ids decide it and why, so Yasharth (beginner Japanese) can follow the reasoning. `accept` lines may carry a note too (`F-0012 | accept A | note=...`).
- **UNSURE:** if you cannot decide an item confidently, still give your best answer, and start its note with `UNSURE:` followed by what is uncertain (the reading of a phrase, a case the guide does not cover, two rules that conflict, a value that depends on a document that is not given). Import does not import UNSURE lines: it holds them, with their items, in `data/cache/labeling/answers/held-unsure.md` and lists their ids, and Yasharth has them reviewed again in a chat. So UNSURE costs a second review; use it when it is warranted, not as a habit.
- Do not guess Japanese meaning silently. If a phrase could mean two things, say so in the note and mark the item UNSURE.

## Known labeler weaknesses

Candidates A and B carry no provider names, so these are patterns to check, not sides to distrust. Seen in the sv3 and sv4 pilots (`eval/reports/silver_pilot_sv4.md`). For these fields, check the answer against the rules in `docs/labeling_guide.md` and the cited sentences yourself instead of accepting the side that looks more complete.

- **spec_access:** one labeler (Gemini) tends to answer `present`, mode `public`, when the document only points to the spec or the bid instructions (仕様書による, 入札説明書による, 別紙「仕様書」のとおり). Under the guide that is see_other_document with the matching ref kind (F-0011, F-0012, F-0044).
- **award_method:** the same labeler tends to answer absent when a proposal and an estimate are scored together and the highest score wins. Under the guide that is best_value (F-0046). A committee selection with no scoring described stays absent (F-0015).
- **List fields (eligibility, deadlines, required_documents):** the other labeler (Qwen) often leaves them incomplete: items missing, an item citing one sentence of two, or a list given as absent. Compare every item with the cited sentences; a candidate C (the union) is often closer, but check that each of its items is real.
- **eligibility polarity:** since sv4 the same condition may be written as a requirement with the negation kept (…ないこと) or as a disqualification with it stripped; both are right (the agreement rule `eligibility_negation` treats them as equal). A disqualification whose text still keeps the negation is the inconsistent form: answer custom with one of the two consistent forms.

## Where the answers go

Write the answers to `data/cache/labeling/answers/<batch-name>-answers.txt`, for `batch-03.md` that is `data/cache/labeling/answers/batch-03-answers.txt`. If that file already exists, do not overwrite it: stop and tell Yasharth (export numbers batches from 01 each time, so an old file can carry the same name).

## What the session must never do

- Never edit code, docs, labels (`data/eval/`, `data/eval_private/`) or caches (`data/cache/`, `data/processed/`). The answers file above is the only file it writes.
- Never run `import`, or any `eval.silver` command other than `show`. Yasharth runs `uv run python -m eval.silver import <answers> --reviewer claude_code` himself.
- Never run git commands that write, and never call a labeling provider or any network service.
- Keep restricted-document text out of anything committed. The batch header line of each item says `license open`, `restricted` or `unknown`; text from a restricted or unknown document may appear only in the answers file (under the gitignored `data/cache/`) and in the chat, never in a file under `docs/`, `eval/reports/` or anywhere else in git (D-22, D-24).

## After the session (Yasharth)

```
uv run python -m eval.silver import data/cache/labeling/answers/batch-03-answers.txt --reviewer claude_code
```

Import is all or nothing: one malformed line or one custom answer that fails a hard check (schema, citations, value in citation) and nothing is written; the errors name the item ids, and the session can fix its file. To measure how far two reviewers agree on the same batch (for example a chat review and a Claude Code review, or two Claude Code sessions), before importing either:

```
uv run python -m eval.silver calibrate data/cache/labeling/answers/batch-03-chat.txt data/cache/labeling/answers/batch-03-answers.txt
```
