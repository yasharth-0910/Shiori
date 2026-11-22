// Starts and stops one llama-server on 127.0.0.1 (D-84). Copied in approach from the dev
// harness (health wait, one model at a time, refuse a busy port or another llama-server),
// without importing any of it. The API key goes to llama-server through its environment
// (LLAMA_API_KEY), never argv, which `ps` shows. Nothing here logs a path or document text;
// llama-server's own output is discarded.
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { randomBytes } from "node:crypto";
import * as fs from "node:fs";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";

const HOST = "127.0.0.1";
const CTX = 16384; // what the extractor was tuned with (eval/hybrid.py)
const READY_MS = 600_000;
// Per-model flags the harness uses (eval/model_feasibility.py EXTRA_ARGS).
const EXTRA_ARGS: Record<string, string[]> = { "LFM2.5-8B": ["--reasoning-budget", "0"] };
const PIDFILE = path.join(os.tmpdir(), "shiori-llama.pid"); // lets the next start clean up after a killed app

export type Llama = { port: number; key: string };
export type Config = { binary: string; model: string };

let proc: ChildProcess | null = null;

const fail = (code: string): never => {
  throw new Error(code);
};

function pgrep(args: string[]): string[] {
  try {
    return execFileSync("pgrep", args, { encoding: "utf8" }).split(/\s+/).filter(Boolean);
  } catch {
    return []; // pgrep exits 1 when nothing matches
  }
}

/** A llama-server this app started in an earlier run and could not stop (the app was killed). */
function killStale(): void {
  let pid = 0;
  try {
    pid = Number(fs.readFileSync(PIDFILE, "utf8"));
  } catch {
    return;
  }
  try {
    const name = execFileSync("ps", ["-p", String(pid), "-o", "comm="], { encoding: "utf8" }).trim();
    if (path.basename(name) === "llama-server") process.kill(pid, "SIGTERM");
  } catch {
    /* gone already */
  }
  fs.rmSync(PIDFILE, { force: true });
}

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

/** Start the server and wait until /health answers. Throws an Error whose message is a short code. */
export async function start(cfg: Config): Promise<Llama> {
  if (proc) fail("llama_already_started");
  if (!fs.existsSync(cfg.binary)) fail("llama_binary_missing");
  if (!fs.existsSync(cfg.model)) fail("model_file_missing");
  killStale();
  if (pgrep(["-x", "llama-server"]).length) fail("another_llama_server_running"); // one local model at a time
  const port = await freePort();
  const key = randomBytes(32).toString("hex");
  const extra = Object.entries(EXTRA_ARGS).find(([k]) => path.basename(cfg.model).includes(k))?.[1] ?? [];
  const args = ["-m", cfg.model, "--host", HOST, "--port", String(port), "-c", String(CTX), "-np", "1", "--reasoning", "off", "--no-webui", "-ngl", "99", ...extra];
  const p = spawn(cfg.binary, args, { env: { ...process.env, LLAMA_API_KEY: key }, stdio: "ignore" });
  proc = p;
  let exited = false;
  p.on("exit", () => {
    exited = true;
    if (proc === p) proc = null;
  });
  p.on("error", () => (exited = true));
  if (p.pid) fs.writeFileSync(PIDFILE, String(p.pid));
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
  fs.rmSync(PIDFILE, { force: true });
}

/** Stop only the server this app started and wait until it has exited (a model switch must not meet its own dying process). */
export async function stopAndWait(): Promise<void> {
  const p = proc;
  if (!p || p.exitCode !== null) return stop();
  const gone = new Promise<void>((r) => p.once("exit", () => r()));
  stop();
  await Promise.race([gone, new Promise((r) => setTimeout(r, 10_000))]);
}
