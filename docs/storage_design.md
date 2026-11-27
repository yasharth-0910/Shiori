# Storage design: keeping documents between sessions

Status: accepted (D-119, 2026-11-27). Of section 6, steps 0 to 2 are done (`app/electron/store.ts`), and step 3 (`app/electron/keeper.ts`, `storageBase` in `paths.ts`, the single instance lock in `main.ts`). The by-hand check of step 3 passed on macOS in a dev run (reported by Yasharth, 2026-11-27): the keeper through a throwaway script under Electron, the lock through two copies of the app. Not run: Windows, Linux, a packaged build, an update (section 7). Steps 4 and 5 are built (`app/electron/settings.ts`, D-120; `app/electron/storage.ts`, wired into `main.ts` and the preload, D-121). Tested with a fake `safeStorage`, fake settings and a temp folder. The by-hand check of step 5 passed on macOS in a dev run (reported by Yasharth, 2026-11-27): saving turned on by hand, a PDF processed, `store_saved` logged, `store_opened docs=1 unreadable=0` after a restart, no text or path in the log, no readable Japanese in the store. That check did not cover delete, the confirm dialogs or the viewer reading the stored copy. Steps 7 and 8 are built in the renderer (D-123): the question line, the saved Library, delete, and the Settings switch, tested as pure logic and rendered with a fake bridge. Their by-hand checks in section 6 have not been run, and step 6 has not been run. Until the user says yes, D-116 still describes the app: results are kept in memory only.

This replaces the "Storage", "Deletion" and "Ephemeral mode" parts of `privacy.md` (see "What this changes in other docs").

## Today

- The Library is React state in the renderer (`app/src/App.tsx`). Quit the app and it is gone.
- The main process keeps two maps in memory: `picked` (document id to the file the user chose) and `jobs`.
- The sidecar keeps results and English translations in memory.
- The document id is the SHA-256 of the file. A Library row is one document plus one model (`resultKey`).
- The PDF viewer loads `shiori://app/doc/<id>.pdf`, and main reads the user's original file to answer it.
- The HTML viewer does not load the file. It shows `text` from the result.

## Recommendation in one paragraph

The main process owns a small folder of encrypted files in the app's user data folder (on Windows, in a folder under local app data instead, see section 2). Each document gets its own folder and its own random key. Files are encrypted with AES-256-GCM from Node's built-in `crypto`. Each document key is itself encrypted ("wrapped") with one master key, and the master key is encrypted by Electron `safeStorage`, which relies on the operating system's secret store. Deleting a document destroys its wrapped key first. No database and no new dependency. Saving is off until the user says yes.

## 1. What is stored

One record per document:

| Stored | Detail |
|---|---|
| Document id | SHA-256 of the file, inside the encrypted record only |
| Format | `pdf` or `html` |
| Date added, app version | For sorting and for knowing which release made a result |
| One result per model | The fields JSON the sidecar returns: field status, Japanese values, normalized values, items, citation ids, checks, and the cited sentences (text, page, section path and titles, boxes or anchor), plus `doc_type` and model id |
| HTML only | The extracted `text` (the document's source text) and `en_summary`, inside each result in the record |
| English translations | The ones main has received, per model: sentence id to `{en, numbers_match, protected_lost}` |
| PDF only | A copy of the PDF bytes, in a second encrypted file |

The copy of the PDF is needed because the original may be moved, changed or deleted, and a citation must always open the exact page it was made from. HTML has no second file: the viewer only uses the extracted text, which is inside the record, so `readSource()` in `store.ts` returns null for HTML.

Never stored:

- The user's file path or file name. The `pdf` entry of a stored result is set to `doc/<id>.pdf`, which is what the app already does in `Processing.tsx`.
- The raw HTML file.
- Sentences that no field cites (the sidecar does not send them).
- Rendered page images, the text PDF.js reads for Find, search text, live processing events.
- Model prompts and raw model answers.
- The sidecar token, the llama-server key, ports.
- Anything in plain text. There is no unencrypted index, title list or cache.

Exports (CSV, .ics) and Copy are different: the user asks for them, they are plain text, and deleting a document does not remove them. The delete dialog should say so.

## 2. Layout and encryption

```
<base>/store/
  master.key            master key, encrypted by safeStorage
  docs/<random name>/
    key                 this document's key, encrypted with the master key
    record.enc          the record above without the PDF copy, as JSON (holds an HTML document's source text)
    source.enc          the PDF bytes (PDF only; an HTML document has no such file)
<base>/settings.json        {"saveDocuments": "yes" or "no"}, written only once the user answers
```

Where `<base>` is:

| OS | `<base>` |
|---|---|
| Windows | `%LOCALAPPDATA%\shiori-app` (local, non-roaming) |
| macOS, Linux | `<userData>` |

On Windows, Electron's default `userData` is in the roaming profile, which can sync across a company's machines. The store holds confidential text, and a synced yes in `settings.json` would turn saving on at another machine without asking there (D-119). So both go under the local app data folder. `app.getPath` in Electron 44.4.5 has no name for that folder, so main reads the `LOCALAPPDATA` environment variable and joins it with the last part of the `userData` path (`shiori-app`). Not run on Windows yet.

If `LOCALAPPDATA` is missing or is not an absolute path, saving is not available (see "When saving is not available"). There is no `<base>`: nothing is saved, `settings.json` is neither read nor written, and the app never falls back to `userData`.

Folder names are 16 random bytes in hex, not the document id. The id is a hash of a public tender, so anyone holding the same file could compare hashes and learn that you opened it.

Keys:

- Master key: 32 random bytes, made on the first save (and again on the first save after "Delete all"). Written as `safeStorage.encryptString(base64 of the key)`.
- Document key: 32 random bytes, one per document, from `crypto.randomBytes`.

Every encrypted file (including `key`) has the same shape:

```
"SHI1" (4 bytes) | nonce (12 bytes) | ciphertext | tag (16 bytes)
```

- AES-256-GCM encrypts and also detects any change: if one byte differs, decryption fails.
- The nonce is 12 new random bytes on every write. A key must never use the same nonce twice. With random nonces and a few hundred writes per key, a repeat is not a practical risk.
- Additional authenticated data (checked but not encrypted) is `shiori-store-v1|<folder name>|<role>`, where role is `key`, `record` or `source`. A file moved to another folder or renamed to another role fails to open.
- Decryption passes `authTagLength: 16`, so a shortened tag is rejected.
- A file is decrypted completely in memory and used only after the tag check passes.
- The four-byte header lets a later version change the format.

Why two levels of keys: `safeStorage` holds one secret for the whole app. It cannot create or delete a keychain item per document. So we make the per-document keys ourselves and protect them with one master key.

Writing safely:

- Write to `<name>.tmp`, flush to disk, rename over the real name. A crash leaves the old file or the new one, never half of one.
- A new PDF document is written as `source.enc`, then `record.enc`, then `key` last. A new HTML document is written as `record.enc`, then `key`. A folder without `key` is incomplete and is removed at startup.
- Before saving a PDF, main reads the file and checks that its SHA-256 still equals the document id. If not, nothing is saved.
- Adding the same document with another model updates the existing record. It does not make a second folder.
- Updating translations never creates a document. If it was deleted, the update does nothing.
- The app takes Electron's single instance lock, so two copies cannot write at once. A second copy quits and the first one comes to the front.

When something is wrong:

| Situation | Behaviour |
|---|---|
| `master.key` exists but `safeStorage` cannot decrypt it (access denied, folder copied from another machine) | Saving and the saved Library are off, with a message. Delete nothing. Never make a new master key over the old one |
| `master.key` is missing but document folders exist | Same message, and offer "Delete all saved documents" |
| One document fails to decrypt | Skip it, count it in the Library notice, keep the others. Offer only "Delete all", because we cannot tell which document it is |
| A folder has no `key` file | Remove it (unfinished save or unfinished delete) |
| A save fails (disk full) | The result still opens in this session, marked "not saved" |
| Windows: `LOCALAPPDATA` is missing or not an absolute path | Saving is not available (see "When saving is not available") |

The only automatic deletion is the "no `key` file" case, and only when the master key opened (or no master key and no complete document exists). A failed decryption never deletes anything.

### The operating system's part

| OS | `safeStorage` uses | Can another program running as you get the master key? |
|---|---|---|
| macOS | Keychain | Normally the system asks the user first |
| Windows | DPAPI | Yes |
| Linux with GNOME Keyring or KWallet | the keyring | Generally yes, while the keyring is unlocked |
| Linux with no keyring | a password built into the program (`basic_text`) | Yes, and so can anyone who copies the folder |

The first three rows come from the platform documentation and have not been tested here. The `basic_text` backend is documented in the installed Electron (44.4.5) type definitions.

### When saving is not available

Two cases, handled the same way:

| Case | `state` | Reason shown |
|---|---|---|
| No usable keyring (in practice Linux) | `no_keyring` | "no system keyring was found. Set up GNOME Keyring or KWallet to save documents." |
| Windows with no usable `LOCALAPPDATA` | `no_local_folder` | "Windows did not give a local app data folder (LOCALAPPDATA)." |

Then the store is off and the app behaves like v0.1: everything works and the Library is in memory. The saving question is not asked and no answer is recorded. The Library and Settings say "Saving is not available on this computer:" followed by the reason, and the switch is disabled. The sentence about GNOME Keyring or KWallet is shown on Linux only.

#### Linux with no keyring

Recommendation: do not save. Check after the app is ready, and only when needed: there is something saved to open, a document has finished and the question has not been answered, or Settings is opened. A user who never turns saving on should not meet a keyring prompt at startup.

- `safeStorage.isEncryptionAvailable()` is false, or
- on Linux, `getSelectedStorageBackend()` is `basic_text` or `unknown`.

Never call `setUsePlainTextEncryption`. Documents saved earlier, when a keyring was present, stay on disk untouched and show as locked.

Writing with `basic_text` would look encrypted and protect nothing, which is worse than being honest.

#### Windows with no local app data folder

Do not save. Never write the store or `settings.json` to the roaming folder instead. Without `<base>` the app cannot find documents saved earlier: they stay on disk untouched, are not listed, and "Delete all saved documents" is disabled.

## 3. Opt-in saving and delete

### Saving is off by default

Nothing about a document is written until the user says yes. "Saving off" is what `privacy.md` calls ephemeral mode, and it is now the starting state.

The saved answer has three values:

| `settings.json` | Meaning | What happens |
|---|---|---|
| absent, unreadable, or any other value | not answered (`unanswered`) | Nothing is saved. The question is shown after a document finishes |
| `"saveDocuments": "no"` | No | Nothing is saved. Never ask again |
| `"saveDocuments": "yes"` | Yes | Each document is saved when it finishes |

The question:

- It appears after the first document finishes, as one line under the top bar: "Keep documents in your Library between sessions? Encrypted on this computer." with **Yes** and **No**.
- It does not block the screen. The user can read the document first.
- Only Yes or No is an answer. If the user quits without choosing, nothing is saved and the line returns after the next finished document.
- A cancelled or failed document does not trigger it. Neither does the fixture demo document.
- The answer is remembered in `settings.json`.

The first Yes also saves the documents that have already finished in this session, including the one the user is looking at. Otherwise the user would say yes and then lose that document. To make this possible, main keeps each finished result and its translations in memory until it quits.

### Settings

The Settings popover (today it says "There is nothing to set yet") gets:

- A switch, **Keep documents in your Library between sessions**, with "Encrypted on this computer." under it. It shows and changes the same saved answer.
- The number of saved documents.
- A button, **Delete all saved documents**.

Rules for the switch:

- If the question was never answered, turning the switch on counts as the first Yes.
- If saving was turned off (or answered No) and is turned on again, saving starts with the next document. Documents processed while it was off are not saved.
- Turning it off does not delete anything. Documents already saved stay in the Library, and the count and delete button stay available.
- While it is off, no document data is written at all: no new document, no new result and no new translation for an already saved one. Before the first Yes there is also no store folder and no master key.
- Deleting always works, whatever the switch says.

Model files, partial downloads and exports are not document storage and are not affected.

### Delete (crypto-shred)

Crypto-shred means: make data unreadable by destroying the key, not by overwriting the data.

1. Main shows a native confirm dialog: this removes the document and all its results for every model; exported files are not removed.
2. Delete `key`. From this moment the other files cannot be decrypted.
3. Delete the rest of the folder.
4. Drop it from main's memory (`picked`, `jobs`, the store's list).

If the app dies after step 2, startup cleanup finishes the job.

**Delete all saved documents:**

- Main shows a native confirm dialog with the number of documents, and says that exported files are not removed.
- It does steps 2 and 3 for every folder, then deletes `master.key`.
- The deleted documents also leave the Library and main's memory, so nothing can save them again. Documents that were never saved stay open.
- The saving switch keeps its value. If it is on, the next document makes a new master key.
- It needs no decryption, so it also works when the store is locked or damaged.
- It is disabled only when the store folder holds nothing.

What delete does not promise:

- The wrapped key is a small file on the same disk. An SSD or a copy-on-write file system may keep its old blocks. Someone who can recover them **and** can use your master key could read the document again.
- Backups (Time Machine, File History, a synced profile) made before the delete still contain the key and the files.
- The sidecar has no delete call, so its in-memory copy lasts until the app quits or the model is switched. Swap files are not covered.

So the honest sentence is: "After delete, Shiori cannot open the document, and the files cannot be read without both a recovered key and your login." It is not "gone forever". Against a thief who does not have your login, the data was already unreadable before the delete.

## 4. Threat model

What this protects:

| Case | Protected? |
|---|---|
| Laptop lost or stolen while powered off or logged out | Yes, as strong as the login password. Full-disk encryption (FileVault, BitLocker, LUKS) is still advised |
| Someone copies the `store` folder, or a disk image, without your login password | Yes. They get random-looking bytes |
| Another user account on the same computer | Yes, unless they have administrator rights and use them against you |
| A file in the store is changed or swapped | Detected. It fails to open |
| Backup or sync tool uploads the folder | Contents stay encrypted. The number of documents, their sizes and dates are visible |

What it does not protect:

| Case | Why |
|---|---|
| Malware running as you | It can ask the OS for the master key (see the table above), read the app's memory, or watch the screen |
| Someone at your unlocked computer | They can open the app |
| A thief who knows your login password | They are you, as far as the OS can tell |
| Compromised operating system, keylogger, screen recorder | Below the level the app works at |
| Swap, hibernation files, crash dumps made by the OS | Plain memory may be written to disk |
| Recovered blocks and old backups after a delete | See "Delete" |
| The user's original file and exported files | Not ours. They stay where the user put them, unencrypted |
| What the folder reveals by itself | Count, sizes and dates of documents. File sizes could be matched to known public tenders |

## 5. How the renderer reaches the store

The renderer never touches the disk and never sees a key or a path. Only main uses the store. The sidecar is unchanged and writes nothing.

New bridge functions (fifteen becomes twenty):

| Function | Input | Output |
|---|---|---|
| `listDocuments()` | none | `Fixture[]`, the saved documents |
| `getStorage()` | none | `{keep: boolean \| null, state: "ok" \| "no_keyring" \| "no_local_folder" \| "locked", saved: number, unreadable: number}`. `null` means not answered |
| `setKeepDocuments(keep)` | boolean | `{saved: number, failed: number}`, what the first Yes saved |
| `deleteDocument(docId)` | 64 hex characters | `boolean`, false if the user cancels the dialog |
| `deleteAllDocuments()` | none | `boolean`, same |

The question line is shown when `keep` is `null`, `state` is `ok` and a document has finished in this session.

As built (D-121): `getStorage` also returns `message`, the sentence "Saving is not available on this computer: <reason>" for `no_keyring` and `no_local_folder`, else `null`. `getStorage` can raise a keyring prompt, so the screens call it only at the times listed under "Linux with no keyring". In `state` `locked`, "Delete all saved documents" is enabled even when both counts are 0.

Changed:

- `getFields(docId)`: main keeps the result in memory and, if `keep` is true, saves it before returning it. It adds `saved: boolean`. A Library row is marked "not saved" only when saving is on and failed. Main supplies `doc_type` and `model_id` from what it already knows. The renderer never sends document content to be saved.
- The empty Library text becomes "Documents are kept only while the app is open. You can turn on saving in Settings." when saving is off.
- `translate(docId, ids, modelId)`: gains the model id, because translations are stored per model. Left out, it means the running model's job (today's screens send none). For the running model's job, main asks the sidecar as today, keeps any new items and saves them if saving is on. For a saved result with no running job, main returns the stored items with `total` equal to `done`, so the screen does not wait for more. Sentences with no stored English show Japanese only.
- `serve()` in `main.ts`: for `/doc/<id>.pdf`, use the picked file if there is one, else decrypt from the store. Send `cache-control: no-store`.

As today, every handler checks the sender (`own(e)`) and validates every argument (`docId`, a known model id shape, a real boolean).

Logging rules (CLAUDE.md):

- Log only event names, counts, byte sizes, timings and error types: `store_saved bytes=...`, `store_open_failed error=...`.
- Never document text, titles, file names, paths or keys. The store logs no document ids, since they identify the file, and no folder names. (The sidecar logs the first 8 characters of the id today. This design does not change that.)
- Node file errors contain the path in their message. Catch them in the store and rethrow a short code, as `llama.ts` does. Electron prints an error thrown by an IPC handler, so no raw error may leave a handler.

Where the code goes: `app/electron/store.ts`, using only Node modules. It receives the two functions that wrap and unwrap the master key, so tests can run it with plain `node --test` and a fake. `app/electron/keeper.ts` holds the small `safeStorage` part and the keyring check.

## Alternatives rejected

| Option | Why not |
|---|---|
| One SQLCipher database per document (the current plan in `privacy.md`) | Needs a native dependency, built for each platform, to store what is two blobs per document. We never query inside them |
| Plain SQLite or JSON, relying on full-disk encryption | Copying the folder gives away everything, and many machines have no disk encryption turned on |
| Encrypt every file directly with `safeStorage` | One key for everything, so no per-document destroy. It takes strings, not file bytes |
| One keychain item per document (`keytar` or similar) | Would make delete stronger against recovered blocks, but adds a native dependency, a different behaviour on each OS, and possibly a prompt per item. Revisit if strong delete becomes a requirement |
| A password the user types, turned into a key | Protects against more, including some malware before unlock, but adds a prompt at every start and a forgotten password loses everything. Could be added later by wrapping the master key a second time |
| The sidecar owns the store (`architecture.md` today) | Python has no built-in AES-GCM, so it needs a new dependency, and the key would have to cross to another process. `safeStorage` only exists in main |
| One encrypted file for the whole library | Every change rewrites everything, one damaged byte loses everything, no per-document delete |
| An encrypted index of titles | A second copy to keep in step. Reading each record at startup is enough. Revisit if startup is slow with many documents |
| Do not keep the PDF, remember its path | Stores a path, breaks when the file moves, and the highlight could point into a changed file |
| Saving on by default | Document text would reach the disk before the user chose that. Decided against on 2026-11-27 |
| Ask before the first document, in a dialog | The user has not seen a result yet, and it blocks the first run |

## 6. Tests and order of work

Each step is done when its tests pass, `npm run typecheck`, `npm test` and `uv run pytest` pass, and the stated check holds. Steps 5 to 8 must ship in the same release: saving without the question, delete and the off switch should not reach users. Step 6 is a gate: if it fails, stop and change the design before building the screens. `EXTRACTOR_VERSION` and the sidecar do not change.

| # | Step | Done when |
|---|---|---|
| 0 | Accept the design: new entry D-119, update `privacy.md`, `architecture.md`, `modules.md`, `threat_model.md` | The docs agree with each other and with this file; open questions below are answered or logged |
| 1 | `store.ts`: seal and open one blob | Tests: round trip; empty and 20 MB input; one flipped byte in header, nonce, body and tag each fails; short tag fails; wrong key, wrong folder and wrong role fail; two seals of the same input differ |
| 2 | `store.ts`: save, list, read PDF, add translations, delete, delete all, startup cleanup | Tests in a temp folder with a fake keeper: save and reopen with a new store object; second model joins the same document; changed source file is not saved; update after delete creates nothing; delete removes `key` first (stop it after step 2 and the document cannot be opened, even with a saved copy of the other files and the master key); copied-back files without `key` stay unreadable; leftover `.tmp` and keyless folders are removed; unreadable master key deletes nothing and writes nothing; canary string and canary file name appear in no file under the store and in no folder name; captured log output holds no canary, path or id |
| 3 | `keeper.ts` and single instance lock | Tests with a fake `safeStorage`: unavailable, `basic_text` and `unknown` give `no_keyring` and create no file. With the platform and environment passed in: on Windows a missing or relative `LOCALAPPDATA` gives `no_local_folder` and creates no file, under `userData` either; macOS and Linux use `userData`. A static test fails if `setUsePlainTextEncryption` appears in `app/`. By hand on the Mac: a key is made, survives a restart, and a second app copy does not start |
| 4 | The saved answer (three values) and the rule for the first Yes, used by the store | Tests: not answered leaves the user data folder and `<base>` byte for byte unchanged (compare snapshots); No changes only `settings.json`; neither makes a master key; unreadable settings means not answered; first Yes saves the finished session documents; off then on does not save earlier ones; off blocks translation updates but not delete |
| 5 | Main wiring: keep results in memory, save in `getFields`, save translations, serve the stored PDF, answer `translate` for saved results, open the store at startup and log `store_opened docs=N unreadable=M` or `store_locked` | Tests for the pure parts; `test_app_ipc.py` still lists every channel and sender check. By hand with saving set to `true` in `settings.json` and an open-license PDF: process, quit, check that the files hold no readable Japanese and that the log holds no text or path |
| 6 | Keychain gate (macOS) | The test in section 7 is run and its result is written into `decisions.md` |
| 7 | `listDocuments`, `getStorage`, `setKeepDocuments`, `deleteDocument`; the question line; Library loads saved documents; empty-state and notice text | `test_app_ipc.py` expects the new function set. Logic tests for when the line shows (each answer, each store state). By hand: first document finishes and the line shows; quit without answering, nothing saved; Yes, quit, rename the original file, reopen, highlights land on the same sentences; No, restart, never asked again; delete one, restart, it is gone and its folder with it |
| 8 | Settings: switch, saved count, "Delete all saved documents" (`deleteAllDocuments`) | Tests: delete all removes every folder and `master.key`, works when locked, keeps the switch value, and the next save makes a new key. By hand: with saving off, one PDF and one HTML notice leave a directory snapshot unchanged apart from `settings.json` and known non-document files. Search the whole user data folder, including Chromium's cache folders, and `<base>` where it is elsewhere (Windows), for a canary sentence from an invented test document: no hit, with saving off and on |
| 9 | Packaged checks and the privacy checklist | macOS: section 7 run again with the real screens. Windows and Linux (with and without a keyring) tried by hand or marked untested. The delete and ephemeral lines in `privacy.md` are ticked only for what was run |

The existing fixture document stays memory only and is never saved.

## 7. Test plan: does the Keychain key survive an update?

**Question.** Builds are ad-hoc signed (D-114), so each build has a different code identity. macOS ties access to a Keychain item to the app's identity. After an update, does the new build get the master key silently, after a prompt, or not at all? Not tested yet.

**When.** Step 6, as soon as step 5 works, and again in step 9.

**Where.** A second macOS user account on the dev Mac, so the real app data and Keychain are not touched. No model is needed. Use an invented or open-license PDF.

### Build two versions

Build the inputs once, as in the README ("Build an installer"). Then build version A:

```bash
cd app && npm run dist
```

Copy the `.dmg` out of `app/release/`. Change `version` in `app/package.json` to a higher test number, run the same command again, copy that `.dmg` as version B, then put the version number back. Copy both files to a folder the test account can read.

### Run

In the test account:

1. Check that `~/Library/Application Support/shiori-app/store` does not exist. In Keychain Access, note whether an entry ending in "Safe Storage" for this app already exists.
2. Install A into the test account's own `~/Applications` folder (make it if missing), so the app in `/Applications` is not replaced. Record its signature hash:

```bash
codesign -dv --verbose=4 "$HOME/Applications/Shiori.app" 2>&1 | grep CDHash
```

3. For step 6 only (no question line yet), turn saving on by hand:

```bash
mkdir -p "$HOME/Library/Application Support/shiori-app" && printf '{"saveDocuments": "yes"}' > "$HOME/Library/Application Support/shiori-app/settings.json"
```

4. Start A from Terminal so the log is visible:

```bash
"$HOME/Applications/Shiori.app/Contents/MacOS/Shiori"
```

5. Add the test PDF and wait for it to finish. (In step 9, answer Yes to the question line.) Quit.
6. **Control:** start A again. The log must say `store_opened docs=1 unreadable=0`. If it does not, saving itself is broken and the test says nothing about updates. Quit.
7. Record the checksums of the saved files:

```bash
find "$HOME/Library/Application Support/shiori-app/store" -type f -exec shasum -a 256 {} +
```

8. Replace the app in `~/Applications` with B. Run the `codesign` command again. **The hash must differ from A's.** If it is the same, the test proves nothing: make a small code change and rebuild B.
9. Start B. Write down any Keychain prompt, word for word, before clicking. If there is one, first click **Deny**. Expected: the log says `store_locked`, and step 7 gives the same checksums (nothing deleted or rewritten). Quit.
10. Start B again. If prompted, click **Always Allow** (you type the password yourself). The log must say `store_opened docs=1 unreadable=0`. In step 9, also open the document and click a citation.
11. Quit and start B a third time. Note whether it prompts again.
12. If B prompted: build a version C the same way, install it over B and start it. This shows whether every update prompts again. Going back to A would not show that, because A created the Keychain entry.
13. Start B once from Finder as well, in case the prompt differs from a Terminal launch.

If a downloaded build matters, repeat steps 8 to 10 with a `.dmg` built by CI.

### Reading the result

| What happens with B | Meaning |
|---|---|
| Opens with no prompt | Pass. Keep the design |
| Prompts once per new build, Always Allow works | Works, with a prompt after each update. Decide whether that is acceptable; if so, say it in the release notes and next to the saving question |
| Prompts at every launch | Poor. Fix before shipping |
| Cannot open, even after allowing | Fail. The design does not work on macOS as written |

If it fails or is not acceptable, the options to look at are: a Developer ID signature (paid account), signing every build with the same self-made certificate (untested), or protecting the master key with a user password instead of the Keychain.

Record for each run: macOS version, both hashes, each prompt, the log lines, and whether the checksums changed.

## What this changes in other docs

- `privacy.md`: "Ephemeral mode" becomes the default, with saving as an opt-in;
- `privacy.md`: replaces SQLCipher with encrypted files; "destroy its key in the keychain" is not possible with `safeStorage` (we delete our own wrapped key file); the encrypted index goes; the threat table line "Deleted documents recovered from SSD" must be narrowed as in "Delete" above.
- `architecture.md`: the store moves from the sidecar to main; the "Local store" technology row changes.
- `modules.md`: the Store entry moves from `core/shiori_core/store/` to `app/electron/store.ts`. Its status there is already "planned".
- `threat_model.md`: rows 14 and the SSD note under "What we cannot promise".

## Open questions

Decided on 2026-11-27: saving is off by default and opt-in.

1. Open, logged in `decisions.md`. Does the macOS Keychain still give the app its key after an update (ad-hoc signing, D-114)? Not tested. Section 7 is the test.
2. Answered (D-119): synchronous `safeStorage` calls. Electron 44 also offers asynchronous ones.
3. Answered (D-119): on Windows the store and `settings.json` live in a local, non-roaming folder (section 2), because the roaming profile can sync across a company's machines and the store holds confidential text.
4. Open, logged in `decisions.md`. Stored results keep the citations and boxes of the release that made them. After an extractor change, should the app offer to process again? The fields response does not carry the extractor version today.
5. Answered (D-119): yes. Translations are saved only while a document's screen is asking for them, and a sentence with no stored English shows Japanese only.
6. Settled on 2026-11-27: `app/electron/main.ts` now turns the spellchecker off and empties its dictionary list (D-118), and turns the HTTP cache off. Checked on macOS only. Windows and Linux have not been run.
7. Settled on 2026-11-27: in `main.ts`, the file reads in `shiori:start` and `serve()` and the write in `shiori:save` now go through `userFile` (`app/electron/userfile.ts`), which logs and throws only the error type. Tests: `app/test/userfile.test.ts` and `tests/test_app_no_network.py`.
