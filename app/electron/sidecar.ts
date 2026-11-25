// The sidecar process and the only HTTP client in the app. It runs in the main process;
// the renderer never sees the port or the token (D-83). The one allowed network target is
// the sidecar's own 127.0.0.1 port. Nothing here logs a path or document text.
import { spawn, type ChildProcess } from "node:child_process";
import * as path from "node:path";
import { app } from "electron";
import type { Llama } from "./llama";
import { sidecarCommand, sidecarEnv, type Layout } from "./paths";

const ROOT = path.join(__dirname, "..", ".."); // repo root; used in dev only
const HOST = "127.0.0.1";

type Hello = { port: number; token: string };

let child: ChildProcess | null = null;
let hello: Promise<Hello> | null = null;
let died: (() => void) | null = null;

/** Called when the sidecar process ends, however it ends (main stops llama-server then). */
export function onDeath(fn: () => void): void {
  died = fn;
}

/**
 * Start the sidecar once (the frozen binary when packaged, `uv run python -m sidecar` in dev) and read its first stdout line: {"port", "token"}.
 * With `llama`, it gets --llama-url (the port is not secret) and the API key in its
 * environment (SHIORI_LLAMA_KEY), never argv.
 */
export function start(llama: Llama | null): Promise<void> {
  hello ??= new Promise<Hello>((resolve, reject) => {
    const layout: Layout = { isPackaged: app.isPackaged, platform: process.platform, resourcesPath: process.resourcesPath, userData: app.getPath("userData"), repoRoot: ROOT };
    const cmd = sidecarCommand(layout, llama ? ["--llama-url", `http://${HOST}:${llama.port}`] : []);
    const env = sidecarEnv(llama ? { ...process.env, SHIORI_LLAMA_KEY: llama.key } : process.env);
    // stdin stays open (a pipe): when this process dies the sidecar sees EOF and exits.
    const p = spawn(cmd.command, cmd.args, { cwd: cmd.cwd, env, stdio: ["pipe", "pipe", "inherit"] });
    child = p;
    let buf = "";
    p.stdout?.on("data", (d: Buffer) => {
      buf += d.toString();
      const nl = buf.indexOf("\n");
      if (nl < 0) return;
      p.stdout?.removeAllListeners("data");
      try {
        const h = JSON.parse(buf.slice(0, nl)) as Hello;
        if (typeof h.port === "number" && typeof h.token === "string") resolve(h);
        else reject(new Error("sidecar_bad_hello"));
      } catch {
        reject(new Error("sidecar_bad_hello"));
      }
    });
    p.on("error", () => reject(new Error("sidecar_start_failed")));
    p.on("exit", () => {
      reject(new Error("sidecar_exited"));
      if (child !== p) return; // stopped on purpose (a model switch): the caller already moved on
      child = null;
      hello = null; // a later start makes a new one
      died?.();
    });
  });
  return hello.then(() => undefined);
}

/** One authenticated call to the sidecar. Returns the parsed JSON body; a non-2xx is an error. */
export async function call<T>(method: "GET" | "POST", url: string, body?: unknown): Promise<T> {
  if (!hello) throw new Error("sidecar_not_started");
  const { port, token } = await hello;
  const res = await fetch(`http://${HOST}:${port}${url}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`sidecar_http_${res.status}`);
  return (await res.json()) as T;
}

/** Quit: closing stdin tells the sidecar to stop, the SIGTERM is the backstop. */
export function stop(): void {
  const p = child;
  child = null;
  hello = null; // the next start makes a new one; this process's exit no longer counts as a death
  p?.stdin?.end();
  p?.kill("SIGTERM");
}
