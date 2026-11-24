// Types the renderer and main share for "Find models on this computer" (D-115). No imports, like downloadtypes.ts.
// A match carries a display folder for the screen only. The renderer never sends a path back: it sends the index of a match.
export type ScanMatch = { index: number; id: string; name: string; sizeBytes: number; folder: string };
export type ScanState = {
  phase: "idle" | "scanning" | "done" | "cancelled";
  folders: number; // folders looked into so far
  hashing: { sizeBytes: number; doneBytes: number } | null; // the file being checked right now (size and progress, no name)
  matches: ScanMatch[];
  others: number; // model files found that no catalog entry matches (a count, nothing else)
  freeBytes: number | null; // free space where a copy would go, read when the scan ends
};
export type UseResult = { ok: true; id: string } | { ok: false; reason: "not_gguf" | "unknown_file" | "disk" | "gone" };
