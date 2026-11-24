// Run: npm test. "Find models on this computer" (D-115): temp folders, fake files, a small fake catalog (no 5 GB files).
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import { test } from "node:test";
import { createScanner, freeBytes, importAsGguf, knownRoots, scanForModels } from "../electron/discover.ts";
import { REGISTRY, type ModelEntry } from "../electron/registry.ts";

const sha = (b: Buffer) => createHash("sha256").update(b).digest("hex");
const bytesA = Buffer.from("GGUF" + "a".repeat(2000));
const bytesB = Buffer.from("GGUF" + "b".repeat(3000));
const wrongA = Buffer.from("GGUF" + "z".repeat(2000)); // same size as A, other content
const entry = (id: string, b: Buffer): ModelEntry => ({ ...(REGISTRY[0] as ModelEntry), id, name: `Fake ${id}`, file: `${id}.gguf`, sizeBytes: b.length, sha256: sha(b), url: "" });
const CATALOG = [entry("a", bytesA), entry("b", bytesB)];
const live = () => new AbortController().signal;

function tmp(): { root: string; put: (rel: string, b: Buffer) => string; done: () => void } {
  const root = mkdtempSync(path.join(tmpdir(), "shiori-scan-"));
  return {
    root,
    put: (rel, b) => {
      const f = path.join(root, rel);
      mkdirSync(path.dirname(f), { recursive: true });
      writeFileSync(f, b);
      return f;
    },
    done: () => rmSync(root, { recursive: true, force: true }),
  };
}

test("scan 1: right size and right hash is listed; right size and wrong hash is not", async () => {
  const t = tmp();
  t.put("good/a.gguf", bytesA);
  t.put("bad/also-a.gguf", wrongA);
  const r = await scanForModels({ roots: [t.root], catalog: CATALOG, signal: live() });
  assert.deepEqual(r.matches.map((m) => m.entry.id), ["a"]);
  assert.equal(r.others, 1); // the wrong-hash file counts as an unsupported model file
  t.done();
});

test("scan 2: every pinned model found is listed, not just the first", async () => {
  const t = tmp();
  t.put("x/a.gguf", bytesA);
  t.put("y/z/b.gguf", bytesB);
  const r = await scanForModels({ roots: [t.root], catalog: CATALOG, signal: live() });
  assert.deepEqual(r.matches.map((m) => m.entry.id).sort(), ["a", "b"]);
  t.done();
});

test("scan 3: a file whose size is not in the catalog is never hashed; only .gguf names count", async () => {
  const t = tmp();
  t.put("odd.gguf", Buffer.from("GGUF-other-size"));
  t.put("notes.txt", bytesA); // right size and content, wrong name: skipped
  let hashed = 0;
  const r = await scanForModels({ roots: [t.root], catalog: CATALOG, signal: live(), onHash: (p) => void (p && hashed++) });
  assert.equal(hashed, 0);
  assert.deepEqual(r.matches, []);
  assert.equal(r.others, 1);
  t.done();
});

test("scan 4: a symlink loop does not hang and the file is found once", async () => {
  const t = tmp();
  t.put("m/a.gguf", bytesA);
  try {
    symlinkSync(path.join(t.root, "m"), path.join(t.root, "m", "loop")); // m/loop -> m
    symlinkSync(t.root, path.join(t.root, "m", "up")); // m/up -> the root
  } catch {
    t.done();
    return; // no symlink permission on this machine
  }
  const r = await Promise.race([scanForModels({ roots: [t.root], catalog: CATALOG, signal: live() }), new Promise<never>((_, rej) => setTimeout(() => rej(new Error("hung")), 5000))]);
  assert.equal(r.matches.length, 1);
  t.done();
});

test("scan 5: the depth limit is 6 below the root", async () => {
  const t = tmp();
  t.put("1/2/3/4/5/a.gguf", bytesA); // 6 segments: found
  t.put("1/2/3/4/5/6/b.gguf", bytesB); // 7 segments: not looked at
  const r = await scanForModels({ roots: [t.root], catalog: CATALOG, signal: live() });
  assert.deepEqual(r.matches.map((m) => m.entry.id), ["a"]);
  const shallow = await scanForModels({ roots: [t.root], catalog: CATALOG, signal: live(), maxDepth: 2 });
  assert.deepEqual(shallow.matches, []);
  t.done();
});

test("scan 6: cancel stops hashing part way and lists nothing", async () => {
  const t = tmp();
  const big = Buffer.alloc(8 << 20, 7);
  t.put("big.gguf", big);
  const ctl = new AbortController();
  let last = 0;
  const r = await scanForModels({
    roots: [t.root],
    catalog: [entry("big", big)],
    signal: ctl.signal,
    onHash: (p) => {
      if (p) {
        last = p.doneBytes;
        if (p.doneBytes > 0) ctl.abort();
      }
    },
  });
  assert.ok(last > 0 && last < big.length, `stopped at ${last} of ${big.length}`);
  assert.deepEqual(r.matches, []);
  t.done();
});

test("scan 7: an Ollama blob (sha256-<hash>, no extension) is checked; a non-model blob is not counted", async () => {
  const t = tmp();
  t.put(`models/blobs/sha256-${"1".repeat(64)}`, bytesA);
  t.put(`models/blobs/sha256-${"2".repeat(64)}`, Buffer.from("not a model, just a manifest layer"));
  t.put(`models/blobs/sha256-${"3".repeat(64)}`, Buffer.from("GGUF unknown model of another size"));
  t.put(`models/elsewhere/sha256-${"4".repeat(64)}`, bytesB); // not under blobs/
  const r = await scanForModels({ roots: [t.root], catalog: CATALOG, signal: live() });
  assert.deepEqual(r.matches.map((m) => m.entry.id), ["a"]);
  assert.equal(r.others, 1); // only the blob that starts with GGUF
  t.done();
});

test("scan 8: a folder that does not exist is skipped without an error", async () => {
  const r = await scanForModels({ roots: [path.join(tmpdir(), "shiori-no-such-folder-xyz")], catalog: CATALOG, signal: live() });
  assert.deepEqual(r, { matches: [], others: 0 });
});

test("known folders: the app folder, then the three tools under the home folder, nothing else", () => {
  const roots = knownRoots(path.join(path.sep, "h"), [path.join(path.sep, "app", "models")]);
  assert.deepEqual(roots, [path.join(path.sep, "app", "models"), path.join(path.sep, "h", ".cache", "huggingface", "hub"), path.join(path.sep, "h", ".lmstudio", "models"), path.join(path.sep, "h", ".ollama", "models")]);
  assert.ok(!roots.some((r) => /Downloads|Documents|Desktop/.test(r)));
});

async function finish(s: ReturnType<typeof createScanner>) {
  for (let i = 0; i < 200 && s.status().phase === "scanning"; i++) await new Promise((r) => setTimeout(r, 10));
  return s.status();
}

test("scanner: results hold no file path, a match index maps back to its file, a second start while scanning throws", async () => {
  const t = tmp();
  const f = t.put("a.gguf", bytesA);
  const logs: string[] = [];
  const s = createScanner({ catalog: CATALOG, modelsDir: () => t.root, log: (e, d) => logs.push(`${e} ${JSON.stringify(d)}`) });
  assert.equal(s.status().phase, "idle");
  s.start([t.root]);
  assert.throws(() => s.start([t.root]), /scan_busy/);
  const st = await finish(s);
  assert.equal(st.phase, "done");
  assert.equal(st.matches.length, 1);
  assert.deepEqual(Object.keys(st.matches[0] as object).sort(), ["folder", "id", "index", "name", "sizeBytes"]);
  assert.ok(typeof st.freeBytes === "number" || st.freeBytes === null);
  assert.equal(s.fileOf(0), f);
  assert.equal(s.fileOf(1), null);
  assert.equal(s.fileOf("0"), null);
  assert.equal(s.fileOf(-1), null);
  t.done();
  void logs;
});

test("scanner: cancel ends in 'cancelled' with no matches and no file behind index 0", async () => {
  const t = tmp();
  const big = Buffer.alloc(8 << 20, 3);
  t.put("big.gguf", big);
  const s = createScanner({ catalog: [entry("big", big)], modelsDir: () => t.root, log: () => {} });
  s.start([t.root]);
  for (let i = 0; i < 500 && !s.status().hashing; i++) await new Promise((r) => setTimeout(r, 2));
  s.cancel();
  const st = await finish(s);
  assert.ok(st.phase === "cancelled" || st.phase === "done"); // done only if the 8 MiB finished before the cancel landed
  if (st.phase === "cancelled") {
    assert.deepEqual(st.matches, []);
    assert.equal(s.fileOf(0), null);
  }
  t.done();
});

test("privacy: no log line holds a path or file name; the discovery code imports no network module and writes no file", async () => {
  const t = tmp();
  t.put("secretfolder/secret-model-name.gguf", bytesA);
  t.put("secretfolder/other-secret.gguf", wrongA);
  const logs: string[] = [];
  const s = createScanner({ catalog: CATALOG, modelsDir: () => t.root, log: (e, d) => logs.push(`${e} ${JSON.stringify(d)}`) });
  s.start([t.root]);
  await finish(s);
  assert.ok(logs.length >= 2);
  for (const l of logs) assert.ok(!l.includes(t.root) && !/secret|\.gguf|[\\/]/.test(l), `path in log: ${l}`);
  for (const l of logs) for (const v of Object.values(JSON.parse(l.slice(l.indexOf("{"))) as Record<string, unknown>)) assert.equal(typeof v, "number");
  t.done();

  const src = readFileSync(new URL("../electron/discover.ts", import.meta.url), "utf8");
  const imports = [...src.matchAll(/^import .*? from "([^"]+)"/gm)].map((m) => m[1]);
  assert.deepEqual(imports.filter((i) => !i?.startsWith("./")).sort(), ["node:crypto", "node:fs", "node:fs/promises", "node:os", "node:path"]);
  assert.ok(!/\b(fetch|XMLHttpRequest|WebSocket)\b|writeFile|appendFile|createWriteStream/.test(src.replace(/\/\/.*$/gm, "")), "no fetch and no file writes in discover.ts");
  assert.equal([...src.matchAll(/console\.log/g)].length, 1); // the default logger, which only ever gets numbers
});

test("use: a .gguf goes straight to importFile; a blob gets a temporary .gguf link that is removed again", async () => {
  const t = tmp();
  const plain = t.put("p.gguf", bytesA);
  const blob = t.put(`models/blobs/sha256-${"5".repeat(64)}`, bytesA);
  const seen: string[] = [];
  const imp = async (f: string) => {
    seen.push(f);
    assert.ok(existsSync(f));
    assert.deepEqual(readFileSync(f), bytesA);
    return { ok: true as const, id: "a" };
  };
  assert.deepEqual(await importAsGguf(plain, path.join(t.root, "tmp"), imp), { ok: true, id: "a" });
  assert.equal(seen[0], plain);
  assert.deepEqual(await importAsGguf(blob, path.join(t.root, "tmp"), imp), { ok: true, id: "a" });
  assert.match(seen[1] as string, /\.gguf$/);
  assert.ok(!existsSync(seen[1] as string), "temporary link removed");
  assert.deepEqual(await importAsGguf(path.join(t.root, "gone.gguf"), t.root, imp), { ok: false, reason: "gone" });
  t.done();
});

test("freeBytes: a number for a folder that exists and for one that does not yet (nearest parent)", () => {
  const t = tmp();
  assert.ok((freeBytes(t.root) ?? 0) > 0);
  assert.ok((freeBytes(path.join(t.root, "not", "yet")) ?? 0) > 0);
  t.done();
});
