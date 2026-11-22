// Run: npm test. Deadlines tab logic: sorting, kind labels, the empty state, the cited sentence a click opens.
import assert from "node:assert/strict";
import { test } from "node:test";
import { stateOf } from "../src/status.ts";
import { formatWhen } from "../src/summary.ts";
import { valueFirst } from "../src/fieldview.ts";
import { deadlineRows as rowsOf, jaDateText, KIND_LABEL, kindLabel } from "../src/deadlines.ts";

const sent = (page: number, text_orig: string) => ({ page, text_orig, section_path: [], section_titles: [], boxes: [] });
const sentences = {
  p1_s1: sent(1, "入札書の提出期限は令和８年１０月１６日（金）午後５時００分とする。"),
  p2_s1: sent(2, "質問は令和8年10月2日までに提出すること。"),
  p3_s1: sent(3, "開札は2026年10月20日 10時に行う。"),
};
const checks = [{ name: "schema_valid", passed: true }, { name: "value_in_citation", passed: true }];
const deadlineRows = (f: Parameters<typeof rowsOf>[0]) => rowsOf(f, (x) => stateOf(x, sentences), formatWhen, valueFirst);
const item = (kind: string | null, datetime: string | null, citations: string[]) => ({ text_ja: null, text_en: null, citations, kind, datetime });
const fx = (items: ReturnType<typeof item>[], over: object = {}) => ({
  doc_id: "d", pdf: "d.pdf", sentences,
  fields: [{ field: "deadlines", status: "present" as const, value_en: null, value_ja: null, items, citations: [], checks, ...over }],
});

test("kind labels for every kind, unknown falls back to Other", () => {
  assert.equal(kindLabel("bid_in_person"), "Bid, in person");
  assert.equal(kindLabel("mail_arrival"), "Bid, by mail (must arrive)");
  assert.equal(kindLabel("application"), "Application or proposal due");
  assert.equal(Object.keys(KIND_LABEL).length, 9);
  assert.equal(kindLabel("nonsense"), "Other");
  assert.equal(kindLabel(null), "Other");
});

test("rows sort by date, undated items last, ties keep order", () => {
  const rows = deadlineRows(fx([
    item("bid_opening", "2026-10-20T10:00:00+09:00", ["p3_s1"]),
    item("other", null, ["p1_s1"]),
    item("electronic", "2026-10-16T17:00:00+09:00", ["p1_s1"]),
    item("question", "2026-10-02", ["p2_s1"]),
  ]));
  assert.deepEqual(rows.map((r) => r.kind), ["Questions", "Bid, electronic", "Bid opening", "Other"]);
  assert.deepEqual(rows.map((r) => r.when), ["2 Oct 2026", "16 Oct 2026, 17:00 JST", "20 Oct 2026, 10:00 JST", null]);
});

test("original Japanese date text is a substring of the cited sentence, full-width digits kept", () => {
  const r = deadlineRows(fx([item("electronic", "2026-10-16T17:00:00+09:00", ["p1_s1"])]))[0]!;
  assert.equal(r.ja, "令和８年１０月１６日（金）午後５時００分");
  assert.ok(sentences.p1_s1.text_orig.includes(r.ja!));
});

test("jaDateText prefers the date matching the stored month and day", () => {
  assert.equal(jaDateText(["令和8年10月2日までに質問し、令和8年10月16日に開札する。"], "2026-10-16"), "令和8年10月16日");
  assert.equal(jaDateText(["期限なし"], "2026-10-16"), null);
});

test("a click target is the first cited sentence that exists, with its page and the field's state", () => {
  const r = deadlineRows(fx([item("bid_opening", "2026-10-20", ["missing", "p3_s1"])]))[0]!;
  assert.deepEqual([r.sid, r.page, r.state], ["p3_s1", 3, "needs_review"]); // a cited id missing from the export blocks Verified (stateOf)
  assert.equal(deadlineRows(fx([item("bid_opening", "2026-10-20", ["p3_s1"])]))[0]?.state, "verified");
  const none = deadlineRows(fx([item("bid_opening", "2026-10-20", ["missing"])]))[0]!;
  assert.equal(none.sid, null); // the button is disabled, no highlight to open
});

test("a failed check gives Needs review on every row", () => {
  const rows = deadlineRows(fx([item("electronic", "2026-10-16", ["p1_s1"])], { checks: [{ name: "value_in_citation", passed: false }] }));
  assert.equal(rows[0]?.state, "needs_review");
});

test("empty state: absent field, no items, or no field gives no rows", () => {
  assert.deepEqual(deadlineRows(fx([], { status: "absent" })), []);
  assert.deepEqual(deadlineRows(fx([])), []);
  assert.deepEqual(deadlineRows({ doc_id: "d", pdf: "d.pdf", sentences, fields: [] }), []);
});

test("the sentence that contains the date text opens first, not an earlier heading", () => {
  const sn = { ...sentences, h1: sent(1, "公募期間"), d1: sent(1, "令和8年10月16日（金）午後5時00分まで") };
  const f = { ...fx([item("application", "2026-10-16T17:00:00+09:00", ["h1", "d1"])]), sentences: sn };
  const r = rowsOf(f, (x) => stateOf(x, sn), formatWhen, valueFirst)[0]!;
  assert.equal(r.sid, "d1");
  const heading = rowsOf({ ...f, fields: [{ ...f.fields[0]!, items: [item("application", "2026-10-16", ["h1"])] }] }, (x) => stateOf(x, sn), formatWhen, valueFirst)[0]!;
  assert.equal(heading.sid, "h1"); // no date text anywhere: the first cited sentence, as before
});
