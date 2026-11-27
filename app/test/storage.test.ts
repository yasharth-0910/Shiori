// Run: npm test. The storage service (docs/storage_design.md sections 3 and 5, D-121), driven the way main's IPC
// handlers drive it, with a fake safeStorage, fake settings, a fake dialog and a temp folder. All Japanese is invented.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { test, type TestContext } from "node:test";
import type { SafeStorage } from "../electron/keeper.ts";
import type { SaveDocuments } from "../electron/settings.ts";
import { createStorage, type Deps, type Live, MAX_RESULT_BYTES, MAX_SOURCE_BYTES, type Queue } from "../electron/storage.ts";
import { type Result, StoreError } from "../electron/store.ts";

const SENTENCE = "架空の調達案件に関する公告である。"; // canary
const FILE_NAME = "架空の機密案件_canary"; // canary
const ENGLISH = "canary translation";
const MODEL = "model-a";

const flip = (b: Buffer) => Buffer.from(b.map((x) => x ^ 0x5a));
const sha = (b: Buffer) => createHash("sha256").update(b).digest("hex");
const en = { en: ENGLISH, numbers_match: true, protected_lost: false };
const queue = (items: Queue["items"] = { p1_s1: en }): Queue => ({ items, done: Object.keys(items).length, total: 1, failed: [] });

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

// One computer: a base folder, the settings value, the keyring and the dialog. `start()` is one run of the app.
function computer(t: TestContext) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "shiori-storage-test-"));
  t.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
  const base = path.join(tmp, "base");
  const c = {
    tmp,
    base,
    root: path.join(base, "store"),
    answer: "unanswered" as SaveDocuments,
    keyring: "ok" as "ok" | "denied" | "missing",
    writeFails: false,
    press: true, // what the user clicks in the confirm dialog
    asked: [] as string[],
    forgot: [] as string[][],
    safeCalls: [] as string[],
    logs: [] as string[],
    docs: () => (fs.existsSync(path.join(base, "store", "docs")) ? fs.readdirSync(path.join(base, "store", "docs")) : []),
    start(over: Partial<Deps> = {}) {
      const safe: SafeStorage = {
        isEncryptionAvailable: () => (c.safeCalls.push("available"), c.keyring !== "missing"),
        getSelectedStorageBackend: () => "gnome_libsecret",
        encryptString: (s) => (c.safeCalls.push("encrypt"), flip(Buffer.from(s))),
        decryptString: (b) => {
          c.safeCalls.push("decrypt");
          if (c.keyring === "denied") throw new Error(`denied ${SENTENCE}`);
          return flip(b).toString();
        },
      };
      return createStorage({
        base,
        platform: "darwin",
        safe,
        settings: {
          read: () => c.answer,
          write: (_base, value) => {
            if (c.writeFails) return "failed";
            c.answer = value;
            return "saved";
          },
        },
        appVersion: "0.1.2",
        confirm: async (question) => (c.asked.push(question), c.press),
        forget: (ids) => c.forgot.push(ids),
        log: (line) => c.logs.push(line),
        ...over,
      });
    },
    // A document the user picked: the file, its id, and what the sidecar would answer.
    pick(content: string, format: "pdf" | "html" = "pdf") {
      const source = path.join(tmp, `${FILE_NAME}-${content.length}-${sha(Buffer.from(content)).slice(0, 6)}.${format}`);
      fs.writeFileSync(source, content);
      const id = sha(Buffer.from(content));
      const response: Result = {
        doc_id: id,
        pdf: path.basename(source),
        fields: [{ field: "title", value_ja: "架空の件名" }],
        sentences: { p1_s1: { page: 1, text_orig: SENTENCE } },
        ...(format === "html" ? { format, text: SENTENCE } : {}),
      };
      return { id, source, bytes: Buffer.from(content), response };
    },
  };
  return c;
}

type Computer = ReturnType<typeof computer>;
type Service = ReturnType<Computer["start"]>;
type Doc = ReturnType<Computer["pick"]>;

const finish = (s: Service, d: Doc, modelId: string | null = MODEL) => s.fields(d.id, { modelId, docType: "notice", sourcePath: d.source }, async () => d.response);
const live = (modelId: string | null = MODEL, items?: Queue["items"]): Live => ({ modelId, ask: async () => queue(items) });
const code = (want: StoreError["code"]) => (e: unknown) => e instanceof StoreError && e.code === want && e.message === want;

test("a first start with nothing saved asks no keyring and writes nothing", (t) => {
  const c = computer(t);
  const s = c.start();
  s.open();
  assert.deepEqual(s.listDocuments(), []);
  assert.equal(s.source("0".repeat(64)), null);
  assert.deepEqual(c.safeCalls, []);
  assert.deepEqual(s.getStorage(), { keep: null, state: "ok", saved: 0, unreadable: 0, message: null });
  assert.ok(!fs.existsSync(c.base));
});

for (const answer of ["unanswered", "no"] as const) {
  test(`while the answer is ${answer} nothing is written`, async (t) => {
    const c = computer(t);
    c.answer = answer;
    const s = c.start();
    const pdf = c.pick("%PDF one");
    const html = c.pick("<html>invented</html>", "html");
    for (const d of [pdf, html]) {
      const r = await finish(s, d);
      assert.equal(r.saved, false);
      assert.equal(r.pdf, `doc/${d.id}.pdf`);
      assert.deepEqual(await s.translate(d.id, ["p1_s1"], MODEL, live()), { ok: true, ...queue() });
    }
    assert.deepEqual(s.listDocuments(), []);
    assert.equal(s.getStorage().keep, answer === "no" ? false : null);
    assert.ok(!fs.existsSync(c.base), "no store folder and no master key");
  });
}

test("setKeepDocuments(false) records no and writes no document", async (t) => {
  const c = computer(t);
  const s = c.start();
  await finish(s, c.pick("%PDF one"));
  assert.deepEqual(s.setKeepDocuments(false), { saved: 0, failed: 0 });
  assert.equal(c.answer, "no");
  assert.ok(!fs.existsSync(c.base));
});

test("the first yes saves what finished in this session, and a restart serves it", async (t) => {
  const c = computer(t);
  const s = c.start();
  const a = c.pick("%PDF one");
  const b = c.pick("<html>invented</html>", "html");
  await finish(s, a, MODEL);
  await finish(s, a, null); // the same document, rules only
  await s.translate(a.id, [], MODEL, live());
  await finish(s, b);
  assert.deepEqual(s.setKeepDocuments(true), { saved: 2, failed: 0 });
  assert.equal(c.answer, "yes");
  assert.deepEqual(s.getStorage(), { keep: true, state: "ok", saved: 2, unreadable: 0, message: null });

  const again = c.start();
  again.open();
  assert.ok(c.logs.includes("store_opened docs=2 unreadable=0"));
  const rows = again.listDocuments();
  assert.deepEqual(rows.map((r) => [r.doc_id, r.model_id, r.doc_type, r.pdf]), [
    [a.id, MODEL, "notice", `doc/${a.id}.pdf`],
    [a.id, null, "notice", `doc/${a.id}.pdf`],
    [b.id, MODEL, "notice", `doc/${b.id}.pdf`],
  ]);
  assert.deepEqual(again.source(a.id), a.bytes);
  assert.equal(again.source(b.id), null, "HTML keeps no file");
  // A saved result with no running job: the stored English, and nothing left to wait for.
  assert.deepEqual(await again.translate(a.id, ["p1_s1"], MODEL, null), { ok: true, items: { p1_s1: en }, done: 1, total: 1, failed: [] });
  assert.deepEqual(await again.translate(a.id, [], null, null), { ok: true, items: {}, done: 0, total: 0, failed: [] });
  // A job that runs another model does not answer for the saved row.
  assert.deepEqual(await again.translate(a.id, [], MODEL, live("model-b", { p1_s1: { ...en, en: "other" } })), { ok: true, items: { p1_s1: en }, done: 1, total: 1, failed: [] });
});

test("a saved result that does not exist is no_document", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const s = c.start();
  const d = c.pick("%PDF one");
  const none = { ok: false, reason: "no_document" };
  assert.deepEqual(await s.translate(d.id, [], MODEL, null), none);
  await finish(s, d);
  assert.deepEqual(await s.translate(d.id, [], undefined, null), none);
  assert.deepEqual(await s.translate(d.id, [], "model-b", null), none);
  assert.deepEqual(await s.translate(d.id, [], "constructor", null), none);
});

test("the live job: no model, a sidecar error, and a model id left out", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const s = c.start();
  const d = c.pick("%PDF one");
  await finish(s, d);
  assert.deepEqual(await s.translate(d.id, [], undefined, live(null)), { ok: false, reason: "no_model" });
  for (const [message, reason] of [["sidecar_http_503", "no_model"], ["sidecar_http_500", "failed"]] as const) {
    const bad: Live = { modelId: MODEL, ask: () => Promise.reject(new Error(message)) };
    assert.deepEqual(await s.translate(d.id, [], MODEL, bad), { ok: false, reason });
  }
  assert.deepEqual(await s.translate(d.id, [], undefined, live()), { ok: true, ...queue() });
  assert.deepEqual(c.start().listDocuments().length, 1);
  assert.deepEqual(await c.start().translate(d.id, [], MODEL, null), { ok: true, ...queue() });
});

test("off blocks results and translation updates, not reading; on again saves nothing earlier", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const s = c.start();
  const a = c.pick("%PDF one");
  assert.equal((await finish(s, a)).saved, true);
  s.setKeepDocuments(false);
  let before = tree(c.base);
  // A document saved earlier gets no new English, and no new document or result is written.
  assert.deepEqual(await s.translate(a.id, [], MODEL, live()), { ok: true, ...queue() });
  const b = c.pick("%PDF two longer");
  assert.equal((await finish(s, b)).saved, false);
  assert.equal((await finish(s, a, "model-b")).saved, false);
  await s.translate(b.id, [], MODEL, live());
  assert.deepEqual(tree(c.base), before);
  assert.equal(s.listDocuments().length, 1);

  assert.deepEqual(s.setKeepDocuments(true), { saved: 0, failed: 0 }, "not the first yes");
  before = tree(c.base);
  await s.translate(b.id, [], MODEL, live()); // processed while off: still not saved
  await s.translate(a.id, [], "model-b", live("model-b"));
  assert.deepEqual(tree(c.base), before);
  assert.equal((await finish(s, c.pick("%PDF three, longer again"))).saved, true, "saving starts with the next document");
  assert.equal(s.getStorage().saved, 2);
});

test("no then yes saves nothing from before", async (t) => {
  const c = computer(t);
  const s = c.start();
  s.setKeepDocuments(false);
  await finish(s, c.pick("%PDF one"));
  assert.deepEqual(s.setKeepDocuments(true), { saved: 0, failed: 0 });
  assert.ok(!fs.existsSync(c.base));
});

test("a document that cannot be saved is counted, and still opens", async (t) => {
  const c = computer(t);
  const s = c.start();
  const a = c.pick("%PDF one");
  const b = c.pick("%PDF two longer");
  await finish(s, a);
  await finish(s, b);
  fs.writeFileSync(b.source, "%PDF changed since it was processed");
  assert.deepEqual(s.setKeepDocuments(true), { saved: 1, failed: 1 });
  fs.rmSync(a.source);
  const r = await finish(s, a, "model-b");
  assert.equal(r.saved, false);
  assert.equal(r.doc_id, a.id);
});

test("without a job nothing is kept", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const s = c.start();
  const d = c.pick("%PDF one");
  assert.equal((await s.fields(d.id, null, async () => d.response)).saved, false);
  const wrong = await s.fields("0".repeat(64), { modelId: MODEL, sourcePath: d.source }, async () => d.response);
  assert.equal(wrong.saved, false);
  assert.ok(!fs.existsSync(c.base));
});

test("delete asks first, then removes the document from the store and from memory", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const s = c.start();
  const a = c.pick("%PDF one");
  const b = c.pick("%PDF two longer");
  await finish(s, a);
  await finish(s, b);
  c.press = false;
  const before = tree(c.base);
  assert.equal(await s.deleteDocument(a.id), false);
  assert.deepEqual([tree(c.base), c.forgot], [before, []]);

  c.press = true;
  c.answer = "no"; // delete works whatever the switch says
  assert.equal(await s.deleteDocument(a.id), true);
  assert.deepEqual(c.forgot, [[a.id]]);
  assert.deepEqual(s.listDocuments().map((r) => r.doc_id), [b.id]);
  assert.equal(s.source(a.id), null);
  c.answer = "yes";
  await s.translate(a.id, [], MODEL, live()); // a late poll
  assert.equal(c.docs().length, 1);
});

test("a deleted session document is not saved by the first yes", async (t) => {
  const c = computer(t);
  const s = c.start();
  const a = c.pick("%PDF one");
  await finish(s, a);
  assert.equal(await s.deleteDocument(a.id), true);
  assert.deepEqual(s.setKeepDocuments(true), { saved: 0, failed: 0 });
  assert.ok(!fs.existsSync(c.base));
});

test("a result still on its way when the document is deleted is not saved", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const s = c.start();
  const a = c.pick("%PDF one");
  await finish(s, a);
  let release!: () => void;
  const waiting = new Promise<void>((r) => (release = r));
  const pending = s.fields(a.id, { modelId: "model-b", sourcePath: a.source }, async () => (await waiting, a.response));
  await s.deleteDocument(a.id);
  release();
  assert.equal((await pending).saved, false);
  assert.deepEqual(c.docs(), []);
});

test("delete all removes everything saved, clears the cached key, keeps the answer", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const s = c.start();
  const a = c.pick("%PDF one");
  const b = c.pick("%PDF two longer");
  await finish(s, a);
  await finish(s, b);
  c.answer = "no";
  const kept = c.pick("%PDF never saved, stays open");
  await finish(s, kept);
  const oldKey = fs.readFileSync(path.join(c.root, "master.key"));

  c.press = false;
  const before = tree(c.base);
  assert.equal(await s.deleteAllDocuments(), false);
  assert.deepEqual([tree(c.base), c.forgot], [before, []]);
  assert.equal(c.asked.at(-1), "Delete all saved documents (2)?");

  c.press = true;
  assert.equal(await s.deleteAllDocuments(), true);
  assert.ok(!fs.existsSync(c.root), "every folder and master.key");
  assert.equal(c.answer, "no");
  assert.deepEqual([...c.forgot.at(-1)!].sort(), [a.id, b.id].sort(), "not the one that was never saved");

  c.answer = "yes";
  assert.equal((await finish(s, a)).saved, true);
  const newKey = fs.readFileSync(path.join(c.root, "master.key"));
  assert.ok(!newKey.equals(oldKey), "a new master key: the cached one was dropped");
  assert.equal(c.start().listDocuments().length, 1);
});

test("a denied keyring: memory only, asked once, nothing changed, delete all still works", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const old = c.pick("%PDF saved before");
  await finish(c.start(), old);
  fs.mkdirSync(path.join(c.root, "docs", "f".repeat(32))); // unfinished: cleanup must leave it while locked
  const before = tree(c.base);
  c.keyring = "denied";
  c.safeCalls.length = 0;

  const s = c.start();
  s.open();
  assert.ok(c.logs.includes("store_locked"));
  assert.deepEqual(s.getStorage(), { keep: true, state: "locked", saved: 0, unreadable: 1, message: null });
  assert.deepEqual(s.listDocuments(), []);
  assert.equal(s.source(old.id), null);
  const d = c.pick("%PDF new");
  assert.equal((await finish(s, d)).saved, false);
  assert.deepEqual(await s.translate(d.id, [], MODEL, live()), { ok: true, ...queue() });
  assert.deepEqual(await s.translate(old.id, [], MODEL, null), { ok: false, reason: "no_document" });
  await assert.rejects(s.deleteDocument(old.id), code("locked"));
  assert.deepEqual(c.asked, []);
  assert.deepEqual(tree(c.base), before);
  assert.equal(c.safeCalls.filter((x) => x === "decrypt").length, 1);

  assert.equal(await s.deleteAllDocuments(), true);
  assert.ok(!fs.existsSync(c.root));
  assert.equal(s.getStorage().state, "ok");
  assert.equal((await finish(s, d)).saved, true);
});

test("no keyring: nothing is saved, no answer is recorded, and the renderer is told why", async (t) => {
  const c = computer(t);
  c.keyring = "missing";
  const s = c.start({ platform: "linux" });
  s.open();
  const d = c.pick("%PDF one");
  await finish(s, d);
  assert.deepEqual(s.setKeepDocuments(true), { saved: 0, failed: 0 });
  assert.equal(c.answer, "unanswered");
  assert.deepEqual(s.getStorage(), {
    keep: null,
    state: "no_keyring",
    saved: 0,
    unreadable: 0,
    message: "Saving is not available on this computer: no system keyring was found. Set up GNOME Keyring or KWallet to save documents.",
  });
  assert.equal(c.start({ platform: "win32" }).getStorage().message, "Saving is not available on this computer: no system keyring was found.");
  c.answer = "yes"; // said earlier, when there was a keyring
  assert.equal((await finish(s, d)).saved, false);
  assert.deepEqual(await s.translate(d.id, [], MODEL, live()), { ok: true, ...queue() });
  assert.equal(await s.deleteDocument(d.id), true);
  assert.ok(!fs.existsSync(c.base));
  assert.deepEqual(c.safeCalls.filter((x) => x !== "available"), []);
});

test("no keyring with documents saved earlier: they stay, only delete all removes them", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const old = c.pick("%PDF saved before");
  await finish(c.start(), old);
  const before = tree(c.base);
  c.keyring = "missing";
  const s = c.start();
  s.open();
  assert.ok(c.logs.includes("store_unavailable reason=no_keyring"));
  assert.deepEqual([s.listDocuments(), s.source(old.id), s.getStorage().unreadable], [[], null, 1]);
  await assert.rejects(s.deleteDocument(old.id), code("locked"));
  assert.deepEqual(tree(c.base), before);
  assert.equal(await s.deleteAllDocuments(), true);
  assert.ok(!fs.existsSync(c.root));
});

test("no local folder: nothing is read or written, under any name", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const cwd = process.cwd();
  process.chdir(c.tmp); // a relative "no_local_folder/store" would show up here
  t.after(() => process.chdir(cwd));
  const s = c.start({ base: "no_local_folder" });
  s.open();
  const d = c.pick("%PDF one");
  assert.equal((await finish(s, d)).saved, false);
  assert.deepEqual(s.setKeepDocuments(true), { saved: 0, failed: 0 });
  assert.deepEqual(s.listDocuments(), []);
  assert.equal(s.source(d.id), null);
  assert.equal(s.getStorage().state, "no_local_folder");
  assert.equal(s.getStorage().message, "Saving is not available on this computer: Windows did not give a local app data folder (LOCALAPPDATA).");
  assert.equal(await s.deleteAllDocuments(), false);
  assert.equal(await s.deleteDocument(d.id), true);
  assert.deepEqual(fs.readdirSync(c.tmp), [path.basename(d.source)]);
  assert.deepEqual([c.safeCalls, c.asked.length], [[], 1]);
});

test("startup cleans up an unlocked store", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  await finish(c.start(), c.pick("%PDF one"));
  fs.mkdirSync(path.join(c.root, "docs", "f".repeat(32)));
  c.start().open();
  assert.equal(c.docs().length, 1);
  assert.ok(c.logs.includes("store_cleanup folders=1"));
});

test("a settings write that fails is a code, and saves nothing", async (t) => {
  const c = computer(t);
  c.writeFails = true;
  const s = c.start();
  await finish(s, c.pick("%PDF one"));
  assert.throws(() => s.setKeepDocuments(true), code("save_failed"));
  assert.ok(!fs.existsSync(c.base));
});

test("a result or a source file over the limit is not saved", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const s = c.start();
  const big = c.pick("%PDF one");
  big.response.sentences.p1_s2 = { page: 1, text_orig: "x".repeat(MAX_RESULT_BYTES) };
  assert.equal((await finish(s, big)).saved, false);
  const long = c.pick("%PDF two longer");
  fs.truncateSync(long.source, MAX_SOURCE_BYTES + 1); // sparse: no real disk use
  assert.equal((await finish(s, long)).saved, false);
  assert.ok(!fs.existsSync(c.base));
  assert.equal(c.logs.filter((l) => l === "store_save skipped: too_large").length, 2);

  const ok = c.pick("%PDF three, longer again");
  await finish(s, ok);
  fs.truncateSync(ok.source, MAX_SOURCE_BYTES + 1); // the saved copy stays; English does not depend on the file
  await s.translate(ok.id, [], MODEL, live());
  assert.deepEqual((await s.translate(ok.id, [], MODEL, null)), { ok: true, ...queue() });
  const before = tree(c.base);
  await s.translate(ok.id, [], MODEL, live(MODEL, { p1_s1: { ...en, en: "x".repeat(MAX_RESULT_BYTES) } }));
  assert.deepEqual(tree(c.base), before);
});

test("bad arguments are rejected without touching disk, the keyring or the dialog", async (t) => {
  const c = computer(t);
  c.answer = "yes";
  const d = c.pick("%PDF one");
  await finish(c.start(), d);
  const before = tree(c.base);
  c.safeCalls.length = 0;
  const s = c.start({
    settings: {
      read: () => assert.fail("read settings"),
      write: () => assert.fail("wrote settings"),
    },
  });
  for (const bad of [undefined, null, 5, {}, [d.id], "", "../x", d.id.slice(1), d.id.toUpperCase(), `${d.id}0`]) {
    await assert.rejects(s.deleteDocument(bad), /^Error: bad_doc_id$/);
    await assert.rejects(s.translate(bad, [], MODEL, live()), /^Error: bad_doc_id$/);
  }
  for (const bad of [undefined, null, 0, 1, "yes", "true", {}]) assert.throws(() => s.setKeepDocuments(bad), /^Error: bad_keep$/);
  for (const bad of [undefined, "p1_s1", [1], ["x"], ["../p1_s1"], Array(201).fill("p1_s1")]) {
    await assert.rejects(s.translate(d.id, bad, MODEL, live()), /^Error: bad_sentence_ids$/);
  }
  for (const bad of [5, {}, [MODEL], "", "__proto__", "a/b", "a".repeat(65)]) {
    await assert.rejects(s.translate(d.id, [], bad, null), /^Error: bad_model_id$/);
  }
  assert.deepEqual([tree(c.base), c.safeCalls, c.asked, c.forgot], [before, [], [], []]);
});

test("nothing the renderer gets, and no log line, holds a path, a file name, a folder name or a key", async (t) => {
  const c = computer(t);
  const s = c.start();
  const d = c.pick("%PDF one");
  const out: unknown[] = [await finish(s, d), s.setKeepDocuments(true), await s.translate(d.id, [], MODEL, live())];
  const folder = c.docs()[0]!;
  const key = flip(fs.readFileSync(path.join(c.root, "master.key"))).toString();
  const again = c.start();
  again.open();
  out.push(again.getStorage(), again.listDocuments(), await again.translate(d.id, [], MODEL, null));
  // Failures too.
  fs.writeFileSync(path.join(c.root, "docs", folder, "source.enc"), "damaged");
  out.push(again.source(d.id));
  fs.rmSync(d.source);
  out.push((await finish(again, d, "model-b")).saved);
  c.keyring = "denied";
  const locked = c.start();
  locked.open();
  out.push(locked.getStorage());
  await locked.deleteDocument(d.id).catch((e: Error) => out.push(e.message, e.stack?.split("\n")[0]));
  fs.rmSync(path.join(c.root, "docs"), { recursive: true });
  fs.writeFileSync(path.join(c.root, "docs"), "not a folder");
  c.keyring = "ok";
  c.start().open();
  assert.throws(() => c.start().listDocuments(), code("read_failed"));

  const shown = JSON.stringify(out);
  for (const secret of [FILE_NAME, c.tmp, folder, key, "master.key"]) assert.ok(!shown.includes(secret), "renderer leak");
  const logged = c.logs.join("\n");
  for (const want of ["store_saved bytes=", "store_opened docs=1 unreadable=0", "store_locked", "store_start failed: read_failed"]) assert.ok(logged.includes(want), want);
  for (const secret of [SENTENCE, ENGLISH, "架空", FILE_NAME, c.tmp, os.tmpdir(), d.id, d.id.slice(0, 8), folder, key]) assert.ok(!logged.includes(secret), "log leak");
});
