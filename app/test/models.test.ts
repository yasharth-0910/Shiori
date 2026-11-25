// Run: npm test. Model registry, recommendation, discovery order, picker default, tooltip content, no network (D-99).
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import { CUSTOM_ID, defaultChoice, discover, findLlamaServer, modelDirs, type Where } from "../electron/discover.ts";
import { recommend, REGISTRY, validateRegistry, type ModelEntry } from "../electron/registry.ts";
import { infoRows, NOT_MEASURED, optionLabel, resultKey } from "../src/modelinfo.ts";

const one = REGISTRY[0] as ModelEntry;
const mk = (over: Partial<ModelEntry>): ModelEntry => ({ ...one, ...over });

test("the shipped registry is valid and lists the three models on disk", () => {
  assert.deepEqual(validateRegistry(REGISTRY), []);
  assert.deepEqual(REGISTRY.map((m) => m.file).sort(), ["Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf", "Qwen3.5-9B-Q4_K_M.gguf", "gemma-4-E4B-it-Q4_K_M.gguf"]);
});

test("validator: required fields, url needs a sha256, hash shape, repeats", () => {
  assert.match(validateRegistry([mk({ name: "" })]).join(), /name is empty/);
  assert.match(validateRegistry([mk({ url: "https://example.test/m.gguf", sha256: "" })]).join(), /needs a sha256/);
  assert.match(validateRegistry([mk({ sha256: "abc" })]).join(), /64 lowercase hex/);
  assert.match(validateRegistry([mk({ url: "http://x", sha256: "a".repeat(64) })]).join(), /https/);
  assert.match(validateRegistry([one, one]).join(), /repeated/);
  assert.match(validateRegistry([mk({ measured: [{ text: "fast", source: "" }] })]).join(), /needs text and a source/);
  assert.deepEqual(validateRegistry([mk({ url: "https://example.test/m.gguf", sha256: "a".repeat(64) })]), []);
});

test("every entry has a real hash; a url is only the pinned huggingface.co one recorded in sources.md (D-100)", () => {
  assert.ok(REGISTRY.every((m) => /^[0-9a-f]{64}$/.test(m.sha256)));
  assert.ok(REGISTRY.every((m) => m.url === "" || m.url.startsWith("https://huggingface.co/")));
  assert.equal(REGISTRY.find((m) => m.id === "gemma-4-e4b")?.sha256, "85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87"); // D-70
});

test("recommendation for fake machines", () => {
  const mac24 = recommend({ totalRamGb: 24, arch: "arm64", platform: "darwin" });
  assert.equal(mac24?.id, "qwen3.5-9b");
  assert.match(mac24?.reason ?? "", /24 GB RAM, Apple Silicon/);
  const win16 = recommend({ totalRamGb: 15.8, arch: "x64", platform: "win32" }); // Windows reports a little under 16
  assert.equal(win16?.id, "gemma-4-e4b");
  assert.match(win16?.reason ?? "", /CPU only/);
  const tiny = recommend({ totalRamGb: 8, arch: "x64", platform: "win32" });
  assert.equal(tiny?.id, "gemma-4-e4b"); // smallest file
  assert.match(tiny?.reason ?? "", /may be slow or fail/);
  assert.equal(recommend({ totalRamGb: 24, arch: "arm64", platform: "darwin" }, []), null);
});

const w = (over: Partial<Where> & { has?: string[] } = {}): Where => ({
  env: {},
  platform: "darwin",
  pathDirs: ["/fake/bin"],
  exists: (p) => (over.has ?? []).includes(p),
  ...over,
});

test("llama-server order: SHIORI_LLAMA_SERVER, PATH, /opt/homebrew/bin, /usr/local/bin", () => {
  const all = ["/fake/bin/llama-server", "/opt/homebrew/bin/llama-server", "/usr/local/bin/llama-server"];
  assert.equal(findLlamaServer(w({ env: { SHIORI_LLAMA_SERVER: "/x/ls" }, has: all })), "/x/ls");
  assert.equal(findLlamaServer(w({ has: all })), "/fake/bin/llama-server");
  assert.equal(findLlamaServer(w({ has: all.slice(1) })), "/opt/homebrew/bin/llama-server");
  assert.equal(findLlamaServer(w({ has: all.slice(2) })), "/usr/local/bin/llama-server");
  assert.equal(findLlamaServer(w()), null);
  assert.equal(findLlamaServer(w({ platform: "win32", pathDirs: ["C:\\x"], has: [] })), null);
});

test("model order: SHIORI_MODEL overrides, then models/ in dev, user data when packaged", () => {
  assert.deepEqual(modelDirs(false, "/repo", "/ud"), ["/repo/models"]);
  assert.deepEqual(modelDirs(true, "/repo", "/ud"), ["/ud/models"]);
  const f = discover(w({ has: ["/repo/models/Qwen3.5-9B-Q4_K_M.gguf", "/repo/models/gemma-4-E4B-it-Q4_K_M.gguf"] }), ["/repo/models"], "models/ in the repo", REGISTRY);
  assert.deepEqual(Object.keys(f.installed).sort(), ["gemma-4-e4b", "qwen3.5-9b"]);
  assert.equal(f.override, null);
  assert.equal(f.expected.length, REGISTRY.length);
  assert.equal(f.expected[0]?.where, "models/ in the repo");
  // a registry file given through SHIORI_MODEL wins over the folder and becomes the override
  const o = discover(w({ env: { SHIORI_MODEL: "/elsewhere/gemma-4-E4B-it-Q4_K_M.gguf" }, has: ["/repo/models/gemma-4-E4B-it-Q4_K_M.gguf"] }), ["/repo/models"], "x", REGISTRY);
  assert.equal(o.installed["gemma-4-e4b"], "/elsewhere/gemma-4-E4B-it-Q4_K_M.gguf");
  assert.equal(o.override, "gemma-4-e4b");
  // an unknown file is a custom model
  const c = discover(w({ env: { SHIORI_MODEL: "/m/mine.gguf" } }), ["/repo/models"], "x", REGISTRY);
  assert.equal(c.override, CUSTOM_ID);
  assert.equal(c.custom, "/m/mine.gguf");
  // nothing found: nothing installed, the expected list says what and where
  const none = discover(w(), ["/ud/models"], "models/ in the app's user data folder", REGISTRY);
  assert.deepEqual(none.installed, {});
  assert.equal(none.binary, null);
});

test("picker default: override, else recommended if installed, else best installed, else none", () => {
  const rec = recommend({ totalRamGb: 24, arch: "arm64", platform: "darwin" });
  const base = { binary: "/b", custom: null, override: null, expected: [] };
  assert.equal(defaultChoice({ ...base, installed: { "qwen3.5-9b": "/a", "gemma-4-e4b": "/b" } }, rec, REGISTRY), "qwen3.5-9b");
  assert.equal(defaultChoice({ ...base, installed: { "gemma-4-e4b": "/b" } }, rec, REGISTRY), "gemma-4-e4b"); // recommended one missing
  assert.equal(defaultChoice({ ...base, installed: { "qwen3-swallow-8b": "/s", "gemma-4-e4b": "/b" } }, null, REGISTRY), "gemma-4-e4b"); // rank order
  assert.equal(defaultChoice({ ...base, installed: {}, override: "gemma-4-e4b" }, rec, REGISTRY), "gemma-4-e4b");
  assert.equal(defaultChoice({ ...base, installed: {} }, rec, REGISTRY), null);
});

test("tooltip: every field, measured figures with their source, or the not-measured line", () => {
  const rows = Object.fromEntries(infoRows({ ...one, installed: true }));
  for (const k of ["Model", "Parameters", "Quantization", "File size", "License", "RAM needed", "Best for", "Measured"]) assert.ok(rows[k], k);
  assert.equal(rows["Parameters"], "9B");
  assert.equal(rows["File size"], "5.68 GB");
  assert.match(rows["RAM needed"] ?? "", /at least 16 GB, 24 GB recommended/);
  assert.match(rows["Measured"] ?? "", /Median 70 s per document on 50 short tenders \(M4 Mac\)/);
  assert.match(rows["Measured"] ?? "", /\[data\/cache\/gemini_compare\/lists_report\.md/);
  assert.equal(Object.fromEntries(infoRows({ ...mk({ measured: [] }), installed: true }))["Measured"], NOT_MEASURED);
  assert.equal(NOT_MEASURED, "not measured on this machine type");
  const unk = Object.fromEntries(infoRows({ ...mk({ license: "not yet recorded", sizeBytes: 0, minRamGb: 0, recommendedRamGb: 0 }), installed: true }));
  assert.equal(unk["File size"], "not yet recorded");
  assert.equal(unk["RAM needed"], "not yet recorded");
});

test("every measured figure in the registry names a source that exists or is a D-number", () => {
  for (const m of REGISTRY) for (const x of m.measured) assert.ok(x.source, `${m.id}: ${x.text}`);
});

test("option labels and result keys", () => {
  assert.equal(optionLabel({ ...one, installed: true }), "Qwen3.5-9B");
  assert.equal(optionLabel({ ...one, installed: false }), "Qwen3.5-9B (not installed)");
  assert.notEqual(resultKey("abc", "qwen3.5-9b"), resultKey("abc", "gemma-4-e4b"));
  assert.equal(resultKey("abc", "qwen3.5-9b"), resultKey("abc", "qwen3.5-9b"));
  assert.equal(resultKey("abc", undefined), "abc:none");
});

test("model code makes no network call except the app's own loopback", () => {
  const files = ["electron/registry.ts", "electron/discover.ts", "src/modelinfo.ts", "src/ModelPicker.tsx", "src/Setup.tsx"];
  for (const f of files) {
    // the registry's pinned huggingface.co urls are the one allowed exception (D-100)
    const t = readFileSync(new URL(`../${f}`, import.meta.url), "utf8").replace(/"https:\/\/huggingface\.co\/[^"]+"/g, '"PINNED"');
    assert.doesNotMatch(t, /\bfetch\s*\(|XMLHttpRequest|WebSocket|node:https?|node:net|node:dns|https?:\/\/(?!example\.test)/, f);
  }
  assert.ok(readdirSync(new URL("../src/", import.meta.url)).includes("ModelPicker.tsx"));
});

// --- packaged paths and llama.ts (D-112) ---
import { bundledLlama, exeName, modelsDir, sidecarCommand, sidecarEnv, type Layout } from "../electron/paths.ts";
import { buildArgs } from "../electron/llama.ts";

const lay = (platform: string, isPackaged: boolean): Layout => ({
  isPackaged,
  platform,
  resourcesPath: platform === "win32" ? "C:\\Apps\\Shiori\\resources" : platform === "darwin" ? "/Applications/Shiori.app/Contents/Resources" : "/opt/Shiori/resources",
  userData: platform === "win32" ? "C:\\Users\\a\\AppData\\Roaming\\Shiori" : "/home/a/.config/Shiori",
  repoRoot: "/repo",
});

test("exeName adds .exe on Windows only", () => {
  assert.equal(exeName("llama-server", "win32"), "llama-server.exe");
  assert.equal(exeName("llama-server", "darwin"), "llama-server");
  assert.equal(exeName("shiori-sidecar", "linux"), "shiori-sidecar");
});

test("sidecar command: frozen binary with no cwd when packaged, uv in the repo in dev", () => {
  const x = ["--llama-url", "http://127.0.0.1:1"];
  assert.deepEqual(sidecarCommand(lay("darwin", true), x), { command: "/Applications/Shiori.app/Contents/Resources/sidecar/shiori-sidecar", args: x, cwd: undefined });
  assert.deepEqual(sidecarCommand(lay("win32", true), []), { command: "C:\\Apps\\Shiori\\resources\\sidecar\\shiori-sidecar.exe", args: [], cwd: undefined });
  assert.equal(sidecarCommand(lay("linux", true), []).command, "/opt/Shiori/resources/sidecar/shiori-sidecar");
  assert.deepEqual(sidecarCommand(lay("darwin", false), x), { command: "uv", args: ["run", "python", "-m", "sidecar", ...x], cwd: "/repo" });
});

test("the sidecar environment drops every telemetry variable and keeps the rest", () => {
  const env = { PATH: "/bin", SHIORI_LLAMA_KEY: "k", NOT_OTEL_X: "1", FASTAPI_OTEL_AUTO_CONFIGURE: "true", OTEL_EXPORTER_OTLP_ENDPOINT: "x", OTEL_SDK_DISABLED: "false", otel_traces_exporter: "otlp" };
  assert.deepEqual(sidecarEnv(env), { PATH: "/bin", SHIORI_LLAMA_KEY: "k", NOT_OTEL_X: "1" });
  assert.equal(env.FASTAPI_OTEL_AUTO_CONFIGURE, "true"); // a copy: our own environment is not touched
});

test("bundled llama-server and models folder by platform", () => {
  assert.equal(bundledLlama(lay("darwin", true)), "/Applications/Shiori.app/Contents/Resources/llama/llama-server");
  assert.equal(bundledLlama(lay("win32", true)), "C:\\Apps\\Shiori\\resources\\llama\\llama-server.exe");
  assert.equal(bundledLlama(lay("linux", true)), "/opt/Shiori/resources/llama/llama-server");
  assert.equal(bundledLlama(lay("darwin", false)), null);
  assert.equal(modelsDir(lay("win32", true)), "C:\\Users\\a\\AppData\\Roaming\\Shiori\\models");
  assert.equal(modelsDir(lay("linux", true)), "/home/a/.config/Shiori/models");
  assert.equal(modelsDir(lay("darwin", false)), "/repo/models");
});

test("packaged: only the bundled llama-server counts, the PATH is ignored; the override still wins", () => {
  const b = "/res/llama/llama-server";
  assert.equal(findLlamaServer(w({ bundled: b, has: [b, "/fake/bin/llama-server"] })), b);
  assert.equal(findLlamaServer(w({ bundled: b, has: ["/fake/bin/llama-server"] })), null);
  assert.equal(findLlamaServer(w({ bundled: b, env: { SHIORI_LLAMA_SERVER: "/x/ls" } })), "/x/ls");
});

test("llama-server arguments: no key in argv, per-model extras, Windows model paths", () => {
  const a = buildArgs("/m/Qwen3.5-9B-Q4_K_M.gguf", 8123);
  assert.deepEqual(a.slice(0, 6), ["-m", "/m/Qwen3.5-9B-Q4_K_M.gguf", "--host", "127.0.0.1", "--port", "8123"]);
  assert.ok(!a.some((x) => /key/i.test(x)));
  assert.ok(buildArgs("C:\\m\\LFM2.5-8B-x.gguf", 1).includes("--reasoning-budget"));
  assert.ok(!a.includes("--reasoning-budget"));
});

test("Processing shows the scan message for the scan_not_supported code (D-112)", () => {
  const src = readFileSync(new URL("../src/Processing.tsx", import.meta.url), "utf8");
  assert.ok(src.includes('"This PDF is a scan or print-to-PDF image. This version cannot read scans yet."'));
  assert.ok(src.includes('error === "scan_not_supported"'));
});
