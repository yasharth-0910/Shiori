# Privacy design

The promise: **no document, extracted text, or result ever leaves the user's machine.** Local storage is allowed and encrypted. The user can wipe any document permanently.

## Threats we design for

| Threat | Mitigation |
|---|---|
| App or a dependency sends data out | Network blocked at the Electron session level; CSP; no SDKs with telemetry; privacy tests |
| Another local app queries our model or sidecar | Bind to 127.0.0.1, random ports, per-session tokens |
| Laptop stolen or disk imaged | Per-document encryption, keys in OS keychain |
| Deleted documents recovered from SSD | Crypto-shredding (destroy the key) |
| Document text ends up in logs or crash dumps | Content-free logging, crash reporting off |
| User documents end up in training data | Training uses only public tenders; app has no upload path at all |

Out of scope: a compromised OS or a malicious user with full access to an unlocked session.

## Design

**Network**
- In main: `session.defaultSession.webRequest.onBeforeRequest` cancels every request that isn't `file://`, `devtools://` (dev builds only), or our own localhost ports.
- Renderer CSP: `default-src 'self'; connect-src 'none'` (renderer talks only via IPC). No remote fonts, no CDN scripts.
- Built-in spellchecker disabled (`spellcheck: false`, and don't load dictionaries; on Windows Electron fetches them from a Google CDN).
- HTTP cache disabled.
- No auto-update calls. Updates are manual downloads, or an opt-in "check for updates" button that only fetches a version file.
- The only allowed outbound path: first-run model download, from pinned URLs, verified by SHA-256, shown clearly to the user. After that the block is total. A manual "import model file" option exists for air-gapped machines.

**Local services**
- Sidecar and llama-server bind to 127.0.0.1 only, never 0.0.0.0.
- Random free port each launch.
- 32-byte random token per launch, required on every request.

**Storage**
- One SQLCipher database per document: PDF bytes, sentences, boxes, results.
- Each document has its own random key, stored via Electron `safeStorage` (backed by macOS Keychain / Windows DPAPI).
- The app keeps an encrypted index of documents (title, date added) under a separate key.
- No plaintext copies. Temp files from OCR are written to an encrypted temp location or kept in memory, and wiped on job completion and on startup.

**Deletion**
- Delete a document: destroy its key in the keychain, then delete the file. Without the key the ciphertext is useless, which matters because SSDs don't reliably overwrite deleted blocks.
- "Delete all" destroys every key and the index key.

**Ephemeral mode**
- Setting that keeps everything in memory for the session. Nothing written to disk except the model file. Closing the window drops it all.

**Logging**
- Events only: stage names, timings, page counts, sentence IDs, error types.
- Never document text, never file names or paths of user documents.
- A log filter on child process output drops any line containing CJK text before writing.
- Crash reporter disabled.

**Training**
- LoRA is trained on public tenders only. The app has no code path that exports user data for any purpose. State this in the UI and README.

## Threat model and static checks

The full threat table (threat, mitigation, the test that proves it, status) is in `threat_model.md`. `tests/test_security_static.py` enforces the code-level rules on `core/`, `sidecar/` and `app/` (when it exists) with `ast`; allowlist entries need a written reason. It sits next to `tests/test_import_boundaries.py`, which it does not repeat.

## Dependency audits (manual, not in CI)

There is no CI yet, so nobody runs these automatically. Run both before every release and after any dependency change. Neither adds a dependency to the project: `uvx` runs pip-audit from a temporary environment, and `npm audit` ships with npm.

```
uv export --no-dev --no-hashes --frozen | uvx pip-audit -r /dev/stdin --no-deps --disable-pip
cd app && npm audit --omit=dev      # when app/ exists (Phase 7)
```

Status: **not run in CI** (no CI). Not yet run on this repo.

On a finding:
1. Read the advisory. Does the vulnerable code path run in Shiori (a PDF parser bug matters; a server-only bug in a package we only import for types may not)?
2. If a fixed version exists, upgrade inside the allowed range, re-lock (`uv lock` or `npm install`), run the full test suite, and note the change in `decisions.md` if it is a runtime dependency.
3. If no fix exists, remove or replace the package, or isolate it (the PDF parser belongs in the low-privilege subprocess). Record an accepted risk in `decisions.md` with the advisory ID, why it does not apply, and a date to look again.
4. Never suppress a finding without that note. Dev-only packages (`eval/`, `training/`, `collector/`) are audited too, but a finding there does not block a release, since they are never shipped.

## User-visible proof

- Settings -> Network activity: lists every outbound request attempt since launch (should be empty) and every blocked attempt.
- Demo test: turn off Wi-Fi, process a document end to end.

## Measured so far

<!-- net_sample:start -->
Network sample (2026-11-23, `scripts/net_sample.py`): one full extraction of the open Wakayama notice 2f2f5bd3
(Qwen3.5-9B, English queue included) on the dev Mac. Every 2 seconds `lsof` listed the internet sockets of the Electron
process tree (Electron, the sidecar, llama-server). 103 samples. Distinct remote endpoints that were not loopback:
none. Distinct loopback endpoints seen: 27. Sockets listening on a non-loopback address: none.
The app's own quit line was "renderer requests blocked: 0". Sampled, not a packet capture: a connection shorter than 2 seconds can be missed,
and it does not cover other processes on the machine.
<!-- net_sample:end -->

## Checklist (must all pass before release)

- [ ] Packet capture (e.g. Little Snitch on Mac, Wireshark) during a full session shows zero outbound connections after model setup
- [ ] Test: renderer `fetch('https://example.com')` is blocked
- [ ] Test: sidecar and llama-server refuse connections from non-loopback interfaces
- [ ] Test: sidecar returns 401 without the token
- [ ] Test: `grep` for CJK characters in all log files after processing 10 docs finds nothing
- [ ] Test: after delete, the document database can't be opened (key gone)
- [ ] Test: ephemeral mode leaves no new files on disk (compare directory snapshots)
- [ ] Import-boundary test passes (no collector/eval/training/cloud SDK imports in shipped code)
- [ ] Static security test passes (`tests/test_security_static.py`: no network, shell, unsafe-load or non-loopback bind code outside the allowlist)
- [ ] Dependency audits run and every finding handled (see "Dependency audits" below), results noted in the release notes
- [ ] Every threat in `threat_model.md` is "done" or has a named phase; none says "not built yet" at release
- [ ] Spellchecker, HTTP cache, auto-update confirmed off
- [ ] Every shipped dependency reviewed for telemetry
