import type { Fixture } from "./types";

export type Status = { doc_id: string; stage: string; pages: number | null; error: string | null };

// The three functions preload.ts exposes. Nothing else crosses the bridge.
declare global {
  interface Window {
    shiori?: {
      startProcessing(): Promise<{ doc_id: string; name: string } | null>;
      getStatus(docId: string): Promise<Status>;
      getFields(docId: string): Promise<Fixture>;
    };
  }
}
