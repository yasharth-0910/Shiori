import type { ModelEntry, Recommendation } from "../electron/registry";
import type { Fixture } from "./types";
import type { DownloadError, DownloadState, ImportResult } from "../electron/downloadtypes";
export type { DownloadError, DownloadState, ImportResult };

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

// The eleven functions preload.ts exposes. Nothing else crosses the bridge.
declare global {
  interface Window {
    shiori?: {
      startProcessing(modelId?: string): Promise<{ doc_id: string; name: string } | { error: "busy" } | null>;
      listModels(): Promise<ModelList>;
      getStatus(docId: string, since?: number): Promise<Status>;
      cancel(docId: string): Promise<void>;
      getFields(docId: string): Promise<Fixture>;
      translate(docId: string, ids: string[]): Promise<Translated>;
      // Native save dialog (main process); resolves true when a file was written, false when the user cancelled.
      saveExport(kind: "csv" | "ics", name: string, content: string): Promise<boolean>;
      // Opens the .ics saved in this session with the default calendar app; false when none was saved. Takes no path.
      openCalendar(): Promise<boolean>;
      // The only network use in the app (D-100). Takes a registry id, never a URL. Returns at once; poll downloadStatus().
      downloadModel(modelId: string): Promise<void>;
      downloadStatus(): Promise<DownloadState>;
      // Native file dialog in main; null when cancelled. A .gguf is copied in only if its SHA-256 is a registry entry's.
      chooseModelFile(): Promise<ImportResult | null>;
    };
  }
}
