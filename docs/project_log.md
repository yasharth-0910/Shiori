# Project log

What actually happened against the plan in `docs/roadmap.md`, one section per phase. Read it right after the roadmap. Update it when a plan changes, a fallback is taken, or something is dropped, and at the end of each phase.

Rules for this file: every line cites a decision number (D-NN, `docs/decisions.md`) or a file. A line that could not be confirmed from those files says "not confirmed". Phases 0 to 3 were written on 2026-11-16 from `docs/decisions.md` (D-01 to D-68), `docs/roadmap.md`, `eval/reports/` and `data/manifests/` only. No label file, cache or code was read to write it.

---

## Phase 0: Repo setup

### Achieved
- All six checklist items ticked, exit is `uv sync && uv run pytest` passing on the Mac (roadmap, Phase 0).
- Import-boundary test exists: fails if `core/` or `sidecar/` imports `collector`, `eval`, `training` or a cloud SDK (roadmap, Phase 0; D-12).
- Founding decisions D-01 to D-07 recorded: separate from Klaro, extraction with citations, model cites sentence IDs, every citation verified, v1 scope is public tenders, Electron + Python sidecar + llama.cpp, org-level split.

### Changed from the plan (what, why, decision number)
- pydantic added as the first runtime dependency; license noted as CLAUDE.md requires (D-11).
- httpx and beautifulsoup4 kept out of runtime dependencies, in a dev-only `collector` group; the boundary test was extended to fail if they appear in `[project].dependencies` (D-12).
- PyMuPDF put in a dev-only `research` group instead of runtime, because of AGPL-3.0 (D-13). This was reversed in Phase 2 (D-28).

### Fallbacks taken
- None recorded in the files.

### Missed or still open
- D-08 (PyMuPDF licensing) and D-09 (model download is the only network path) are still `Status: proposed`, not accepted (decisions.md).
- Whether the exit check was re-run after later phases: not confirmed.

### Lessons
- Dependency licenses and the runtime/dev split are decided at the moment a package is added, not later (D-11, D-12, D-13).

---

## Phase 1: Collect public tenders

### Achieved
- Closed 2026-10-02: 519 documents, 37 organizations, 21 of them with 5+ documents, 47 complete bundles, 224 IT documents under D-27 (roadmap, Phase 1; `data/manifests/corpus_report.md` line 5 says 519 documents, 37 organizations, 191 bundles).
- 46 WTO notices from p-portal, 38 with the English Summary inside the notice (D-26).
- 16 ZIPs, 160 members, 34 PDFs extracted after part D, with their own manifest rows (D-21).
- Spot check of 10 random files recorded in `data/manifests/corpus_report.md` (section at line 405).

### Changed from the plan (what, why, decision number)
- "15 orgs" was read as 15 organizations with 5+ documents each; the corpus has 21 (roadmap, Phase 1 closing note).
- GEPS bid documents declared out of scope, not downloaded by hand either, because they sit behind a contact-details form (D-15, building on D-14).
- Sites that forbid crawlers or block our User-Agent are skipped: Kanpo, 官公需情報ポータルサイト, Tokyo e-procurement, JPO (D-14, D-17).
- p-portal notices collected as HTML text, not PDF, so they get no page highlights (D-18). Tender pages whose HTML is the notice are saved as html notices (D-20).
- Restricted and unknown documents may be used locally on the basis of Copyright Act Art. 30-4 but never redistributed (D-22). Each document gets a license class (D-16). Labels for restricted documents live outside git (D-24).
- Scanned-PDF target (at least 15) dropped: 0 of 89 PDFs were raster scans; replaced by a rendered-scan OCR test set (D-23).
- JETRO English counterpart item replaced by the English Summary inside p-portal WTO notices (D-26).
- "IT" given one strict definition after the loose one tagged every p-portal notice as IT: 224 of 503 documents, ZIPs not counted (D-27).
- p-portal notices filed under the 調達機関, original notice only (D-25).

### Fallbacks taken
- JETRO cross-check replaced by the English Summary (D-26).
- Real scans replaced by rendered text pages plus the few real image-only or outlined PDFs found (D-23).
- Restricted local-government documents used locally under Art. 30-4 so that the corpus can reach enough organizations for an org-level split (D-22).

### Missed or still open
- `jetro_ref` is empty in the manifest; JETRO's search returned 403 and its terms forbid reuse (D-26).
- Whether JPO's 403 is a bot block or an IP block: unresolved (decisions.md open questions).
- 気象庁 / 気象衛星センター name merge: only needs doing if p-portal ever brings 気象庁 notices (D-25, open questions).
- Four near-duplicate p-portal notices (高松国税総合庁舎 elevators): not decided (open questions).
- How often national versus local agencies use scanned PDFs: unanswered (open questions).
- doc_type cues in `collector/collect.py` were not checked by a Japanese reader (open questions).
- IT misses (ネットワーク, サーバ, ICT and others) and false hits (データ入力) are known and unfixed (D-27).

### Lessons
- Rendered pages are cleaner than real scans, so scores on them are an upper bound (D-23).
- IT counts depend on one fixed definition; change it only with a new decision (D-27).
- Collection rests on the site's robots.txt and terms, and a blocked site is skipped, not worked around (D-14, D-17).

---

## Phase 2: Extractor (PDF to sentences with IDs and boxes)

### Achieved
- Closed 2026-10-02: Yasharth checked the debug renders; every roadmap box is ticked (roadmap, Phase 2).
- 49,312 sentences over the corpus, 88% with a non-empty section path (D-32; `data/manifests/segmentation_report.md` line 15 shows 42,743, 88%).
- OCR with NDLOCR-Lite: character error rate 6.9% on clean and 6.8% degraded rendered pages (200 pages at 200 dpi), about 1 to 2 s per page (D-36; `data/manifests/ocr_report.md`).
- HTML ingest: all 181 HTML files in the corpus load (D-37).
- Value converters for dates, times, amounts, fiscal years, tax wording (D-33, D-38).
- Model feasibility on the dev Mac for eight GGUFs: speed, memory, JSON validity, not accuracy (D-34, `eval/reports/model_feasibility.md`).

### Changed from the plan (what, why, decision number)
- PyMuPDF moved from the dev-only group into runtime dependencies, behind one module `core/shiori_core/pdf/` (D-28).
- Boxes are stored in displayed-page coordinates and text comes from MuPDF with `TEXT_INHIBIT_SPACES` (D-29).
- Only page numbers and page-wide repeats are left out of sentences; repeated table headers stay in (D-30).
- Ruled tables come from `find_tables`, one-row tables ignored (D-31).
- NDLOCR-Lite chosen and PaddleOCR never downloaded, because NDLOCR worked (D-36; roadmap Phase 2 line on OCR).
- Whole-page "line" boxes are dropped before OCR text is used (D-36).
- HTML sentences anchored by character offsets; English Summary marked `en`, not parsed as Japanese (D-37).
- A date whose weekday disagrees now returns the date with a warning instead of no value (D-38, superseding part of D-33).
- Segmentation changes from review bumped `EXTRACTOR_VERSION` to 0.3.0 (D-37).

### Fallbacks taken
- PaddleOCR was the named fallback and was not needed (D-36).
- NDLOCR-Lite is loaded by adding its `src/` to `sys.path`, not installed as a package, because its pins (flet, reportlab, pypdf and others) are not needed (D-36).
- Lines are flagged, never deleted, so a wrong flag can be undone (D-29).

### Missed or still open
- Pages larger than A4 are not tiled for OCR: 24% CER on 10 such pages (D-36, open questions).
- Text inside diagrams, Gantt charts and screenshots is read badly or not at all (open questions).
- OCR misreads that still look valid: 令和8年 as 令和6年, 令和 as 昭和, 円 as 門 (D-36).
- NDLOCR-Lite with a Japanese install path on Windows: not tried (D-36, open questions).
- Two-column pages interleave (4 Okayama pages); vertical text is not joined into lines (D-32, open questions).
- A heading fused to its body (Hokkaido `p3_s9`) is not split; a weekday split from its date by `<br>` is not joined (open questions).
- Mixed pages are not OCR'd; 3 of 10 hold text outside the text layer (open questions).
- PyMuPDF AGPL-3.0 licensing is unresolved; it must be settled before Phase 8 (D-08, D-28).
- Speed numbers for models are from one run and a Mac CPU, optimistic for a Windows laptop (D-34).

### Lessons
- MuPDF's default inserted spaces were the cause of the `1 6 日` case; the flag fixed it, so any replacement backend must reproduce it (D-29).
- Model output must be treated as untrusted: invented IDs, rewritten quotes, contradictory fields were all seen (D-34).
- A wrong value that still looks plausible is the failure to fear from OCR (D-36).

---

## Phase 3: Labeling and eval set

### Achieved
- Field schema 1.0.0 frozen with 23 fields, with a doc/code agreement test (D-39). Splits frozen (37 orgs: train 21, dev 8, test 8) (D-40). Label provenance states defined (D-41).
- Silver pipeline built in `eval/silver/`: two labelers, auto checks, agreement rules, review export and import (D-43 to D-47, D-49 to D-59).
- Pilot: 5 documents labeled and reviewed (roadmap Part C, D; `eval/reports/silver_pilot_*.md`).
- Gold wave 1: 4 of 5 documents labeled, reviewed and imported. The gold set is now 9 reviewed label files in `data/eval/dev/labels/` (D-68).
- Local labeler bake-off on the 5 pilot documents: Qwen3.5-9B tier 1 fields 30 of 40, Qwen3-Swallow-8B 19 of 40, LFM2.5-8B-A1B 5 of 40, LFM2.5-1.2B-JP 3 of 40, Gemini sv4 reference 32 of 40 (D-67, `eval/reports/local_labeler_bakeoff.md`).
- Security baseline: threat model and static tests (D-65). Scan tooling for restricted text (D-60, D-64).

### Changed from the plan (what, why, decision number)
- 60 dev + 40 test documents became the gold-first plan: 20 open dev documents in waves of 5, tier 1 fields always reviewed (D-61), then stopped at 9 reviewed documents; waves 2 and 3 not run (D-68). The 60 + 40 labeled-set line in the roadmap is still unchecked (roadmap Part B).
- Second labeler: Groq replaced by the local Qwen3.5-9B on every document; Groq kept only for documents Gemini may not see (restricted, unknown) (D-50). Gold waves never use Groq (D-62). Groq's 8,000 tokens a minute and 200,000 a day made it the bottleneck, and its candidate was right 10 of 37 times against Gemini's 29 of 37 in the sv1 pilot review (D-50). Later, the cloud labeler left the roadmap altogether; the code stays unused (D-68).
- Gemini: strict schema refused with HTTP 400, so it moved to JSON mode with one repair request (D-48, D-49). Its quota day is Pacific, and failed requests count against 20 a day (D-57). Capped at 3 tries per request (D-58).
- Reviewer moved from a chat to Claude Code, `reviewed_by: claude_code`, still never `human_audited` (D-55).
- Prompt frozen as sv4 for the whole run after the gate (D-58). The gate bar was 90% and Gemini got 85 of 96 (89%); it was declared passed in substance (D-58).
- A daily cap now stops one provider, not the run (D-56). The gold daemon was built to wait for quota resets (D-62, D-66).
- Repo going public: D-64 planned a fresh-history repo (old private repo stays private, `eval.repo_scan --tree-only --public` exits 0 first). The repo was rebuilt with fresh history as planned: the first commit is bb56b82 "Initial public commit" (`git log --oneline`, 2026-11-16) and the remote is origin https://github.com/yasharth-0910/Shiori.git (`git remote -v`). Whether the repo is public: no file in the repo says so, so this log does not state it. D-60 had earlier allowed pushing private with known debt.
- Local labeler stays Qwen3.5-9B, Qwen3-Swallow-8B is the non-overlap check (D-67).

### Fallbacks taken
- Gemini cap: 20 requests a day, 503s counted against it, daily-quota 429 hit on the first sv4 gate attempt (D-46, D-57). Fallback was waiting for the Pacific reset and the daemon sleeping to it (D-62).
- Gemini 503s on document `389a7520420c` on every retry on 2026-11-16 (5 of 7 requests that day). The document is parked, not relabeled; no label file exists (D-68).
- Groq parked: restricted-only after D-50, never used for gold (D-62), no longer a roadmap dependency (D-68).
- Local Qwen3.5-9B stands in as the second labeler, so every silver label carries `labeler_overlap` (D-50). Qwen3.5-9B is excluded from the Phase 4 model comparison or reported apart (D-50, open questions).
- Local shape repair: one repair request for empty `normalized` values (D-52, D-53).
- Gemini fix A (JSON mode) chosen over field groups (D-49).
- If more labeled documents are needed after Phase 5: two local voices from different families, or Claude Code reviewing every tier 1 field. Not decided yet (D-68).

### Missed or still open
- No native-speaker audit yet, so there are no `human_audited` labels. Yasharth reads at beginner level and his check does not change a label's state (D-41; roadmap Phase 3 lines on the native speaker; open questions).
- Every label is silver, reviewed by a model (`claude_chat` or `claude_code`), not verified truth (D-41, D-55).
- Silver error estimate: 6% (2 of 34 consensus spot-check items changed on review, n=34). Source: eval.silver status output, 2026-11-16, line "consensus spot-check: 34 reviewed, 2 changed (6% silver error estimate, n=34)". It is a model-reviewed estimate on a small n, not a human audit (D-41, D-43).
- Phase 3 exit (second pass over 10 random documents with under 5% label errors): not confirmed as run. The roadmap leaves the line unchecked.
- Test split labeling: not done, stays for the end (D-68; roadmap Part B).
- Translation subset of about 300 sentences: not started (roadmap Part B).
- Yasharth's pass over the labels (`review_note` only): not done (roadmap Part B).
- 60 + 40 labeled set: not done (roadmap Part B; D-68).
- PyMuPDF license unresolved (D-08, D-28; roadmap Phase 8).
- `known_debt` cleanup: 15 entries in `eval/repo_scan_allow.json` still match old history and are deleted only after the history is gone (D-64). The roadmap says dropping history is "not yet done" (roadmap Phase 8). Whether the fresh-history repo exists now: not confirmed.
- Windows 16 GB test: not run. All speed numbers are from the MacBook Air M4 (D-34, D-67; roadmap Phase 4).
- Qwen3.5-4B and Gemma 4 E4B were not in the bake-off (no standard GGUF); Nemotron Nano 9B JP was not run because `--max-calls 25` ran out first, and D-34 measured 0.6 tok/s for it on CPU (D-67; open questions follow-up bake-off).
- Pair agreement numbers, flag rate and wrong-accept numbers are not in the bake-off report (D-67).
- Local models got at most 1 of 12 list fields right; list fields are the first target for Phase 5 (D-67).
- Bake-off covers 5 documents, 3 from one Wakayama template family; it can rule models out but not rank close ones (D-67).
- 389a7520420c parked with no label (D-68). `gold_set.json` still lists 20 selected and 5 reserve documents, not the 9 reviewed (D-68).
- Splitter cuts dates and phone numbers across line breaks, so those labels carry less structure (open questions, 2026-11-16).
- Silver cloud labels are not LoRA targets until D-10's check of provider output terms is settled (D-42).

### Lessons
- A bar set without evidence behind the number (90%) had to be waived later (D-58).
- Provider quotas are per provider and have their own time zone; failures count (D-57).
- Rules written from the pilot make a comparison on the pilot optimistic (D-54).
- A local model's labels share its blind spots with the labels it helped make, so scores against them are optimistic (D-50, D-67).
- A small, fully reviewed set that can be defended beat a large silver set that was costing many quota days (D-61, D-68).
- Labeling that runs unattended needs hard stops written down first: `--max-calls`, STOP file, three failures in a row, battery (D-62).

---

## Phase 4: Baseline benchmark and model choice

### Achieved
- The eval harness `eval/run.py` exists. Its stub extractor (not found everywhere) gives the floor: 37 of 186 verified, tier 1 10 of 80.
- The rules-only extractor (`core/shiori_core/extract/rules.py`) exists and scores 84 of 186 verified, tier 1 42 of 80, on the 9 dev documents it was written from. That is not a generalization number.
- Still needed: a hold-out of reviewed documents the rules never saw, so the rules score can be read as more than a fit to those 9.
- Hybrid extractor built (2026-11-16, D-69): `core/shiori_core/extract/llm.py` answers eligibility, deadlines and required_documents with local Qwen3.5-9B, rules answer the rest, `eval.run --extractor hybrid`. Its prompts and retrieval window are tuned on the same 9 documents they are scored on, so its numbers are a fit too. Run on the 9 dev documents (`eval/reports/hybrid_dev_hybrid.md`, 8 of them notice-like): item precision 55 of 78 (71%), item recall 55 of 127 (43%), whole-field 5 of 24 (21%) against 1 of 24 for rules and 1 of 12 for the grouped bake-off (other denominator); 10 of 88 proposed items dropped by the citation check; 107 s per document and 42 s per call of model time. These are fit numbers (same documents tuned and scored, Qwen3.5-9B was a labeler of them). required_documents retrieval was widened once, after a 2-document trial found nothing under its own cues (D-69). One call (an unlabeled document's deadlines, 58f13b9c) ran 230 s and returned broken JSON: the answer hit the 2,048 token cap while looping in the unbounded `flags` array (`finish_reason` length, same output twice at temperature 0). Fixed in `llm.py`: no `flags` in the model's schema (set in code), every array bounded, a 300 s call timeout, one retry then not found, no retry for a cut answer. The same call now takes 35 s.
- Second pass (2026-11-16, D-69): a deadline's time must sit in its date's own span in the same sentence (594c3cb6 shape); prompt examples moved to unlabeled dev documents (a90497874108, 08558fc7fe0a, 5d75d4a67c71), so the leak from f19cddbd4cba is gone. Dev, 9 documents, fit numbers: item precision 55 of 78 to 54 of 79, item recall 55 to 54 of 127, whole-field 5 to 6 of 24 (`eval/reports/hybrid_dev_hybrid_v2.md`). The time rule costs deadlines whose date and time were split across two sentences by the segmenter (136dfba9 h_s79 to h_s82). Diagnostic of the 127 label items (`eval/reports/hybrid_diagnostic_dev_hybrid_v2.md`): 54 hit, 41 not in the retrieved window (32 of them required_documents), 3 not produced, 2 dropped by a check, 27 produced but wrong in value or kind. Nothing was tuned from it yet.
- Third pass (2026-11-16, D-69 addendum 2): category d (19 eligibility and 7 deadlines items) split by reading model and label side by side: eligibility 4 kind, 5 polarity, 3 split, 7 wrong sentence; deadlines 5 kind, 2 flags (`hybrid_diagnostic_dev_hybrid_v2b.md`, a re-run of the v2 code that reproduced the v2 counts exactly and saved the traces). Convention differences: 4 eligibility kind, 3 polarity, 1 deadlines kind; the other 18 are real. required_documents retrieval widened by heading cues (書類, 入札方法, 入札者に要求される事項) and nothing else: required_documents item recall 18 of 51 to 38 of 51 (precision 18 of 21 to 38 of 45), category a 32 to 0, whole-field 2 of 8 unchanged; eligibility and deadlines identical. Extractor frozen (`hybrid_freeze_dev_hybrid_v3.md`). Next: a hold-out of reviewed documents the cues never saw.
- Hold-out run (2026-11-16, frozen v3, hashes checked first, one run each): 5 open notices (58f13b9c, a81e99fe, d230e51e, 6b7142ab, 594c3cb6; no bid_instructions, no spec), model-reviewed labels, candidates from Gemini and Qwen3.5-9B so it leans toward the extractor, n small. Verified accuracy, dev-9 to hold-out: hybrid 89 of 186 (48%) to 49 of 115 (43%), rules 84 of 186 (45%) to 45 of 115 (39%); tier 1 hybrid 45 of 80 to 25 of 50; the 8 rules fields 61 of 62 to 39 of 40; list fields whole-field 6 of 24 to 4 of 15 (rules 1 of 24 to 0 of 15). List items: precision 74 of 103 to 49 of 61, recall 74 of 127 to 49 of 60. Dropped items 10 of 113 to 11 of 72; 130 to 95 s per document (different document mix). Miss categories on 60 label items: hit 49, a 1, b 2, c 0, d 8 (deadlines 6 of 19 in d). `--diagnose` counts untraced dev-9 documents as category a, so the hold-out counts were taken by subtracting the dev-9 ones (reproduces totals exactly); not edited. Side by side: `eval/reports/holdout_v3_side_by_side.md`. These five documents now count as dev for any later tuning.
- Rules v4 (2026-11-17): six more deterministic fields in `rules.py`: award_method, spec_access, submission_modes, delivery_deadline, performance_period, contracting_officer. The 14 labeled dev documents (dev-9 plus the five hold-out documents, now dev) score verified accuracy 129 of 301 (43%) to 178 of 301 (59%), tier 1 66 of 130 (51%) to 93 of 130 (72%); per field before to after: award_method 1 to 11 of 13, spec_access 0 to 6 of 13, submission_modes 1 to 12 of 13, performance_period 0 to 13 of 14, contracting_officer 3 to 12 of 13, delivery_deadline 13 to 13 of 14 (silent: no 納入期限 line in the 14). Wrong value shown stays 1 of 301 (unified_qualification, 58f13b9c, from before), hallucination 0. These are fits: the rules were written from these 14 documents and there is no unseen set for the six fields. Left out: see `eval/reports/rules_v4_side_by_side.md` (spec_access is the weakest; the four near-identical Ministry notices are labeled differently, so unreadable 交付方法 lines answer nothing). `Extracted` gained a `status` so pointers score as see_other_document. Freeze record `eval/reports/freeze_rules_v4.md`; the v3 hybrid freeze record is untouched and its hashes no longer match.
- Measurement fix (2026-11-17): `eval.hybrid --diagnose` now counts only documents with calls in the trace (`traced_rows`, test in `tests/test_hybrid_diagnostic.py`). Hold-out v3 trace: 60 label items (eligibility 27, deadlines 19, required_documents 14), hit 49, a 1, b 2, c 0, d 8, instead of 187 items and 128 in category a; this matches the subtraction written in `holdout_v3_side_by_side.md`.
- Phase 5 fix 2 (2026-11-18): the 8 required_documents items Qwen3.5-9B left out of its window: 5 were a skipped run in one flat list (28ad40ea), 3 were merged into a multi-sentence item; none truncated, capped or late. One rule line added to the required_documents prompt only. Dev, 13 rows, real runs before and after: rows right 5 to 6 of 13, items hit 50 to 56 of 65, b 8 to 2, one row went right to wrong (6b7142ab, 2 extra items). A fit, one run each (`eval/reports/phase5_fix2_required_documents.md`).
### Changed from the plan (what, why, decision number)
### Fallbacks taken
### Missed or still open
### Lessons

---

## Phase 5: Failure analysis and pipeline fixes

### Achieved
- Phase 5 design review (2026-11-18, read-only, no model, no code change): why list fields stay at 26 to 28% verified (11 of 39 for both Qwen3.5-9B after fix 2 and Gemma 4 E4B after fix 1). Of the 28 rows not right per model, rows touched / rows where it is the only cause, Qwen: label or convention 16 / 11, retrieval 4 / 0, value and kind normalization 5 / 2, validator reading one sentence at a time 10 / 2, model 7 / 2 (Gemma: 19 / 8, 4 / 0, 10 / 3, 11 / 0, 5 / 0). With the labels as they are, Qwen can reach at most 23 of 39. The proviso and electronic-kind rules are in the prompt and both models still miss them. Recommended next: settle conventions and extra items with a native reader, let the validator read the neighbouring sentence, set deadline kind and missing dates in code. Upper bounds, fit to these 14 documents (`eval/reports/phase5_design_review.md`).
- Fix 4 (2026-11-18, D-72): same-datetime, same-sentence deadline copies. On 5d75d4a67c71 Qwen3.5-9B and Gemma 4 E4B each gave 6 deadline rows for 3 events; replay on the saved traces (no model run) leaves 3 each, other models unchanged (`eval/reports/phase5_fix4_deadline_dupes.md`). Item counts only, not rescored.
- Fix 5 (2026-11-19, D-73): drop copies of a merged proviso item; a bid receipt line the model called other becomes electronic on an electronic-only notice. Replay on the saved traces (no model run) against the corrected dev labels, rows right of 42: Qwen3.5-9B 15 to 19, Gemma 4 E4B 16 to 18, no row lost (`eval/reports/phase5_fix5_copies_and_deadline_cue.md`).
- Phase 5 summary (2026-11-19, D-74): five list-field fixes, rows right of all three list fields on dev: Qwen3.5-9B 10 of 39 at the start, 19 of 42 now; Gemma 4 E4B 10 of 39 at the start, 18 of 42 now. Steps: fix 1 date recovery and polarity, fix 2 required_documents prompt line, fix 3 proviso merge and 第73条 kind (D-71), fix 4 same-sentence deadline copies (D-72), fix 5 merged-proviso copies and the bid receipt cue (D-73). The table per step is `eval/reports/phase5_summary_after_fix4.md`; fix 5 is `eval/reports/phase5_fix5_copies_and_deadline_cue.md` (Qwen 15 to 19, Gemma 16 to 18, no row lost). Part of the gain is dev label corrections (`9deb37d`, `4719503`), not code, and every number is fitted to the dev documents the models and prompts were tuned on. The 14th document adds 3 rows, so start and end do not share a denominator. The exit criterion was not met (every change moved more than 1 point; one row is 2.4 points of 42); Phase 5 is closed by decision (D-74) because the 55 rows still wrong need a native reader or a different model (`eval/reports/phase5_remaining_errors_after_fix4.md`), and the group 3 rule rested on one example and was skipped. Base model state: Qwen3.5-9B leads by one row; Gemma's license is still unverified (D-70 Open question).
### Changed from the plan (what, why, decision number)
- Exit criterion closed by decision instead of met: one row is 2.4 points on 42 rows, so a 1 point line cannot be read, and the remaining errors need a native reader or a different model (D-74).
### Fallbacks taken
### Missed or still open
- Open at the end of Phase 5 (D-74): the label or convention questions (eligibility legal or other, required_documents name boundary, extra answer items), retrieval misses (a model run is needed to measure a window change), and the categories for the non-list fields. The Phase 4 and Phase 3 leftovers are unchanged.
### Lessons

---

## Phase 6: LoRA fine-tuning

### Achieved
### Changed from the plan (what, why, decision number)
### Fallbacks taken
### Missed or still open
### Lessons

---

## Phase 7: Desktop app MVP

### Achieved
- Step 1 (2026-11-19, D-75): Electron + React + Vite shell in `app/`, PDF.js viewer, fields panel from a fixture of one open dev document, citation chip jumps to the page and draws the box. `tests/test_app_no_network.py`. Checked by screenshot at devicePixelRatio 2 (p1 title line, p4 issuer line).
- Live Processing screen (2026-11-20, D-90): events with a cursor in the status call, per-group "Now reading" cards with the sentences given to the model, one answer card per field as its group finishes (`on_field`, an optional callback in `llm.extract_lists`), cooperative cancel. Check on notice-2aa7506a with the real Qwen3.5-9B model, run through the sidecar before and after the callback: the fields JSON (23 fields: status, value_ja, citations, items, normalized, checks) is byte-identical (`cmp`), 14 fields answered both times. Real-app checks: mid-extraction cards, Cancel (Library back after 125 s: the model call in progress had to finish; sidecar logged cancel_asked then job_cancelled, no later model call), 640 px window (one column, no sideways scroll), prefers-reduced-motion (computed animation none).
- Document type from the first page (2026-11-20, D-92): `shiori_core.doctype` picks notice, bid_instructions or spec when a document is added; 105 of 113 right on the non-test corpus (a fit). The Workspace shows a "Read as" chip. The spec 4965207b still answers 0 of its 6 fields (rules do not read 委託期間 or an unlabeled title); notice output byte-identical.
- Spec rules and grouped fields (2026-11-20, D-93): on a spec the rules read the 業務の名称 title and the 委託期間 period (a ただし clause cut off), and the Workspace puts fields that do not apply to the document type in one collapsed section, out of the counts. Rules dev eval unchanged for every field and document; notice rules output byte-identical.
- Heading cues and scalar fallback (2026-11-20, D-94, D-95): 業務の名称 and 委託期間 are accepted cues, so the spec answers show Verified. One grouped model call fills scalar fields the rules missed; on dev it moved 1 row not found to right and none to wrong.
### Changed from the plan (what, why, decision number)
### Fallbacks taken
### Missed or still open
### Lessons

---

## Phase 8: Privacy hardening and packaging

### Achieved
### Changed from the plan (what, why, decision number)
### Fallbacks taken
### Missed or still open
### Lessons

---

## Phase 9: Write-up and public benchmark

### Achieved
### Changed from the plan (what, why, decision number)
### Fallbacks taken
### Missed or still open
### Lessons

- 2026-11-21 (D-97): schema 1.1.0, deadline kind `application`, two cues (公募期間, 応募期間). Dev eval stopped at 4 right-to-wrong `deadlines` rows (see Open questions); changes left in the working tree, not tuned further.

- 2026-11-23 (D-103): HTML notices in the app. Built the sidecar change, the text viewer and the highlight check for HTML (136dfba9, p-portal, dev split, open licence). Unit and sidecar tests pass. Real-app highlight check passed on 136dfba9: 8 clicks, 0 offset mismatches. The Deadlines click and the English Summary screenshot are covered in the v0.1 wrap-up checks.

- 2026-11-24 (D-112): packaging path. Packaged-mode paths, llama.ts child tracking, `scan_not_supported`, PyInstaller spec, `fetch_llama.py` with pinned hashes. Frozen sidecar (macOS arm64) gave the same fields JSON as the unfrozen one on two dev documents. OCR dropped from v0.1 (optional download after). No installer yet. A llama-server left by a SIGKILLed app is no longer cleaned up on the next start.

- 2026-11-27 (D-119): accepted the storage design. Encrypted files owned by the main process replace the SQLCipher plan; saving is off by default. Steps 0 and 1 done (`app/electron/store.ts`, not imported anywhere). Nothing is saved yet.

- 2026-11-27: storage step 2b done (delete one, delete all, startup cleanup in `store.ts`, tests only). Still not imported by app code, so nothing is saved.

- 2026-11-27: storage step 3 code and tests (`keeper.ts`, `storageBase` in `paths.ts`, single instance lock in `main.ts`). The keeper is not imported by app code. By-hand Mac check passed in a dev run (reported by Yasharth): a master key was made and survived a restart, and a second app copy did not start. Not run on Windows, Linux or a packaged build.

- 2026-11-27 (D-120): storage step 4, first part: `settings.ts` reads and writes the saved answer, tests only. The key changed from `keepDocuments` to `saveDocuments`. The rest of step 4 (the first Yes, off blocking translation updates) is not built. Nothing is saved yet.

- 2026-11-27 (D-121): storage step 5. `storage.ts` is wired into `main.ts`; the bridge has twenty functions. Tests use a fake `safeStorage`, fake settings and a temp folder, plus a one-off run of the compiled `main.js` against a stand-in Electron. Not run in real Electron; the by-hand check of step 5 is open. Do not release before steps 6 to 8.

- 2026-11-27: the by-hand check of storage step 5 passed on macOS in a dev run (reported by Yasharth): saved, found again after a restart, no text or path in the log, no readable Japanese in the store. Next is step 6, the Keychain gate (`storage_design.md` section 7).

- 2026-11-28 (D-122): tested llama.cpp ngram speculative decoding (`ngram-map-k`) on the 15 dev documents. It changed 2 of 56 answers in all three flagged runs, one document's eligibility became not found, and the time saved (7.4%) was within the gap between two unflagged runs. Dropped; the app's server flags are unchanged. Details in `speed_analysis.md` section 6.

- 2026-11-28 (D-123): storage steps 7 and 8 built in the renderer, before step 6. Plan change: no `getStorage` at startup, so a locked store is not announced until Settings opens or a document finishes (open question). Screens rendered with a fake bridge only. The update sentence is still a placeholder.

- 2026-11-28 (D-124): fixed Windows audit rows W05, W08 and W18 and the two D-123 open questions in `app/`. Plan change: `getStorage` is now asked at startup when saved folders exist. Tested with fakes only, not in real Electron and not on Windows.

