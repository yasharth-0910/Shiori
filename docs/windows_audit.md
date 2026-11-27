# Windows audit (reading only)

Date: 2026-11-28. Nothing was run on Windows, no code was changed, no model was called. Line numbers are for the tree at commit `d052bd3`.

How sure:

- **read**: follows from the code or files in this repo.
- **inferred (high, medium, low)**: the line is real, but the effect depends on how Windows, Node, libuv, Electron or antivirus software behaves, taken from general knowledge and not checked here.

Severity: **breaks** (a main feature does not work on an affected machine), **degrades** (works worse, fails sometimes, or leaves something behind), **cosmetic**.

## 1. Found in the code

Rows marked "all OSes" are not Windows-only, but Windows makes them more likely.

### Breaks

| ID | File and line | What goes wrong on Windows | How sure | Smallest fix |
|---|---|---|---|---|
| W01 | `app/electron-builder.config.cjs:46`, `packaging/fetch_llama.py:65` | The bundled llama.cpp binaries import `VCRUNTIME140.dll`, `VCRUNTIME140_1.dll` and `MSVCP140.dll`. None of the three is in the pinned Windows zip or added to the installer. On a PC without the Visual C++ redistributable, llama-server cannot start. The app shows "Model failed to start (llama_exited_while_loading)" or similar and runs rules only. The CI smoke test cannot catch this because the runner has Visual Studio. | read (imports and zip listing); inferred high (clean PCs lack the DLLs) | Copy the three DLLs into `resources/llama` at build time, or run the redistributable from the NSIS installer. Record the license in `docs/decisions.md`. |
| W02 | `app/electron-builder.config.cjs:56`, `README.md:58` | The installer, `shiori-sidecar.exe` and `llama-server.exe` are unsigned. Most PCs show SmartScreen (README covers this). With Windows 11 Smart App Control enforcing, or a company AppLocker policy, they are blocked with no "Run anyway". Antivirus may also quarantine the PyInstaller sidecar as a false positive; the app then only reports `sidecar_start_failed`. | inferred high (SmartScreen), medium (Smart App Control, antivirus) | Short term: say in README that Smart App Control blocks the app and how a quarantined sidecar looks. Real fix is a code-signing certificate. |

### Degrades

| ID | File and line | What goes wrong on Windows | How sure | Smallest fix |
|---|---|---|---|---|
| W03 | `app/electron/sidecar.ts:35`, `app/electron/llama.ts:61` | Neither `spawn` sets `windowsHide`. Both children are console programs (`packaging/sidecar.spec:38` has `console=True`) started by a GUI app, so each is likely to open a visible console window. Closing that window kills the process. For the sidecar, `windowsHide` alone may not be enough because stderr is `"inherit"`. | inferred medium to high | `windowsHide: true` on both. In the sidecar spawn, use `"ignore"` for stderr when packaged. |
| W04 | `app/electron/main.ts:70`, `app/electron/main.ts:296`, `app/electron/discover.ts:28` | Packaged models and partial downloads (about 5 to 6 GB each) go under `userData`, which is `%APPDATA%`, the roaming profile. On a managed PC this can sync at sign-in and sign-out or exceed the profile quota. The store already avoids this (`paths.ts:40`). `paths.ts:48` `modelsDir` has the same choice and `main.ts` does not call it. | read (the folder); inferred high (roaming effect) | On win32, build the models and downloads folders from the same local base that `storageBase` returns. |
| W05 | `app/electron/store.ts:141-142`, `app/electron/storage.ts:114` | Any error reading `master.key` becomes `locked`, including a passing `EBUSY` or `EPERM` from antivirus or backup software. `locked` is remembered until restart or "Delete all", and Settings offers "Delete all", so a brief file lock can push the user to destroy readable documents. | read (the mapping); inferred medium (the trigger) | Map only a failed unwrap or a missing file to `locked`. Throw `read_failed` for `EBUSY`, `EPERM`, `EACCES` so the next call tries again. |
| W06 | `app/electron/store.ts:97`, `app/electron/settings.ts:29` | `renameSync` over an existing file fails with `EPERM`, `EACCES` or `EBUSY` while another process holds the target without delete sharing (antivirus, indexer, backup). There is no retry. A document is reported not saved, or the saving answer fails with "Could not save your answer". English is retried only if another translate poll arrives. The old file stays intact. | inferred high (Windows rename behaviour), medium (how often) | One shared helper: retry the rename a few times with a short wait on those three codes. |
| W07 | `app/electron/store.ts:195-196`, `app/electron/store.ts:303` | `rmSync` is called with no retries. A file held by another process gives `EPERM`, `EBUSY` or `ENOTEMPTY` and delete fails. `force` only ignores a missing file. If the key is removed but the folder is not, the call throws, so `storage.ts:245-246` skips `drop` and the document stays in memory until delete is pressed again. | inferred high (error codes), medium (how often) | Add `recursive: true, maxRetries: 5` to all three calls (Node applies `maxRetries` only with `recursive`). |
| W08 | `app/electron/store.ts:303`, `app/electron/store.ts:314-322` | "Delete all" stops at the first folder that throws. Later folders keep their keys and stay readable, and `master.key` stays. Startup cleanup stops the same way. The user does see an error. All OSes. | read | Try every folder, remember the first error, throw it after the loop. |
| W09 | `app/electron/sidecar.ts:30`, `app/electron/sidecar.ts:51`, `app/electron/main.ts:80` | If the sidecar fails to spawn (`error` event or a synchronous throw, for example blocked by antivirus) or sends a bad hello while staying alive, `hello` is not reset (`exit` need not follow a spawn error), and `ensureBackend` returns the failed backend for the same model. Every later "Add document" fails until the app restarts or the model is switched. All OSes. | read (the state); inferred medium (Windows spawn throwing) | In `main.ts` catch block call `sidecar.stop()`, and at line 80 do not reuse a backend whose state is `failed`. |
| W10 | `app/electron/download.ts:169-171` | Renaming the finished multi-GB `.part` file can fail while antivirus is scanning it. This becomes `disk`. The partial file is kept, so a second click re-hashes and tries again, but the message points at disk space. | inferred medium | Retry the rename on `EPERM`, `EACCES`, `EBUSY` (same helper as W06). |
| W11 | `app/electron/download.ts:220-226`, `app/electron/download.ts:177` | Importing a model that is already installed renames over a file that a running llama-server may hold open, which fails after copying several GB. The cleanup `rmSync` inside the `catch` can itself throw on a locked file; then the IPC call rejects with a raw error that holds a file path, which Electron prints (`main.ts:442` does not wrap it). | inferred medium (rename), low (cleanup throwing) | Return success early when `to` exists with the right size and hash. Wrap both cleanup `rmSync` calls in `try`. |
| W12 | `app/electron/discover.ts:272-277` | "Use this one" on a model with no `.gguf` name (an Ollama blob) tries a symlink (needs Developer Mode or admin), then a hard link (same drive only, not on FAT or exFAT). A blob on another drive fails with "Check that the disk has room". Reachable through "Search a folder". | read (fallbacks); inferred high (privilege) | Let `importFile` accept the real path with the name check turned off, and drop the link code. |
| W13 | `app/electron/download.ts:60`, `app/electron/download.ts:71` | Node's `https` does not use the system proxy, and by default does not use the Windows certificate store. Behind a company proxy or antivirus HTTPS scanning, the model download fails as `offline` or `interrupted`. Import from disk still works. | inferred medium | Pass the system CA list (`tls.getCACertificates("system")`) with the default one, and name "choose a file from disk" in the error text. Proxy support is a separate decision. |
| W14 | `core/shiori_core/extract/llm.py:48` | One model call may take at most 300 s. `app/electron/registry.ts:45` records 211 s for a whole short document on the M4 CPU. A slower Windows laptop without a GPU can exceed 300 s on one call; it is retried once (`llm.py:637-650`) and the field ends as not found. | inferred medium | Raise the limit for CPU-only machines, after one timed run on the target laptop. |
| W15 | `app/electron/main.ts:335`, `sidecar/server.py:694` | A PDF with a path over 260 characters is read and hashed by Node, but Python may report `is_file()` false unless Windows long paths are enabled. The document fails with `sidecar_http_400`. | inferred low to medium | Send `path.toNamespacedPath(file)` to the sidecar. |
| W16 | `app/electron-builder.config.cjs:57` | The NSIS settings do not remove app data. Uninstalling leaves the downloaded models (several GB), `%APPDATA%\shiori-app` and the saved documents and settings in `%LOCALAPPDATA%\shiori-app`. | inferred high | State it in README, or add an uninstall step that asks before deleting both folders. |

### Cosmetic

| ID | File and line | What goes wrong on Windows | How sure | Smallest fix |
|---|---|---|---|---|
| W17 | `app/electron/main.ts:174` | `hiddenInset` is a macOS style. Windows is expected to show a normal title bar and the default menu bar above the app's own header (`app/src/App.tsx:155` only pads for macOS). See U2. | inferred medium | Set `titleBarStyle` only on darwin and remove the menu on win32. |
| W18 | `app/electron/store.ts:172-178`, `app/electron/store.ts:218` | If a record is briefly unreadable during a save, `find` misses it and a second folder is made for the same document. The Library can then list it twice and translations split. Delete already removes both (`store.ts:288-291`). | read (path); inferred low (trigger) | Same transient-error handling as W05: fail the save instead of treating the document as new. |
| W19 | `.github/workflows/release.yml:112-114` | Windows Python writes text with CRLF, so `SHA256SUMS-windows-x64.txt` has CRLF line ends and `sha256sum -c` or `shasum -c` on another OS looks for a file name ending in CR. Comparing by eye still works. | read | `open(..., "w", newline="\n")`. |
| W20 | `app/electron/main.ts:543-545` | `SIGTERM` is not delivered on Windows, and Electron does not emit `will-quit` on shutdown or sign-out. `stopAll` may not run then; the OS ends the processes. | inferred high | None needed. Correct the comment at line 533. |
| W21 | `app/electron/sidecar.ts:81-82` | `kill("SIGTERM")` on Windows terminates at once, so the stdin-close shutdown and the handler at `sidecar/__main__.py:127-128` get no chance to run. The sidecar writes nothing to disk, so nothing is lost. | inferred high | Optional: on win32 end stdin and kill after a short delay. |
| W22 | `app/electron/download.ts:220`, `app/electron/discover.ts:57` | File names are compared case-sensitively. A different casing of the installed model path causes a needless re-copy, and `SHIORI_MODEL` with different casing is treated as a custom model. | read | Compare lower-cased on win32. |
| W23 | `app/electron/main.ts:406` | Exporting over a CSV that is open in Excel fails (`EBUSY`) and shows only "Export failed." (`app/src/Workspace.tsx:199`). | inferred high | Add "close the file if it is open" to the message. |
| W24 | `packaging/third_party_notices.py:30` (also 76, 81, 94, 104, 121, 140, 168) | Local installer builds read and write without an encoding. CI sets `PYTHONUTF8` (`release.yml:46`), but the README build steps do not, so a local Windows build can fail on cp1252. Dev-time only. | read | Pass `encoding="utf-8"`. |

## 2. Checked in the code, no finding

- **Loopback and firewall.** Sidecar binds `127.0.0.1` (`sidecar/server.py:769-775`), llama-server gets `--host 127.0.0.1` (`llama.ts:50`). A listener on loopback does not normally raise a Windows firewall prompt. Only `llama-server.exe` is unpacked from the llama.cpp programs.
- **Non-ASCII and spaces for llama-server.** The pinned `llama-server.exe` manifest declares `activeCodePage` UTF-8 and `longPathAware`, so the narrow `argv` and `fopen` calls in its DLLs should receive UTF-8 on Windows 10 1903 or later. Long paths still need the system setting.
- **Spaces in paths.** Both spawns pass an argument array with no shell (`sidecar.ts:35`, `llama.ts:61`).
- **OCR ASCII path.** Not reachable in a normal packaged run: OCR is not bundled and `ndlocr_dir()` returns None when frozen without `SHIORI_NDLOCR_DIR` (`core/shiori_core/ocr/ndlocr.py:33-36`).
- **LOCALAPPDATA.** Missing, relative, `\dir` and `C:dir` values give `no_local_folder` (`paths.ts:40-45`), and `settings.ts` never reads or writes then. `main.ts:118` passes `process.env` itself, so name casing does not matter.
- **safeStorage.** `keeper.ts` applies the keyring check to Linux only, which is right for DPAPI. See U4.
- **Executable names and path separators.** `.exe` is added in `paths.ts:16` and `discover.ts:19`; `llama.ts:49` accepts backslashes; the `shiori://` handler compares with `path.sep` (`main.ts:158-159`). `/opt/homebrew/bin` and `/usr/local/bin` (`discover.ts:20`) are dev-only and harmless.
- **No POSIX-only calls** found in `core/` or `sidecar/` by search (no `fork`, `kill`, `fcntl`, `/tmp`). The sidecar reads stdin with `os.read(0, ...)`.
- **CRLF.** CSV and ICS use CRLF on purpose (`app/src/export.ts`). The hello line is parsed with `JSON.parse`, which accepts a trailing CR. There is no `.gitattributes`; no problem from that was found in the files read.
- **Open handles on the user's PDF.** `read_pages` closes the PDF with a context manager (`ingest.py:121`).
- **Cross-drive move of a download.** `EXDEV` is handled (`download.ts:171-179`).
- **Case in the store.** Folder names and ids are lower-case hex.
- **Japanese text display.** `lang="ja"` styles list Meiryo (`app/src/style.css:31`).

## 3. Cannot know without running Windows

| ID | Question | Where | Why it matters |
|---|---|---|---|
| U1 | Does the GUI app have a valid stderr to pass on? If not, Python may get `sys.stderr = None`, and uvicorn's default log setup is known to fail then. | `sidecar.ts:35`, `sidecar/__main__.py:109-119` | Would stop the sidecar starting. CI cannot show it because it runs the sidecar from a shell. The W03 fix covers it. Check this first. |
| U2 | Does Electron on Windows ignore `hiddenInset`, or hide the title bar and window buttons? | `main.ts:174` | If hidden, there is no close or minimise button, which raises W17 to breaks. |
| U3 | After End Task on the app, are the sidecar and llama-server gone? libuv is expected to put children in a kill-on-close job, which would make the comment at `llama.ts:4` wrong for Windows. | `llama.ts:4` | A leftover llama-server holds several GB of RAM. |
| U4 | `safeStorage` on Windows is expected to keep its DPAPI-wrapped key in `userData\Local State` (roaming), while `master.key` is in the local folder. Does saving survive a profile reset, a roaming sign-in, a password reset, and a force-kill right after the first save? | `keeper.ts:18`, `paths.ts:40` | Losing that key shows the store as locked for good. |
| U5 | Does Cancel stop a model call at once? `shutdown()` from another thread may not wake a blocked `recv` on Windows. | `llm.py:237-246` | Cancel could wait until the call ends. |
| U6 | Does everything work with a Japanese or accented user name and a space in it: install, sidecar start, PDF open, model load, save, delete? Some Node 22 to 24 releases had `rmSync` and `cpSync` faults on non-ASCII Windows paths (from memory; not checked for Electron 44.4.5). | `store.ts:195-196`, `store.ts:303` | Delete is a privacy promise. |
| U7 | Is the PyInstaller sidecar `longPathAware`, and what happens when the install folder is deep or non-ASCII? | `packaging/sidecar.spec:32-40` | Decides W15. |
| U8 | Does the stdin watcher thread ever stall a lazy DLL load? CI only calls `/health`, never processes a document. | `sidecar/__main__.py:36-40` | A hang on first document would not show in CI. |
| U9 | What do Defender and SmartScreen actually do with this installer and the two executables? | `release.yml:67` | Decides how bad W02 is. |
| U10 | Do PDFs with non-embedded Japanese fonts render, and do highlights land correctly, with Windows fonts and display scaling? | `app/src/PdfView.tsx:38` | Highlights are the core feature. |
| U11 | Does an upgrade install succeed while the app or a child process is running? | `electron-builder.config.cjs:57` | Locked files can stop the installer. |
| U12 | Time and peak RAM on a 16 GB laptop without a GPU. | `llama.ts:13-15` | Decides W14. |

No tests run on Windows: `.github/workflows/checks.yml:20` is Linux only. The Windows release job starts the packaged sidecar, calls `/health`, closes stdin and runs `llama-server --version` (`release.yml:73-104`). `docs/release_notes_v0.1.2.md:30` says this passes; the CI logs were not read for this audit.

## 4. Unit tests that could simulate these on the Mac (proposed, not written)

Faults can be injected by mocking the default `node:fs` object (`mock.method` plus `module.syncBuiltinESMExports()`); check first that the modules under test see the mock with the way `node --test` loads them. Making a folder read-only with `chmod` gives a real `EACCES` without mocks.

| For | Test |
|---|---|
| W01 | Read the import names from every `.dll` and `.exe` in the unpacked Windows llama folder and fail when one is neither shipped nor on a list of Windows system DLLs. Skips when the folder is absent. |
| W03 | Static check, like `tests/test_app_llama.py`: both spawns set `windowsHide: true`, and the packaged sidecar stderr is not `"inherit"`. |
| W04 | Move the folder choice into `paths.ts` and call it with win32 values: models and downloads are under `LOCALAPPDATA`, never `userData`. |
| W05, W18 | `readFileSync` throws `EBUSY` once on `master.key` (then on `record.enc`): the call fails with `read_failed`, the next one works, and there is still one folder. |
| W06, W10 | `renameSync` throws `EPERM` twice, then passes: save, settings write and download all succeed. Throwing every time leaves the old file intact. |
| W07 | `rmSync` records its options: delete passes `recursive` and `maxRetries`. |
| W08 | Three documents, the second folder cannot be removed: delete all throws, and the first and third are gone. |
| W09 | Start the sidecar with a command that does not exist, then start again: the second call spawns anew. Needs `spawn` and `electron` to be injectable. |
| W11 | `renameSync` and `rmSync` both throw during import: the result is `{ ok: false }`, nothing rejects. |
| W12 | `symlinkSync` throws `EPERM` and `linkSync` throws `EXDEV`: the import still succeeds. |
| W14 | A fake slow server with a small timeout shows the retry and not-found path; the CPU value is read from one setting. |
| W19 | Static check that the checksum step in `release.yml` opens its output with `newline="\n"`. |
| W22 | `discover` with platform win32 and a differently cased `SHIORI_MODEL` finds the registry entry. |
| W24 | Run the notices script with `PYTHONWARNDEFAULTENCODING=1` and `-W error::EncodingWarning`. |

W02, W13, W15, W16, W17, W20, W21, W23 and U1 to U12 need a real Windows machine for a meaningful check.
