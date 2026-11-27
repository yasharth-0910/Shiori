// Run: npm test. Every child process goes through electron/child.ts: no console window on Windows (W03), and a
// child's stderr is counted, never logged (U1).
import assert from "node:assert/strict";
import childProcess from "node:child_process";
import { EventEmitter, once } from "node:events";
import * as fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
import * as path from "node:path";
import { mock, test } from "node:test";
import { startChild } from "../electron/child.ts";
import * as llama from "../electron/llama.ts";

const ELECTRON = path.join(import.meta.dirname, "..", "electron");
const SECRET = "入札公告 本文 /Users/someone/秘密.pdf";

/** Runs `script` in a real node child and returns what was logged, plus anything printed by this process. */
async function run(script: string) {
  const lines: string[] = [];
  const printed = [mock.method(console, "log", () => {}), mock.method(console, "error", () => {})];
  try {
    const p = startChild("sidecar", process.execPath, ["-e", script], { stdio: ["ignore", "ignore", "pipe"] }, (l) => lines.push(l));
    await once(p, "close");
    assert.equal(printed[0]!.mock.callCount() + printed[1]!.mock.callCount(), 0);
  } finally {
    mock.restoreAll();
  }
  return lines;
}

test("stderr content never reaches the log: only the line count and the exit code", async () => {
  const lines = await run(`process.stderr.write(${JSON.stringify(`${SECRET}\nTraceback: ${SECRET}\nno newline ${SECRET}`)}); process.exitCode = 3`);
  assert.deepEqual(lines, ["sidecar_closed: code=3 signal=null stderr_lines=3"]);
});

test("stderr is drained: a child writing more than a pipe holds still ends", { timeout: 30_000 }, async () => {
  const lines = await run(`process.stderr.write(${JSON.stringify(`${SECRET}\n`)}.repeat(100000))`);
  assert.deepEqual(lines, ["sidecar_closed: code=0 signal=null stderr_lines=100000"]);
});

test("a command that cannot start logs the error type, never the path", async () => {
  const lines: string[] = [];
  const p = startChild("llama", path.join(ELECTRON, "秘密", "no-such-binary"), [], { stdio: "ignore" }, (l) => lines.push(l));
  await new Promise((r) => p.on("close", r));
  assert.equal(lines[0], "llama_process failed: ENOENT");
  assert.match(lines[1]!, /^llama_closed: code=-?\d+ signal=null$/);
  assert.equal(lines.length, 2);
});

test("a synchronous spawn error is logged and thrown on as its type only", () => {
  const lines: string[] = [];
  mock.method(childProcess, "spawn", () => {
    throw Object.assign(new Error(`spawn ${SECRET} EPERM`), { code: "EPERM" });
  });
  syncBuiltinESMExports();
  try {
    assert.throws(() => startChild("llama", "x", [], {}, (l) => lines.push(l)), { message: "EPERM" });
  } finally {
    mock.restoreAll();
    syncBuiltinESMExports();
  }
  assert.deepEqual(lines, ["llama_spawn failed: EPERM"]);
});

test("the spawn options hold windowsHide true, also for llama-server, and a caller cannot turn it off", async () => {
  const seen: { windowsHide?: boolean; stdio?: unknown }[] = [];
  mock.method(childProcess, "spawn", (_command: string, _args: string[], options: (typeof seen)[number]) => {
    seen.push(options);
    const p = new EventEmitter();
    setImmediate(() => p.emit("exit", 1, null));
    return p;
  });
  syncBuiltinESMExports();
  try {
    startChild("x", "x", [], { windowsHide: false });
    // Any existing file passes the checks before the spawn; the fake child exits at once.
    await assert.rejects(llama.start({ binary: process.execPath, model: process.execPath }), { message: "llama_exited_while_loading" });
  } finally {
    mock.restoreAll();
    syncBuiltinESMExports();
  }
  assert.deepEqual(seen.map((o) => o.windowsHide), [true, true]);
  assert.equal(seen[1]!.stdio, "ignore");
});

// Static: a new process start cannot skip child.ts, and so cannot miss windowsHide.
const sources = fs.readdirSync(ELECTRON, { recursive: true, encoding: "utf8" }).filter((f) => f.endsWith(".ts"));
const read = (f: string) => fs.readFileSync(path.join(ELECTRON, f), "utf8");

test("only child.ts can start a process", () => {
  for (const f of sources) {
    const text = read(f);
    assert.doesNotMatch(text, /utilityProcess/, f);
    if (f === "child.ts") continue;
    // Elsewhere child_process may only be imported for its types.
    for (const line of text.split("\n")) if (/child_process/.test(line)) assert.match(line, /^import type /, `${f}: ${line}`);
  }
  const child = read("child.ts");
  assert.equal(child.match(/spawn\(/g)?.length, 1);
  assert.ok(child.includes("spawn(command, args, { ...options, windowsHide: true })"));
});

test("no child inherits stderr, and the sidecar's is piped", () => {
  for (const f of sources) assert.doesNotMatch(read(f), /["']inherit["']/, f);
  assert.ok(read("sidecar.ts").includes('stdio: ["pipe", "pipe", "pipe"]'));
});
