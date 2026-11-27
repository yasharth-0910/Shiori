// Pure helpers for the first-run onboarding (D-115). No React, so node --test can run them.
import type { ModelList } from "./shiori.d.ts";

export type Stage = "intro" | "find" | "ready" | "models";

// The README footnote, word for word, without its pointer to docs/decisions.md (the installed app has no docs folder).
// test/onboarding.test.ts checks this still matches the README.
export const PRIVACY_TEXT =
  "Privacy in Shiori means this: the app reads and processes your documents only on your own computer, runs its language model locally, makes no network requests while you work, and sends no telemetry. The only network use is downloading a model, which you start yourself and which sends none of your documents. This describes the shipped app, not how it was built: during development, some public tender documents, including some whose sites reserve rights, were sent to cloud AI services to prepare reference labels. The app does not call any cloud service.";

/** Onboarding opens by itself only when no model is installed (and not in the dev-check mode that skips the picker). */
export const showOnboarding = (l: ModelList): boolean => !l.skipPicker && !l.models.some((m) => m.installed);

const gb = (bytes: number) => `${(bytes / 1e9).toFixed(2)} GB`;

/** The line shown before "Use this one" copies a file: how big it is and how much room is left. */
export function copyNotice(sizeBytes: number, freeBytes: number | null): { text: string; enough: boolean } {
  const copy = `This copies the model (${gb(sizeBytes)}) into Shiori's models folder.`;
  if (freeBytes === null) return { text: `${copy} Shiori could not read the free disk space.`, enough: true };
  if (freeBytes < sizeBytes) return { text: `${copy} Free space there: ${gb(freeBytes)}. That is not enough.`, enough: false };
  return { text: `${copy} Free space there: ${gb(freeBytes)}.`, enough: true };
}

export const othersText = (n: number): string => (n <= 0 ? "" : `${n} other model ${n === 1 ? "file was" : "files were"} found that this version does not support.`);
