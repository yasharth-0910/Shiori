// The storage service (docs/storage_design.md sections 3 and 5, D-119, D-121): main's only way to the store. The saving
// rules are enforced here, not in the renderer. Arguments from the renderer arrive as unknown and are checked before the
// disk is touched. A storage failure leaves as a StoreError (a code and nothing else), and log lines hold events, counts
// and codes only. Only Node modules: safeStorage, the settings file, the confirm dialog and main's maps are passed in.
import * as fs from "node:fs";
import * as path from "node:path";
import { createKeeper, type SafeStorage } from "./keeper.ts";
import type { SaveDocuments } from "./settings.ts";
import { createStore, type Keeper, type Result, StoreError, type Translation } from "./store.ts";

// What one save may carry. A result is the fields JSON plus its English; the source is the PDF that gets copied.
export const MAX_RESULT_BYTES = 20 * 1024 * 1024;
export const MAX_SOURCE_BYTES = 200 * 1024 * 1024;

const ID = /^[0-9a-f]{64}$/;
const SENTENCE = /^(?:p\d+_s\d+|h_s\d+|value:title)$/; // a sentence id, as core makes them, or the title value's queue key (D-91)
const MODEL = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/; // a registry id or "custom"
const FOLDER = /^[0-9a-f]{32}$/;

export type StorageState = "ok" | "no_keyring" | "no_local_folder" | "locked";
export type StorageInfo = { keep: boolean | null; state: StorageState; saved: number; unreadable: number; files: boolean; message: string | null };
// `folders`: saved folders by name. `files`: a folder or master.key exists. Neither needs the key.
export type SavedList = { documents: Result[]; folders: number; files: boolean };
export type Queue = { items: Record<string, Translation>; done: number; total: number; failed: string[] };
export type Translated = ({ ok: true } & Queue) | { ok: false; reason: "no_model" | "no_document" | "failed" };
/** What main knows about a finished job. */
export type Finished = { modelId: string | null; docType?: string; sourcePath?: string };
/** The document's job in this session: the model it runs with, and the sidecar's translate call. */
export type Live = { modelId: string | null; ask(ids: string[]): Promise<Queue> };

export type Deps = {
  base: string; // what storageBase() returned
  platform: string;
  safe: SafeStorage;
  settings: {
    read(base: string): SaveDocuments;
    write(base: string, value: "yes" | "no"): "saved" | "not_available" | "failed";
  };
  appVersion: string;
  confirm(message: string, detail: string): Promise<boolean>; // a native dialog
  forget(docIds: string[]): void; // drop deleted documents from main's maps
  log?(line: string): void;
};

// A finished result of this session, kept in memory until quit so the first Yes can save it.
type Entry = { result: Result; sourcePath?: string; english: Record<string, Translation>; saved: boolean };

const NO_KEY: Keeper = {
  wrap: () => {
    throw new StoreError("locked");
  },
  unwrap: () => {
    throw new StoreError("locked");
  },
};

const checkId = (id: unknown): string => {
  if (typeof id !== "string" || !ID.test(id)) throw new Error("bad_doc_id");
  return id;
};

const message = (state: StorageState, platform: string): string | null => {
  const lead = "Saving is not available on this computer: ";
  if (state === "no_local_folder") return `${lead}Windows did not give a local app data folder (LOCALAPPDATA).`;
  if (state !== "no_keyring") return null;
  return `${lead}no system keyring was found.${platform === "linux" ? " Set up GNOME Keyring or KWallet to save documents." : ""}`;
};

/** Creating the service touches neither the disk nor safeStorage. */
export function createStorage(d: Deps) {
  const log = d.log ?? ((line: string) => console.error(line));
  const available = d.base !== "no_local_folder"; // when false, `root` below is never read or written
  const root = path.join(d.base, "store");
  const docs = path.join(root, "docs");
  const session = new Map<string, Entry>(); // by document id and model
  const deletions = new Map<string, number>(); // so a result still on its way is not saved after a delete
  let keeper: Keeper | "no_keyring" | undefined;
  let store: ReturnType<typeof createStore> | undefined;
  let locked = false; // remembered until delete all, so a refused keychain prompt is not raised again by the next call

  function names(dir: string): string[] {
    try {
      return fs.readdirSync(dir);
    } catch (e) {
      const code = (e as NodeJS.ErrnoException).code ?? "unknown";
      if (code === "ENOENT") return [];
      log(`store_look failed: ${code}`);
      throw new StoreError("read_failed");
    }
  }

  // Counted without the key, so it also works when the store is locked. Reading needs no keyring when this is 0.
  const folderCount = () => (available ? names(docs).filter((n) => FOLDER.test(n) && fs.existsSync(path.join(docs, n, "key"))).length : 0);

  // From names alone, so it needs no key and also counts folders that are unfinished or cannot be opened.
  function onDisk(): Omit<SavedList, "documents"> {
    if (!available) return { folders: 0, files: false };
    const folders = names(docs).filter((n) => FOLDER.test(n)).length;
    return { folders, files: folders > 0 || names(root).includes("master.key") };
  }

  // Asked only when needed: it can raise a keyring prompt.
  function getKeeper(): Keeper | "no_keyring" {
    if (keeper === undefined) {
      try {
        keeper = createKeeper(d.safe, d.platform);
      } catch {
        keeper = "no_keyring";
      }
    }
    return keeper;
  }

  function use<T>(op: (s: NonNullable<typeof store>) => T): { state: "ok"; value: T } | { state: Exclude<StorageState, "ok"> } {
    if (!available) return { state: "no_local_folder" };
    const k = getKeeper();
    if (k === "no_keyring") return { state: "no_keyring" };
    if (locked) return { state: "locked" };
    try {
      return { state: "ok", value: op((store ??= createStore(d.base, k, log))) };
    } catch (e) {
      if (!(e instanceof StoreError) || e.code !== "locked") throw e;
      locked = true;
      log("store_locked");
      return { state: "locked" };
    }
  }

  const saving = () => d.settings.read(d.base) === "yes";

  const recordTooLarge = (e: Entry) => Buffer.byteLength(JSON.stringify([e.result, e.english])) > MAX_RESULT_BYTES;

  // Checked when a document is saved; an English update does not carry the file.
  function sourceTooLarge(e: Entry): boolean {
    if ((e.result.format ?? "pdf") !== "pdf" || !e.sourcePath) return false;
    try {
      return fs.statSync(e.sourcePath).size > MAX_SOURCE_BYTES;
    } catch {
      return false; // gone or unreadable: the save itself fails and says so
    }
  }

  function writeEnglish(e: Entry): void {
    if (!Object.keys(e.english).length) return;
    if (recordTooLarge(e)) return log("store_save skipped: too_large");
    try {
      use((s) => s.addTranslations(e.result.doc_id, e.result.model_id ?? null, e.english));
    } catch {
      // the store logged the error type; the next poll tries again
    }
  }

  // The only place a document is written. The callers check the saved answer.
  function save(e: Entry): boolean {
    if (recordTooLarge(e) || sourceTooLarge(e)) {
      log("store_save skipped: too_large");
      return false;
    }
    try {
      if (use((s) => s.save(e.result, e.sourcePath ?? "", d.appVersion)).state !== "ok") return false;
    } catch {
      return false; // the store logged the error type; the result still opens in this session
    }
    e.saved = true;
    writeEnglish(e);
    return true;
  }

  function drop(ids: string[]): void {
    for (const id of ids) deletions.set(id, (deletions.get(id) ?? 0) + 1);
    for (const [k, e] of session) if (ids.includes(e.result.doc_id)) session.delete(k);
    d.forget(ids);
  }

  // After a delete all that stopped part way: forgets what is really gone, so it leaves memory and cannot be saved
  // again. When what is left cannot be read, nothing is forgotten.
  function dropRemoved(ids: string[]): void {
    try {
      const r = folderCount() ? use((s) => s.list()) : null; // no folder with a key: everything is gone
      if (r && r.state !== "ok") return;
      const left = new Set(r?.value.documents.map((doc) => doc.id));
      drop(ids.filter((id) => !left.has(id)));
    } catch {
      // the delete's own error is the one to report
    }
  }

  function stored(docId: string, modelId: string | null): Translated {
    const none: Translated = { ok: false, reason: "no_document" };
    try {
      if (!folderCount()) return none;
      const r = use((s) => s.read(docId));
      const doc = r.state === "ok" ? r.value : null;
      const model = modelId ?? "none";
      if (!doc || !Object.hasOwn(doc.results, model)) return none;
      const items = doc.translations[model] ?? {};
      const n = Object.keys(items).filter((k) => !k.startsWith("value:")).length; // the sidecar counts sentences only
      return { ok: true, items, done: n, total: n, failed: [] };
    } catch {
      return { ok: false, reason: "failed" };
    }
  }

  return {
    /** Startup, after app ready. safeStorage is asked only when the store folder holds something. Never throws. */
    open(): void {
      try {
        if (!available || !names(root).length) return;
        const r = use((s) => {
          try {
            s.cleanup(); // removes nothing when locked
          } catch (e) {
            if (e instanceof StoreError && e.code === "locked") throw e; // a failed removal still leaves a readable store
          }
          return s.list();
        });
        if (r.state === "ok") log(`store_opened docs=${r.value.documents.length} unreadable=${r.value.unreadable}`);
        else if (r.state !== "locked") log(`store_unavailable reason=${r.state}`);
      } catch (e) {
        log(`store_start failed: ${e instanceof StoreError ? e.code : "unknown"}`);
      }
    },

    /** One entry per saved document and model, empty when the store cannot be used, and what is on disk. */
    listDocuments(): SavedList {
      const disk = onDisk();
      const r = folderCount() ? use((s) => s.list()) : null;
      if (r?.state !== "ok") return { documents: [], ...disk };
      const documents = r.value.documents.sort((a, b) => a.added.localeCompare(b.added)).flatMap((doc) => Object.values(doc.results).map((x) => x.result));
      return { documents, ...disk };
    },

    getStorage(): StorageInfo {
      const answer = d.settings.read(d.base);
      const keep = answer === "unanswered" ? null : answer === "yes";
      const r = use((s) => s.list());
      const found = r.state === "ok" ? { saved: r.value.documents.length, unreadable: r.value.unreadable } : { saved: 0, unreadable: folderCount() };
      return { keep, state: r.state, ...found, files: onDisk().files, message: message(r.state, d.platform) };
    },

    /** The first Yes also saves what has finished in this session. Counts are documents. */
    setKeepDocuments(keep: unknown): { saved: number; failed: number } {
      if (typeof keep !== "boolean") throw new Error("bad_keep");
      const none = { saved: 0, failed: 0 };
      if (!available || getKeeper() === "no_keyring") return none; // no answer is recorded
      const first = d.settings.read(d.base) === "unanswered";
      if (d.settings.write(d.base, keep ? "yes" : "no") !== "saved") {
        log("settings_write failed");
        throw new StoreError("save_failed");
      }
      if (!keep || !first) return none;
      const done = new Set<string>();
      const failed = new Set<string>();
      for (const e of session.values()) (save(e) ? done : failed).add(e.result.doc_id);
      return { saved: [...done].filter((id) => !failed.has(id)).length, failed: failed.size };
    },

    /** false when the user cancels. Works whatever the saved answer is. */
    async deleteDocument(docId: unknown): Promise<boolean> {
      const id = checkId(docId);
      // Without the key one saved document cannot be told from another: only delete all helps then.
      const mustOpen = () => {
        if (folderCount() && use((s) => s.list()).state !== "ok") throw new StoreError("locked");
      };
      mustOpen(); // before asking, so the user is not asked about something that cannot be done
      const ok = await d.confirm("Delete this document?", "This removes the document and all its results for every model. Files you exported are not removed.");
      if (!ok) return false;
      if (folderCount() && use((s) => s.deleteDocument(id)).state !== "ok") throw new StoreError("locked");
      drop([id]);
      return true;
    },

    /** false when the user cancels, or when there is no folder to delete from. Works when the store is locked. */
    async deleteAllDocuments(): Promise<boolean> {
      if (!available) return false;
      const ok = await d.confirm(`Delete all saved documents (${folderCount()})?`, "This removes every saved document and all its results. Files you exported are not removed.");
      if (!ok) return false;
      // The documents to drop from memory: what opens now, and what this session saved. Others stay open.
      const ids = new Set([...session.values()].filter((e) => e.saved).map((e) => e.result.doc_id));
      try {
        const r = folderCount() ? use((s) => s.list()) : null;
        if (r?.state === "ok") for (const doc of r.value.documents) ids.add(doc.id);
      } catch {
        // an unreadable folder must not stop the delete
      }
      try {
        (store ?? createStore(d.base, NO_KEY, log)).deleteAll(); // decrypts nothing; drops the store's cached master key
      } catch (e) {
        dropRemoved([...ids]);
        throw e;
      }
      locked = false;
      drop([...ids]);
      return true;
    },

    /** getFields: keeps the finished result in memory, saves it if the answer is yes, and adds `saved`. `info` is null
     * when main has no job for the document; then nothing is kept. */
    async fields(docId: string, info: Finished | null, ask: () => Promise<Result>): Promise<Result & { saved: boolean }> {
      const before = deletions.get(docId);
      const raw = await ask();
      const response = { ...raw, pdf: `doc/${docId}.pdf` }; // the sidecar sends the file's name; the renderer gets none
      if (!info || raw.doc_id !== docId || deletions.get(docId) !== before) return { ...response, saved: false };
      const result: Result = { ...response, model_id: info.modelId, doc_type: info.docType };
      const entry: Entry = { result, sourcePath: info.sourcePath, english: {}, saved: false };
      session.set(`${docId} ${info.modelId ?? ""}`, entry);
      if (saving()) save(entry);
      return { ...response, saved: entry.saved };
    },

    /** The job's own model goes to the sidecar; any other saved result is answered from the store. `modelId` left out
     * means the job's model. English is written only while the answer is yes, and only for a result this session saved. */
    async translate(docId: unknown, ids: unknown, modelId: unknown, live: Live | null): Promise<Translated> {
      const id = checkId(docId);
      if (!Array.isArray(ids) || ids.length > 200 || !ids.every((i) => typeof i === "string" && SENTENCE.test(i))) throw new Error("bad_sentence_ids");
      if (modelId !== undefined && modelId !== null && !(typeof modelId === "string" && MODEL.test(modelId))) throw new Error("bad_model_id");
      if (!live || (modelId !== undefined && modelId !== live.modelId)) {
        return modelId === undefined ? { ok: false, reason: "no_document" } : stored(id, modelId); // e.g. the fixture demo
      }
      if (live.modelId === null) return { ok: false, reason: "no_model" };
      let queue: Queue;
      try {
        queue = await live.ask(ids);
      } catch (err) {
        return { ok: false, reason: (err as Error).message === "sidecar_http_503" ? "no_model" : "failed" };
      }
      const entry = session.get(`${id} ${live.modelId}`); // gone if the document was deleted while we waited
      if (entry) {
        Object.assign(entry.english, queue.items);
        if (entry.saved && saving()) writeEnglish(entry);
      }
      return { ok: true, ...queue };
    },

    /** The stored PDF, for the viewer. Never throws. */
    source(docId: string): Buffer | null {
      try {
        if (!folderCount()) return null;
        const r = use((s) => s.readSource(docId));
        return r.state === "ok" ? r.value : null;
      } catch {
        return null;
      }
    },
  };
}
