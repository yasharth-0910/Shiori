// Run: npm test. The document store (docs/storage_design.md sections 2 and 6, steps 1 and 2). Seal and open stay in
// memory. The store tests write only inside their own temp folder, with a fake keeper. All Japanese text is invented.
import assert from "node:assert/strict";
import { createDecipheriv, createHash, randomBytes } from "node:crypto";
import * as fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
import * as os from "node:os";
import * as path from "node:path";
import { test, type TestContext } from "node:test";
import { createStore, type Keeper, open, type Result, type Role, seal, StoreError } from "../electron/store.ts";

const key = randomBytes(32);
const folder = "0123456789abcdef0123456789abcdef";
const plain = Buffer.from("入札公告 invented test text");
const blob = seal(key, folder, "record", plain);
const HEADER = 4;
const BODY = 4 + 12;
const TAG = 16;

// The error carries its code and nothing else: no cause, no path, no data, no key bytes.
function failsClosed(op: () => unknown, code: StoreError["code"] = "open_failed"): void {
  assert.throws(op, (e: unknown) => {
    assert.ok(e instanceof StoreError);
    assert.equal(e.code, code);
    assert.equal(e.message, code);
    assert.equal(e.cause, undefined);
    assert.deepEqual(Object.keys(e).sort(), ["code", "name"]);
    return true;
  });
}

test("round trip", () => {
  for (const role of ["key", "record", "source"] as Role[]) {
    assert.deepEqual(open(key, folder, role, seal(key, folder, role, plain)), plain);
  }
});

test("empty and 20 MB input", () => {
  for (const input of [Buffer.alloc(0), randomBytes(20 * 1024 * 1024)]) {
    const sealed = seal(key, folder, "source", input);
    assert.equal(sealed.length, BODY + input.length + TAG);
    assert.ok(open(key, folder, "source", sealed).equals(input));
  }
});

test("a plain Uint8Array view with an offset opens", () => {
  const padded = new Uint8Array(blob.length + 10);
  padded.set(blob, 5);
  assert.deepEqual(open(key, folder, "record", padded.subarray(5, 5 + blob.length)), plain);
});

test("the file shape and the authenticated data are the ones in the design", () => {
  assert.equal(blob.subarray(0, HEADER).toString("latin1"), "SHI1");
  const d = createDecipheriv("aes-256-gcm", key, blob.subarray(HEADER, BODY), { authTagLength: TAG });
  d.setAAD(Buffer.from(`shiori-store-v1|${folder}|record`));
  d.setAuthTag(blob.subarray(blob.length - TAG));
  assert.deepEqual(Buffer.concat([d.update(blob.subarray(BODY, blob.length - TAG)), d.final()]), plain);
});

for (const [part, from, to] of [
  ["header", 0, HEADER],
  ["nonce", HEADER, BODY],
  ["body", BODY, blob.length - TAG],
  ["tag", blob.length - TAG, blob.length],
] as const) {
  test(`one flipped byte anywhere in the ${part} fails`, () => {
    for (let i = from; i < to; i++) {
      const bad = Buffer.from(blob);
      bad[i]! ^= 1;
      failsClosed(() => open(key, folder, "record", bad));
    }
  });
}

test("a short tag or a cut file fails", () => {
  // The empty blob is only header, nonce and tag, so every cut of it shortens the tag.
  for (const whole of [blob, seal(key, folder, "record", Buffer.alloc(0))]) {
    for (let n = 0; n < whole.length; n++) failsClosed(() => open(key, folder, "record", whole.subarray(0, n)));
  }
  failsClosed(() => open(key, folder, "record", Buffer.concat([blob, Buffer.alloc(1)])));
});

test("wrong key, wrong folder and wrong role fail", () => {
  failsClosed(() => open(randomBytes(32), folder, "record", blob));
  failsClosed(() => open(key, "f".repeat(32), "record", blob));
  failsClosed(() => open(key, folder, "source", blob));
  failsClosed(() => open(key, folder, "key", blob));
});

test("a key of the wrong length fails closed", () => {
  for (const bad of [Buffer.alloc(0), randomBytes(16), randomBytes(31), randomBytes(33)]) {
    failsClosed(() => seal(bad, folder, "record", plain), "seal_failed");
    failsClosed(() => open(bad, folder, "record", blob));
  }
});

test("two seals of the same input differ", () => {
  const a = seal(key, folder, "record", plain);
  const b = seal(key, folder, "record", plain);
  assert.ok(!a.subarray(HEADER, BODY).equals(b.subarray(HEADER, BODY)), "same nonce");
  assert.ok(!a.subarray(BODY).equals(b.subarray(BODY)), "same ciphertext");
});

// ---- The store ----

const SENTENCE = "架空の調達案件に関する公告である。"; // canary: must never be readable on disk
const FILE_NAME = "架空の機密案件_canary"; // canary: must not be stored at all

// Stands in for safeStorage: reversible, and the key is not readable in the wrapped bytes.
const flip = (b: Buffer) => Buffer.from(b.map((x) => x ^ 0x5a));
const keeper: Keeper = { wrap: (s) => flip(Buffer.from(s)), unwrap: (b) => flip(b).toString() };
const denied: Keeper = {
  wrap: () => {
    throw new Error(`denied ${SENTENCE}`);
  },
  unwrap: () => {
    throw new Error(`denied ${SENTENCE}`);
  },
};

// Replaces one node:fs function for the store too, until the test ends.
function mockFs(t: TestContext, name: "fsyncSync" | "readFileSync" | "renameSync" | "rmSync", impl?: (...a: never[]) => unknown) {
  const m = impl ? t.mock.method(fs.default, name, impl as never) : t.mock.method(fs.default, name);
  syncBuiltinESMExports();
  t.after(() => {
    m.mock.restore();
    syncBuiltinESMExports();
  });
  return m;
}

const sha = (b: Buffer) => createHash("sha256").update(b).digest("hex");

function setup(t: TestContext, format: "pdf" | "html" = "pdf", content = "%PDF invented bytes") {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "shiori-store-test-"));
  t.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
  const base = path.join(tmp, "base");
  const source = path.join(tmp, `${FILE_NAME}.${format}`);
  const bytes = Buffer.from(content);
  fs.writeFileSync(source, bytes);
  const logs: string[] = [];
  const store = (k: Keeper = keeper) => createStore(base, k, (line) => logs.push(line));
  const root = path.join(base, "store");
  const docs = () => (fs.existsSync(path.join(root, "docs")) ? fs.readdirSync(path.join(root, "docs")) : []);
  return { tmp, base, root, source, bytes, id: sha(bytes), logs, store, docs };
}

function result(docId: string, model: string | null = "model-a", over: Partial<Result> = {}): Result {
  return {
    doc_id: docId,
    pdf: `${FILE_NAME}.pdf`, // what the sidecar sends: the file's base name
    model_id: model,
    doc_type: "notice",
    fields: [{ field: "title", value_ja: "架空の件名" }],
    sentences: { p1_s1: { page: 1, text_orig: SENTENCE } },
    ...over,
  };
}

// Every file and folder under `dir`: relative name -> bytes (null for a folder).
function tree(dir: string): Map<string, Buffer | null> {
  const out = new Map<string, Buffer | null>();
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { recursive: true, withFileTypes: true })) {
    const full = path.join(e.parentPath, e.name);
    out.set(path.relative(dir, full), e.isDirectory() ? null : fs.readFileSync(full));
  }
  return out;
}

const en = (text: string) => ({ en: text, numbers_match: true, protected_lost: false });

test("reading an empty store creates nothing and asks the keeper nothing", (t) => {
  const s = setup(t);
  const store = s.store(denied);
  assert.deepEqual(store.list(), { documents: [], unreadable: 0 });
  assert.equal(store.read(s.id), null);
  assert.equal(store.readSource(s.id), null);
  assert.equal(store.addTranslations(s.id, "model-a", { p1_s1: en("x") }), false);
  assert.ok(!fs.existsSync(s.base));
});

test("save and reopen with a new store object", (t) => {
  const s = setup(t);
  s.store().save(result(s.id), s.source, "0.1.2");

  const again = s.store();
  const doc = again.read(s.id)!;
  assert.equal(doc.id, s.id);
  assert.equal(doc.format, "pdf");
  assert.ok(!Number.isNaN(Date.parse(doc.added)));
  assert.deepEqual(doc.results["model-a"], { app_version: "0.1.2", result: { ...result(s.id), pdf: `doc/${s.id}.pdf` } });
  assert.deepEqual(again.list(), { documents: [doc], unreadable: 0 });
  assert.deepEqual(again.readSource(s.id), s.bytes);
  assert.equal(again.read("0".repeat(64)), null);

  const [name] = s.docs();
  assert.match(name!, /^[0-9a-f]{32}$/);
  assert.deepEqual([...tree(s.root).keys()].sort(), [
    "docs",
    path.join("docs", name!),
    path.join("docs", name!, "key"),
    path.join("docs", name!, "record.enc"),
    path.join("docs", name!, "source.enc"),
    "master.key",
  ]);
});

test("the files follow the two levels of keys in the design", (t) => {
  const s = setup(t);
  s.store().save(result(s.id), s.source, "0.1.2");
  const [name] = s.docs();
  const file = (f: string) => fs.readFileSync(path.join(s.root, "docs", name!, f));
  const master = Buffer.from(keeper.unwrap(fs.readFileSync(path.join(s.root, "master.key"))), "base64");
  assert.equal(master.length, 32);
  const docKey = open(master, name!, "key", file("key"));
  assert.equal(docKey.length, 32);
  assert.ok(!docKey.equals(master));
  assert.equal(JSON.parse(open(docKey, name!, "record", file("record.enc")).toString()).id, s.id);
  assert.deepEqual(open(docKey, name!, "source", file("source.enc")), s.bytes);
});

test("a new document is written source, record, key, each through a flushed .tmp file", (t) => {
  const s = setup(t);
  const order: string[] = [];
  const rename = fs.renameSync;
  const sync = mockFs(t, "fsyncSync");
  mockFs(t, "renameSync", (from: string, to: string) => {
    assert.equal(from, `${to}.tmp`);
    order.push(path.basename(to));
    rename(from, to);
  });
  s.store().save(result(s.id), s.source, "0.1.2");
  assert.deepEqual(order, ["master.key", "source.enc", "record.enc", "key"]);
  assert.equal(sync.mock.callCount(), 4);
});

test("an HTML notice keeps its text in the record and no copy of the file", (t) => {
  const s = setup(t, "html", "<html>invented raw markup</html>");
  const html = result(s.id, "model-a", { format: "html", text: SENTENCE, en_summary: { start: 0, end: 2 } });
  s.store().save(html, s.source, "0.1.2");
  const doc = s.store().read(s.id)!;
  assert.equal(doc.format, "html");
  assert.equal(doc.results["model-a"]!.result.text, SENTENCE);
  assert.deepEqual(doc.results["model-a"]!.result.en_summary, { start: 0, end: 2 });
  assert.equal(s.store().readSource(s.id), null);
  assert.deepEqual(fs.readdirSync(path.join(s.root, "docs", s.docs()[0]!)).sort(), ["key", "record.enc"]);
});

test("only the listed parts of a result are stored", (t) => {
  const s = setup(t);
  const extra = { ...result(s.id), path: s.source, token: "invented" } as Result;
  s.store().save(extra, s.source, "0.1.2");
  assert.deepEqual(Object.keys(s.store().read(s.id)!.results["model-a"]!.result).sort(), ["doc_id", "doc_type", "fields", "model_id", "pdf", "sentences"]);
});

test("a second model joins the same document", (t) => {
  const s = setup(t);
  const store = s.store();
  store.save(result(s.id, "model-a"), s.source, "0.1.2");
  const first = store.read(s.id)!;
  const before = tree(s.root);
  s.store().save(result(s.id, "model-b"), s.source, "0.1.3");
  s.store().save(result(s.id, null), s.source, "0.1.3"); // rules only
  assert.equal(s.docs().length, 1);
  const doc = s.store().read(s.id)!;
  assert.equal(doc.added, first.added);
  assert.deepEqual(Object.keys(doc.results).sort(), ["model-a", "model-b", "none"]);
  assert.deepEqual(doc.results["model-a"], first.results["model-a"]);
  assert.equal(doc.results["model-b"]!.app_version, "0.1.3");
  // Only the record is rewritten.
  const name = s.docs()[0]!;
  for (const f of ["key", "source.enc"]) assert.deepEqual(tree(s.root).get(path.join("docs", name, f)), before.get(path.join("docs", name, f)));
});

test("a changed source file is not saved", (t) => {
  const s = setup(t);
  fs.writeFileSync(s.source, "%PDF something else");
  failsClosed(() => s.store().save(result(s.id), s.source, "0.1.2"), "source_changed");
  assert.ok(!fs.existsSync(s.base), "not even a store folder or a master key");

  // Also for a second model on a saved document.
  fs.writeFileSync(s.source, s.bytes);
  s.store().save(result(s.id), s.source, "0.1.2");
  fs.writeFileSync(s.source, "%PDF something else");
  const before = tree(s.base);
  failsClosed(() => s.store().save(result(s.id, "model-b"), s.source, "0.1.2"), "source_changed");
  assert.deepEqual(tree(s.base), before);

  fs.rmSync(s.source);
  failsClosed(() => s.store().save(result(s.id), s.source, "0.1.2"), "save_failed");
  assert.deepEqual(tree(s.base), before);
});

test("a document id that is not a SHA-256 is not saved", (t) => {
  const s = setup(t, "html");
  failsClosed(() => s.store().save(result("../x", "model-a", { format: "html" }), s.source, "0.1.2"), "save_failed");
  assert.ok(!fs.existsSync(s.base));
});

test("translations join an existing document, per model", (t) => {
  const s = setup(t);
  s.store().save(result(s.id, "model-a"), s.source, "0.1.2");
  s.store().save(result(s.id, "model-b"), s.source, "0.1.2");
  assert.equal(s.store().addTranslations(s.id, "model-a", { p1_s1: { ...en("one"), extra: 1 } as ReturnType<typeof en> }), true);
  assert.equal(s.store().addTranslations(s.id, "model-a", { "value:title": en("Title"), p9_s9: en("cited by nothing") }), true);
  const doc = s.store().read(s.id)!;
  assert.deepEqual(doc.translations, { "model-a": { p1_s1: en("one"), "value:title": en("Title") } });

  // Nothing new: nothing is written.
  const before = tree(s.base);
  assert.equal(s.store().addTranslations(s.id, "model-a", { p1_s1: en("one") }), true);
  assert.deepEqual(tree(s.base), before);
});

test("translations never create a document or a model result", (t) => {
  const s = setup(t);
  s.store().save(result(s.id), s.source, "0.1.2");
  const before = tree(s.base);
  assert.equal(s.store().addTranslations("0".repeat(64), "model-a", { p1_s1: en("x") }), false);
  assert.equal(s.store().addTranslations(s.id, "model-b", { p1_s1: en("x") }), false);
  assert.deepEqual(tree(s.base), before);
});

test("saving a result again keeps only the translations of unchanged Japanese", (t) => {
  const s = setup(t);
  const two = { p1_s1: { page: 1, text_orig: SENTENCE }, p1_s2: { page: 1, text_orig: "二つ目の架空の文。" } };
  s.store().save(result(s.id, "model-a", { sentences: two }), s.source, "0.1.2");
  s.store().addTranslations(s.id, "model-a", { p1_s1: en("one"), p1_s2: en("two"), "value:title": en("Title") });
  const moved = { ...two, p1_s2: { page: 1, text_orig: "別の架空の文。" } };
  s.store().save(result(s.id, "model-a", { sentences: moved }), s.source, "0.1.3");
  assert.deepEqual(s.store().read(s.id)!.translations["model-a"], { p1_s1: en("one"), "value:title": en("Title") });
});

test("one damaged document is counted and the others stay", (t) => {
  const s = setup(t);
  s.store().save(result(s.id), s.source, "0.1.2");
  const first = s.docs()[0]!;
  const other = Buffer.from("%PDF another invented file");
  fs.writeFileSync(s.source, other);
  s.store().save(result(sha(other)), s.source, "0.1.2");
  const record = path.join(s.root, "docs", first, "record.enc");
  const bad = fs.readFileSync(record);
  bad[bad.length - 1]! ^= 1;
  fs.writeFileSync(record, bad);
  fs.mkdirSync(path.join(s.root, "docs", "f".repeat(32))); // no key file: unfinished, not counted
  const before = tree(s.base);

  const { documents, unreadable } = s.store().list();
  assert.deepEqual([documents.map((d) => d.id), unreadable], [[sha(other)], 1]);
  assert.equal(s.store().read(s.id), null);
  assert.deepEqual(tree(s.base), before);
});

for (const [name, spoil, use] of [
  ["the keeper refuses", () => {}, denied],
  ["the keeper returns something that is not a key", () => {}, { ...keeper, unwrap: () => "short" }],
  ["master.key is missing but documents exist", (root: string) => fs.rmSync(path.join(root, "master.key")), keeper],
  [
    "master.key cannot be read",
    (root: string) => {
      fs.rmSync(path.join(root, "master.key"));
      fs.mkdirSync(path.join(root, "master.key"));
    },
    keeper,
  ],
] as [string, (root: string) => void, Keeper][]) {
  test(`unreadable master key (${name}) writes nothing and deletes nothing`, (t) => {
    const s = setup(t);
    s.store().save(result(s.id), s.source, "0.1.2");
    spoil(s.root);
    const before = tree(s.base);
    const store = s.store(use);
    failsClosed(() => store.save(result(s.id, "model-b"), s.source, "0.1.2"), "locked");
    failsClosed(() => store.addTranslations(s.id, "model-a", { p1_s1: en("x") }), "locked");
    failsClosed(() => store.list(), "locked");
    failsClosed(() => store.read(s.id), "locked");
    failsClosed(() => store.readSource(s.id), "locked");
    assert.deepEqual(tree(s.base), before);
  });
}

test("no master key and only an unfinished folder: the next save makes a key", (t) => {
  const s = setup(t);
  fs.mkdirSync(path.join(s.root, "docs", "f".repeat(32)), { recursive: true });
  assert.deepEqual(s.store().list(), { documents: [], unreadable: 0 });
  s.store().save(result(s.id), s.source, "0.1.2");
  assert.equal(s.store().list().documents.length, 1);
  assert.equal(s.docs().length, 2, "cleanup is not part of this step");
});

test("a save that fails part way says so with a code and leaves no key file", (t) => {
  const s = setup(t);
  const rename = fs.renameSync;
  mockFs(t, "renameSync", (from: string, to: string) => {
    if (to.endsWith("record.enc")) throw Object.assign(new Error(`ENOSPC: ${to}`), { code: "ENOSPC" });
    rename(from, to);
  });
  failsClosed(() => s.store().save(result(s.id), s.source, "0.1.2"), "save_failed");
  assert.ok(s.logs.includes("store_save failed: ENOSPC"));
  assert.deepEqual(s.store().list(), { documents: [], unreadable: 0 });
});

test("no canary on disk or in a name, and no canary, path or id in the log", (t) => {
  const s = setup(t);
  const seen: string[] = [];
  for (const m of ["log", "info", "warn", "error", "debug"] as const) t.mock.method(console, m, (...a: unknown[]) => seen.push(a.join(" ")));
  const store = createStore(s.base, keeper); // the default logger
  store.save(result(s.id), s.source, "0.1.2");
  store.save(result(s.id, "model-b"), s.source, "0.1.2");
  store.addTranslations(s.id, "model-a", { p1_s1: en("canary translation") });
  store.list();
  store.readSource(s.id);
  const stored = JSON.stringify(store.read(s.id));
  for (const secret of [FILE_NAME, s.tmp]) assert.ok(!stored.includes(secret), "file name or path inside the record");

  const names = [...tree(s.base).keys()].join("\n");
  for (const secret of [FILE_NAME, SENTENCE, s.id, s.id.slice(0, 8)]) assert.ok(!names.includes(secret));
  for (const bytes of tree(s.base).values()) {
    if (!bytes) continue;
    for (const secret of [SENTENCE, FILE_NAME, "canary translation", "架空の件名", s.id, "%PDF"]) {
      for (const enc of ["utf8", "utf16le"] as const) assert.ok(!bytes.includes(Buffer.from(secret, enc)));
    }
  }
});

test("failure logs and errors hold no canary, path, folder name or id", (t) => {
  const s = setup(t);
  const seen: string[] = [];
  for (const m of ["log", "info", "warn", "error", "debug"] as const) t.mock.method(console, m, (...a: unknown[]) => seen.push(a.join(" ")));
  const store = createStore(s.base, keeper);
  store.save(result(s.id), s.source, "0.1.2");
  const name = s.docs()[0]!;
  const errors: unknown[] = [];
  const fails = (op: () => unknown) => {
    try {
      op();
      assert.fail("did not throw");
    } catch (e) {
      assert.ok(e instanceof StoreError);
      errors.push(e);
    }
  };
  fails(() => store.save(result(s.id), path.join(s.tmp, `${FILE_NAME}-missing.pdf`), "0.1.2"));
  fails(() => createStore(s.base, denied).list());
  fs.writeFileSync(path.join(s.root, "docs", name, "source.enc"), "damaged");
  fails(() => store.readSource(s.id));
  fs.rmSync(path.join(s.root, "docs", name, "source.enc"));
  fails(() => store.readSource(s.id));
  fs.writeFileSync(path.join(s.root, "docs", name, "record.enc"), "damaged");
  assert.equal(store.list().unreadable, 1);

  const out = [...seen, ...errors.map((e) => `${(e as Error).message}\n${(e as Error).stack?.split("\n")[0]}`)].join("\n");
  assert.ok(seen.some((l) => l.startsWith("store_saved bytes=")));
  assert.ok(seen.some((l) => l.startsWith("store_open failed: ")));
  for (const secret of [SENTENCE, FILE_NAME, s.tmp, os.tmpdir(), s.id, s.id.slice(0, 8), name]) assert.ok(!out.includes(secret), "leak");
});

// ---- Delete and startup cleanup ----

// Two saved documents; `id` and `name` are the one the test deletes.
function twoDocuments(t: TestContext) {
  const s = setup(t);
  s.store().save(result(s.id), s.source, "0.1.2");
  const name = s.docs()[0]!;
  const other = Buffer.from("%PDF another invented file");
  fs.writeFileSync(s.source, other);
  s.store().save(result(sha(other)), s.source, "0.1.2");
  fs.writeFileSync(s.source, s.bytes);
  const dir = path.join(s.root, "docs", name);
  const master = () => Buffer.from(keeper.unwrap(fs.readFileSync(path.join(s.root, "master.key"))), "base64");
  return { ...s, name, dir, otherId: sha(other), master };
}

const ids = (store: ReturnType<typeof createStore>) => store.list().documents.map((d) => d.id);

test("after delete the document is gone and the others stay", (t) => {
  const s = twoDocuments(t);
  const store = s.store();
  assert.equal(store.deleteDocument(s.id), true);
  for (const st of [store, s.store()]) {
    assert.deepEqual(ids(st), [s.otherId]);
    assert.equal(st.read(s.id), null);
    assert.equal(st.readSource(s.id), null);
  }
  assert.ok(!fs.existsSync(s.dir));
  assert.equal(s.docs().length, 1);

  const before = tree(s.base);
  assert.equal(store.deleteDocument(s.id), false);
  assert.equal(store.deleteDocument("not an id"), false);
  assert.deepEqual(tree(s.base), before);
});

test("delete removes every folder that holds the document", (t) => {
  const s = setup(t);
  s.store().save(result(s.id), s.source, "0.1.2");
  const record = path.join(s.root, "docs", s.docs()[0]!, "record.enc");
  const good = fs.readFileSync(record);
  fs.writeFileSync(record, "damaged for a moment");
  s.store().save(result(s.id), s.source, "0.1.2"); // cannot see the first one, so makes a second
  fs.writeFileSync(record, good);
  assert.equal(s.docs().length, 2);
  s.store().deleteDocument(s.id);
  assert.deepEqual(s.docs(), []);
});

test("a delete stopped after its first removal leaves a document that cannot be opened", (t) => {
  const s = twoDocuments(t);
  const removed: string[] = [];
  const rm = fs.rmSync;
  mockFs(t, "rmSync", (target: string, options: fs.RmOptions) => {
    removed.push(target);
    if (removed.length === 2) throw Object.assign(new Error(`stopped at ${target}`), { code: "EIO" });
    rm(target, options);
  });
  failsClosed(() => s.store().deleteDocument(s.id), "delete_failed");
  assert.equal(removed[0], path.join(s.dir, "key"));
  assert.deepEqual(fs.readdirSync(s.dir).sort(), ["record.enc", "source.enc"]);

  // Copies of the remaining files and the master key, opened as a store of their own.
  const copy = path.join(s.tmp, "copy");
  fs.cpSync(s.base, copy, { recursive: true });
  for (const base of [s.base, copy]) {
    const store = createStore(base, keeper, () => {});
    assert.deepEqual(store.list().unreadable, 0);
    assert.deepEqual(ids(store), [s.otherId]);
    assert.equal(store.read(s.id), null);
    assert.equal(store.readSource(s.id), null);
  }
  // The master key itself opens neither file.
  for (const [file, role] of [["record.enc", "record"], ["source.enc", "source"]] as const) {
    failsClosed(() => open(s.master(), s.name, role, fs.readFileSync(path.join(s.dir, file))));
  }

  s.store().cleanup();
  assert.ok(!fs.existsSync(s.dir));
});

test("files copied back without the key stay unreadable", (t) => {
  const s = twoDocuments(t);
  const copy = path.join(s.tmp, "copy");
  fs.cpSync(s.dir, copy, { recursive: true });
  fs.rmSync(path.join(copy, "key"));
  s.store().deleteDocument(s.id);
  fs.cpSync(copy, s.dir, { recursive: true });
  const store = s.store();
  assert.deepEqual(ids(store), [s.otherId]);
  assert.equal(store.read(s.id), null);
  assert.equal(store.readSource(s.id), null);
});

test("an update after a delete creates nothing", (t) => {
  const s = twoDocuments(t);
  const store = s.store();
  store.deleteDocument(s.id);
  const before = tree(s.base);
  for (const st of [store, s.store()]) assert.equal(st.addTranslations(s.id, "model-a", { p1_s1: en("x") }), false);
  assert.deepEqual(tree(s.base), before);
});

test("a locked store deletes no single document", (t) => {
  const s = twoDocuments(t);
  const before = tree(s.base);
  failsClosed(() => s.store(denied).deleteDocument(s.id), "locked");
  assert.deepEqual(tree(s.base), before);
});

test("delete all removes every folder and the master key, and the next save makes a new key", (t) => {
  const s = twoDocuments(t);
  fs.writeFileSync(path.join(s.base, "settings.json"), '{"saveDocuments": "yes"}');
  fs.mkdirSync(path.join(s.root, "docs", "f".repeat(32))); // unfinished folder
  const old = s.master();
  const store = s.store();
  store.list(); // caches the master key
  store.deleteAll();
  assert.deepEqual([...tree(s.base).keys()], ["settings.json"]);
  assert.deepEqual(store.list(), { documents: [], unreadable: 0 });

  store.save(result(s.id), s.source, "0.1.2");
  assert.ok(!s.master().equals(old), "the cached master key was used again");
  assert.deepEqual(ids(s.store()), [s.id]);
});

for (const [how, damage, k] of [
  ["the keeper refuses", () => {}, denied],
  ["master.key is damaged", (file: string) => fs.writeFileSync(file, "damaged"), keeper],
  ["master.key is missing", (file: string) => fs.rmSync(file), keeper],
] as const) {
  test(`delete all works when locked: ${how}`, (t) => {
    const s = twoDocuments(t);
    damage(path.join(s.root, "master.key"));
    failsClosed(() => s.store(k).list(), "locked");
    s.store(k).deleteAll();
    assert.ok(!fs.existsSync(s.root));
    s.store().save(result(s.id), s.source, "0.1.2");
    assert.deepEqual(ids(s.store()), [s.id]);
  });
}

test("delete all and cleanup on an empty store create nothing and ask the keeper nothing", (t) => {
  const s = setup(t);
  s.store(denied).deleteAll();
  s.store(denied).cleanup();
  assert.ok(!fs.existsSync(s.base));
});

test("startup cleanup removes .tmp files and keyless folders and keeps every document", (t) => {
  const s = twoDocuments(t);
  const record = path.join(s.dir, "record.enc");
  fs.writeFileSync(record, "damaged"); // unreadable, but it has a key: never removed
  const before = tree(s.base);
  fs.writeFileSync(path.join(s.root, "master.key.tmp"), "half");
  for (const f of ["record.enc.tmp", "source.enc.tmp", "key.tmp"]) fs.writeFileSync(path.join(s.dir, f), "half");
  const unfinished = path.join(s.root, "docs", "f".repeat(32));
  fs.mkdirSync(unfinished);
  for (const f of ["source.enc", "record.enc", "key.tmp"]) fs.writeFileSync(path.join(unfinished, f), "half");

  s.store().cleanup();
  assert.deepEqual(tree(s.base), before);
  assert.deepEqual(ids(s.store()), [s.otherId]);
  s.store().cleanup();
  assert.deepEqual(tree(s.base), before);
});

test("startup cleanup removes unfinished first saves when there is no master key yet", (t) => {
  const s = setup(t);
  const unfinished = path.join(s.root, "docs", "f".repeat(32));
  fs.mkdirSync(unfinished, { recursive: true });
  fs.writeFileSync(path.join(unfinished, "source.enc"), "half");
  fs.writeFileSync(path.join(s.root, "master.key.tmp"), "half");
  s.store(denied).cleanup();
  assert.deepEqual([...tree(s.root).keys()], ["docs"]);
});

test("startup cleanup removes nothing when locked", (t) => {
  const s = twoDocuments(t);
  fs.writeFileSync(path.join(s.dir, "record.enc.tmp"), "half");
  fs.mkdirSync(path.join(s.root, "docs", "f".repeat(32)));
  let before = tree(s.base);
  failsClosed(() => s.store(denied).cleanup(), "locked");
  assert.deepEqual(tree(s.base), before);
  fs.rmSync(path.join(s.root, "master.key"));
  before = tree(s.base);
  failsClosed(() => s.store().cleanup(), "locked");
  assert.deepEqual(tree(s.base), before);
});

test("after delete all no canary string or file name is left under the store", (t) => {
  const s = twoDocuments(t);
  s.store().addTranslations(s.id, "model-a", { p1_s1: en("canary translation") });
  // Planted in plain text, so the search below has something to find if anything is left behind.
  fs.writeFileSync(path.join(s.dir, `${FILE_NAME}.tmp`), SENTENCE);
  fs.writeFileSync(path.join(s.root, "docs", FILE_NAME), SENTENCE);
  fs.writeFileSync(path.join(s.root, `${FILE_NAME}.tmp`), SENTENCE);
  s.store().deleteAll();
  for (const [name, bytes] of tree(s.base)) {
    assert.ok(!name.includes(FILE_NAME) && !name.includes(SENTENCE), "canary name");
    for (const secret of [SENTENCE, FILE_NAME, "canary translation"]) assert.ok(!bytes?.includes(Buffer.from(secret)), "canary bytes");
  }
  assert.ok(!fs.existsSync(s.root));
});

test("delete and cleanup logs and errors hold no canary, path, folder name or id", (t) => {
  const s = twoDocuments(t);
  const seen: string[] = [];
  for (const m of ["log", "info", "warn", "error", "debug"] as const) t.mock.method(console, m, (...a: unknown[]) => seen.push(a.join(" ")));
  const store = createStore(s.base, keeper); // the default logger
  const rm = fs.rmSync;
  let broken = true;
  mockFs(t, "rmSync", (target: string, options: fs.RmOptions) => {
    if (broken) throw Object.assign(new Error(`EACCES: ${SENTENCE} ${target}`), { code: "EACCES" });
    rm(target, options);
  });
  fs.mkdirSync(path.join(s.root, "docs", "f".repeat(32)));
  failsClosed(() => store.deleteDocument(s.id), "delete_failed");
  failsClosed(() => store.cleanup(), "delete_failed");
  failsClosed(() => store.deleteAll(), "delete_failed");
  broken = false;
  store.deleteDocument(s.id);
  store.cleanup();
  store.deleteAll();

  const out = seen.join("\n");
  for (const line of ["store_deleted", "store_cleanup folders=", "store_deleted_all folders=", "store_delete failed: EACCES"]) assert.ok(out.includes(line), line);
  for (const secret of [SENTENCE, FILE_NAME, s.tmp, os.tmpdir(), s.id, s.id.slice(0, 8), s.name, "f".repeat(32)]) assert.ok(!out.includes(secret), "leak");
});

// ---- Passing file errors (Windows audit W05, W18) ----

// Reads of files called `name` throw `code`, `times` times in all. Returns how many reads threw.
function busy(t: TestContext, name: string, code: string, times: number): () => number {
  const read = fs.readFileSync;
  let thrown = 0;
  mockFs(t, "readFileSync", (file: string, ...rest: []) => {
    if (path.basename(file) === name && thrown < times) {
      thrown++;
      throw Object.assign(new Error(`${code}: ${SENTENCE} ${file}`), { code });
    }
    return read(file, ...rest);
  });
  return () => thrown;
}

for (const file of ["master.key", "key", "record.enc"]) {
  for (const code of ["EBUSY", "EPERM", "EACCES", "EAGAIN"]) {
    test(`W05 W18: ${code} once on ${file} is tried again, and there is still one folder`, (t) => {
      const s = setup(t);
      s.store().save(result(s.id), s.source, "0.1.2");
      const thrown = busy(t, file, code, 1);
      const store = s.store();
      store.save(result(s.id, "model-b"), s.source, "0.1.2");
      assert.equal(thrown(), 1);
      assert.deepEqual(Object.keys(store.read(s.id)!.results).sort(), ["model-a", "model-b"]);
      assert.equal(s.docs().length, 1);
    });
  }

  test(`W05 W18: EBUSY every time on ${file} is read_failed, not locked, and writes nothing`, (t) => {
    const s = setup(t);
    s.store().save(result(s.id), s.source, "0.1.2");
    const before = tree(s.base);
    let times = Infinity;
    const read = fs.readFileSync;
    const m = mockFs(t, "readFileSync", (f: string, ...rest: []) => {
      if (path.basename(f) === file && times > 0) throw Object.assign(new Error(`EBUSY ${f}`), { code: "EBUSY" });
      return read(f, ...rest);
    });
    const store = s.store();
    for (const op of [
      () => store.save(result(s.id, "model-b"), s.source, "0.1.2"),
      () => store.list(),
      () => store.read(s.id),
      () => store.readSource(s.id),
      () => store.addTranslations(s.id, "model-a", { p1_s1: en("x") }),
      () => store.deleteDocument(s.id),
    ]) {
      const reads = m.mock.callCount();
      failsClosed(op, "read_failed");
      assert.ok(m.mock.callCount() - reads >= 4, "tried more than once");
    }
    times = 0;
    assert.deepEqual(tree(s.base), before);
    assert.deepEqual(ids(store), [s.id], "the same object works afterwards");
    for (const secret of [s.tmp, s.id, SENTENCE]) assert.ok(!s.logs.join("\n").includes(secret), "log leak");
    assert.ok(s.logs.includes("store_file_read failed: EBUSY"));
  });
}

test("W05: cleanup with a busy master.key is read_failed and removes nothing", (t) => {
  const s = setup(t);
  s.store().save(result(s.id), s.source, "0.1.2");
  fs.mkdirSync(path.join(s.root, "docs", "f".repeat(32)));
  const before = tree(s.base);
  busy(t, "master.key", "EBUSY", 4);
  failsClosed(() => s.store().cleanup(), "read_failed");
  assert.deepEqual(tree(s.base), before);
});

// ---- One bad folder (Windows audit W08) ----

// Three documents; every removal inside the second folder that the store lists fails.
function stuckFolder(t: TestContext) {
  const s = setup(t);
  for (const content of ["%PDF one", "%PDF two longer", "%PDF three, longer again"]) {
    fs.writeFileSync(s.source, content);
    s.store().save(result(sha(Buffer.from(content))), s.source, "0.1.2");
  }
  const names = fs.readdirSync(path.join(s.root, "docs"));
  const stuck = names[1]!;
  const rm = fs.rmSync;
  const state = { broken: true };
  mockFs(t, "rmSync", (target: string, options: fs.RmOptions) => {
    if (state.broken && target.includes(stuck)) throw Object.assign(new Error(`EBUSY ${target}`), { code: "EBUSY" });
    rm(target, options);
  });
  return { ...s, names, stuck, state };
}

test("W08: delete all removes the other folders, throws, and keeps master.key and the stuck folder", (t) => {
  const s = stuckFolder(t);
  const master = fs.readFileSync(path.join(s.root, "master.key"));
  const kept = tree(path.join(s.root, "docs", s.stuck));
  failsClosed(() => s.store().deleteAll(), "delete_failed");
  assert.deepEqual(s.docs(), [s.stuck]);
  assert.deepEqual(tree(path.join(s.root, "docs", s.stuck)), kept);
  assert.deepEqual(fs.readFileSync(path.join(s.root, "master.key")), master);
  assert.equal(s.store().list().documents.length, 1, "what stayed is still readable");
  assert.ok(s.logs.includes("store_delete_all failed: EBUSY"));
  s.state.broken = false;
  s.store().deleteAll();
  assert.ok(!fs.existsSync(s.root));
});

test("W08: cleanup continues past a bad folder, then throws", (t) => {
  const s = stuckFolder(t);
  const [first, , last] = s.names as [string, string, string];
  for (const name of [first, last]) fs.writeFileSync(path.join(s.root, "docs", name, "record.enc.tmp"), "half");
  fs.writeFileSync(path.join(s.root, "docs", s.stuck, "record.enc.tmp"), "half");
  fs.writeFileSync(path.join(s.root, "master.key.tmp"), "half");
  failsClosed(() => s.store().cleanup(), "delete_failed");
  for (const name of [first, last]) assert.ok(!fs.existsSync(path.join(s.root, "docs", name, "record.enc.tmp")));
  assert.ok(fs.existsSync(path.join(s.root, "docs", s.stuck, "record.enc.tmp")));
  assert.equal(s.docs().length, 3);
  s.state.broken = false;
  s.store().cleanup();
  assert.ok(!fs.existsSync(path.join(s.root, "docs", s.stuck, "record.enc.tmp")));
  assert.ok(!fs.existsSync(path.join(s.root, "master.key.tmp")));
});
