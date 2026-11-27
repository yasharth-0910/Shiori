// The document store (docs/storage_design.md sections 1 and 2, D-119). Only Node modules. The app reaches it
// through storage.ts. Every file under <base>/store is a blob: "SHI1" | 12-byte nonce | ciphertext | 16-byte tag, AES-256-GCM. The
// folder name and the role are authenticated too, so a file moved to another folder or renamed to another role does not
// open. master.key is the exception: the keeper wraps it. Delete destroys the document's key file, not its data: old disk
// blocks and backups made earlier can still hold the key (section 3, "What delete does not promise").
import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";

export type Role = "key" | "record" | "source";

type Code = "seal_failed" | "open_failed" | "locked" | "source_changed" | "save_failed" | "read_failed" | "delete_failed";

// A code and nothing else (no cause, path, data or key bytes), because it may end up in a log.
export class StoreError extends Error {
  readonly code: Code;
  constructor(code: Code) {
    super(code);
    this.name = "StoreError";
    this.code = code;
  }
}

const MAGIC = Buffer.from("SHI1");
const BODY = MAGIC.length + 12; // after the nonce
const TAG = 16;

const aad = (folder: string, role: Role) => Buffer.from(`shiori-store-v1|${folder}|${role}`);

export function seal(key: Uint8Array, folder: string, role: Role, plain: Uint8Array): Buffer {
  try {
    const nonce = randomBytes(BODY - MAGIC.length); // new on every write: a key must never reuse one
    const c = createCipheriv("aes-256-gcm", key, nonce, { authTagLength: TAG });
    c.setAAD(aad(folder, role));
    return Buffer.concat([MAGIC, nonce, c.update(plain), c.final(), c.getAuthTag()]);
  } catch {
    throw new StoreError("seal_failed");
  }
}

// Returns the plain bytes only after the tag check has passed.
export function open(key: Uint8Array, folder: string, role: Role, blob: Uint8Array): Buffer {
  try {
    const b = Buffer.from(blob.buffer, blob.byteOffset, blob.byteLength);
    if (b.length < BODY + TAG || !b.subarray(0, MAGIC.length).equals(MAGIC)) throw new StoreError("open_failed");
    const d = createDecipheriv("aes-256-gcm", key, b.subarray(MAGIC.length, BODY), { authTagLength: TAG });
    d.setAAD(aad(folder, role));
    d.setAuthTag(b.subarray(b.length - TAG));
    return Buffer.concat([d.update(b.subarray(BODY, b.length - TAG)), d.final()]);
  } catch {
    throw new StoreError("open_failed");
  }
}

// Wraps the master key with the operating system's secret store. The real one (Electron safeStorage) is step 3.
export interface Keeper {
  wrap(plain: string): Buffer;
  unwrap(wrapped: Buffer): string;
}

// The parts of a fields response that are stored (section 1). Main adds model_id and doc_type before saving.
export type Result = {
  doc_id: string;
  pdf?: string; // replaced on save: the sidecar sends the file's name, which is never stored
  format?: "pdf" | "html"; // absent means pdf
  text?: string; // HTML only
  en_summary?: unknown; // HTML only
  model_id?: string | null;
  doc_type?: string;
  fields: { field: string; value_ja: string | null }[];
  sentences: Record<string, { text_orig: string }>;
};
export type Translation = { en: string; numbers_match: boolean; protected_lost?: boolean };
export type StoredDocument = {
  id: string;
  format: "pdf" | "html";
  added: string; // ISO time of the first save
  results: Record<string, { app_version: string; result: Result }>; // by model id, "none" for rules only
  translations: Record<string, Record<string, Translation>>; // by model id, then sentence id
};

const ID = /^[0-9a-f]{64}$/;
const FOLDER = /^[0-9a-f]{32}$/;

const errorType = (e: unknown) => (e as NodeJS.ErrnoException)?.code ?? (e instanceof Error ? e.name : "unknown");
const missing = (e: unknown) => errorType(e) === "ENOENT";

// A crash leaves the old file or the new one, never half of one.
function write(file: string, data: Buffer): void {
  const fd = fs.openSync(`${file}.tmp`, "w");
  try {
    fs.writeFileSync(fd, data);
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  fs.renameSync(`${file}.tmp`, file);
}

// The Japanese a translation was made from; undefined when no stored sentence has this id.
const japanese = (r: Result, id: string) =>
  id === "value:title" ? r.fields.find((f) => f.field === "title")?.value_ja : r.sentences[id]?.text_orig;

// `base` is the folder that holds store/ (section 2). Creating the object touches neither the disk nor the keeper.
// Every method throws StoreError and nothing else, and logs no text, name, path, folder name or document id.
export function createStore(base: string, keeper: Keeper, log: (line: string) => void = console.error) {
  const root = path.join(base, "store");
  const masterFile = path.join(root, "master.key");
  const docs = path.join(root, "docs");
  let cached: Buffer | undefined; // the master key, once it opened; deleteAll() drops it

  function guard<T>(event: string, code: Code, op: () => T): T {
    try {
      return op();
    } catch (e) {
      log(`${event} failed: ${errorType(e)}`);
      throw e instanceof StoreError ? e : new StoreError(code);
    }
  }

  function folders(): string[] {
    try {
      return fs.readdirSync(docs).filter((name) => FOLDER.test(name));
    } catch (e) {
      if (missing(e)) return [];
      throw e;
    }
  }

  // A folder without `key` is an unfinished save or delete.
  const complete = () => folders().filter((name) => fs.existsSync(path.join(docs, name, "key")));

  // The master key, or null when there is none and nothing depends on one. Anything else is "locked": a new key is
  // never made over an old one, or beside documents that an old one protects.
  function master(): Buffer | null {
    if (cached) return cached;
    let wrapped: Buffer;
    try {
      wrapped = fs.readFileSync(masterFile);
    } catch (e) {
      if (missing(e) && complete().length === 0) return null;
      throw new StoreError("locked");
    }
    let key: Buffer;
    try {
      key = Buffer.from(keeper.unwrap(wrapped), "base64");
    } catch {
      throw new StoreError("locked");
    }
    if (key.length !== 32) throw new StoreError("locked");
    return (cached = key);
  }

  function newMaster(): Buffer {
    const key = randomBytes(32);
    fs.mkdirSync(root, { recursive: true });
    write(masterFile, keeper.wrap(key.toString("base64")));
    return (cached = key);
  }

  function openDocument(key: Buffer, folder: string) {
    const file = (name: string) => fs.readFileSync(path.join(docs, folder, name));
    const docKey = open(key, folder, "key", file("key"));
    const doc = JSON.parse(open(docKey, folder, "record", file("record.enc")).toString()) as StoredDocument;
    return { folder, docKey, doc };
  }

  function scan() {
    const key = master();
    const found: ReturnType<typeof openDocument>[] = [];
    let unreadable = 0;
    for (const folder of key ? complete() : []) {
      try {
        found.push(openDocument(key as Buffer, folder));
      } catch (e) {
        unreadable++; // skipped and left as it is: a failed decryption never deletes anything
        log(`store_open failed: ${errorType(e)}`);
      }
    }
    return { found, unreadable };
  }

  // ponytail: decrypts every record per lookup; keep an id -> folder map if that gets slow.
  const find = (docId: string) => scan().found.find((d) => d.doc.id === docId);

  function writeRecord(folder: string, docKey: Buffer, doc: StoredDocument): number {
    const blob = seal(docKey, folder, "record", Buffer.from(JSON.stringify(doc)));
    write(path.join(docs, folder, "record.enc"), blob);
    return blob.length;
  }

  // Key first: from then on the other files cannot be decrypted, and cleanup() finishes a removal that stopped.
  function shred(folder: string): void {
    const dir = path.join(docs, folder);
    fs.rmSync(path.join(dir, "key"), { force: true });
    fs.rmSync(dir, { recursive: true, force: true });
  }

  return {
    // Adds the result to its document, or makes the document. `sourcePath` is the user's file; its path and name are
    // not stored. A PDF is copied, and only if its bytes still hash to the document id.
    save(result: Result, sourcePath: string, appVersion: string): void {
      guard("store_save", "save_failed", () => {
        const id = result.doc_id;
        if (!ID.test(id)) throw new StoreError("save_failed");
        const format = result.format ?? "pdf";
        let source: Buffer | undefined;
        if (format === "pdf") {
          source = fs.readFileSync(sourcePath);
          if (createHash("sha256").update(source).digest("hex") !== id) throw new StoreError("source_changed");
        }
        // Only the listed parts, so nothing else a caller hangs on the object reaches the disk.
        const { doc_id, model_id, doc_type, fields, sentences, text, en_summary } = result;
        const clean: Result = { doc_id, pdf: `doc/${id}.pdf`, format: result.format, model_id, doc_type, fields, sentences, text, en_summary };
        const model = model_id ?? "none";
        const entry = { app_version: appVersion, result: clean };

        const old = find(id); // throws when locked, before anything is written
        if (old) {
          // Sentence ids can point at other text after a new extractor, so English stays only with unchanged Japanese.
          const before = old.doc.results[model]?.result;
          const kept = Object.entries(old.doc.translations[model] ?? {}).filter(([sid]) => before && japanese(before, sid) === japanese(clean, sid));
          old.doc.results[model] = entry;
          if (kept.length) old.doc.translations[model] = Object.fromEntries(kept);
          else delete old.doc.translations[model];
          log(`store_saved bytes=${writeRecord(old.folder, old.docKey, old.doc)}`);
          return;
        }
        const key = master() ?? newMaster();
        const folder = randomBytes(16).toString("hex"); // not the id, which anyone holding the same file can compute
        const docKey = randomBytes(32);
        const dir = path.join(docs, folder);
        fs.mkdirSync(dir, { recursive: true });
        let bytes = 0;
        if (source) {
          const blob = seal(docKey, folder, "source", source);
          write(path.join(dir, "source.enc"), blob);
          bytes = blob.length;
        }
        bytes += writeRecord(folder, docKey, { id, format, added: new Date().toISOString(), results: { [model]: entry }, translations: {} });
        write(path.join(dir, "key"), seal(key, folder, "key", docKey)); // last: only now does the document exist
        log(`store_saved bytes=${bytes}`);
      });
    },

    list(): { documents: StoredDocument[]; unreadable: number } {
      return guard("store_list", "read_failed", () => {
        const { found, unreadable } = scan();
        return { documents: found.map((d) => d.doc), unreadable };
      });
    },

    read(docId: string): StoredDocument | null {
      return guard("store_read", "read_failed", () => find(docId)?.doc ?? null);
    },

    // The stored PDF. null for an unknown document and for HTML, whose copy is the `text` inside each result.
    readSource(docId: string): Buffer | null {
      return guard("store_read_source", "read_failed", () => {
        const d = find(docId);
        if (!d || d.doc.format !== "pdf") return null;
        return open(d.docKey, d.folder, "source", fs.readFileSync(path.join(docs, d.folder, "source.enc")));
      });
    },

    // Never creates a document or a model result: false when there is nothing to add to.
    addTranslations(docId: string, modelId: string | null, items: Record<string, Translation>): boolean {
      return guard("store_translations", "save_failed", () => {
        const d = find(docId);
        const model = modelId ?? "none";
        const result = d?.doc.results[model]?.result;
        if (!d || !result) return false;
        const merged = { ...d.doc.translations[model] };
        for (const [sid, { en, numbers_match, protected_lost }] of Object.entries(items)) {
          if (japanese(result, sid) != null) merged[sid] = { en, numbers_match, protected_lost };
        }
        // The screen polls, so the same items arrive many times: write only when something changed.
        if (JSON.stringify(merged) === JSON.stringify(d.doc.translations[model] ?? {})) return true;
        d.doc.translations[model] = merged;
        log(`store_saved bytes=${writeRecord(d.folder, d.docKey, d.doc)}`);
        return true;
      });
    },

    // false when no readable document has this id. Needs the master key: without it the folder cannot be told apart.
    deleteDocument(docId: string): boolean {
      return guard("store_delete", "delete_failed", () => {
        // All matches: a save made while a record could not be read leaves a second folder for the same document.
        const matches = scan().found.filter((d) => d.doc.id === docId);
        if (!matches.length) return false;
        for (const d of matches) shred(d.folder);
        log("store_deleted");
        return true;
      });
    },

    // Every document folder, then the master key and anything left beside it. Decrypts nothing, so it works when locked.
    deleteAll(): void {
      guard("store_delete_all", "delete_failed", () => {
        cached = undefined; // the next save makes a new master key; if this stops half way, the file is read again
        const all = folders();
        for (const folder of all) shred(folder);
        fs.rmSync(root, { recursive: true, force: true });
        log(`store_deleted_all folders=${all.length}`);
      });
    },

    // For startup: removes leftover .tmp files and folders without a key. Nothing is removed when the store is locked.
    cleanup(): void {
      guard("store_cleanup", "delete_failed", () => {
        master(); // throws when locked
        fs.rmSync(`${masterFile}.tmp`, { force: true });
        let removed = 0;
        for (const folder of folders()) {
          const dir = path.join(docs, folder);
          const names = fs.readdirSync(dir); // throws rather than guess: a folder we cannot list is not a keyless one
          if (!names.includes("key")) {
            shred(folder);
            removed++;
          } else {
            for (const name of names) if (name.endsWith(".tmp")) fs.rmSync(path.join(dir, name), { force: true });
          }
        }
        log(`store_cleanup folders=${removed}`);
      });
    },
  };
}
