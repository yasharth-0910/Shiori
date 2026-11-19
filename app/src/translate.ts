// On-demand English for cited sentences (D-85). Pure logic; the sidecar does the work.
import type { Field, Fixture } from "./types";

export const MT_LABEL = "Machine translation";
export const NUMBERS_NOTE = "numbers differ, check the Japanese";

export type Tr = { en: string; numbers_match: boolean };
export type Reason = "no_model" | "no_document" | "failed";
export type TrState = { status: "loading" } | { status: "ok"; items: Record<string, Tr> } | { status: "unavailable"; reason: Reason };

/** What to show above one Japanese sentence: the English, its fixed label, and a note when the numbers check failed. */
export function enLine(tr: Tr | undefined): { text: string; label: string; note: string | null } | null {
  return tr ? { text: tr.en, label: MT_LABEL, note: tr.numbers_match ? null : NUMBERS_NOTE } : null;
}

export function unavailableText(reason: Reason): string {
  if (reason === "no_model") return "Model not set up";
  if (reason === "no_document") return "Translation is not available for this document.";
  return "Translation failed. The Japanese sentences are shown as they are.";
}

/** The cited sentences of a field that this document has, once each, in order. */
export function idsOf(f: Field, fx: Fixture): string[] {
  return [...new Set([...f.citations, ...f.items.flatMap((i) => i.citations)])].filter((id) => id in fx.sentences);
}
