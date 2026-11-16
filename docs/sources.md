# Sources

Where data, reference material, tools, and models come from. Entries marked **[verify]** haven't been checked yet; check them before building on them and remove the tag. Note license or terms of use for every source.

---

## 1. Tender documents (Phase 1)

| Source | URL | What's there | Notes |
|---|---|---|---|
| 調達ポータル (Government Procurement Portal) | https://www.p-portal.go.jp/ | Central national portal for procurement notices. Search by 調達案件名称, 調達機関, dates | Launched Oct 2018, replaced the old GEPS portal. Search is a server-rendered POST form (session + CSRF, no JS needed), max 500 hits per search. Per-notice GET permalink: `/pps-web-biz/UAA01/OAA0122?anken=<調達案件番号>`. Notice body is HTML text with an English Summary on WTO notices. Bid documents (入札説明書, 仕様書) are on GEPS (`www.geps.go.jp`) behind a contact-details form, which we do not automate (D-14). No robots.txt. Terms: 政府標準利用規約 2.0 |
| Ministry and agency procurement pages | e.g. JMA satellite center https://www.data.jma.go.jp/mscweb/ja/supply/ippan.html , JPO https://www.jpo.go.jp/news/chotatsu/index.html | Some agencies list their notices with direct PDF links and also point to 調達ポータル | JMA MSC: static table, direct PDFs, but only 6 notices and only 公告 + results (bundles are on GEPS); PDL1.0. JPO: 403 on every page including robots.txt for our User-Agent (checked 2026-10-02), so unusable for now. More agency pages still need checking |
| JETRO Japanese Government Procurement (English) | https://www.jetro.go.jp/en/database/procurement/ | English summaries of notices covered by the WTO GPA and Japan-EU / Japan-UK EPAs, national and local | HTML only, no PDFs. Search runs in JavaScript; result articles are static pages under `/en/database/procurement/national/articles/`. Terms are proprietary (https://www.jetro.go.jp/en/legal/): fine for checking labels, not for republishing or training without written permission. `links-local.html` lists about 89 core-city procurement pages |
| 官報 (Kanpo, official gazette) | https://www.kanpo.go.jp/ (old `kanpou.npb.go.jp` redirects here) | Official publication of WTO-covered procurement notices. A 政府調達 issue appears on each publication day | New site since 2025-04-01. Free access is 90 days (not 30); 政府調達 issues from 2016-04-01 remain readable after that. robots.txt disallows all issue paths and the terms forbid crawlers, so manual download only (D-14). Terms: PDL1.0 |
| 官公需情報ポータルサイト | https://www.kkj.go.jp/ | Aggregated tender info from national agencies, incorporated administrative agencies, local governments | Run by the Small and Medium Enterprise Agency. robots.txt is `Disallow: /` for all agents (checked 2026-10-02), so no automated collection. May offer a search API **[verify]**: not checked, because robots.txt covers the whole site and a published API would need its own terms read first |
| Prefectural / designated city e-procurement | e.g. Tokyo e-procurement https://www.e-procurement.metro.tokyo.lg.jp/ | Local government tenders | Format variety, often different templates from national notices. Tokyo's e-procurement robots.txt disallows everything but the top page, and its bureau sites have no central tender listing. Static municipal pages work better: Funabashi (https://www.city.funabashi.lg.jp/jigyou/nyusatsu/001/index.html) posts full proposal bundles as direct PDFs, but its terms reserve all rights. Check each city's terms before collecting |
| Digital Agency (デジタル庁) procurement | https://www.digital.go.jp/procurement | IT system procurement with long specs | Priority source. 一般競争 notices link out to p-portal; 公募, RFI and 意見招請 answers are posted as direct PDF/xlsx/docx. RFIs often include a full 調達仕様書 draft. Terms: PDL1.0 (https://www.digital.go.jp/copyright-policy) |

Collect bundles where possible (notice + bid instructions + spec for the same tender). Survey details: `data/manifests/source_survey.md`.

**Terms of use:** checked per site on 2026-10-02 and recorded in the manifest's `license_note`. Two government licenses turned up, both compatible with CC BY 4.0: the older Government Standard Terms of Use (政府標準利用規約 2.0; p-portal) and its successor, the Public Data License (公共データ利用規約 第1.0版, PDL1.0; Digital Agency, JMA, Kanpo). JETRO and Funabashi City reserve all rights. This determines whether the eval set can be published in Phase 9.

---

## 2. References for Japanese rules

| Resource | URL | Use |
|---|---|---|
| Japanese Law Translation (Ministry of Justice) | https://www.japaneselawtranslation.go.jp/ **[verify]** | Official English translations of Japanese laws, plus the Standard Legal Terms Dictionary (法令用語日英標準対訳辞書). Reference for glossary terms. Includes procurement-related laws such as 会計法 (Public Accounting Act) and 予算決算及び会計令 **[verify which are translated]** |
| 公用文作成の考え方 (Agency for Cultural Affairs, 2022) | search the title on bunka.go.jp **[verify]** | Official guidance on how government documents are written, including numbering and punctuation conventions (DOC-2, TXT-5) |
| W3C Requirements for Japanese Text Layout (JLREQ) | https://www.w3.org/TR/jlreq/ | Line breaking, punctuation, vertical text background |
| Unicode UAX #15 (normalization) | https://unicode.org/reports/tr15/ | What NFKC does and doesn't do (TXT-3) |
| Era (元号) start dates | Cabinet Office / any official source | DATE-1 table |
| JETRO guides on Japanese government procurement | jetro.go.jp **[verify]** | English explanations of procedures and the unified qualification system |

---

## 3. Parallel data and evaluation

| Resource | Use | License / terms |
|---|---|---|
| JETRO English notices paired with original Japanese notices | Partial parallel data for title/org/date fields, label checking | JETRO terms reserve all rights (https://www.jetro.go.jp/en/legal/): reading for label checks is fine; republishing or training needs written permission |
| English Summary sections inside WTO notices | Built-in partial reference translations | government terms |
| Japanese Law Translation parallel texts | Domain-adjacent JA-EN legal text, glossary mining | **[verify]** terms before any training use |
| JParaCrawl (NTT) | General JA-EN parallel corpus | research / non-commercial; don't train shipped models on it without checking |
| KFTT (Kyoto Free Translation Task) | JA-EN, Wikipedia-based | CC BY-SA |
| sacrebleu (chrF) | translation metric | Apache 2.0 |
| unbabel-comet (wmt22-comet-da) | translation metric | Apache 2.0 code; check model card |
| Swallow LLM Leaderboard | Independent Japanese LLM evals, including JA-EN translation | reference only |
| Nejumi LLM Leaderboard (W&B) | Japanese LLM leaderboard | reference only |

---

## 4. Tools

| Tool | Use | License | Notes |
|---|---|---|---|
| PyMuPDF | text + char boxes, rendering for debug | **AGPL-3.0** | fine for research; decide before shipping (decisions.md) |
| pypdfium2 | text + boxes alternative | Apache 2.0 / BSD | candidate replacement |
| pdfplumber / pdfminer.six | text + char boxes, table detection | MIT | candidate replacement, slower |
| NDLOCR-Lite (National Diet Library) | Japanese OCR, CPU only, Win/Mac/Linux, ONNX models | CC BY 4.0 | https://github.com/ndl-lab/ndlocr-lite . Known issue: may fail when installed under a path with full-width (Japanese) characters |
| PaddleOCR | OCR fallback, has Japanese models | Apache 2.0 | |
| SudachiPy / fugashi + UniDic | tokenization for BM25 | Apache 2.0 / various | |
| jaconv / neologdn | width conversion, normalization helpers | MIT / Apache | use with care, check what they change |
| llama.cpp | local inference, GGUF, quantization, JSON-schema constrained output | MIT | `llama-server` binary per OS |
| mlx-lm | LoRA training on Apple Silicon | MIT | |
| Unsloth / PEFT | LoRA on GPU (Colab/Kaggle) | Apache 2.0 | fallback |
| PDF.js | PDF rendering in Electron | Apache 2.0 | |
| SQLCipher | encrypted SQLite | BSD-style (community edition) | |
| Playwright | only if a source has no direct links | Apache 2.0 | dev-time |

---

## 5. Candidate models (Phase 4)

Checked on Hugging Face on 2026-10-02 (D-34). Constraint: must run quantized (Q4) on a 16 GB Windows laptop without GPU, which means roughly 9B dense parameters or less. "Rev" is the Hugging Face commit of the repo at that date. Licenses were read from the model card or the license text itself; none of this is legal advice.

| Candidate | Upstream repo, rev | GGUF source, rev | License | Redistribution inside an app |
|---|---|---|---|---|
| Qwen3.5-9B | `Qwen/Qwen3.5-9B` `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | `unsloth/Qwen3.5-9B-GGUF` `3885219b6810b007914f3a7950a8d1b469d598a5` (converted by Unsloth, not Qwen) | Apache-2.0 | Fine |
| Qwen3.5-4B | `Qwen/Qwen3.5-4B` `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` | `unsloth/Qwen3.5-4B-GGUF` `e87f176479d0855a907a41277aca2f8ee7a09523` (Unsloth) | Apache-2.0 | Fine |
| Gemma 4 E4B-it (the current small Gemma; E2B, 12B and 26B-A4B also exist) | `google/gemma-4-E4B-it` `ee0ef6023621cff504d758262d4e04895a5af4a2` | `unsloth/gemma-4-E4B-it-GGUF` `bfc15c382204943c3a8fff0c750b94ae2364d7a3`; Google also ships `google/gemma-4-E4B-it-qat-q4_0-gguf` `4b4a2c1d58` | Apache-2.0 (Gemma 4 dropped the older Gemma terms) | Fine |
| Qwen3-Swallow-8B-RL-v0.2 (newest Swallow in the 8-9B range; replaces Gemma-2-Llama-Swallow 9B) | `tokyotech-llm/Qwen3-Swallow-8B-RL-v0.2` `9218f4843b6f93369a0b0999d8f58d61487ea71c` | `mmnga-o/Qwen3-Swallow-8B-RL-v0.2-gguf` `3fc755c6ab3780ebad6671130fc1b630bbd1575b` (community conversion; no official GGUF) | Apache-2.0 | Fine. Gemma-2-Llama-Swallow 9B (`9d643c2f98`, May 2025) carries Gemma + Llama 3.3 terms and is only a fallback |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese | `nvidia/NVIDIA-Nemotron-Nano-9B-v2-Japanese` `3979dd16634988c34cc3bd911583c51e6a731d10` | `mradermacher/NVIDIA-Nemotron-Nano-9B-v2-Japanese-GGUF` `3c43afc63592a1c005e17e71f2baaee5b4dafc32` (community; no official GGUF) | NVIDIA Nemotron Open Model License | Allowed. Conditions: ship the license text, keep notices, include "Licensed by NVIDIA Corporation under the NVIDIA Nemotron Model License." in a Notice file, and the licensee indemnifies NVIDIA for third-party claims. Patent or copyright suit against anyone over the model ends the license |
| LFM2.5-1.2B-JP-202606 (supersedes the March `LFM2.5-1.2B-JP`) | `LiquidAI/LFM2.5-1.2B-JP-202606` `52b8b4475311a63bf839c6494f78f8ad59d13515` | `LiquidAI/LFM2.5-1.2B-JP-202606-GGUF` `448ba3f7d408c2f5c32cec8038612f7c1ed9f054` (official) | LFM Open License v1.0 | License is LFM Open License v1.0. Redistribution is allowed with the license copy and change notices, but commercial use is not covered at companies with USD 10M or more annual revenue. Fine for this personal, evaluation-only project (D-35); re-check the exact wording before any commercial use |
| LLM-jp-4.1-8B-thinking (new 8B; the 32B-A3B and 33B variants are too big for 16 GB laptops) | `llm-jp/llm-jp-4.1-8b-thinking` `7c19bc90e49b717381e4f474ee95964c05217a28` | `llm-jp/llm-jp-4.1-8b-thinking-gguf` `3afab819c6b6a149312864d3529e5b49794dda25` (official) | Apache-2.0 | Fine. Not downloaded in the feasibility run (a thinking model; add if accuracy work needs another Japanese-first 8B) |
| Sarashina2.2-3B-instruct (SB Intuitions; open sizes are 0.5B, 1B, 3B plus a 3B vision model) | `sbintuitions/sarashina2.2-3b-instruct-v0.1` `4f3626fb1b64b3e97c908e67f27b2d627ba2a999` | `mmnga/sarashina2.2-3b-instruct-v0.1-gguf` `31d771319b` (community, March 2025 conversion) | MIT | Fine. Benchmarked in D-34: 8192-token context limit, and its GGUF needs the `/completion` route with a hand-applied chat template when a JSON schema is set (chat route returns HTTP 500) |
| PLaMo (Preferred Networks): `plamo-2-translate`, `plamo-2.1-2b-cpt`, `plamo-3-nict-2b-base` | `pfnet/plamo-2-translate` `cae8da342a3e051ed69f90ce24c23eacff908732` | community GGUFs only (`mmnga/plamo-2-translate-gguf`) | PLaMo Community License; the repos are gated (accept terms to download) | **Flag [verify].** I did not read the full agreement. The card says to contact them for non-commercial use, so terms differ by use. Not downloaded; the translate model is a hover-translation candidate, not an extraction candidate |
| LFM2.5-8B-A1B (mixture-of-experts: 8.3B total, 1.5B active per token, 32 experts with 4 used) | `LiquidAI/LFM2.5-8B-A1B` `5dd22602c2e9f6a097b1de4c4efe0658b605015c` | `LiquidAI/LFM2.5-8B-A1B-GGUF` `49c14831707011e64d70b2ebd8462ba08d608434` (official) | LFM Open License v1.0 | Same license note as LFM2.5-1.2B-JP above (D-35). Benchmarked in D-34: fastest model above 2B, needs `--reasoning-budget 0` because it ignores `--reasoning off`; Japanese quality unknown |

Benchmarked in D-34 (2026-10-02): LFM2.5-1.2B-JP, LFM2.5-8B-A1B, Qwen3.5-4B, Gemma 4 E4B, Sarashina2.2-3B, Qwen3.5-9B, Qwen3-Swallow-8B, Nemotron Nano 9B JP. Not benchmarked: LLM-jp-4.1-8B, PLaMo.

Not on the list any more: LLM-jp-4 32B-A3B as a 16 GB candidate (about 20 GB of weights at Q4; use only as a Mac upper reference).

Other notes from the check:

- Qwen3.5, Gemma 4, Swallow, LLM-jp and LFM2.5-8B-A1B can emit a reasoning trace before the answer. The feasibility run turns thinking off (`--reasoning off`; for LFM2.5-8B-A1B `--reasoning-budget 0`, D-34). Whether thinking helps extraction is an accuracy question for later.
- Every GGUF in the table is a third-party conversion except LFM2.5, the LLM-jp one and Google's own QAT Gemma file. Converted files are not checked against the upstream weights; the revision hash above pins what was tested. If one of these ships in the app, convert from the upstream repo ourselves and pin that hash.

Record for each: exact Hugging Face repo, revision hash, GGUF source (official or converted by us), license.
