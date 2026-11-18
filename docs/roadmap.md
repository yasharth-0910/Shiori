# Roadmap

## Current phase

**Phase 5: Failure analysis and pipeline fixes, in progress (fixes 1 to 4 on the list fields, D-71, D-72). Phase 4 is mostly done: the harness, the pipeline and the dev model comparison exist; the Windows 16 GB run and the base-model decision entry are not done. Phase 3 is closed except the native-speaker audit and the test split labeling (both stay for the end; D-68).**

Update this line whenever a phase's exit criteria are met. Don't start the next phase's heavy work early, except where noted as parallel.

## Ground rules for the whole plan

- Each phase has exit criteria. A phase is done when those are met, not when the code "looks finished".
- Nothing in the app gets built on top of an unmeasured pipeline. Measure first, then build UI around what works.
- Yasharth has placement season and applications running through Oct 2026 (OIST deadline 15 Oct). Phases 0 to 2 are light enough to fit around that. Heavy work starts after.

---

## Phase 0: Repo setup

- [x] `pyproject.toml` with uv, ruff, pyright, pytest configured
- [x] Package skeletons: `collector/`, `core/shiori_core/`, `eval/`, `training/`, `sidecar/` (empty `__init__.py` + README each)
- [x] `data/` layout from `data/README.md`, with `.gitkeep` files where needed
- [x] `.gitignore` confirmed (raw PDFs, models, venvs, node_modules ignored)
- [x] Import-boundary test: fails if `core/` or `sidecar/` imports from `collector`, `eval`, `training`, or any cloud SDK (`anthropic`, `openai`, `google`, `requests` to non-localhost is checked later in privacy tests)
- [x] CI-free is fine for now; `uv run pytest` passing locally is the bar

**Exit:** `uv sync && uv run pytest` passes on the Mac.

## Phase 1: Collect public tenders

Goal: a real, varied corpus of Japanese tender PDFs with clean provenance.

- [x] Verify each source in `docs/sources.md` is reachable and note how documents are linked (direct PDF, listing page, search UI)
- [x] Write `collector/` scripts per source, following the etiquette in `CLAUDE.md`
- [x] Target corpus: **150 to 200 documents** across **at least 15 issuing organizations**, including:
  - [x] National ministries and agencies (調達ポータル linked notices, ministry procurement pages)
  - [x] At least some IT/system procurement (システム, 運用保守, 開発 in the title). These matter most for the software-vendor use case
  - [x] Local governments (prefectures, designated cities) for format variety
  - [x] WTO-covered notices that have a JETRO English counterpart (useful cross-check, see sources.md). Met through D-26: the English Summary inside p-portal WTO notices
  - [x] ~~At least 15 scanned (image-only) PDFs~~ Replaced by D-23: no scans turned up in current tenders. Keep any real image-only or outlined-text PDF found (one so far, Toyama) for the OCR test set
  - [x] Bundles where possible: 入札公告 + 入札説明書 + 仕様書 for the same tender
- [x] Manifest rows for every file (`data/manifests/documents.jsonl`)
- [x] `collector/report.py` prints corpus stats: docs per org, per doc type, text-layer vs scanned, page count distribution
- [x] Spot-check 10 random files open correctly and match their manifest rows

**Exit:** corpus stats report committed to `data/manifests/corpus_report.md` and meets the targets above.

Closed 2026-10-02: 519 documents, 37 organizations, 21 of them with 5+ documents (target read as 15 orgs with 5+ each), 47 complete bundles, 224 IT documents by D-27. The JETRO item is met through D-26: 46 WTO notices from p-portal, 38 with the English Summary inside the notice. Spot check in corpus_report.md.

## Phase 2: Extractor (PDF -> sentences with IDs and boxes)

This comes before labeling because labels point at sentence IDs.

- [x] `core/shiori_core/ingest`: open PDF, detect text layer vs scanned per page
- [x] Text-layer extraction with character-level bounding boxes
- [x] OCR path for scanned pages (NDLOCR-Lite first, PaddleOCR as fallback), line-level boxes (D-36: NDLOCR-Lite works, no fallback needed)
- [x] Rendered-scan OCR test set (D-23): render pages of text PDFs to images, keep their text layer as ground truth, plus the real image-only/outlined-text PDFs found in Phase 1. Script it so it can be rebuilt (`eval/ocr_report.py`, 200 pages at 200 dpi, clean and degraded; one DPI, not several)
- [x] Header/footer removal (page numbers like "- 3 -", repeated org names)
- [x] Normalization with offset map (see japanese_rules.md section 1)
- [x] Segmentation into sentences/items with stable IDs (`p{page}_s{n}`)
- [x] Section parser for 公用文 numbering (第1 / 1 / (1) / ア / (ア)) so each sentence knows its section path
- [x] Debug renderer: `uv run python -m shiori_core.debug_render <doc_id>` writes a PDF/PNG with every sentence box drawn and labeled
- [x] Tests on at least 5 real documents, including 1 rendered or outlined-text page (D-23) and 1 with tables
- [x] HTML ingest for p-portal notices and tender pages, sentences anchored by character offsets (D-37)
- [x] English Summary handling: `Sentence.language`, Summary heading path only (D-37)

**Exit:** debug renders for 20 random docs look right (boxes on the right text, sensible sentence breaks, section paths correct). Extraction failures are logged by type in `docs/decisions.md` open questions.

Closed 2026-10-02: Yasharth checked the debug renders. Every box above is ticked; limits found are in the open questions (A3 pages, diagram text, OCR digit and era misreads).

## Phase 3: Labeling and eval set

Labels are silver, not gold. Yasharth reads Japanese at beginner level, so no label he checks counts as human-verified. The provenance states (D-41) say what each label has been through; only a native speaker's review makes a label `human_audited`.

Part A: schema, splits, formats (no cloud calls, no labeling)
- [x] Field schema frozen as 1.0.0 in `docs/field_schema.md` and `core/shiori_core/fields.py`, with a doc/code agreement test (D-39)
- [x] Label file format and validator (`eval/label_format.py`, `uv run python -m eval.validate_labels`), documented in `eval_protocol.md` and `data/README.md` (D-41)
- [x] Org-level split frozen in `data/eval/splits.json`, constraint checks in `data/eval/splits.md`, frozen-copy test (D-40)
- [x] Label set `data/eval/label_set.json`: 60 dev + 40 test documents, seeded and stratified, report in `data/eval/label_set.md` (D-40)
- [x] Decisions for the freeze, provenance, splits and seeds, cloud pre-labeling (D-39 to D-42)

Part B: labeling (needs cloud calls; check provider terms first, D-42)
- [x] `labeler` module: shows a document's sentences with IDs and writes label lines (`eval/silver/`; pilot run)
- [x] `silver_pipeline`: pre-label with two labelers, run the auto checks, set `agreement` (terms in D-42; run on the pilot and gold wave 1)
- [x] Model review (`claude_chat`, later `claude_code`) of disagreements and failed checks (pilot and gold wave 1)
- [ ] Yasharth's pass with the heading cues, normalized values and the English Summary (`review_note` only; does not change the state)
- [ ] Find a native speaker for a sample (open question); only their review gives `human_audited`
- [ ] 60 dev + 40 test documents labeled for all 23 v1 fields, all files passing `eval.validate_labels` (not done: D-61 replaced it with the gold set, and D-68 stopped it at 9 reviewed documents; the test split is labeled at the end)
- [ ] Translation subset: ~300 sentences with reference English, for hover translation scoring

Part C: pipeline v2 from the pilot review (D-46, D-47; no labeling calls)
- [x] Text fields accept `see_other_document` with a ref; F-0029 imported
- [x] `docs/labeling_guide.md`, sent in the sv2 prompt
- [x] Providers run independently; one ledger for every request; backoff and `provider_unavailable`
- [x] Per-field strict schema, field groups for Groq, chunk merging, ellipsis tolerance, cue fix
- [x] Agreement relaxations replayed on the 37 reviewed items; 3 switched on
- [x] Review export with C and `mapping.json`; `reviewed_choice`; `review-stats`; pilot mapping recovered
- [x] sv2 pilot: 28ad40ea4b1f and 4c40bbd831fe for real, the 3 reviewed documents in comparison mode (`eval/reports/silver_pilot_sv2.md`, D-48)
- [x] Answer F-0022 (563042df9941 notice_date) so that document's label file can be written (answered absent, `pilot-extra2.txt`)

Part D: pipeline v3 from the sv2 pilot (D-49 to D-51)
- [x] Gemini in JSON mode, forms generated from `fields.py`, one shape repair request through the ledger
- [x] Second labeler: local Qwen3.5-9B on every document; Groq only for restricted and unknown documents; `labeler_overlap` on every Qwen-assisted label; `--local-fallback` removed
- [x] Local model: output cap 8,192 bounded by the context, field groups under 60% of it, truncations recorded and not retried
- [x] Groq: `json_validate_failed` part retried once as two half field groups
- [x] Labeling guide sv3: org rule for local bodies (教育庁 is a department), answer forms
- [x] 4c40bbd831fe: delivery_deadline reopened with Qwen's answer as C (`reopen`); F-0039 still flagged
- [x] sv3 pilot: 28ad40ea4b1f for real, the 3 reviewed documents in comparison mode (`eval/reports/silver_pilot_sv3.md`, D-51)
- [x] Decide on a shape repair for the local model (it left `normalized` null on 2 of 4 pilot documents): D-52, plain message D-53
- [x] Review the exported flags of 28ad40ea4b1f and 4c40bbd831fe (F-0039 last, `pilot4.txt`; all 5 pilot label files validate)

Part E: sv4 and review in Claude Code (D-54, D-55; no labeling calls)
- [x] Prompt sv4 for every labeler: the pending guide rules, the client-organization rule for issuer_org and the contact vs delivery place rule in the prompt; one grouped local call, focused calls behind `--local-focused`; repair message for a present entry with no citations
- [x] Each pre-labeler records its own prompt version
- [x] Reviewer `claude_code`, `docs/review_session.md`, UNSURE notes listed on import, `calibrate`
- [x] Dev run plan and review-item projection (`eval/reports/dev_run_plan_sv4.md`)
- [ ] Dev run (after Yasharth's go-ahead): the 5 pilot documents first as an sv4 gate, then the daily selections of the plan
- [ ] Calibrate the first Claude Code batches against a chat review of the same batch

**Exit:** all label files pass the validator, and a second pass over 10 random documents finds fewer than 5% label errors (a native speaker if one is found, otherwise a different model, reported as silver). Silver cloud labels are not LoRA targets until D-10 is resolved.

## Phase 4: Baseline benchmark and model choice

- [x] Eval harness (`eval/run.py`): runs pipeline config on a split, writes JSON + markdown report
- [x] Extraction pipeline v0 (candidate retrieval by heading cues + LLM extraction with JSON-schema constrained output + deterministic normalization + citation verification)
- [x] Run 5 to 7 candidate models from `docs/sources.md` on **dev** (list fields, 8 models plus Qwen3.5-4B and Gemma 4 E4B in D-70; `eval/reports/model_compare_list_fields.md`)
- [ ] Record per model: verified field accuracy, citation precision/recall, hallucination rate, latency per doc, peak RAM, model file size, license (partly: accuracy, wall time and license are recorded for the list fields; the full table, peak RAM included, is not confirmed)
- [ ] Run the best 2 on Windows 16 GB CPU-only (borrow a machine if needed) for latency

**Exit:** a decision entry in `docs/decisions.md` naming the base model, with the benchmark table attached.

## Phase 5: Failure analysis and pipeline fixes

- [ ] Categorize every dev-set error (list fields done in `eval/reports/phase5_design_review.md` and the wrong-value report; the other fields not) (extraction, segmentation, retrieval miss, model misread, normalization, verification false reject)
- [ ] Fix the non-ML causes first (rules, retrieval, prompts, glossary) (fixes 1 to 4 done on list fields: unpaired deadlines, required_documents prompt line, eligibility proviso and 第73条 kind, same-sentence deadline copies; more are open)
- [ ] Re-run dev after each change; keep a changelog of score movements in the report folder (`eval/reports/phase5_fix*`; fixes 3 and 4 are replays on saved traces, not new model runs)

**Exit:** two consecutive changes give under 1 point of improvement, meaning the cheap fixes are exhausted.

## Phase 6: LoRA fine-tuning

- [ ] Build training set from **train split only**: numbered sentences -> JSON fields with sentence IDs
- [ ] Check data provenance and terms (see decisions.md) before using any cloud-model-generated targets for training
- [ ] Train with `mlx-lm` on the Mac (fallback: Colab/Kaggle GPU)
- [ ] Merge adapter, convert to GGUF, quantize (Q4_K_M first)
- [ ] Evaluate quantized model on dev, then run test once for the milestone

**Exit:** fine-tuned quantized model beats the best baseline on dev by a margin worth the effort (aim for 5+ points verified field accuracy), and test confirms it.

## Phase 7: Desktop app MVP

Can start in parallel once Phase 2 is done, using gold labels as fake model output, because the viewer and highlight logic don't depend on the model.

- [ ] Electron shell, React renderer, strict CSP, contextIsolation on, nodeIntegration off
- [ ] Main process spawns sidecar and llama-server on 127.0.0.1 with random ports and a session token
- [ ] PDF.js viewer with highlight overlay from stored boxes
- [ ] Fields panel: English value, status (verified / not found), citation chips
- [ ] Click citation -> jump to page, highlight, show original Japanese + on-demand English for that sentence
- [ ] Executive summary panel generated from verified fields only
- [ ] Progress reporting while a document processes

**Exit:** a full tender processes end to end on the Mac with Wi-Fi off, and on a Windows 16 GB laptop.

## Phase 8: Privacy hardening and packaging

- [ ] Everything in the `docs/privacy.md` checklist passes
- [ ] Encrypted per-document storage, crypto-shred delete, ephemeral mode
- [ ] Network activity screen
- [ ] Packaging: sidecar via PyInstaller, llama-server binaries per OS, signed builds if possible
- [ ] License review of every shipped component (PyMuPDF decision must be settled here)
- [x] Replace real examples from restricted documents in the working tree with open-license ones: `uv run python -m eval.repo_scan --tree-only --public` exits 0 (D-64). Not yet done: drop the git history (fresh repo, D-64), after which plain `--public` must exit 0 and the 15 history-only `known_debt` entries are deleted. The repo is not made public before that (D-60, D-64)
  - Progress: the two Funabashi collector fixtures and `tests/test_collector_run.py` now hold invented text only (working tree scans clean). Known debt is still 16 entries / 25 (file, doc) pairs, because the scan also reads git history and the old blobs of those files are still in it. Those entries go stale only after a commit and a history rewrite (or a fresh public repo).

**Exit:** privacy checklist all green, installers for Mac and Windows.

## Phase 9: Write-up and public benchmark

- [ ] Public README with real numbers and limitations
- [ ] Publish the eval set (public documents, labels, scripts) if source terms allow
- [ ] Short technical write-up / blog post
- [ ] Demo video (Wi-Fi off, process a tender, click through citations)

## Later (not v1)

- More document types: contracts (契約書), meeting minutes, emails
- Korean and German adapters on the same pipeline
- MCP server exposing the local document store to other local tools
- Agentic workflows (compare two tenders, draft a bid/no-bid checklist)
