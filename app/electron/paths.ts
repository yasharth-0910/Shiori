// Where the sidecar, llama-server and the model files are, in a dev run and in a packaged app (D-112).
// Pure functions: every input is a parameter, so tests can use mac, win and linux values.
import * as path from "node:path";

export type Layout = {
  isPackaged: boolean;
  platform: string; // process.platform
  resourcesPath: string; // process.resourcesPath, packaged only
  userData: string; // app.getPath("userData")
  repoRoot: string; // dev only
};

const pathFor = (platform: string) => (platform === "win32" ? path.win32 : path.posix);

/** "llama-server" -> "llama-server.exe" on Windows. */
export const exeName = (base: string, platform: string): string => (platform === "win32" ? `${base}.exe` : base);

export type SidecarCommand = { command: string; args: string[]; cwd: string | undefined };

/** Packaged: the frozen sidecar in resources, no uv, no cwd. Dev: `uv run python -m sidecar` from the repo. */
export function sidecarCommand(l: Layout, extra: string[]): SidecarCommand {
  const p = pathFor(l.platform);
  if (l.isPackaged) return { command: p.join(l.resourcesPath, "sidecar", exeName("shiori-sidecar", l.platform)), args: extra, cwd: undefined };
  return { command: "uv", args: ["run", "python", "-m", "sidecar", ...extra], cwd: l.repoRoot };
}

/** The sidecar's environment: a copy without FASTAPI_OTEL_AUTO_CONFIGURE and OTEL_*, so nothing inherited can turn on
 * telemetry. Case is ignored, as Windows ignores it. */
export const sidecarEnv = (env: Record<string, string | undefined>): Record<string, string | undefined> =>
  Object.fromEntries(Object.entries(env).filter(([k]) => !/^(OTEL_|FASTAPI_OTEL_AUTO_CONFIGURE$)/i.test(k)));

/** The llama-server shipped inside the app; null in dev (the PATH search is used there). */
export function bundledLlama(l: Layout): string | null {
  return l.isPackaged ? pathFor(l.platform).join(l.resourcesPath, "llama", exeName("llama-server", l.platform)) : null;
}

/** The folder that holds store/ and settings.json (storage_design.md section 2). Windows: under LOCALAPPDATA, joined
 * with the last part of userData; a missing or relative value (`\dir` and `C:dir` too) gives "no_local_folder", never
 * userData, which roams. Elsewhere: userData. */
export function storageBase(platform: string, env: Record<string, string | undefined>, userData: string): string | "no_local_folder" {
  if (platform !== "win32") return userData;
  const local = env.LOCALAPPDATA;
  if (!local || !path.win32.isAbsolute(local) || path.win32.parse(local).root.length < 2) return "no_local_folder";
  return path.win32.join(local, path.win32.basename(userData));
}

/** The folder model files are looked for in: <userData>/models when packaged, <repo>/models in dev. */
export const modelsDir = (l: Layout): string => pathFor(l.platform).join(l.isPackaged ? l.userData : l.repoRoot, "models");
