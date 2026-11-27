// A file operation on a path the user chose (docs/privacy.md, "Logging"). Node's error message holds the path, and
// Electron prints an uncaught handler error as it is, so only the error type is logged and thrown on.
// Pure, so a test can drive it.
/** The Node code such as ENOENT, else the error name. Never the message, which can hold a path. */
export const errorType = (e: unknown): string => (e as NodeJS.ErrnoException)?.code ?? (e instanceof Error ? e.name : "unknown");

export function userFile<T>(event: string, op: () => T, log: (line: string) => void = console.error): T {
  try {
    return op();
  } catch (e) {
    const type = errorType(e);
    log(`${event} failed: ${type}`);
    throw new Error(type);
  }
}
