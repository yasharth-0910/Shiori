// Run: npm test. The model download (D-100) against a local server on 127.0.0.1 serving a small fake model.
// Real downloads use https only; allowLoopbackHttp (tests only) lets the registry url be http://127.0.0.1.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import * as http from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { createDownloader } from "../electron/download.ts";
import { allowRequest, requestFilter } from "../electron/netfilter.ts";
import { REGISTRY, validateRegistry, type ModelEntry } from "../electron/registry.ts";

const FAKE = Buffer.from(Array.from({ length: 300_000 }, (_, i) => (i * 7 + (i >> 8)) & 255));
const sha = (b: Buffer) => createHash("sha256").update(b).digest("hex");

type Plan = { body: Buffer; cutAfter?: number; redirect?: boolean };
async function serve(plan: () => Plan) {
  const seen: { url: string; range: string | undefined }[] = [];
  const server = http.createServer((req, res) => {
    seen.push({ url: req.url ?? "", range: req.headers.range });
    if (req.url === "/start") {
      res.writeHead(302, { location: "/m.gguf" }).end();
      return;
    }
    const { body, cutAfter } = plan();
    const m = /^bytes=(\d+)-$/.exec(req.headers.range ?? "");
    const from = m ? Number(m[1]) : 0;
    const part = body.subarray(from);
    res.writeHead(m ? 206 : 200, { "content-length": part.length, ...(m ? { "content-range": `bytes ${from}-${body.length - 1}/${body.length}` } : {}) });
    if (cutAfter !== undefined && !m) {
      res.write(part.subarray(0, cutAfter), () => res.socket?.destroy()); // connection dies mid-body
    } else res.end(part);
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const port = (server.address() as AddressInfo).port;
  return { seen, port, close: () => new Promise<void>((r) => (server.closeAllConnections(), server.close(() => r()))) };
}

const setup = (port: number, over: Partial<ModelEntry> = {}) => {
  const root = mkdtempSync(join(tmpdir(), "shiori-dl-"));
  const entry: ModelEntry = { ...(REGISTRY[0] as ModelEntry), id: "fake", file: "fake.gguf", sizeBytes: FAKE.length, sha256: sha(FAKE), url: `http://127.0.0.1:${port}/m.gguf`, ...over };
  const logs: string[] = [];
  const dl = createDownloader({ registry: [entry], modelsDir: join(root, "models"), tempDir: join(root, "tmp"), allowLoopbackHttp: true, log: (e, d) => logs.push(`${e} ${JSON.stringify(d)}`) });
  return { root, entry, dl, logs, models: join(root, "models"), part: join(root, "tmp", "fake.gguf.part") };
};

test("download 1: a good hash installs the file and leaves no partial file", async () => {
  const s = await serve(() => ({ body: FAKE }));
  const t = setup(s.port, { url: `http://127.0.0.1:${s.port}/start` }); // also follows a redirect
  await t.dl.start("fake");
  assert.equal(t.dl.status().phase, "done");
  assert.deepEqual(readFileSync(join(t.models, "fake.gguf")), FAKE);
  assert.equal(existsSync(t.part), false);
  assert.deepEqual(s.seen.map((r) => r.url), ["/start", "/m.gguf"]);
  assert.ok(t.logs.some((l) => l.startsWith("download_done")) && t.logs.every((l) => !l.includes("127.0.0.1") && !l.includes(t.root)), "logs name no URL or path");
  await s.close();
});

test("download 2: a bad hash deletes the partial file and installs nothing", async () => {
  const s = await serve(() => ({ body: Buffer.from(FAKE).reverse() })); // same size, other bytes
  const t = setup(s.port);
  await t.dl.start("fake");
  assert.deepEqual({ phase: t.dl.status().phase, error: t.dl.status().error }, { phase: "failed", error: "hash_mismatch" });
  assert.equal(existsSync(t.part), false);
  assert.equal(existsSync(join(t.models, "fake.gguf")), false);
  await s.close();
});

test("download 3: an interrupted transfer resumes with a Range request", async () => {
  let first = true;
  const s = await serve(() => {
    const cut = first ? 120_000 : undefined;
    first = false;
    return { body: FAKE, cutAfter: cut };
  });
  const t = setup(s.port);
  await t.dl.start("fake");
  assert.deepEqual({ phase: t.dl.status().phase, error: t.dl.status().error }, { phase: "failed", error: "interrupted" });
  const kept = readFileSync(t.part).length;
  assert.ok(kept > 0 && kept < FAKE.length, "the partial file is kept");
  await t.dl.start("fake");
  assert.equal(t.dl.status().phase, "done");
  assert.equal(s.seen[1]?.range, `bytes=${kept}-`);
  assert.deepEqual(readFileSync(join(t.models, "fake.gguf")), FAKE);
  assert.equal(existsSync(t.part), false);
  await s.close();
});

test("download 4: a URL supplied by the renderer is refused, nothing is requested", async () => {
  const s = await serve(() => ({ body: FAKE }));
  const t = setup(s.port);
  for (const bad of [`http://127.0.0.1:${s.port}/m.gguf`, `https://example.test/m.gguf`, "//host/x"]) assert.throws(() => t.dl.start(bad), /unknown_model/);
  assert.equal(s.seen.length, 0);
  await s.close();
});

test("download 5: an id that is not in the registry is refused; so is a model with no url", async () => {
  const s = await serve(() => ({ body: FAKE }));
  const t = setup(s.port);
  for (const bad of ["nope", "", undefined, null, 5, { id: "fake" }, ["fake"]]) assert.throws(() => t.dl.start(bad), /unknown_model/);
  const none = setup(s.port, { url: "" });
  assert.throws(() => none.dl.start("fake"), /download_not_available/);
  assert.equal(s.seen.length, 0);
  await s.close();
});

test("https only: without the test switch an http url is never requested", async () => {
  const s = await serve(() => ({ body: FAKE }));
  const t = setup(s.port);
  const strict = createDownloader({ registry: [t.entry], modelsDir: t.models, tempDir: join(t.root, "tmp"), log: () => {} });
  await strict.start("fake");
  assert.equal(strict.status().error, "http_error");
  assert.equal(s.seen.length, 0);
  await s.close();
});

test("offline: a refused connection is reported as offline, and a second download cannot start meanwhile", async () => {
  const s = await serve(() => ({ body: FAKE }));
  const port = s.port;
  await s.close();
  const t = setup(port);
  const p = t.dl.start("fake");
  assert.throws(() => t.dl.start("fake"), /download_busy/);
  await p;
  assert.equal(t.dl.status().error, "offline");
});

test("choose from disk: only a .gguf whose SHA-256 is a registry entry's is copied in", async () => {
  const t = setup(1);
  const dir = mkdtempSync(join(tmpdir(), "shiori-pick-"));
  const good = join(dir, "whatever-name.gguf");
  writeFileSync(good, FAKE);
  assert.deepEqual(await t.dl.importFile(good), { ok: true, id: "fake" });
  assert.deepEqual(readFileSync(join(t.models, "fake.gguf")), FAKE);
  assert.deepEqual(readdirSync(t.models), ["fake.gguf"]); // no .tmp left behind
  const other = join(dir, "other.gguf");
  writeFileSync(other, Buffer.from("not a model"));
  assert.deepEqual(await t.dl.importFile(other), { ok: false, reason: "unknown_file" });
  const wrongExt = join(dir, "x.bin");
  writeFileSync(wrongExt, FAKE);
  assert.deepEqual(await t.dl.importFile(wrongExt), { ok: false, reason: "not_gguf" });
});

test("registry validator: a url without a hash, a non-https url and an empty hash all fail", () => {
  const one = REGISTRY[0] as ModelEntry;
  const mk = (o: Partial<ModelEntry>) => validateRegistry([{ ...one, ...o }]).join();
  assert.match(mk({ sha256: "" }), /sha256 is empty/);
  assert.match(mk({ url: "http://huggingface.co/x/y.gguf" }), /url must be https/);
  assert.match(mk({ url: "ftp://huggingface.co/x/y.gguf" }), /url must be https/);
  assert.match(mk({ sha256: "A".repeat(64) }), /64 lowercase hex/);
  assert.deepEqual(validateRegistry(REGISTRY), []);
});

test("shipped registry urls: huggingface.co, a pinned 40-hex revision, the file name the entry expects, a 64-hex hash", () => {
  for (const m of REGISTRY) {
    if (!m.url) continue;
    const u = new URL(m.url);
    assert.equal(u.protocol, "https:");
    assert.equal(u.host, "huggingface.co");
    assert.match(u.pathname, new RegExp(`^/[\\w.-]+/[\\w.-]+/resolve/[0-9a-f]{40}/${m.file.replace(/\./g, "\\.")}$`), m.id);
    assert.match(m.sha256, /^[0-9a-f]{64}$/);
  }
});

test("request filter: only shiori, devtools, data and blob pass; the rest is cancelled and counted without keeping the url", () => {
  for (const ok of ["shiori://app/", "devtools://devtools/x", "data:text/html,x", "blob:shiori://app/1"]) assert.equal(allowRequest(ok), true, ok);
  for (const no of ["https://example.test/x", "http://127.0.0.1:8000/x", "http://localhost/x", "wss://example.test/s", "file:///etc/passwd", "ftp://x/y"]) assert.equal(allowRequest(no), false, no);
  const f = requestFilter();
  const out: boolean[] = [];
  for (const url of ["shiori://app/a.js", "https://example.test/", "http://127.0.0.1:1/"]) f.onBeforeRequest({ url }, (r) => out.push(r.cancel));
  assert.deepEqual(out, [false, true, true]);
  assert.equal(f.blockedCount(), 2);
  assert.deepEqual(Object.keys(f).sort(), ["blockedCount", "onBeforeRequest"]);
});
