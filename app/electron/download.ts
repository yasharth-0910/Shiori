// The model download (D-100). The ONE file in the app allowed to import a network module: the first-run
// download is the one exception to "the shipped app makes no network request" (CLAUDE.md, D-09).
// - It takes a registry id, never a URL: the URL is the registry entry's pinned one.
// - https only; redirects are followed over https only, because the SHA-256 (not the host) is what makes the bytes trusted.
// - Bytes go to <tempDir>/<file>.part, resume with a Range request, and move into the models folder only after the
//   whole file hashes to the registry value. A mismatch deletes the partial file.
// - Logs hold event names, byte counts and timings. Never a URL, a path or a file name.
// Also here, because it ends the same way (hash, then copy in): choosing a model file from disk.
import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as http from "node:http";
import * as https from "node:https";
import * as path from "node:path";
import type { DownloadError, DownloadState, ImportResult } from "./downloadtypes";
import type { ModelEntry } from "./registry";

export type { DownloadError, DownloadState, ImportResult, Phase } from "./downloadtypes";

export type Options = {
  registry: ModelEntry[];
  modelsDir: string; // where a verified model ends up
  tempDir: string; // where partial files live (the app's user data folder)
  log?: (event: string, data: Record<string, number | string>) => void;
  // Tests only: lets a registry url be plain http on the loopback address. main.ts never sets it.
  allowLoopbackHttp?: boolean;
};

const MAX_REDIRECTS = 5;
const OFFLINE = new Set(["ECONNREFUSED", "ENOTFOUND", "ENETUNREACH", "EHOSTUNREACH", "EAI_AGAIN", "ETIMEDOUT"]);

class Fail extends Error {
  kind: DownloadError;
  constructor(kind: DownloadError) {
    super(kind);
    this.kind = kind;
  }
}

/** SHA-256 of a file, streamed (a model is several GB). */
export function sha256File(file: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const h = createHash("sha256");
    fs.createReadStream(file)
      .on("data", (c) => h.update(c))
      .on("error", reject)
      .on("end", () => resolve(h.digest("hex")));
  });
}

export function createDownloader(o: Options) {
  const log = o.log ?? ((e, d) => console.log(`download: ${e}`, JSON.stringify(d)));
  let state: DownloadState = { id: null, phase: "idle", received: 0, total: 0, error: null };
  let running: Promise<void> | null = null;

  const allowed = (u: URL) => u.protocol === "https:" || (!!o.allowLoopbackHttp && u.protocol === "http:" && u.hostname === "127.0.0.1");

  // One request (no redirect handling). Resolves with the response; the caller reads the body.
  const get = (u: URL, headers: Record<string, string>) =>
    new Promise<http.IncomingMessage>((resolve, reject) => {
      const req = (u.protocol === "https:" ? https : http).get(u, { headers }, resolve);
      req.setTimeout(30_000, () => req.destroy(Object.assign(new Error("timeout"), { code: "ETIMEDOUT" })));
      req.on("error", reject);
    });

  // Follows redirects, https only, up to MAX_REDIRECTS. Only a Range header is ever sent (to any host).
  async function open(url: string, offset: number): Promise<http.IncomingMessage> {
    let u = new URL(url);
    for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
      if (!allowed(u)) throw new Fail("http_error");
      const res = await get(u, offset > 0 ? { Range: `bytes=${offset}-` } : {}).catch((e: NodeJS.ErrnoException) => {
        throw new Fail(OFFLINE.has(e.code ?? "") ? "offline" : "interrupted");
      });
      const code = res.statusCode ?? 0;
      if (code >= 300 && code < 400 && res.headers.location) {
        res.resume();
        u = new URL(res.headers.location, u);
        continue;
      }
      return res;
    }
    throw new Fail("http_error");
  }

  async function transfer(m: ModelEntry, part: string): Promise<void> {
    let offset = fs.existsSync(part) ? fs.statSync(part).size : 0;
    if (offset > m.sizeBytes) offset = 0; // not ours
    if (offset === 0) fs.rmSync(part, { force: true });
    state.received = offset;
    state.total = m.sizeBytes;
    if (offset < m.sizeBytes) {
      if (offset > 0) log("download_resume", { id: m.id, offset });
      let res = await open(m.url, offset);
      if (res.statusCode === 416 && offset > 0) {
        res.resume(); // the server does not like our offset: start over once
        fs.rmSync(part, { force: true });
        offset = 0;
        state.received = 0;
        res = await open(m.url, 0);
      }
      const code = res.statusCode ?? 0;
      if (code !== 200 && code !== 206) {
        res.resume();
        throw new Fail("http_error");
      }
      if (code === 200 && offset > 0) {
        fs.rmSync(part, { force: true }); // the server ignored Range and sent everything
        state.received = 0;
      }
      await new Promise<void>((resolve, reject) => {
        const out = fs.createWriteStream(part, { flags: code === 206 ? "a" : "w" });
        let failed: Fail | null = null;
        const fail = (f: Fail) => {
          failed ??= f;
          res.destroy();
          out.end();
        };
        res.on("data", (c: Buffer) => {
          state.received += c.length;
          if (!out.write(c)) {
            res.pause();
            out.once("drain", () => res.resume());
          }
        });
        res.on("error", () => fail(new Fail("interrupted")));
        res.on("aborted", () => fail(new Fail("interrupted")));
        out.on("error", () => fail(new Fail("disk")));
        res.on("end", () => out.end());
        // 'close' on res without 'end' = the connection dropped before the body finished.
        res.on("close", () => {
          if (!res.complete) fail(new Fail("interrupted"));
        });
        out.on("close", () => (failed ? reject(failed) : resolve()));
      });
    }
    state.phase = "verifying";
    const got = fs.existsSync(part) ? fs.statSync(part).size : 0;
    if (got !== m.sizeBytes) {
      // short: a dropped connection that looked clean; keep the partial file for the next resume. long: wrong file.
      if (got < m.sizeBytes) throw new Fail("interrupted");
      fs.rmSync(part, { force: true });
      throw new Fail("hash_mismatch");
    }
    if ((await sha256File(part)) !== m.sha256) {
      fs.rmSync(part, { force: true });
      throw new Fail("hash_mismatch");
    }
    place(part, path.join(o.modelsDir, m.file));
  }

  async function run(m: ModelEntry): Promise<void> {
    const t0 = Date.now();
    log("download_start", { id: m.id });
    try {
      fs.mkdirSync(o.tempDir, { recursive: true });
      fs.mkdirSync(o.modelsDir, { recursive: true });
      await transfer(m, path.join(o.tempDir, `${m.file}.part`));
      state.phase = "done";
      log("download_done", { id: m.id, bytes: m.sizeBytes, ms: Date.now() - t0 });
    } catch (e) {
      const kind: DownloadError = e instanceof Fail ? e.kind : "disk";
      state = { ...state, phase: "failed", error: kind };
      log("download_failed", { id: m.id, reason: kind, bytes: state.received, ms: Date.now() - t0 });
    }
  }

  /** Moves a finished file next to the other models: rename, or copy then rename across disks. */
  function place(from: string, to: string): void {
    try {
      fs.renameSync(from, to);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EXDEV") throw new Fail("disk");
      try {
        fs.copyFileSync(from, `${to}.tmp`);
        fs.renameSync(`${to}.tmp`, to);
        fs.rmSync(from, { force: true });
      } catch {
        fs.rmSync(`${to}.tmp`, { force: true });
        throw new Fail("disk");
      }
    }
  }

  return {
    /**
     * Starts the download of a registry model. `id` must be a registry id: a URL (or anything else) is refused.
     * Throws at once for a bad id, a model with no recorded url, an installed model or a download already running;
     * a transfer failure is reported through status(). The promise ends when the transfer does and never rejects.
     */
    start(id: unknown): Promise<void> {
      const m = typeof id === "string" ? o.registry.find((x) => x.id === id) : undefined;
      if (!m) throw new Error("unknown_model");
      if (!m.url || !m.sha256) throw new Error("download_not_available");
      if (running) throw new Error("download_busy");
      if (fs.existsSync(path.join(o.modelsDir, m.file))) throw new Error("already_installed");
      state = { id: m.id, phase: "downloading", received: 0, total: m.sizeBytes, error: null };
      const p = run(m).finally(() => {
        if (running === p) running = null;
      });
      running = p;
      return p;
    },
    status: (): DownloadState => ({ ...state }),
    /**
     * A .gguf chosen from disk is copied in only when its SHA-256 equals a registry entry's. `file` comes from the
     * native file dialog in main, never from the renderer. The copy goes to <name>.tmp first, then is renamed.
     */
    async importFile(file: string): Promise<ImportResult> {
      if (!/\.gguf$/i.test(file)) return { ok: false, reason: "not_gguf" };
      let hash: string;
      try {
        hash = await sha256File(file);
      } catch {
        return { ok: false, reason: "disk" };
      }
      const m = o.registry.find((x) => x.sha256 === hash);
      if (!m) return { ok: false, reason: "unknown_file" };
      const to = path.join(o.modelsDir, m.file);
      try {
        fs.mkdirSync(o.modelsDir, { recursive: true });
        if (path.resolve(file) !== path.resolve(to)) {
          fs.copyFileSync(file, `${to}.tmp`);
          fs.renameSync(`${to}.tmp`, to);
        }
      } catch {
        fs.rmSync(`${to}.tmp`, { force: true });
        return { ok: false, reason: "disk" };
      }
      log("import_done", { id: m.id, bytes: m.sizeBytes });
      return { ok: true, id: m.id };
    },
  };
}

export type Downloader = ReturnType<typeof createDownloader>;
