// Run: npm test (node strips the types). Imports the pure status rule only.
import assert from "node:assert/strict";
import { test } from "node:test";
import { stateOf, unusualSection } from "../src/status.ts";

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

test("only heading_cue fails: still verified, note shown", () => {
  const f = field({
    checks: [
      { name: "schema_valid", passed: true },
      { name: "value_in_citation", passed: true },
      { name: "heading_cue", passed: false },
    ],
  });
  assert.equal(stateOf(f, sentences), "verified");
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
