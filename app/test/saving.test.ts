// Run: npm test. The screens' saving rules (D-123): the question line for each answer and store state, the notices,
// the settings state, and which rows count as saved.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  afterYes, askAfterFinish, askAtStartup, emptyText, LOCKED_NOTE, markFailed, MEMORY_ONLY, NO_DOCUMENTS, removedIds, savedIds, SAVING_OFF, settingsState,
  showQuestion, storeNotes, UPDATE_NOTE, withDemo, withFinished, withoutDocs, withRows, type Doc,
} from "../src/saving.ts";
import type { StorageInfo } from "../src/shiori.d.ts";

const MESSAGE = "Saving is not available on this computer: no system keyring was found.";
// `files` follows the counts unless a test sets it.
const info = (over: Partial<StorageInfo> = {}): StorageInfo => {
  const i = { keep: null, state: "ok" as const, saved: 0, unreadable: 0, message: null, ...over };
  return { files: i.saved + i.unreadable > 0, ...i };
};
const unanswered = info();
const yes = info({ keep: true, saved: 2 });
const no = info({ keep: false });
const noKeyring = info({ state: "no_keyring", message: MESSAGE });
const noFolder = info({ state: "no_local_folder", message: "Saving is not available on this computer: Windows did not give a local app data folder (LOCALAPPDATA)." });
const locked = info({ keep: true, state: "locked", unreadable: 1 });

test("the question line: only after a finished document, with no answer, while saving works", () => {
  assert.equal(showQuestion(true, unanswered), true);
  assert.equal(showQuestion(false, unanswered), false); // nothing finished
  assert.equal(showQuestion(true, null), false); // getStorage not asked yet
  for (const i of [yes, no, noKeyring, noFolder, locked, info({ state: "locked" })]) assert.equal(showQuestion(true, i), false, `${i.keep} ${i.state}`);
});

test("getStorage is asked after a finished document unless the answer is known to be No", () => {
  assert.deepEqual([null, unanswered, yes, locked, no].map(askAfterFinish), [true, true, true, true, false]);
});

test("startup asks getStorage only when a saved folder exists, listed or locked", () => {
  assert.equal(askAtStartup({ folders: 0 }), false); // nothing saved, or only a leftover master.key: no keyring prompt
  assert.equal(askAtStartup({ folders: 2 }), true);
  const lockedList = { documents: [], folders: 1, files: true };
  assert.equal(askAtStartup(lockedList), true);
  assert.deepEqual(storeNotes(locked), [LOCKED_NOTE]); // what that call then shows
});

test("empty Library text and notices, for each answer and store state", () => {
  assert.deepEqual([null, unanswered, no, yes, noKeyring, noFolder, locked].map(emptyText),
    [NO_DOCUMENTS, SAVING_OFF, SAVING_OFF, NO_DOCUMENTS, MEMORY_ONLY, MEMORY_ONLY, MEMORY_ONLY]);
  assert.equal(SAVING_OFF, "Documents are kept only while the app is open. You can turn on saving in Settings.");
  for (const i of [null, unanswered, yes, no]) assert.deepEqual(storeNotes(i), []);
  assert.deepEqual(storeNotes(noKeyring), [MESSAGE]); // main's sentence, word for word
  assert.deepEqual(storeNotes(noFolder), [noFolder.message]);
  assert.deepEqual(storeNotes(locked), [LOCKED_NOTE]);
  assert.deepEqual(storeNotes(info({ keep: true, unreadable: 1 })), ['1 saved document could not be opened. Only "Delete all saved documents" in Settings removes it.']);
});

test("settings: unanswered, yes and no", () => {
  assert.deepEqual(settingsState(unanswered), { checked: false, switchDisabled: false, count: "Saved documents: 0", deleteDisabled: true, notes: [] });
  assert.deepEqual(settingsState(yes), { checked: true, switchDisabled: false, count: "Saved documents: 2", deleteDisabled: false, notes: [] });
  // off deletes nothing: the count and the delete button stay
  assert.deepEqual(settingsState(info({ keep: false, saved: 1 })), { checked: false, switchDisabled: false, count: "Saved documents: 1", deleteDisabled: false, notes: [] });
  assert.equal(settingsState(info({ keep: true, unreadable: 1 })).deleteDisabled, false);
});

test("settings: not available and locked", () => {
  assert.deepEqual(settingsState(noKeyring), { checked: false, switchDisabled: true, count: null, deleteDisabled: true, notes: [MESSAGE] });
  const earlier = settingsState(info({ keep: true, state: "no_keyring", unreadable: 3, message: MESSAGE }));
  assert.deepEqual(earlier, { checked: true, switchDisabled: true, count: "Saved documents on disk that cannot be opened: 3", deleteDisabled: false, notes: [MESSAGE] });
  assert.deepEqual([settingsState(noFolder).switchDisabled, settingsState(noFolder).deleteDisabled, settingsState(noFolder).count], [true, true, null]);
  // locked: the saved answer is yes, but the switch never shows "on" under "saving is off"
  assert.deepEqual(settingsState(locked), { checked: false, switchDisabled: true, count: "Saved documents on disk that cannot be opened: 1", deleteDisabled: false, notes: [LOCKED_NOTE] });
  assert.equal(settingsState(info({ state: "locked" })).deleteDisabled, false); // enabled even with both counts 0
  assert.deepEqual(settingsState(null), { checked: false, switchDisabled: true, count: null, deleteDisabled: true, notes: [] });
});

test("settings: delete all is enabled whenever a store file exists, or the store could not be read", () => {
  const leftover = info({ keep: true, files: true }); // only master.key: both counts are 0
  assert.equal(settingsState(leftover).deleteDisabled, false);
  assert.equal(settingsState(info({ state: "no_keyring", files: true, message: MESSAGE })).deleteDisabled, false);
  assert.equal(settingsState(info({ keep: true })).deleteDisabled, true); // no file at all
  assert.equal(settingsState(null, true).deleteDisabled, false); // getStorage failed on the first ask
  assert.equal(settingsState(info(), true).deleteDisabled, false); // or after an earlier answer
});

const row = (doc_id: string, over: Partial<Doc> = {}, fx: Partial<Doc["fx"]> = {}): Doc => ({
  fx: { doc_id, pdf: `doc/${doc_id}.pdf`, fields: [], sentences: {}, model_id: "m1", ...fx },
  counts: { verified: 0, needs_review: 0, not_found: 0, other_document: 0 },
  ...over,
});
const brief = (all: Doc[]) => all.map((d) => `${d.fx.doc_id}:${d.fx.model_id ?? "none"}${d.saved ? " saved" : ""}${d.notSaved ? " failed" : ""}`);

test("rows: saved ones load beside the session's; the demo goes first, replaces nothing and is never saved", () => {
  const saved = row("a", { saved: true });
  const demo = row("demo", {}, { model_id: undefined });
  assert.deepEqual(brief(withDemo(withRows([], [saved]), demo)), ["demo:none", "a:m1 saved"]);
  assert.deepEqual(brief(withRows(withDemo([], demo), [saved])), ["demo:none", "a:m1 saved"]);
  const same = row("demo", { saved: true }, { model_id: null });
  assert.deepEqual(withDemo([same], demo), [same]);
  assert.deepEqual(savedIds(withRows([demo], [saved, row("a", { saved: true }, { model_id: "m2" }), row("b")])), ["a"]);
});

test("rows: a finished result, and when it is marked not saved", () => {
  const ok = withFinished([], row("a", {}, { saved: true }));
  assert.deepEqual(brief(ok), ["a:m1 saved"]);
  assert.equal(ok[0]?.session, true);
  assert.deepEqual(brief(markFailed(ok, ok[0]!.fx, yes)), ["a:m1 saved"]);
  const failed = row("b", {}, { saved: false });
  const all = withFinished(ok, failed);
  assert.deepEqual(brief(markFailed(all, failed.fx, yes)), ["a:m1 saved", "b:m1 failed"]);
  assert.deepEqual(brief(markFailed(all, failed.fx, locked)), ["a:m1 saved", "b:m1 failed"]);
  for (const i of [unanswered, no, info({ keep: true, state: "no_keyring" }), noFolder]) assert.equal(markFailed(all, failed.fx, i), all, `${i.keep} ${i.state}`);
  // run again and this save fails: the earlier copy is still there
  assert.deepEqual(brief(markFailed(withFinished(ok, row("a", {}, { saved: false })), { ...ok[0]!.fx, saved: false }, yes)), ["a:m1 saved failed"]);
});

test("rows after Yes: the first one saves this session's results, a later one saves nothing earlier", () => {
  const demo = row("demo", {}, { model_id: undefined });
  const all = withFinished(withFinished([demo], row("a")), row("b"));
  const listed = [row("a").fx];
  assert.deepEqual(brief(afterYes(all, listed, true)), ["demo:none", "a:m1 saved", "b:m1 failed"]);
  assert.deepEqual(brief(afterYes(all, listed, false)), ["demo:none", "a:m1 saved", "b:m1"]);
});

test("after a delete all that stopped part way, only the documents that are gone leave the screen", () => {
  const all = [row("a", { saved: true }), row("a", {}, { model_id: "m2" }), row("b", { saved: true }), row("c")];
  const left = { documents: [row("b").fx], folders: 1, files: true };
  assert.deepEqual(removedIds(all, left, yes), ["a"]); // not b, which stayed, nor c, which was never saved
  const nothing = { documents: [], folders: 0, files: true }; // only master.key stayed
  assert.deepEqual(removedIds(all, nothing, null), ["a", "b"]);
  const hidden = { documents: [], folders: 1, files: true };
  for (const i of [null, locked, noKeyring]) assert.deepEqual(removedIds(all, hidden, i), [], i?.state);
  assert.deepEqual(removedIds(all, hidden, yes), ["a", "b"]); // the folder left lost its key
});

test("delete takes every model's row of that document", () => {
  const all = [row("a", { saved: true }), row("a", {}, { model_id: "m2" }), row("b", { saved: true })];
  assert.deepEqual(brief(withoutDocs(all, ["a"])), ["b:m1 saved"]);
});

test("the update sentence is still a placeholder", () => assert.equal(UPDATE_NOTE, "TODO after the Keychain gate"));
