// Types the renderer and main share for the model download (D-100). No imports, like registry.ts, so src/ can use them.
export type Phase = "idle" | "downloading" | "verifying" | "done" | "failed";
export type DownloadError = "offline" | "interrupted" | "http_error" | "hash_mismatch" | "disk";
export type DownloadState = { id: string | null; phase: Phase; received: number; total: number; error: DownloadError | null };
export type ImportResult = { ok: true; id: string } | { ok: false; reason: "not_gguf" | "unknown_file" | "disk" };
