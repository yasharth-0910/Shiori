import type { Fixture } from "./types";

export type Translated =
  | { ok: true; items: Record<string, { en: string; numbers_match: boolean; protected_lost?: boolean }>; done: number; total: number; failed: string[] }
  | { ok: false; reason: "no_model" | "no_document" | "failed" };

// A live event from the pipeline (D-90). Text fields are Japanese from the document; they go to the screen only.
export type ProcEvent =
  | { n: number; kind: "candidates"; field: string; count: number; page: number; section: string; text: string }
  | { n: number; kind: "answer"; field: string; value_ja: string; page: number | null }
  | { n: number; kind: "check"; field: string; exact: boolean | null };

// Everything past `error` is what the sidecar measured or counted; absent while the model loads.
export type Status = {
  doc_id: string;
  stage: string;
  pages: number | null;
  detail: string | null;
  error: string | null;
  model?: string | null; // the model file's name
  seconds?: Record<string, number>; // per finished sidecar stage
  sentences?: number | null;
  fields_total?: number;
  answered?: number;
  events: ProcEvent[];
  cursor: number;
};

// The five functions preload.ts exposes. Nothing else crosses the bridge.
declare global {
  interface Window {
    shiori?: {
      startProcessing(): Promise<{ doc_id: string; name: string } | null>;
      getStatus(docId: string, since?: number): Promise<Status>;
      cancel(docId: string): Promise<void>;
      getFields(docId: string): Promise<Fixture>;
      translate(docId: string, ids: string[]): Promise<Translated>;
    };
  }
}
