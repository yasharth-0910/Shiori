import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { enLine, idsOf, MT_LABEL, NUMBERS_NOTE, PROTECTED_NOTE, unavailableText } from "../src/translate.ts";
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

test("the field is translated when opened, not before", () => {
  const w = readFileSync(new URL("../src/Workspace.tsx", import.meta.url), "utf8");
  assert.equal((w.match(/window\.shiori\.translate\(/g) ?? []).length, 1);
  assert.match(w, /translateField\(f\);/); // only called from the open branch of toggle
  assert.doesNotMatch(w, /useEffect/); // no effect fetches on mount
});
