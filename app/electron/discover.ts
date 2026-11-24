// Finds llama-server and the model files on this machine (D-99). Local file checks only. Every
// input (env, paths, exists, the registry) is a parameter so tests use fake paths. Env vars stay overrides.
import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as fsp from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
import type { ImportResult } from "./downloadtypes";
import type { Facts, ModelEntry, Recommendation } from "./registry";
import type { ScanState, UseResult } from "./scantypes";

// `bundled`: the llama-server inside a packaged app (paths.ts bundledLlama); null in dev.
export type Where = { env: NodeJS.ProcessEnv; platform: string; exists: (p: string) => boolean; pathDirs: string[]; bundled?: string | null };

/** SHIORI_LLAMA_SERVER, then (packaged) the bundled one only, else PATH, /opt/homebrew/bin, /usr/local/bin. null = not found. */
export function findLlamaServer(w: Where): string | null {
  if (w.env.SHIORI_LLAMA_SERVER) return w.env.SHIORI_LLAMA_SERVER; // an override is used as given; start() reports a bad one
  if (w.bundled) return w.exists(w.bundled) ? w.bundled : null; // a packaged app never looks at the PATH
  const exe = w.platform === "win32" ? "llama-server.exe" : "llama-server"; // same rule as paths.ts exeName (no runtime import: node --test needs extensions)
  for (const d of [...w.pathDirs, "/opt/homebrew/bin", "/usr/local/bin"]) {
    const p = path.join(d, exe);
    if (w.exists(p)) return p;
  }
  return null;
}

/** Folders searched for model files: the repo's models/ in dev, the user data folder when packaged. */
export function modelDirs(isPackaged: boolean, repoRoot: string, userData: string): string[] {
  return [path.join(isPackaged ? userData : repoRoot, "models")];
}

export type Found = {
  binary: string | null;
  installed: Record<string, string>; // registry id -> file path
  custom: string | null; // SHIORI_MODEL, when it is not one of the registry files
  override: string | null; // the id SHIORI_MODEL selects ("custom" or a registry id)
  expected: { file: string; where: string }[]; // what the registry wants and where, for the "not set up" screen
};

export const CUSTOM_ID = "custom";

/** SHIORI_MODEL first, then the model folders. */
export function discover(w: Where, dirs: string[], label: string, list: ModelEntry[]): Found {
  const installed: Record<string, string> = {};
  for (const m of list)
    for (const d of dirs) {
      const p = path.join(d, m.file);
      if (w.exists(p)) {
        installed[m.id] = p;
        break;
      }
    }
  let custom: string | null = null;
  let override: string | null = null;
  const env = w.env.SHIORI_MODEL;
  if (env) {
    const known = list.find((m) => m.file === path.basename(env));
    if (known) {
      installed[known.id] = env;
      override = known.id;
    } else {
      custom = env;
      override = CUSTOM_ID;
    }
  }
  return { binary: findLlamaServer(w), installed, custom, override, expected: list.map((m) => ({ file: m.file, where: label })) };
}

export function systemFacts(): Facts {
  return { totalRamGb: os.totalmem() / 2 ** 30, arch: os.arch(), platform: os.platform() };
}

export function realWhere(bundled: string | null = null): Where {
  return { env: process.env, platform: process.platform, exists: fs.existsSync, pathDirs: (process.env.PATH ?? "").split(path.delimiter).filter(Boolean), bundled };
}

/** The picker's default: the override, else the recommended model if installed, else the best-ranked installed one, else null. */
export function defaultChoice(found: Found, rec: Recommendation | null, list: ModelEntry[]): string | null {
  if (found.override) return found.override;
  if (rec && found.installed[rec.id]) return rec.id;
  return [...list].sort((a, b) => a.rank - b.rank).find((m) => found.installed[m.id])?.id ?? null;
}

// ---- Find models on this computer (D-115) ----------------------------------------------------------------------
// Local file reads only: no network module, no log line with a path. The caller starts it, only after a click.
// Order per file: name filter, then exact byte size against the catalog, and only then the SHA-256.

export const MAX_DEPTH = 6;

/** The app's own models folder(s), then the Hugging Face cache, LM Studio and Ollama under the user's home (same on Windows: the profile folder). */
export function knownRoots(home: string, appModelDirs: string[]): string[] {
  return [...appModelDirs, path.join(home, ".cache", "huggingface", "hub"), path.join(home, ".lmstudio", "models"), path.join(home, ".ollama", "models")];
}

const isGgufName = (p: string) => /\.gguf$/i.test(p);
/** Ollama keeps GGUF files as <models>/blobs/sha256-<hash> with no extension. */
const isOllamaBlob = (p: string) => path.basename(path.dirname(p)) === "blobs" && /^sha256-[0-9a-f]{64}$/i.test(path.basename(p));

async function hasGgufMagic(file: string): Promise<boolean> {
  let fh: fsp.FileHandle | undefined;
  try {
    fh = await fsp.open(file, "r");
    const b = Buffer.alloc(4);
    const r = await fh.read(b, 0, 4, 0);
    return r.bytesRead === 4 && b.toString("latin1") === "GGUF";
  } catch {
    return false;
  } finally {
    await fh?.close();
  }
}

/** Streamed SHA-256 that stops at once on abort. null = aborted or unreadable. */
async function sha256Abortable(file: string, signal: AbortSignal, onBytes: (n: number) => void): Promise<string | null> {
  const h = createHash("sha256");
  const s = fs.createReadStream(file, { highWaterMark: 1 << 20 });
  try {
    for await (const c of s) {
      if (signal.aborted) {
        s.destroy();
        return null;
      }
      h.update(c as Buffer);
      onBytes((c as Buffer).length);
    }
  } catch {
    return null;
  }
  return signal.aborted ? null : h.digest("hex");
}

export type ScanOptions = {
  roots: string[];
  catalog: ModelEntry[];
  signal: AbortSignal;
  maxDepth?: number;
  onFolder?: () => void;
  onHash?: (p: { sizeBytes: number; doneBytes: number } | null) => void;
};
export type ScanFound = { entry: ModelEntry; file: string };

/** Walks the roots (depth limit, symlink loops skipped by real path) and returns the exact SHA-256 matches plus a count of other model files. */
export async function scanForModels(o: ScanOptions): Promise<{ matches: ScanFound[]; others: number }> {
  const maxDepth = o.maxDepth ?? MAX_DEPTH;
  const bySize = new Map<number, ModelEntry[]>();
  for (const m of o.catalog) bySize.set(m.sizeBytes, [...(bySize.get(m.sizeBytes) ?? []), m]);
  const seenDirs = new Set<string>();
  const seenFiles = new Set<string>();
  const matches: ScanFound[] = [];
  let others = 0;

  async function onFile(file: string, size: number): Promise<void> {
    const gguf = isGgufName(file);
    if (!gguf && !isOllamaBlob(file)) return;
    const real = await fsp.realpath(file).catch(() => file);
    if (seenFiles.has(real)) return; // the same file reached through a link or an overlapping root
    seenFiles.add(real);
    const sized = bySize.get(size);
    if (!sized) {
      if (gguf || (await hasGgufMagic(file))) others++;
      return;
    }
    let done = 0;
    o.onHash?.({ sizeBytes: size, doneBytes: 0 });
    const hash = await sha256Abortable(file, o.signal, (n) => o.onHash?.({ sizeBytes: size, doneBytes: (done += n) }));
    o.onHash?.(null);
    if (hash === null) return; // cancelled, or the file could not be read
    const hit = sized.find((m) => m.sha256 === hash);
    if (hit) matches.push({ entry: hit, file });
    else others++; // right size, wrong content
  }

  async function walk(dir: string, depth: number): Promise<void> {
    if (o.signal.aborted) return;
    let names: fs.Dirent[];
    try {
      names = await fsp.readdir(dir, { withFileTypes: true });
    } catch {
      return; // unreadable or missing: skipped
    }
    o.onFolder?.();
    for (const e of names) {
      if (o.signal.aborted) return;
      const p = path.join(dir, e.name);
      const st = await fsp.stat(p).catch(() => null); // follows links; a broken link is skipped
      if (!st) continue;
      if (st.isDirectory()) {
        if (depth >= maxDepth) continue;
        const real = await fsp.realpath(p).catch(() => null);
        if (!real || seenDirs.has(real)) continue; // a link back up the tree
        seenDirs.add(real);
        await walk(p, depth + 1);
      } else if (st.isFile()) await onFile(p, st.size);
    }
  }

  for (const r of o.roots) {
    const real = await fsp.realpath(r).catch(() => null);
    if (!real || seenDirs.has(real)) continue;
    seenDirs.add(real);
    await walk(r, 1);
  }
  return { matches, others };
}

/** Free bytes on the disk that holds `dir` (or its nearest existing parent). null when it cannot be read. */
export function freeBytes(dir: string): number | null {
  let d = path.resolve(dir);
  while (!fs.existsSync(d) && path.dirname(d) !== d) d = path.dirname(d);
  try {
    const s = fs.statfsSync(d);
    return Number(s.bavail) * Number(s.bsize);
  } catch {
    return null;
  }
}

export type ScanLog = (event: string, data: Record<string, number>) => void;

/** One scan at a time, its result kept in memory only. The renderer sees match indexes, never paths. */
export function createScanner(o: { catalog: ModelEntry[]; modelsDir: () => string; log?: ScanLog }) {
  const log: ScanLog = o.log ?? ((e, d) => console.log(`scan: ${e}`, JSON.stringify(d)));
  const idle: ScanState = { phase: "idle", folders: 0, hashing: null, matches: [], others: 0, freeBytes: null };
  let state: ScanState = idle;
  let files: string[] = [];
  let ctl: AbortController | null = null;

  return {
    /** Starts a scan of these roots. Returns at once; poll status(). A scan already running throws. */
    start(roots: string[]): void {
      if (state.phase === "scanning") throw new Error("scan_busy");
      const c = (ctl = new AbortController());
      state = { ...idle, phase: "scanning" };
      files = [];
      const t0 = Date.now();
      log("scan_start", { roots: roots.length });
      void scanForModels({
        roots,
        catalog: o.catalog,
        signal: c.signal,
        onFolder: () => void (state = { ...state, folders: state.folders + 1 }),
        onHash: (h) => void (state = { ...state, hashing: h }),
      }).then(
        (r) => {
          files = r.matches.map((m) => m.file);
          const matches = r.matches.map((m, index) => ({ index, id: m.entry.id, name: m.entry.name, sizeBytes: m.entry.sizeBytes, folder: path.dirname(m.file) }));
          state = { ...state, phase: c.signal.aborted ? "cancelled" : "done", hashing: null, matches: c.signal.aborted ? [] : matches, others: r.others, freeBytes: freeBytes(o.modelsDir()) };
          if (c.signal.aborted) files = [];
          log(c.signal.aborted ? "scan_cancelled" : "scan_done", { matches: state.matches.length, others: r.others, folders: state.folders, ms: Date.now() - t0 });
        },
        () => {
          state = { ...state, phase: "done", hashing: null };
          log("scan_failed", { ms: Date.now() - t0 });
        },
      );
    },
    status: (): ScanState => ({ ...state, freeBytes: state.freeBytes }),
    cancel: (): void => ctl?.abort(),
    /** The file behind a match index, for main only. */
    fileOf: (index: unknown): string | null => (Number.isInteger(index) ? (files[index as number] ?? null) : null),
  };
}

/** importFile (download.ts) only takes a name ending in .gguf. An Ollama blob has none, so give it a temporary link with one. */
export async function importAsGguf(file: string, tmpDir: string, importFile: (f: string) => Promise<ImportResult>): Promise<UseResult> {
  if (!fs.existsSync(file)) return { ok: false, reason: "gone" };
  if (isGgufName(file)) return importFile(file);
  const link = path.join(tmpDir, `blob-${process.pid}-${Date.now()}.gguf`);
  try {
    fs.mkdirSync(tmpDir, { recursive: true });
    try {
      fs.symlinkSync(file, link);
    } catch {
      fs.linkSync(file, link); // symlinks need a privilege on Windows; a hard link needs the same disk
    }
  } catch {
    return { ok: false, reason: "disk" };
  }
  try {
    return await importFile(link);
  } finally {
    fs.rmSync(link, { force: true });
  }
}
