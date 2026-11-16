# CLAUDE.md

Instructions for Claude Code working in this repo. Read this file fully at the start of every session.

## What this project is

Shiori (栞, "bookmark") is a local, offline desktop app that reads Japanese public tender documents (入札公告, 仕様書, 入札説明書) and produces an English executive summary plus key fields (deadline, eligibility, budget terms, etc.). Every field links to the exact sentence it came from. Clicking a field opens the PDF at that page with the source text highlighted.

It is a solo project by Yasharth. He is learning Japanese (beginner level), so he cannot verify Japanese meaning by reading it. Design and report with that in mind.

Core ideas, in priority order:

1. Nothing leaves the user's machine. Ever.
2. Every extracted value must cite source sentences, and citations are verified by code before display. "Not found" is better than a wrong answer.
3. Small local model (under ~9B params, quantized), optionally LoRA fine-tuned on public tender data.
4. Measured, not vibes. Every model or pipeline change is judged against the frozen eval set.

## Hard rules

- **Never run `git commit`, `git push`, or anything that creates commits or tags.** Never add Claude as co-author anywhere. Yasharth handles all git operations himself. You may run `git status` and `git diff`.
- **The shipped app (`app/`, `sidecar/`, `core/`) must make zero network requests.** The only exception is the explicit first-run model download screen, which pins URLs and SHA-256 hashes. No telemetry, analytics, crash reporters, remote fonts, CDNs, or auto-update calls.
- **Never import dev-time code into the app.** `collector/`, `eval/`, `training/`, and any cloud LLM SDK stay out of `core/`, `sidecar/`, and `app/`. Add a test that fails if they do.
- **Never log document text.** Logs may contain event names, timings, page counts, sentence IDs, and error types. No content, no file paths of user documents.
- **Never edit `data/eval/test/` or `data/eval_private/test/`** or tune prompts, thresholds, or hyperparameters against the test split. Use `data/eval/dev/` for iteration. Test is run only for milestone reports.
- **Never split Japanese text on whitespace.** Read `docs/japanese_rules.md` before touching text processing.
- **Always keep the original text.** Normalized text is for matching only, and must carry an offset map back to the original characters so highlights land on the right glyphs.
- **Don't guess Japanese meaning silently.** If you are unsure what a phrase means or which field it belongs to, say so in your summary and add it to the Open questions section in `docs/decisions.md`.

## Standing rules for the labeling phase

- Never commit, and never run a git command that writes (no `add`, `commit`, `push`, `tag`, `reset`, `checkout` of files, `stash`, `merge`). `git status` and `git diff` are fine.
- `EXTRACTOR_VERSION` stays 0.3.0.
- Never touch `data/eval/test/` or `data/eval_private/test/`.
- Never print a key, and never write one into a log, a report or a file.
- Run cloud labeling calls only when Yasharth's message says to run them. A plan, a probe or a key check is not permission to start a run.
- Watch background jobs by process id, not by a command-line match (`pgrep -f`, `pkill -f`), so another job or a similar command is never mistaken for it or stopped by accident.
- Keep restricted-document text out of anything committed: reports, docs, decisions, tests and chat paste-ins that end up in files. Item ids, doc id prefixes, field names and counts are fine.
- End every report with what you actually saw (output, counts, files read), not what you will try next.

## Where things are

```
CLAUDE.md              this file
README.md              short project overview
docs/
  roadmap.md           phases, current phase, checklists, exit criteria  <- read first
  architecture.md      processes, data flow, data model
  modules.md           every module: purpose, inputs, outputs, status
  field_schema.md      the fields we extract, types, normalization, heading cues
  japanese_rules.md    Japanese text rules the pipeline must handle
  eval_protocol.md     how labeling, splits, metrics and reports work
  privacy.md           privacy design and the checklist the app must pass
  sources.md           where data, references, tools and models come from
  decisions.md         decision log (ADR style) + open questions
collector/             dev-time scripts that download public tenders
core/                  Python package `shiori_core`: the document pipeline
eval/                  eval harness, metrics, reports
training/              dataset builders and LoRA scripts
sidecar/               FastAPI server wrapping core for the desktop app
app/                   Electron + React + TypeScript desktop app
data/                  local data (mostly gitignored, see data/README.md)
models/                local model files (gitignored)
```

## How to work

1. Open `docs/roadmap.md`, find **Current phase**, and work only on that phase unless Yasharth asks for something else.
2. Read `docs/project_log.md` right after `docs/roadmap.md` at the start of every session.
3. Update `docs/project_log.md` whenever a plan changes, a fallback is taken, or something is dropped, and at the end of each phase.
4. Before writing code for a module, check its entry in `docs/modules.md`. Update the entry (status, interfaces) when you change it.
5. Any decision that affects architecture, licensing, privacy, or the eval protocol goes in `docs/decisions.md` as a new numbered entry.
6. Every Japanese rule you implement gets a unit test with a real example (ideally taken from a collected document, with the doc ID in the test name or comment).
7. End every task with a short plain-English summary: what changed, what to check manually, and anything uncertain. Yasharth needs to be able to explain every part of this project in an interview, so explain the why, not just the what. Keep it short.

## Stack and commands

- Python 3.12, managed with `uv`. Lint with `ruff`, type-check with `pyright` (basic), test with `pytest`. Use `pydantic` models for anything crossing a module boundary.
- Node 20+, TypeScript strict mode, Electron, React, Vite.
- Local inference: `llama.cpp` (`llama-server`) with GGUF models. LoRA training on Mac: `mlx-lm`.
- Dev machine: MacBook Air M4, 24 GB RAM. The app must also run on Windows laptops with 16 GB RAM and no GPU. Don't pick anything that only works on Apple Silicon for the shipped app.

```
uv sync                         # install python deps (dev tools included)
uv sync --all-groups            # also the collector group (httpx, bs4); pymupdf is a runtime dep (D-28)
uv run pytest                   # tests
uv run ruff check . && uv run ruff format .
uv run pyright                  # type check (basic mode)
uv run python -m collector <source> --limit N [--bundles N] [--dry-run]   # sources: digital + collector/sources/sites.py
uv run python -m collector.report                         # writes data/manifests/corpus_report.md
uv run pytest tests/test_security_static.py               # static security rules on core/, sidecar/, app/ (ast, no execution; D-65, docs/threat_model.md)
uv run pytest -m corpus                                   # only tests that read data/raw/ (skipped when files are missing)
uv run python -m shiori_core.debug_render <doc_id|path>   # sentence boxes as PNGs in data/processed/<doc_id>/debug/ + sentences.txt
uv run python -m eval.extraction_report                   # writes data/manifests/extraction_report.md + sample renders
uv run python -m eval.segmentation_report                 # writes data/manifests/segmentation_report.md + review sample (sentences.txt, renders)
uv run python -m eval.ocr_report                          # writes data/manifests/ocr_report.md: CER on 200 rendered pages (clean, degraded) + real scanned pages (about 15 min)
uv run python -m eval.splits                              # writes data/eval/splits.json + splits.md (frozen, D-40; fails if constraints break)
uv run python -m eval.label_set                           # writes data/eval/label_set.json + label_set.md (seed 20261003; first run reads every document, OCR included)
uv run python -m eval.validate_labels [files]             # checks label files against schema 1.0.0 and the documents
uv run python -m eval.silver plan [--pilot | --split dev|test] [--open-only]   # calls, tokens, requests left today; no API calls
uv run python -m eval.silver run --pilot|--split dev|--docs <ids> --yes --max-calls N   # labels (prompt sv4): Gemini (open) or Groq (restricted) + local Qwen3.5-9B, one grouped call each (cloud calls, needs the go-ahead); resumes from data/cache/labeling/; documents with labels only get compared (eval/reports/silver_pilot_sv4.md); max-calls counts local requests and retries too; a provider at its daily cap stops for the day, the rest goes on, and the next day's same command resumes (D-56)
uv run python -m eval.silver --local-focused <command> ...   # local labeler asks list fields and contact one per call (version sv4-l1, cached apart); give it to every command that reads those answers
uv run python -m eval.silver shadow --docs <ids> [--model <gguf>]   # local model, same prompt, raw cache only (no labels, no flags)
uv run python -m eval.silver report --docs <ids> [--notes F]   # rebuild eval/reports/silver_pilot_<prompt>.md from the caches (no API calls)
uv run python -m eval.silver repair --docs <ids> [--model <gguf>]   # shape check + one repair request on cached local answers (D-52; local only, no full re-run)
uv run python -m eval.silver resolve --docs <ids>         # resolve from the raw cache alone (no provider is made, no request)
uv run python -m eval.silver reopen <doc> <field> --reason "..." [--label] [--reviewed] [--with <model|gemini|groq>[@<prompt>]]   # accepted consensus back to a review item (--label: the label itself as A; --reviewed: a reviewed line, new item id); a written label file changes only when the review is imported
uv run python -m eval.gold_select                  # writes data/eval/gold_set.json + eval/reports/gold_set.md: 20 open dev documents in waves (seed 20261016, D-61); no API calls
uv run python -m eval.model_loadcheck [--link qwen3.5:4b gemma4:e4b] [gguf ...]   # does llama-server load each GGUF and answer one short request; one server at a time; writes eval/reports/model_loadcheck.md
uv run python -m eval.rules_v4_report   # writes eval/reports/rules_v4_side_by_side.md: rules before and after the six v4 fields on the 14 labeled dev documents (dev only, no model, fits not forecasts)
uv run python -m eval.run --split dev --extractor rules   # same harness with the rules-only extractor (core/shiori_core/extract/rules.py); dev only, no model, no cloud call
uv run python -m eval.run --split dev --extractor stub   # Phase 4 harness: scores an extractor on the dev documents with label files, writes eval/reports/run_<name>.json + .md (stub = not-found everywhere, the floor); dev only, no cloud call
uv run python -m eval.run --split dev --extractor hybrid [--docs <id prefixes>]   # rules + local Qwen3.5-9B for eligibility, deadlines, required_documents (D-69); starts and stops one llama-server on 127.0.0.1:8792, refuses if another runs; also writes eval/reports/hybrid_<name>.md; dev only, no cloud call; scores are a fit to the 9 tuning documents
uv run python -m eval.hybrid --unlabeled N   # same extractor on N unlabeled open dev documents, prints the first 3 items of each list to the terminal only
uv run python -m eval.hybrid --diagnose NAME | --freeze NAME   # rewrite a finished hybrid run's diagnostic from data/cache/hybrid/trace_NAME.json (no model) | write eval/reports/hybrid_freeze_NAME.md (file hashes, prompt hashes, settings)
uv run python -m eval.bakeoff --plan                          # local labeler bake-off on the 5 pilot documents: models, requests, estimated hours; no request
uv run python -m eval.bakeoff --yes --max-calls N              # real run, one model at a time, resumes from the per-model cache; stop with data/cache/labeling/STOP; writes eval/reports/local_labeler_bakeoff.md (local only, no cloud call)
uv run python -m eval.repo_scan [--public] [--tree-only]   # secrets, forbidden paths and restricted text in the repo and its history; known debt passes unless --public; --tree-only skips history (does not cover it, D-64); repo may go public only on fresh history with --tree-only --public at 0 (D-64)
uv run python -m eval.silver daemon --gold --wave N [--plan] [--retry-failed]   # (--retry-failed asks the wave's failed parts again, D-66; a 401 stops that provider)  # one gold wave (D-62): prints the plan (no requests at all) unless --yes --max-calls N; Gemini + local within daily budgets, sleeps to the Pacific reset, stops on --max-calls, 3 failures in a row, battery (pauses) or data/cache/labeling/STOP; pid in daemon.pid; log in daemon.log; exports batch-wN-NN.md; imports nothing (cloud calls, needs the go-ahead)
uv run python -m eval.silver status                       # per document, per provider progress, usage today (failures by outcome)
uv run python -m eval.silver export --split dev [--open-only] [--docs <ids>]   # review batches + export/mapping.json in data/cache/labeling/export/
uv run python -m eval.silver import <answers.txt> [--reviewer claude_chat|claude_code]   # read the reviewer's one-line answers (all or nothing; accept A|B|C, absent, custom); UNSURE: lines are held in answers/held-unsure.md, not imported. Yasharth runs it
uv run python -m eval.silver calibrate <answers-a> <answers-b>   # two answer files for the same batch: agreement rate, differences side by side (writes nothing)
uv run python -m eval.silver show <doc>                   # a document's Japanese sentences, id | section | text (read-only; for review sessions, docs/review_session.md)
uv run python -m eval.silver review-stats [--answers <answers.txt>] [--out F]   # per provider and field type: how often its candidate was right
uv run python -m eval.silver replay [--out F] [--write-mapping]   # pilot review as a regression set: A/B mapping, review stats, agreement rules
uv run python -m eval.silver probe gemini|groq            # one tiny generation request (a cloud call; recorded in the ledger)
uv run python -m eval.silver keys                         # one list-models request per provider (GEMINI_API_KEY, GROQ_API_KEY in .env; recorded in the ledger)
git clone --depth 1 https://github.com/ndl-lab/ndlocr-lite models/ndlocr-lite   # OCR engine and models (D-36), once; needs an ASCII path
```

Add commands here as they become real. Remove ones that turn out wrong.

## Collector etiquette (phase 1 and onward)

- Only public pages. No logins, no CAPTCHA solving, no bypassing anything.
- Check `robots.txt`. At most 1 request every 3 seconds per host. Set a descriptive User-Agent with a contact email (ask Yasharth for it). The collector reads it from `SHIORI_CONTACT_EMAIL` (environment or `.env`, see `.env.example`) and refuses to run without it; never write an address into the repo.
- Cache everything; never re-download a file whose SHA-256 is already in the manifest.
- Every downloaded file gets a manifest row (schema in `data/README.md`). A file without a manifest row doesn't exist as far as the pipeline is concerned.
- PDFs live in `data/raw/` and are never committed. Manifests are committed.
- Verify a URL works before writing a scraper around it. Government sites change layout often; prefer stable listing pages and direct PDF links.

## Licensing awareness

Before adding a dependency or model to `core/`, `sidecar/`, or `app/`, note its license in `docs/decisions.md`. Known watch items: PyMuPDF is AGPL-3.0, Llama-derived models (some Swallow versions) use the Llama community license, Gemma has its own terms, JParaCrawl is research-only. Dev-time tools in `eval/` and `training/` are less sensitive but still note them.

## Style

- Plain, direct English in docs and comments. No hype words, no emoji, no em dashes.
- Small functions, explicit names, type hints everywhere.
- Prefer deterministic code over LLM calls whenever a rule can do the job (dates, amounts, section numbering).
