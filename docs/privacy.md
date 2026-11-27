# Privacy design

The promise: **the app never sends a document, extracted text or result off the user's machine.** Today it keeps results in memory only (D-116) and writes no document or result file of its own. Files you export are plain text and yours to look after, including whatever your calendar or sync tools do with them. Encrypted saving and permanent delete are planned, not built. Their design is accepted (D-119, `storage_design.md`).

This file says what the code does today (checked 2026-11-27). Anything marked **Planned, not built** is not in the app. Releases v0.1.0 and v0.1.1 do not have the spellchecker and HTTP cache settings described below (D-118).

## What privacy means in Shiori

**In scope (the shipped app):**
- Your documents are processed only on your own machine. Text, results and the PDF viewer never touch a remote server.
- The language model runs locally (llama.cpp, a GGUF file on disk).
- The app makes no network request while you work. The page that shows your document is blocked from the network, and tests scan the app code for network use.
- No telemetry, analytics, crash reporting, remote fonts or auto-update calls.
- The only network use is downloading a model, which you start yourself and which sends none of your documents. It fetches a model file from a pinned URL and checks its SHA-256 hash.
- "Find models on this computer" (D-115) reads files locally, only after a click, and only in the app's models folder, the Hugging Face cache, LM Studio and Ollama folders, or one folder you pick. It compares size and SHA-256 with the pinned models. It makes no network request, keeps its result in memory only, and writes no file path or file name to any log.

**Out of scope (not covered by the promise above):**
- How the project was built. During development, some public tender documents were sent to cloud AI services to prepare reference labels, including some whose source sites reserve rights. The rules and the exact facts are in D-42, D-44, D-50 and D-111 (`docs/decisions.md`). The shipped app does not call any cloud service.
- The licenses of downloaded models. Each model keeps its own license, and the user is responsible for accepting it.

## Threats we design for

| Threat | What the code does today |
|---|---|
| App or a dependency sends data out | Page requests cancelled at the Electron session; CSP; shipped Python may not import network or cloud SDK modules (tests); sidecar telemetry off (D-117) |
| Another local app queries our model or sidecar | Bind to 127.0.0.1, random ports, a new token or key at each start |
| Laptop stolen or disk imaged | The app saves no documents or results. Your original files and exports are not protected by it. Encrypted saving: **Planned, not built** (`storage_design.md`) |
| Deleted documents recovered from SSD | Nothing is saved, so there is nothing for the app to delete. Delete by destroying a key: **Planned, not built** (`storage_design.md`) |
| Document text ends up in logs or crash dumps | The app's own log lines carry no document text; the app never starts Electron's crash reporter. Filter for Japanese text in child process output: **Planned, not built** (see "Logging") |
| User documents end up in training data | No code uploads documents or results |

Out of scope: a compromised OS or a malicious user with full access to an unlocked session.

## Design

**Network**
- In main, `session.defaultSession.webRequest.onBeforeRequest` (`app/electron/netfilter.ts`) cancels every request from the page unless its address starts with `shiori:`, `devtools:`, `data:` or `blob:`. So `file:`, `127.0.0.1` and `localhost` are cancelled too. This is the same in packaged and dev builds. Cancelled requests are counted, not listed. Every permission request from the page is refused.
- That filter covers page requests only. It does not cover the main process (the model download and the calls to the sidecar) or requests Chromium makes on its own. Whether Electron makes any such request of its own has not been checked with a packet capture.
- Renderer CSP (`app/index.html`): `default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; worker-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-src 'none'; object-src 'none'`. The page can connect only to its own `shiori://` address and reaches the main process over IPC. No remote fonts, no CDN scripts.
- Spellchecker off. On Windows and Linux, Electron by default downloads spellcheck dictionaries from a Google CDN. Chromium loads every listed dictionary when a session is made, whether the checker is on or not, so `main.ts` empties the list at that moment, turns the checker off, and sets `spellcheck: false` on the window. That this stops the download comes from reading the source (D-118); it has not been run on Windows or Linux. macOS uses the system checker and downloads nothing.
- HTTP cache off (`disable-http-cache`, set before the app is ready). Checked in a real Electron run on the dev Mac (2026-11-27); not run on Windows or Linux.
- No auto-update calls. Updates are manual downloads.
- A "check for updates" button that only fetches a version file: **Planned, not built** (`storage_design.md` does not cover it).
- The only network use in the app's code is the model download (`app/electron/download.ts`). It starts only when you click Download, on first run or later from the Models screen. It uses pinned https URLs, follows redirects over https only, and keeps a file only if its size and SHA-256 match. The page stays blocked before, during and after. "Choose a model file from disk" works for air-gapped machines and copies a file only if its hash matches a listed model.

**Local services**
- The sidecar and llama-server are started on 127.0.0.1, never 0.0.0.0, each on a random free port.
- The sidecar makes a new random 32-byte token at each start and answers 401 to any request without it. It does not check the `Origin` header and sends no CORS headers.
- llama-server gets a new random 32-byte API key at each start, through its environment. How llama-server enforces it (for example on `/health`) is its own behaviour and is not tested here.

**Storage**
- Today: the Library, results and translations are held in memory and are gone when the app quits (D-116).
- The app writes model files and partial downloads, the exports you choose to save, and whatever Electron itself keeps in the user data folder.
- No temp files for document text: no code in `core/` or `sidecar/` that the app runs writes one. The packaged app has no OCR (D-112). What the OCR engine does inside a dev run has not been checked.
- Encrypted saved documents: **Planned, not built.** The design is accepted (D-119) and described in `storage_design.md`.

**Deletion**
- Permanent delete of a saved document: **Planned, not built** (`storage_design.md`).
- "Delete all": **Planned, not built** (`storage_design.md`).
- Today, quitting drops what the app held in memory. Operating system swap files are not covered.

**Ephemeral mode**
- A setting for it: **Planned, not built** (`storage_design.md`). Today the app never saves results, so there is nothing to switch.

**Logging**
- The app writes no log file. Messages go to the terminal output of the process.
- Event lines hold names, timings, counts, byte sizes, model ids and error types. The sidecar also logs the first 8 characters of the document id, which is a hash of the file.
- A failed read, stat or write of a path you chose, in `main.ts`, logs the error type only (`app/electron/userfile.ts`). Download and model scan lines hold no path or file name (tested). Not every other error path has been audited.
- llama-server's output is discarded. The sidecar's error output is passed through unfiltered. Its own log lines hold no document text (`tests/test_sidecar.py`), but an error it does not catch has not been checked.
- A log filter on child process output that drops lines with Japanese text: **Planned, not built** (`storage_design.md` does not cover it).
- The app never starts Electron's crash reporter. There is no test for this. Crash reports made by the operating system are outside the app.
- Dev checks (`SHIORI_HLCHECK`, `SHIORI_SHOT*`) print text from the screen, which can be document text. A packaged app ignores them.

**Training**
- No fine-tuning exists yet (`training/` holds a readme only). If it is added, it trains on public tenders only.
- No code sends user data anywhere. Document content leaves the app only when you export or copy it.
- Saying this about training in the UI and the README is not done yet.

## Threat model and static checks

The full threat table (threat, mitigation, the test that proves it, status) is in `threat_model.md`. `tests/test_security_static.py` enforces the code-level rules on the Python in `core/`, `sidecar/` and `app/` with `ast`, and checks that only `download.ts` imports a network module in the app's TypeScript; allowlist entries need a written reason. It sits next to `tests/test_import_boundaries.py`, which it does not repeat.

## Dependency audits (manual, not in CI)

CI exists: `.github/workflows/checks.yml` runs ruff, pyright, pytest, the app tests and the app type check on pushes to `main` and on pull requests (Linux only). Neither it nor `release.yml` runs a dependency audit, so nobody runs these automatically. Run both before every release and after any dependency change. Neither adds a dependency to the project: `uvx` runs pip-audit from a temporary environment, and `npm audit` ships with npm.

```
uv export --no-dev --no-hashes --frozen | uvx pip-audit -r /dev/stdin --no-deps --disable-pip
cd app && npm audit --omit=dev
```

Status: **not run in CI**. No run is recorded in `docs/`.

On a finding:
1. Read the advisory. Does the vulnerable code path run in Shiori (a PDF parser bug matters; a server-only bug in a package we only import for types may not)?
2. If a fixed version exists, upgrade inside the allowed range, re-lock (`uv lock` or `npm install`), run the full test suite, and note the change in `decisions.md` if it is a runtime dependency.
3. If no fix exists, remove or replace the package, or isolate it (for the PDF parser, a low-privilege subprocess, which is not built). Record an accepted risk in `decisions.md` with the advisory ID, why it does not apply, and a date to look again.
4. Never suppress a finding without that note. Dev-only packages (`eval/`, `training/`, `collector/`) are audited too, but a finding there does not block a release, since they are never shipped.

## User-visible proof

- A Settings -> Network activity screen listing outbound and blocked requests: **Planned, not built** (`storage_design.md` does not cover it). Today the app prints one line when it quits with the number of blocked page requests.
- Demo test: turn off Wi-Fi, process a document end to end. Not done yet.

## Measured so far

<!-- net_sample:start -->
Network sample (2026-11-23, `scripts/net_sample.py`): one full extraction of the open Wakayama notice 2f2f5bd3
(Qwen3.5-9B, English queue included) on the dev Mac. Every 2 seconds `lsof` listed the internet sockets of the Electron
process tree (Electron, the sidecar, llama-server). 103 samples. Distinct remote endpoints that were not loopback:
none. Distinct loopback endpoints seen: 27. Sockets listening on a non-loopback address: none.
The app's own quit line was "renderer requests blocked: 0". Sampled, not a packet capture: a connection shorter than 2 seconds can be missed,
and it does not cover other processes on the machine.
<!-- net_sample:end -->

Real model download (2026-11-22): through the Setup screen, Gemma 4 E4B, 4.98 GB, about 18 minutes, SHA-256 verified against the registry hash. The terminal log shows the `download_done` event. Figures are from the terminal log of that run; no packet capture was taken during it.

## Checklist (must all pass before release)

No box is ticked. The note after each line says what exists today.

- [ ] Packet capture (e.g. Little Snitch on Mac, Wireshark) during a full session shows zero outbound connections after model setup. Not done (a socket sample only, see above)
- [ ] Test: renderer `fetch` to an outside host is blocked. Test exists: `tests/test_app_filter_electron.py` (skipped without a built app)
- [ ] Test: sidecar and llama-server refuse connections from non-loopback interfaces. Tests check the bind address only (`tests/test_sidecar.py::test_binds_loopback_only`, `tests/test_app_llama.py`)
- [ ] Test: sidecar returns 401 without the token. Test exists: `tests/test_sidecar.py::test_every_request_without_the_token_gets_401`
- [ ] Test: `grep` for CJK characters in all log output after processing 10 docs finds nothing. Not run
- [ ] Test: after delete, the saved document can't be opened (key gone). **Planned, not built** (`storage_design.md`)
- [ ] Test: ephemeral mode leaves no new files on disk (compare directory snapshots). **Planned, not built** (`storage_design.md`)
- [ ] Import-boundary test passes (no collector/eval/training/cloud SDK imports in shipped Python). Test exists: `tests/test_import_boundaries.py`
- [ ] Static security test passes (`tests/test_security_static.py`: no network, shell, unsafe-load or non-loopback bind code outside the allowlist). Test exists
- [ ] Dependency audits run and every finding handled (see "Dependency audits" above), results noted in the release notes. No run recorded
- [ ] Every threat in `threat_model.md` is "done"; none says "Planned, not built" at release. Several do today
- [ ] Spellchecker, HTTP cache, auto-update confirmed off. Source tests exist (`tests/test_app_no_network.py`); runtime checked on macOS only
- [ ] Every shipped dependency reviewed for telemetry. FastAPI is covered (D-117); no record of a full review
