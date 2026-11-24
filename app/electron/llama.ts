// Starts and stops one llama-server on 127.0.0.1 (D-84). Copied in approach from the dev
// harness (health wait, one model at a time), without importing any of it. It tracks only the
// child it started (D-112): no pgrep, ps or kill by name, so it works the same on Windows. A
// llama-server left behind by a killed (SIGKILL) app is not found again; the user ends it by hand. The API key goes to llama-server through its environment
// (LLAMA_API_KEY), never argv, which `ps` shows. Nothing here logs a path or document text;
// llama-server's own output is discarded.
import { spawn, type ChildProcess } from "node:child_process";
import { randomBytes } from "node:crypto";
import * as fs from "node:fs";
import * as net from "node:net";
import * as path from "node:path";

const HOST = "127.0.0.1";
const CTX = 16384; // what the extractor was tuned with (eval/hybrid.py)
const READY_MS = 600_000;
// Per-model flags the harness uses (eval/model_feasibility.py EXTRA_ARGS).
const EXTRA_ARGS: Record<string, string[]> = { "LFM2.5-8B": ["--reasoning-budget", "0"] };

export type Llama = { port: number; key: string };
export type Config = { binary: string; model: string };

let proc: ChildProcess | null = null;

const fail = (code: string): never => {
  throw new Error(code);
};

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.on("error", reject);
    s.listen(0, HOST, () => {
      const { port } = s.address() as net.AddressInfo;
      s.close(() => resolve(port));
    });
  });
}

async function healthy(port: number): Promise<boolean> {
  try {
    return (await fetch(`http://${HOST}:${port}/health`, { signal: AbortSignal.timeout(2000) })).ok;
  } catch {
    return false;
  }
}

/** llama-server's command line for a model file; the key is not here, it goes in the environment. */
export function buildArgs(model: string, port: number): string[] {
  const extra = Object.entries(EXTRA_ARGS).find(([k]) => path.basename(model.replaceAll("\\", "/")).includes(k))?.[1] ?? [];
  return ["-m", model, "--host", HOST, "--port", String(port), "-c", String(CTX), "-np", "1", "--reasoning", "off", "--no-webui", "-ngl", "99", ...extra];
}

/** Start the server and wait until /health answers. Throws an Error whose message is a short code. */
export async function start(cfg: Config): Promise<Llama> {
  if (proc) fail("llama_already_started");
  if (!fs.existsSync(cfg.binary)) fail("llama_binary_missing");
  if (!fs.existsSync(cfg.model)) fail("model_file_missing");
  const port = await freePort();
  const key = randomBytes(32).toString("hex");
  const args = buildArgs(cfg.model, port);
  const p = spawn(cfg.binary, args, { env: { ...process.env, LLAMA_API_KEY: key }, stdio: "ignore" });
  proc = p;
  let exited = false;
  p.on("exit", () => {
    exited = true;
    if (proc === p) proc = null;
  });
  p.on("error", () => (exited = true));
  const t0 = Date.now();
  while (Date.now() - t0 < READY_MS) {
    if (exited) fail("llama_exited_while_loading");
    if (await healthy(port)) return { port, key };
    await new Promise((r) => setTimeout(r, 1000));
  }
  stop();
  return fail("llama_not_ready");
}

/** Stop it (quit, sidecar death, signal). Safe to call twice. */
export function stop(): void {
  proc?.kill("SIGTERM");
  proc = null;
}

/** Stop only the server this app started and wait until it has exited (a model switch must not meet its own dying process). */
export async function stopAndWait(): Promise<void> {
  const p = proc;
  if (!p || p.exitCode !== null) return stop();
  const gone = new Promise<void>((r) => p.once("exit", () => r()));
  stop();
  await Promise.race([gone, new Promise((r) => setTimeout(r, 10_000))]);
}
