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

/** The llama-server shipped inside the app; null in dev (the PATH search is used there). */
export function bundledLlama(l: Layout): string | null {
  return l.isPackaged ? pathFor(l.platform).join(l.resourcesPath, "llama", exeName("llama-server", l.platform)) : null;
}

/** The folder model files are looked for in: <userData>/models when packaged, <repo>/models in dev. */
export const modelsDir = (l: Layout): string => pathFor(l.platform).join(l.isPackaged ? l.userData : l.repoRoot, "models");
