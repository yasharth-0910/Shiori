// Run: npm test (node strips the types). Imports the pure status rule only.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { docTypeText, stateOf, unusualSection } from "../src/status.ts";

const sentences = { p1_s5: { page: 1, text_orig: "x", section_path: [], section_titles: [], boxes: [] } };
const field = (over: object) => ({
  field: "title",
  status: "present" as const,
  value_en: "T",
  value_ja: "T",
  items: [],
  citations: ["p1_s5"],
  checks: [
    { name: "schema_valid", passed: true },
    { name: "value_in_citation", passed: true },
  ],
  ...over,
});

test("all stored checks passed and cited id present: verified", () => {
  assert.equal(stateOf(field({}), sentences), "verified");
});

test("hand-altered row: value_in_citation failed -> needs review", () => {
  const f = field({
    checks: [
      { name: "schema_valid", passed: true },
      { name: "value_in_citation", passed: false },
    ],
  });
  assert.equal(stateOf(f, sentences), "needs_review");
});

test("only heading_cue fails: needs review (D-76), note still available", () => {
  const f = field({
    checks: [
      { name: "schema_valid", passed: true },
      { name: "value_in_citation", passed: true },
      { name: "heading_cue", passed: false },
    ],
  });
  assert.equal(stateOf(f, sentences), "needs_review");
  assert.equal(unusualSection(f), true);
  assert.equal(unusualSection(field({})), false);
});

test("only a failed non-gating check (field_applicable) does not block either", () => {
  const f = field({ checks: [{ name: "value_in_citation", passed: true }, { name: "field_applicable", passed: false }] });
  assert.equal(stateOf(f, sentences), "verified");
});

test("only soft checks stored: not verified", () => {
  assert.equal(stateOf(field({ checks: [{ name: "heading_cue", passed: true }] }), sentences), "needs_review");
});

test("cited id missing from the fixture -> not verified", () => {
  assert.equal(stateOf(field({ citations: ["p9_s9"] }), sentences), "needs_review");
  const item = { text_ja: "a", text_en: "b", citations: ["p9_s9"] };
  assert.equal(stateOf(field({ items: [item] }), sentences), "needs_review");
});

test("no stored checks -> not verified", () => {
  assert.equal(stateOf(field({ checks: [] }), sentences), "needs_review");
});

test("absent and see_other_document keep their own states", () => {
  assert.equal(stateOf(field({ status: "absent", citations: [] }), sentences), "not_found");
  assert.equal(stateOf(field({ status: "see_other_document" }), sentences), "other_document");
});

// Procurement type in the dev fixture: Section 2 sentence plus a Section 8 sentence, heading_cue false.
test("procurement type shape (p1_s13 + p4_s19, heading_cue false): needs review, note kept", () => {
  const two = {
    p1_s13: sentences.p1_s5,
    p4_s19: sentences.p1_s5,
  };
  const f = field({
    field: "procurement_type",
    citations: ["p1_s13", "p4_s19"],
    checks: [
      { name: "schema_valid", passed: true },
      { name: "citations_exist", passed: true },
      { name: "value_in_citation", passed: true },
      { name: "values_roundtrip", passed: true },
      { name: "heading_cue", passed: false },
    ],
  });
  assert.equal(stateOf(f, two), "needs_review");
  assert.equal(unusualSection(f), true);
});

// The fixture is gitignored (it holds document text), so this runs only where it exists.
test("real fixture: procurement_type is needs review", { skip: !existsSync("public/fixture.json") }, () => {
  const fx = JSON.parse(readFileSync("public/fixture.json", "utf8"));
  const f = fx.fields.find((x: { field: string }) => x.field === "procurement_type");
  assert.equal(stateOf(f, fx.sentences), "needs_review");
  assert.equal(unusualSection(f), true);
});

test("docTypeText gives plain words for the three detected types and passes an unknown one through", () => {
  assert.equal(docTypeText("notice"), "Notice");
  assert.equal(docTypeText("bid_instructions"), "Bid instructions");
  assert.equal(docTypeText("spec"), "Specification");
  assert.equal(docTypeText("tender_page"), "tender_page");
});
