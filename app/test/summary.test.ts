// Run: npm test. Summary lines are fixed templates over Verified fields only (D-77).
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { stateOf } from "../src/status.ts";
import { buildSummary } from "../src/summary.ts";

const sentence = (page: number) => ({ page, text_orig: "x", section_path: [], section_titles: [], boxes: [] });
const sentences = { p1_s1: sentence(1), p4_s2: sentence(4), p5_s3: sentence(5) };
const checks = [{ name: "schema_valid", passed: true }, { name: "value_in_citation", passed: true }];
const field = (name: string, over: object = {}) => ({
  field: name, status: "present" as const, value_en: null, value_ja: null, items: [], citations: ["p4_s2"], checks, ...over,
});
const run = (fields: ReturnType<typeof field>[]) => {
  const fx = { doc_id: "d", pdf: "d.pdf", fields, sentences };
  return buildSummary(fx, (f) => stateOf(f, sentences));
};
const texts = (r: ReturnType<typeof run>) => r.lines.map((l) => l.text);

test("issuer template + page chip data", () => {
  const r = run([field("issuer_org", { value_en: "Wakayama Prefecture" })]);
  assert.deepEqual(texts(r), ["Issued by Wakayama Prefecture."]);
  assert.deepEqual([r.lines[0]?.sid, r.lines[0]?.page], ["p4_s2", 4]);
});

test("title template", () => {
  assert.deepEqual(texts(run([field("title", { value_en: "Hidaka Project." })])), ["The RFP is for: Hidaka Project."]);
});

test("procurement type template", () => {
  assert.deepEqual(texts(run([field("procurement_type", { value_en: "proposal competition" })])), ["Procurement type: proposal competition."]);
});

test("deadlines: one line per item, datetime first when stored, page from the item's own citation", () => {
  const items = [
    { text_ja: null, text_en: "Bid opening", citations: ["p5_s3"], datetime: "2026-09-10T13:30" },
    { text_ja: null, text_en: "Questions close", citations: [] },
  ];
  const r = run([field("deadlines", { items })]);
  assert.deepEqual(texts(r), ["Deadline: 2026-09-10T13:30 Bid opening.", "Deadline: Questions close."]);
  assert.deepEqual(r.lines.map((l) => l.page), [5, 4]); // second item falls back to the field's citation
});

test("eligibility: one line per item", () => {
  const items = [1, 2].map((n) => ({ text_ja: "a", text_en: `Condition ${n}`, citations: ["p1_s1"] }));
  assert.deepEqual(texts(run([field("eligibility", { items })])), ["Eligibility item: Condition 1.", "Eligibility item: Condition 2."]);
});

test("award method template", () => {
  assert.deepEqual(texts(run([field("award_method", { value_en: "Lowest price" })])), ["Award method: Lowest price."]);
});

test("how to submit template (from items)", () => {
  const items = [{ text_ja: null, text_en: "By mail", citations: ["p1_s1"] }];
  assert.deepEqual(texts(run([field("submission_modes", { items })])), ["How to submit: By mail."]);
});

test("lines come out in the fixed order whatever the field order", () => {
  const r = run([
    field("award_method", { value_en: "A" }),
    field("issuer_org", { value_en: "B" }),
    field("title", { value_en: "C" }),
  ]);
  assert.deepEqual(r.lines.map((l) => l.key), ["issuer_org:0", "title:0", "award_method:0"]);
});

test("a Needs review field never appears in a line; it is listed instead", () => {
  const bad = field("issuer_org", { value_en: "SECRET-VALUE", checks: [...checks, { name: "heading_cue", passed: false }] });
  const failed = field("award_method", { value_en: "OTHER-VALUE", checks: [{ name: "value_in_citation", passed: false }] });
  const r = run([bad, failed]);
  assert.deepEqual(r.lines, []);
  assert.ok(!JSON.stringify(r.lines).includes("VALUE"));
  assert.deepEqual(r.unused.map((u) => u.field), ["issuer_org", "award_method"]);
});

test("Not found fields are listed, not used", () => {
  const r = run([field("title", { status: "absent", citations: [] })]);
  assert.deepEqual([r.lines.length, r.unused.map((u) => u.field)], [0, ["title"]]);
});

test("Verified field with no English text: no line, listed with a note", () => {
  const r = run([field("deadlines", { items: [{ text_ja: null, text_en: null, citations: ["p1_s1"] }] })]);
  assert.equal(r.lines.length, 0);
  assert.equal(r.unused[0]?.note, "Verified, but no English text stored");
});

test("wording: no 'tender' or 'dossier' in any template", () => {
  const items = [{ text_ja: "a", text_en: "x", citations: ["p1_s1"] }];
  const r = run(["issuer_org", "title", "procurement_type", "award_method"].map((n) => field(n, { value_en: "x" }))
    .concat(["deadlines", "eligibility", "submission_modes"].map((n) => field(n, { items }))));
  assert.equal(r.lines.length, 7);
  assert.ok(!/tender|dossier/i.test(texts(r).join(" ")));
});

test("real fixture: only Verified fields feed lines", { skip: !existsSync("public/fixture.json") }, () => {
  const fx = JSON.parse(readFileSync("public/fixture.json", "utf8"));
  const r = buildSummary(fx, (f) => stateOf(f, fx.sentences));
  for (const l of r.lines) {
    const f = fx.fields.find((x: { field: string }) => x.field === l.key.split(":")[0]);
    assert.equal(stateOf(f, fx.sentences), "verified");
  }
});
