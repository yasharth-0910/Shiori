// Finds llama-server and the model files on this machine (D-99). Local file checks only. Every
// input (env, paths, exists, the registry) is a parameter so tests use fake paths. Env vars stay overrides.
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { Facts, ModelEntry, Recommendation } from "./registry";

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
