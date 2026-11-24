# Shiori (栞)

**Drop in a Japanese tender. Get the answer, with receipts.**

Japanese public tenders are long, dense and written in official-document Japanese. Shiori is a desktop app that reads one for you on your own computer\* and shows, in English, the things you need before you bid: the title, who issued it, the deadlines, who may bid, which documents to send, and so on. Every value points at the sentence it came from. Click it and the PDF opens on that page with the source sentence highlighted, so you can check it against the original.

\*Privacy in Shiori means this: the app reads and processes your documents only on your own computer, runs its language model locally, makes no network requests while you work, and sends no telemetry. The only network use is the first-run model download, which sends none of your documents. This describes the shipped app, not how it was built: during development, some public tender documents, including some whose sites reserve rights, were sent to cloud AI services to prepare reference labels (docs/decisions.md, D-111). The app does not call any cloud service.

> Early work in progress. There is no installer yet. You can run it from source (see below).

## Demo video

[![Shiori intro video: reading a Japanese tender in English, with sources](https://img.youtube.com/vi/NeasBmbAPtA/maxresdefault.jpg)](https://youtu.be/NeasBmbAPtA)

<sub>35 seconds of the desktop app on one public tender (Wakayama Prefecture): open a document, see the fields in English, click one to jump to its source sentence, and search the document when a field is not found. [Watch on YouTube](https://youtu.be/NeasBmbAPtA).</sub>

## Screenshots

Real screenshots of the current app, taken with Qwen3.5-9B on a MacBook Air M4. The document is the 2026 Wakayama Prefecture financial accounting system tender notice (4 pages), a public document used under the terms listed in "Sources and licenses" below. You do not need to read the Japanese on the right: the point is that each answer on the left maps to a sentence on the right.

**Fields.** Each of the 23 fields is Verified (the cited sentence was checked by code), Needs review, or Not found. The count chips at the top show all three groups for this run (12 Verified, 3 Needs review, 8 Not found). Not found is shown as an answer, not hidden.

![Fields tab: 23 fields with Verified, Needs review and Not found counts, title, issuer and notice date in English](docs/assets/shiori-fields.png)

**Citation click.** Clicking a value opens the PDF at its page and highlights the sentence it came from (red box, right). The panel shows the English line (marked "Machine translation"), the original Japanese sentence, the page, and the section path.

![Title field opened: English translation, Japanese source sentence, page 1, and the same sentence highlighted in the PDF](docs/assets/shiori-citation.png)

**Deadlines.** The dates found in the notice, each with its Japan time, your own time zone, the original Japanese wording and the page. (Export to CSV and a calendar file is a button in the app; it is not shown here.)

![Deadlines tab: bid by mail 26 Oct 2026 17:00 JST and bid in person 27 Oct 2026 14:00 JST, both Verified, page 2](docs/assets/shiori-deadlines.png)

Source of the document in these screenshots: Wakayama Prefecture, tender notice (入札公告) for the 2026 financial accounting system, published at pref.wakayama.lg.jp under the Wakayama Prefecture website information terms of use (和歌山県ホームページ公開情報利用規約), which are compatible with CC BY 4.0. The screenshots are shown unmodified apart from file format.

## What it does

- **Every field has a receipt.** The model only points at numbered sentences. Code then checks that the value really appears in the sentences it cited. A value that fails the check is dropped instead of shown as a guess, and some checks (for example a heading that looks unusual for that field) downgrade Verified to Needs review (`CLAUDE.md`, `docs/architecture.md`, D-76).
- **Runs locally.** A small quantized model (Qwen3.5-9B by default) runs on your machine through llama.cpp. There is no cloud model and no upload in the app.\*
- **Built for Japanese documents.** Era dates (令和8年), 万/億 amounts, fiscal years and tax wording are handled by tested rules, not left to the model (`docs/japanese_rules.md`). Rules do what they can, and the model is used for the lists: eligibility, deadlines and required documents.
- **Hover to translate.** A sentence in the viewer can be translated to English on demand.
- **Export.** All fields go to a CSV file and the deadlines to a calendar (.ics) file, which you save yourself.

## Install

Installers are built by GitHub Actions (`.github/workflows/release.yml`) and attached to each release. Every push to main that changes code or packaging files also builds installers for four platforms and keeps them as run artifacts for 14 days. Each release also has a `SHA256SUMS-*.txt` file per platform; compare it with your download (`shasum -a 256 <file>` on macOS and Linux, `certutil -hashfile <file> SHA256` on Windows).

**The builds are not notarized or signed by a known developer.** That needs paid accounts (Apple Developer, a Windows code-signing certificate) and this is a solo project without them. The macOS app has an ad-hoc signature, which only seals the bundle so macOS does not call it damaged; it does not make Apple trust it. Your OS will warn you the first time. Only macOS on Apple Silicon (arm64) has been tested, by me. The macOS Intel, Windows and Linux builds are made by CI from the same pinned inputs and have not been run by anyone.

- **macOS.** Download `Shiori-<version>-mac-arm64.dmg` for Apple Silicon (M1 and newer) or `Shiori-<version>-mac-x64.dmg` for Intel (same signing, but nobody has run it).
  1. Open the .dmg and drag Shiori to Applications.
  2. Double-click Shiori in Applications. macOS says it cannot verify the app. Click Done (or OK).
  3. Open System Settings, Privacy & Security, scroll down to the message about Shiori and click Open Anyway. Enter your password or Touch ID, then click Open.
  After that it opens normally. If macOS still says "Shiori is damaged and can't be opened", the download flag is the cause. Clear it and try again:
  ```bash
  xattr -cr /Applications/Shiori.app
  ```
  The app is not notarized because notarizing needs a paid Apple Developer account, which this project does not have.
- **Windows.** Run `Shiori-<version>-win-x64.exe`. If SmartScreen says it protected your PC, click More info, then Run anyway.
- **Linux.** Download `Shiori-<version>-linux-x64.AppImage`, then `chmod +x Shiori-*.AppImage` and run it. On Ubuntu 22.04 and later it will not start without FUSE 2: `sudo apt install libfuse2`.

The installer does not contain a language model. On first run the app shows a Setup screen and downloads the model (about 5.7 GB, SHA-256 checked, see below). That is the only network use. Scanned PDFs (pages that are images) are not supported yet: the app refuses them with a message instead of giving partial answers (D-112).

Manual test list (for the author, per platform):
1. Install on a clean user account (not the one used for development).
2. With Wi-Fi on, start the app and download the model on the Setup screen.
3. Turn Wi-Fi off.
4. Add a sample tender PDF and wait for it to finish.
5. Click a field's citation and check that the PDF opens on that page with the sentence highlighted.

Build an installer yourself (macOS arm64 shown; run from the repo root):

```
uv sync
uv run pyinstaller packaging/sidecar.spec --noconfirm --distpath packaging/build/sidecar --workpath build/pyi
uv run python packaging/fetch_llama.py --target macos-arm64
cd app && npm ci && cd ..
uv run python packaging/third_party_notices.py
cd app && npm run dist
```

The installer ends up in `app/release/`.

## Run it from source

You need: macOS (the only machine it has been run on), Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22.13 or newer, and `llama-server` from llama.cpp (for example `brew install llama.cpp`).

```
uv sync
cd app
npm install
npm run dev
```

The first time, no model is installed, so the app opens a Setup screen. Pick a model and click Download. It downloads the GGUF file (Qwen3.5-9B is about 5.7 GB) from a pinned Hugging Face address and checks its SHA-256 before using it; if the hash does not match, the file is deleted. That is the only time the app uses the internet. If you already have the file, "Choose a model file from disk" copies it in after the same hash check. Then click Add document and choose a tender PDF. In my runs of this one notice on an M4 Mac, the model job took 116 s and 190 s (two runs, not a benchmark).

Details: `app/electron/registry.ts` (models, URLs, hashes) and `docs/decisions.md` D-99 and D-100.

## Privacy: what the app does, what was measured, what was not

What the app does (`docs/privacy.md`, `docs/threat_model.md`): the document, its text and the results stay on your machine.\* The page that shows your document is not allowed to make any network request. The local services bind to 127.0.0.1 only, on a random port with a per-launch token. Logs hold event names, timings and counts, not document text.

\*Privacy in Shiori means this: the app reads and processes your documents only on your own computer, runs its language model locally, makes no network requests while you work, and sends no telemetry. The only network use is the first-run model download, which sends none of your documents. This describes the shipped app, not how it was built: during development, some public tender documents, including some whose sites reserve rights, were sent to cloud AI services to prepare reference labels (docs/decisions.md, D-111). The app does not call any cloud service.

What was measured:
- A counting request filter in the app cancels every request from the page except its own app address. A test runs it in a real Electron session and checks that a page's request to an outside host is cancelled (`tests/test_app_filter_electron.py`, D-100). In the screenshot runs above, the app reported 0 blocked requests.
- A network sample (2026-11-23, [`scripts/net_sample.py`](scripts/net_sample.py), result in `docs/privacy.md`): during one full extraction of the Wakayama notice above, every 2 seconds the script listed the internet sockets of the app, the sidecar and llama-server. 103 samples, no remote endpoint outside this machine, no socket listening on a non-loopback address, and the app's quit line said "renderer requests blocked: 0". This is a sample, not a packet capture, so a connection shorter than 2 seconds could be missed.
- A test scans the app code for network use and allows exactly one file, the model download (`tests/test_app_no_network.py`, `tests/test_security_static.py`).
- The model download is tested against a local fake server: a good hash installs, a bad hash deletes the file, an interrupted transfer resumes (`app/test/download.test.ts`). The three registry hashes and sizes were also compared with the hub's headers once (D-100).
- A real model download through the Setup screen was done on 22 Nov: Gemma 4 E4B, 4.98 GB, about 18 minutes, hash verified (`docs/privacy.md`, "Measured so far").

What has not been done yet:
- A packet capture during a full session.
- The Wi-Fi-off demo run.
- The Windows 16 GB laptop run.
- Encrypted local storage and the user-visible network activity list from `docs/privacy.md` are designs, not built features (`docs/roadmap.md`).

## Status and limits

Read this before trusting any output.

- **Early.** Unsigned installers exist (see Install), but the app has been run on one Mac only (Apple Silicon).
- **The labels are silver.** The reference answers were built by Gemini and a local model, with code checks, and then reviewed by Claude. Five label lines are marked "native check pending" because no native Japanese reader has checked them yet. Nothing is marked human-audited (`docs/eval_protocol.md`).
- **Frozen before the test run.** The rules, prompts and label files were frozen at extractor 0.3.0 before the one test run (D-109), and nothing was tuned afterwards. The code hash and `git status` were identical before and after the run. Scores on the development documents are fits, not forecasts (D-96).

**Test numbers (v0.1, one run on 2026-11-23, 10 test documents: 5 notices, 3 bid instructions, 2 specs).** Source: `eval/reports/test_milestone_v0_1.md`. Pipeline: rules plus local Qwen3.5-9B. Each rate is given for all items and without the 5 native-check-pending lines.

| rate | all items | without the 5 |
|---|---|---|
| Verified field accuracy | 82 of 190 (43%) | 81 of 185 (44%) |
| Citation precision | 136 of 155 (88%) | 136 of 155 (88%) |
| Citation recall | 136 of 356 (38%) | 136 of 350 (39%) |
| Not found | 127 of 190 (67%) | 122 of 185 (66%) |
| Wrong value shown | 23 of 190 (12%) | 23 of 185 (12%) |
| Shown value not in its cited sentences | 0 of 63 (0%) | 0 of 63 (0%) |
| Over-abstention (label has a value, answer Not found) | 63 of 126 (50%) | 61 of 124 (49%) |

How the 82 is made up (same report, section "Breakdown of the 190 fields"): 40 shown values fully right, plus 42 correct Not found (the label says absent). The other 108 are 23 shown wrong, 63 over-abstained and 22 where the label points to another document. The scores are against silver labels and Qwen3.5-9B was one of the two labelers, so they lean optimistic.

Known limits:
- **List fields are the weak spot.** Verified field accuracy in the report: eligibility 2 of 8 (25%), deadlines 1 of 8 (12%), required_documents 1 of 8 (12%). 18 of the 23 wrong answers are in these three fields. Verified there means each item is cited, not that the list is complete. A list that got some items right still counts as wrong; partly right was not measured.
- **About half of the values that exist come out Not found** (over-abstention above).
- **issuer_org** was right on 2 of 10 documents and Not found on 9 of 10. It gives Not found for 北海道 documents because the rule only knows 県 and 市. There was no dev example, so the rule was not added (D-96).
- **Dates go through code, not the model**, because the local model gets some 令和 year conversions wrong.
- **Speed and memory were measured on a MacBook Air M4 only.** Per document: mean 104 s, median 119 s, max 212 s (total 1038 s for 10; the two specs took 0 s, they ran no model call). Peak memory: 85 MiB for the app process and 7042 MiB for llama-server, which is rough because the model is memory-mapped (`eval/reports/test_milestone_v0_1.md`). The run on a 16 GB Windows laptop has not been done.
- **English lines for cited sentences are machine translation** by a small local model and can be wrong. Always check the Japanese sentence next to it. The app marks these lines "Machine translation".
- **Not every document type is covered.** It is built around tender notices and bid instructions. Specs and other types give fewer answers, and a field it cannot support with a verified sentence says Not found.
- Verified means the value was found in the cited sentence by code. It does not mean the answer is complete or that the document says what you need.

The corpus used for development is 519 public tender documents from 37 issuing organizations, 47 of them complete bundles (notice plus spec) (`data/manifests/corpus_report.md`). The documents are not in this repo.

## Support

If Shiori is useful to you, you can support it here: [Buy Me a Coffee](https://buymeacoffee.com/yashaarth/shiori-reading-japanese-tender-documents-english-sources).

## Help wanted

If you read Japanese, please try one example and tell me where the English or the highlighted sentence is wrong. Open an issue on this repo or message me on [LinkedIn](https://www.linkedin.com/in/yasharth-singh-b2493b284/). A native reader's check is the main thing missing.

## For developers

```
uv run pytest
uv run python -m eval.repo_scan
```

Docs: start with `docs/roadmap.md`, then `architecture.md`, `field_schema.md`, `japanese_rules.md`, `eval_protocol.md`, `privacy.md`, `decisions.md`.

## Sources and licenses

The open-license documents used here come from the Digital Agency, the Japan Meteorological Agency, the Government Procurement Portal (p-portal), Hokkaido, Wakayama Prefecture and Okayama Prefecture. They are published under the Public Data License 1.0 (PDL1.0), the Government Standard Terms of Use 2.0, or terms compatible with CC BY 4.0, which ask for the source to be named. Short sentences from them appear in tests and docs, and labels for some of them are in `data/eval/`, in some cases shortened or edited. Documents whose terms do not allow redistribution are used locally. Some short sentences from them remain in older commits of this repo (D-101), and they will be removed on request. Details in `docs/sources.md`.

## License

Shiori is released under the GNU Affero General Public License v3.0 (AGPL-3.0-only, see `LICENSE`). It uses PyMuPDF, which is AGPL-3.0, so the whole app is AGPL-3.0 (D-110 lists every component and its license). Old commits predate the license (D-101). Models you download keep their own licenses.

A personal project by Yasharth Singh.
