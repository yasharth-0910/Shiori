// The screens' saving rules (docs/storage_design.md sections 3 and 5, D-119, D-123). Pure, so node --test can run them.
// main enforces what is saved; this only decides what is shown. `info` is null until getStorage has been asked, which
// happens only when something saved exists, a document has finished, or Settings is opened (it can raise a keyring prompt).
import { resultKey } from "./modelinfo.ts";
import type { StorageInfo } from "./shiori.d.ts";
import type { Fixture } from "./types.ts";
import type { State } from "./status.ts";

/** The one sentence about saved documents and app updates. Nothing else in the app says anything about updates. */
export const UPDATE_NOTE = "TODO after the Keychain gate";

export const QUESTION = "Keep documents in your Library between sessions? Encrypted on this computer.";
export const NO_DOCUMENTS = "No documents yet.";
export const MEMORY_ONLY = "Documents are kept only while the app is open.";
export const SAVING_OFF = `${MEMORY_ONLY} You can turn on saving in Settings.`;
export const LOCKED_NOTE = "Saved documents cannot be opened, so saving is off. Nothing was deleted.";

const unavailable = (i: StorageInfo) => i.state === "no_keyring" || i.state === "no_local_folder";
const docs = (n: number) => `${n} saved ${n === 1 ? "document" : "documents"}`;

/** The question line: a document finished in this session, no answer yet, and saving works. */
export const showQuestion = (finished: boolean, info: StorageInfo | null): boolean => finished && info?.keep === null && info.state === "ok";

/** After a finished document getStorage is asked, unless the answer is already known to be No. */
export const askAfterFinish = (info: StorageInfo | null): boolean => info?.keep !== false;

/** What an empty Library says. */
export function emptyText(info: StorageInfo | null): string {
  if (!info) return NO_DOCUMENTS; // not asked yet: say nothing about saving
  if (info.state !== "ok") return MEMORY_ONLY; // the note above says why
  return info.keep ? NO_DOCUMENTS : SAVING_OFF;
}

/** Notices for the Library and Settings. The not-available sentence is main's, word for word. */
export function storeNotes(info: StorageInfo | null): string[] {
  if (!info) return [];
  const out = info.message ? [info.message] : [];
  if (info.state === "locked") out.push(LOCKED_NOTE);
  if (info.state === "ok" && info.unreadable > 0)
    out.push(`${docs(info.unreadable)} could not be opened. Only "Delete all saved documents" in Settings removes ${info.unreadable === 1 ? "it" : "them"}.`);
  return out;
}

export type SettingsState = { checked: boolean; switchDisabled: boolean; count: string | null; deleteDisabled: boolean; notes: string[] };

export function settingsState(info: StorageInfo | null): SettingsState {
  if (!info) return { checked: false, switchDisabled: true, count: null, deleteDisabled: true, notes: [] };
  const held = info.saved + info.unreadable;
  const count = info.state === "ok" ? `Saved documents: ${info.saved}` : held ? `Saved documents on disk that cannot be opened: ${held}` : null;
  return {
    checked: info.keep === true,
    switchDisabled: unavailable(info),
    count,
    // Locked: delete all is the way out, even with nothing countable. No local folder: there is nothing to delete from.
    deleteDisabled: info.state === "locked" ? false : info.state === "no_local_folder" || held === 0,
    notes: storeNotes(info),
  };
}

/** A Library row. `saved`: main holds a saved copy of this document. `notSaved`: saving was on and this result failed.
 * `session`: finished in this session. The fixture demo has none of the three. */
export type Doc = { fx: Fixture; counts: Record<State, number>; saved?: boolean; notSaved?: boolean; session?: boolean };

const keyOf = (d: Doc) => resultKey(d.fx.doc_id, d.fx.model_id);

/** One row per document and model; a newer row replaces the older one and goes last ("Recently added"). */
export function withRows(all: Doc[], rows: Doc[]): Doc[] {
  const keys = new Set(rows.map(keyOf));
  return [...all.filter((d) => !keys.has(keyOf(d))), ...rows];
}

/** The fixture demo goes first and never replaces a row that is already there. */
export const withDemo = (all: Doc[], demo: Doc): Doc[] => (all.some((d) => keyOf(d) === keyOf(demo)) ? all : [demo, ...all]);

/** A finished result. A copy saved earlier under the same key stays saved even if this save failed. */
export function withFinished(all: Doc[], row: Doc): Doc[] {
  const old = all.find((d) => keyOf(d) === keyOf(row));
  return withRows(all, [{ ...row, session: true, saved: !!row.fx.saved || !!old?.saved }]);
}

/** Marks a finished result "not saved" when saving is on and available, and main did not save it. */
export function markFailed(all: Doc[], fx: Fixture, info: StorageInfo): Doc[] {
  if (fx.saved || info.keep !== true || unavailable(info)) return all;
  const key = resultKey(fx.doc_id, fx.model_id);
  return all.map((d) => (keyOf(d) === key ? { ...d, notSaved: true } : d));
}

/** After a switch to Yes: marks the rows the store now lists. `first` (the answer was not given before) means main tried
 * to save every result of this session, so one that is not listed failed. Later a missing one was simply never tried. */
export function afterYes(all: Doc[], listed: Fixture[], first: boolean): Doc[] {
  const keys = new Set(listed.map((f) => resultKey(f.doc_id, f.model_id)));
  return all.map((d) => (keys.has(keyOf(d)) ? { ...d, saved: true, notSaved: false } : first && d.session ? { ...d, notSaved: true } : d));
}

export const savedIds = (all: Doc[]): string[] => [...new Set(all.filter((d) => d.saved).map((d) => d.fx.doc_id))];

/** Delete removes a document with every model's result, as main does. */
export const withoutDocs = (all: Doc[], ids: string[]): Doc[] => all.filter((d) => !ids.includes(d.fx.doc_id));
