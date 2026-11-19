import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { enLine, idsOf, MT_LABEL, NUMBERS_NOTE, PROTECTED_NOTE, progressNote, unavailableText, working, type TrState } from "../src/translate.ts";
import type { Field, Fixture } from "../src/types.ts";

const field = (over: Partial<Field>): Field => ({ field: "eligibility", status: "present", value_en: null, value_ja: null, items: [], citations: [], checks: [], ...over });

test("every English line carries the Machine translation label", () => {
  assert.equal(enLine({ en: "Bid bond is waived.", numbers_match: true })?.label, MT_LABEL);
  assert.equal(enLine({ en: "x", numbers_match: false })?.label, MT_LABEL);
  assert.equal(enLine(undefined), null); // nothing asked yet: no English line at all
});

test("a failed numbers check adds the note and keeps the translation", () => {
  assert.deepEqual(enLine({ en: "Deadline: Oct 16", numbers_match: false }), { text: "Deadline: Oct 16", label: MT_LABEL, note: NUMBERS_NOTE });
  assert.equal(enLine({ en: "Deadline: Oct 15", numbers_match: true })?.note, null);
});

test("a lost protected name or term adds its own note, next to the numbers note if both apply", () => {
  assert.equal(enLine({ en: "x", numbers_match: true, protected_lost: true })?.note, PROTECTED_NOTE);
  assert.equal(enLine({ en: "x", numbers_match: false, protected_lost: true })?.note, `${NUMBERS_NOTE}; ${PROTECTED_NOTE}`);
  assert.equal(enLine({ en: "x", numbers_match: true, protected_lost: false })?.note, null);
  assert.equal(enLine({ en: "x", numbers_match: true, protected_lost: true })?.text, "x"); // the English is never changed
});

test("no model: the detail view says Model not set up", () => {
  assert.equal(unavailableText("no_model"), "Model not set up");
});

test("ids to translate: cited sentences the document has, once each", () => {
  const fx = { sentences: { a: {}, b: {}, c: {} } } as unknown as Fixture;
  const f = field({ citations: ["a", "b", "zz"], items: [{ text_ja: null, text_en: null, citations: ["b", "c"] }] });
  assert.deepEqual(idsOf(f, fx), ["a", "b", "c"]);
});

test("English is drawn in one component, which always prints the label; Workspace has no English line of its own", () => {
  const machine = readFileSync(new URL("../src/MachineEn.tsx", import.meta.url), "utf8");
  assert.match(machine, /MT_LABEL/);
  for (const name of ["Workspace.tsx", "SummaryPanel.tsx"]) {
    assert.doesNotMatch(readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8"), /className="en"/, name);
  }
});

test("the Workspace asks the queue on mount and when a field opens, and never waits for it", () => {
  const w = readFileSync(new URL("../src/Workspace.tsx", import.meta.url), "utf8");
  assert.equal((w.match(/window\.shiori\.translate\(/g) ?? []).length, 1); // one call site: the helper `ask`
  assert.match(w, /useState<TrState>\(\{ status: "loading" \}\)/); // renders at once, English fills in later
  assert.equal((w.match(/ask\(idsOf\(f, fx\)\)/g) ?? []).length, 1); // the field's ids go to the front, from the open branch only
  assert.match(w, /if \(!working\(tr\)\) return;\n\s+const t = setTimeout\(.*1500\)/); // polls while the queue works, then stops (also after a retry restarts it)
});

test("progress note: counts while the queue works, nothing when it is empty", () => {
  const ok = (done: number, total: number, failed: string[] = []): TrState => ({ status: "ok", items: {}, done, total, failed });
  assert.equal(progressNote(ok(14, 41)), "English: 14 of 41 sentences");
  assert.equal(progressNote(ok(41, 41)), null);
  assert.equal(progressNote(ok(0, 0)), null);
  assert.equal(progressNote(ok(40, 41, ["p1_s1"])), "1 could not be translated"); // empty, but one failed
  assert.equal(progressNote(ok(30, 41, ["p1_s1"])), "English: 30 of 41 sentences"); // still working
  assert.equal(progressNote({ status: "unavailable", reason: "no_model" }), null); // no model: no note, nothing queued
  assert.equal(progressNote({ status: "loading" }), null);
  assert.equal(working(ok(14, 41)), true);
  assert.equal(working(ok(41, 41)), false);
  assert.equal(working({ status: "unavailable", reason: "no_model" }), false);
});
