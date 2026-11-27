import type { ModelEntry, Recommendation } from "../electron/registry";
import type { Fixture } from "./types";
import type { ScanMatch, ScanState, UseResult } from "../electron/scantypes";
import type { DownloadError, DownloadState, ImportResult } from "../electron/downloadtypes";
export type { DownloadError, DownloadState, ImportResult, ScanMatch, ScanState, UseResult };

export type ModelInfo = ModelEntry & { installed: boolean };
export type ModelList = {
  models: ModelInfo[];
  recommended: Recommendation | null;
  default: string | null;
  running: string | null; // the model id the backend is running now
  binaryFound: boolean;
  expected: { file: string; where: string }[];
  skipPicker: boolean; // dev checks only (SHIORI_PICK)
};

export type Translated =
  | { ok: true; items: Record<string, { en: string; numbers_match: boolean; protected_lost?: boolean }>; done: number; total: number; failed: string[] }
  | { ok: false; reason: "no_model" | "no_document" | "failed" };

// A live event from the pipeline (D-90). Text fields are Japanese from the document; they go to the screen only.
export type ProcEvent =
  | { n: number; kind: "reading"; field: string; count: number; sentences: { page: number; section: string; text: string }[] }
  | { n: number; kind: "answer"; field: string; value_ja: string; page: number | null; exact: boolean | null }
  | { n: number; kind: "none"; field: string };

// Everything past `error` is what the sidecar measured or counted; absent while the model loads.
export type Status = {
  doc_id: string;
  stage: string;
  pages: number | null;
  detail: string | null;
  error: string | null;
  model?: string | null; // the model file's name
  model_id?: string | null; // the registry id of the model that answered (D-99)
  seconds?: Record<string, number>; // per finished sidecar stage
  sentences?: number | null;
  fields_total?: number;
  answered?: number;
  doc_type?: string; // notice, bid_instructions or spec (D-92)
  events: ProcEvent[];
  cursor: number;
};

// Saved documents (D-119, D-121). Mirrors StorageInfo in electron/storage.ts. `keep` null: not answered.
export type StorageInfo = {
  keep: boolean | null;
  state: "ok" | "no_keyring" | "no_local_folder" | "locked";
  saved: number; // documents, not Library rows
  unreadable: number;
  files: boolean; // a saved folder or master.key exists
  message: string | null; // "Saving is not available on this computer: <reason>"
};

// Mirrors SavedList in electron/storage.ts. `folders` and `files` need no key.
export type SavedList = { documents: Fixture[]; folders: number; files: boolean };

// The twenty functions preload.ts exposes. Nothing else crosses the bridge.
declare global {
  interface Window {
    shiori?: {
      startProcessing(modelId?: string): Promise<{ doc_id: string; name: string } | { error: "busy" } | null>;
      listModels(): Promise<ModelList>;
      getStatus(docId: string, since?: number): Promise<Status>;
      cancel(docId: string): Promise<void>;
      // `saved`: main wrote this result to the store.
      getFields(docId: string): Promise<Fixture & { saved: boolean }>;
      // `modelId` is the result's model; a saved result with no running job is answered from the store.
      translate(docId: string, ids: string[], modelId?: string | null): Promise<Translated>;
      // Native save dialog (main process); resolves true when a file was written, false when the user cancelled.
      saveExport(kind: "csv" | "ics", name: string, content: string): Promise<boolean>;
      // Opens the .ics saved in this session with the default calendar app; false when none was saved. Takes no path.
      openCalendar(): Promise<boolean>;
      // The only network use in the app (D-100). Takes a registry id, never a URL. Returns at once; poll downloadStatus().
      downloadModel(modelId: string): Promise<void>;
      downloadStatus(): Promise<DownloadState>;
      // Native file dialog in main; null when cancelled. A .gguf is copied in only if its SHA-256 is a registry entry's.
      chooseModelFile(): Promise<ImportResult | null>;
      // Find models on this computer (D-115). Starts only on a click. "folder" opens a native folder dialog in main; false = cancelled.
      scanModels(kind: "computer" | "folder"): Promise<boolean>;
      scanStatus(): Promise<ScanState>;
      scanCancel(): Promise<void>;
      // Registers a match by its index (never a path), through the same import as chooseModelFile: the file is copied in.
      useScanned(index: number): Promise<UseResult>;
      // The saved documents, one entry per document and model (empty when there are none or the store cannot be used),
      // and what is on disk.
      listDocuments(): Promise<SavedList>;
      // Can raise a keyring prompt: call it only at the times storage_design.md lists.
      getStorage(): Promise<StorageInfo>;
      // Records the answer. The first Yes also saves this session's finished documents; the counts are those.
      setKeepDocuments(keep: boolean): Promise<{ saved: number; failed: number }>;
      // main asks in a native dialog; false when cancelled.
      deleteDocument(docId: string): Promise<boolean>;
      deleteAllDocuments(): Promise<boolean>;
    };
  }
}
