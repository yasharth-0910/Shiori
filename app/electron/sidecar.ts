// The sidecar process and the only HTTP client in the app. It runs in the main process;
// the renderer never sees the port or the token (D-83). The one allowed network target is
// the sidecar's own 127.0.0.1 port. Nothing here logs a path or document text.
import { spawn, type ChildProcess } from "node:child_process";
import * as path from "node:path";

const ROOT = path.join(__dirname, "..", ".."); // repo root; dev only, packaging comes in Phase 9
const HOST = "127.0.0.1";

type Hello = { port: number; token: string };

let child: ChildProcess | null = null;
let hello: Promise<Hello> | null = null;

/** Start `uv run python -m sidecar` once and read its first stdout line: {"port", "token"}. */
function start(): Promise<Hello> {
  hello ??= new Promise<Hello>((resolve, reject) => {
    // stdin stays open (a pipe): when this process dies the sidecar sees EOF and exits.
    const p = spawn("uv", ["run", "python", "-m", "sidecar"], { cwd: ROOT, stdio: ["pipe", "pipe", "inherit"] });
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
      child = null;
      hello = null; // a later call starts a new one
      reject(new Error("sidecar_exited"));
    });
  });
  return hello;
}

/** One authenticated call to the sidecar. Returns the parsed JSON body; a non-2xx is an error. */
export async function call<T>(method: "GET" | "POST", url: string, body?: unknown): Promise<T> {
  const { port, token } = await start();
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
  child?.stdin?.end();
  child?.kill("SIGTERM");
}
