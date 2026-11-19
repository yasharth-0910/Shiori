import type { Fixture } from "./types";

export type Translated =
  | { ok: true; items: Record<string, { en: string; numbers_match: boolean; protected_lost?: boolean }> }
  | { ok: false; reason: "no_model" | "no_document" | "failed" };

export type Status = { doc_id: string; stage: string; pages: number | null; detail: string | null; error: string | null };

// The four functions preload.ts exposes. Nothing else crosses the bridge.
declare global {
  interface Window {
    shiori?: {
      startProcessing(): Promise<{ doc_id: string; name: string } | null>;
      getStatus(docId: string): Promise<Status>;
      getFields(docId: string): Promise<Fixture>;
      translate(docId: string, ids: string[]): Promise<Translated>;
    };
  }
}
