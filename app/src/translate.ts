// English for cited sentences (D-85), translated in the background by the sidecar (D-88). Pure logic.
import type { Field, Fixture } from "./types";

export const MT_LABEL = "Machine translation";
export const NUMBERS_NOTE = "numbers differ, check the Japanese";
export const PROTECTED_NOTE = "a name or term was changed, check the Japanese"; // a masked span did not come back (D-87)

export type Tr = { en: string; numbers_match: boolean; protected_lost?: boolean };
export type Reason = "no_model" | "no_document" | "failed";
export type Queue = { done: number; total: number; failed: string[] };
export type TrState = { status: "loading" } | ({ status: "ok"; items: Record<string, Tr> } & Queue) | { status: "unavailable"; reason: Reason };

/** "English: 14 of 41 sentences" while the queue has work; "1 could not be translated" once it is empty and one failed; otherwise nothing. */
export function progressNote(t: TrState): string | null {
  if (t.status !== "ok" || t.total === 0) return null;
  const left = t.total - t.done - t.failed.length;
  if (left > 0) return `English: ${t.done} of ${t.total} sentences`;
  return t.failed.length ? `${t.failed.length} could not be translated` : null;
}

/** Is the queue still working? Polling goes on while it is. */
export const working = (t: TrState): boolean => t.status === "ok" && t.total - t.done - t.failed.length > 0;

/** What to show above one Japanese sentence: the English, its fixed label, and a note when the numbers check failed. */
export function enLine(tr: Tr | undefined): { text: string; label: string; note: string | null } | null {
  if (!tr) return null;
  const notes = [tr.numbers_match ? null : NUMBERS_NOTE, tr.protected_lost ? PROTECTED_NOTE : null].filter((n) => n !== null);
  return { text: tr.en, label: MT_LABEL, note: notes.length ? notes.join("; ") : null };
}

export function unavailableText(reason: Reason): string {
  if (reason === "no_model") return "Model not set up";
  if (reason === "no_document") return "Translation is not available for this document.";
  return "Translation failed. The Japanese sentences are shown as they are.";
}

/** The cited sentences of a field that this document has, once each, in order. */
export function idsOf(f: Field, fx: Fixture): string[] {
  const own = [...new Set([...f.citations, ...f.items.flatMap((i) => i.citations)])].filter((id) => id in fx.sentences);
  return f.field === "title" && f.value_ja ? ["value:title", ...own] : own; // the title's value is queued like a sentence (D-91)
}
