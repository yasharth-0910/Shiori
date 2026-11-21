// Run: npm test. Summary lines are fixed templates over Verified fields only (D-77).
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { stateOf } from "../src/status.ts";
import { bidDeadline, buildSummary, daysLeft, formatWhen } from "../src/summary.ts";

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

const dl = (kind: string, datetime: string | null, citations = ["p5_s3"]) => ({ text_ja: null, text_en: null, citations, kind, datetime });

test("formatWhen: date and 24h time as stored, date-only has no time", () => {
  assert.equal(formatWhen("2026-10-16T17:00:00+09:00"), "16 Oct 2026, 17:00");
  assert.equal(formatWhen("2026-01-05"), "5 Jan 2026");
  assert.equal(formatWhen("not a date"), null);
});

test("deadline line templates, one per kind", () => {
  const w = "2026-10-16T17:00:00+09:00";
  const got = Object.fromEntries(
    ["bid_in_person", "mail_arrival", "electronic", "bid_opening", "question", "briefing", "document_request", "application", "other"].map((k) => [
      k, texts(run([field("deadlines", { items: [dl(k, w)] })]))[0],
    ]),
  );
  assert.deepEqual(got, {
    bid_in_person: "Bids due 16 Oct 2026, 17:00 (in person).",
    mail_arrival: "Bids due 16 Oct 2026, 17:00 (by mail).",
    electronic: "Bids due 16 Oct 2026, 17:00 (electronic).",
    bid_opening: "Bid opening 16 Oct 2026, 17:00.",
    question: "Questions due 16 Oct 2026, 17:00.",
    briefing: "Briefing 16 Oct 2026, 17:00.",
    document_request: "Document requests due 16 Oct 2026, 17:00.",
    application: "Applications due 16 Oct 2026, 17:00.",
    other: "Other deadline 16 Oct 2026, 17:00.",
  });
});

test("deadlines: one line per item, page from the item's own citation, no datetime gives no line", () => {
  const items = [dl("electronic", "2026-10-16T17:00:00+09:00"), dl("question", "2026-10-01", []), dl("document_request", null)];
  const r = run([field("deadlines", { items })]);
  assert.deepEqual(texts(r), ["Bids due 16 Oct 2026, 17:00 (electronic).", "Questions due 1 Oct 2026."]);
  assert.deepEqual(r.lines.map((l) => l.page), [5, 4]); // second item falls back to the field's citation
});

test("eligibility: Must for requirements, Cannot bid if for disqualifications, neutral when polarity is missing", () => {
  const item = (polarity: string | undefined, en: string) => ({ text_ja: "a", text_en: en, citations: ["p1_s1"], polarity });
  const items = [item("requirement", "Graded A."), item("disqualification", "Persons under suspension."), item(undefined, "Other")];
  assert.deepEqual(texts(run([field("eligibility", { items })])), [
    "Must: Graded A.", "Cannot bid if: Persons under suspension.", "Eligibility item: Other.",
  ]);
});

test("daysLeft with a fixed today", () => {
  const today = new Date(2026, 9, 10, 23, 59); // 10 Oct 2026, late evening: the time of day does not matter
  assert.deepEqual(["2026-10-10", "2026-10-11", "2026-10-16", "2026-10-09"].map((d) => daysLeft(d, today)), [0, 1, 6, -1]);
});

test("bidDeadline: earliest upcoming bid kind, Verified only, past-only gives the latest as closed", () => {
  const today = new Date(2026, 9, 10);
  const mk = (items: ReturnType<typeof dl>[], over: object = {}) => ({ doc_id: "d", pdf: "d.pdf", sentences, fields: [field("deadlines", { items, ...over })] });
  const state = (fx: ReturnType<typeof mk>) => (f: Parameters<typeof stateOf>[0]) => stateOf(f, fx.sentences);
  const items = [
    dl("question", "2026-10-11T10:00:00+09:00"), // not a bid kind
    dl("electronic", "2026-10-02T17:00:00+09:00"), // past
    dl("mail_arrival", "2026-10-20T11:00:00+09:00"),
    dl("bid_in_person", "2026-10-16T17:00:00+09:00"),
  ];
  const fx = mk(items);
  assert.deepEqual(bidDeadline(fx, state(fx), today), { when: "16 Oct 2026, 17:00", days: 6 });
  const past = mk(items.slice(1, 2));
  assert.deepEqual(bidDeadline(past, state(past), today), { when: "2 Oct 2026, 17:00", days: -8 });
  const none = mk(items.slice(0, 1));
  assert.equal(bidDeadline(none, state(none), today), null);
  const bad = mk(items, { checks: [{ name: "value_in_citation", passed: false }] });
  assert.equal(bidDeadline(bad, state(bad), today), null);
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

test("Verified field with nothing to build a line from: no line, listed with a note", () => {
  const r = run([field("deadlines", { items: [{ text_ja: null, text_en: null, citations: ["p1_s1"] }] })]);
  assert.equal(r.lines.length, 0);
  assert.equal(r.unused[0]?.note, "Verified, but no line could be built from the stored values");
});

test("wording: no 'tender' or 'dossier' in any template", () => {
  const items = [{ text_ja: "a", text_en: "x", citations: ["p1_s1"], datetime: "2026-10-16", kind: "electronic", polarity: "requirement" as const }];
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
