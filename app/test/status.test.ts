// Run: npm test (node strips the types). Imports the pure status rule only.
import assert from "node:assert/strict";
import { test } from "node:test";
import { stateOf } from "../src/status.ts";

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

test("hand-altered row: value_in_citation failed -> found, not verified", () => {
  const f = field({
    checks: [
      { name: "schema_valid", passed: true },
      { name: "value_in_citation", passed: false },
    ],
  });
  assert.equal(stateOf(f, sentences), "unverified");
});

test("cited id missing from the fixture -> not verified", () => {
  assert.equal(stateOf(field({ citations: ["p9_s9"] }), sentences), "unverified");
  const item = { text_ja: "a", text_en: "b", citations: ["p9_s9"] };
  assert.equal(stateOf(field({ items: [item] }), sentences), "unverified");
});

test("no stored checks -> not verified", () => {
  assert.equal(stateOf(field({ checks: [] }), sentences), "unverified");
});

test("absent and see_other_document keep their own states", () => {
  assert.equal(stateOf(field({ status: "absent", citations: [] }), sentences), "not_found");
  assert.equal(stateOf(field({ status: "see_other_document" }), sentences), "other_document");
});
