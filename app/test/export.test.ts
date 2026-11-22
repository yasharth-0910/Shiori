// Run: npm test. Export: CSV quoting and BOM, .ics folding and escaping, undated items left out, [CHECK], stable UIDs.
// The two deadline items are the real ones of 2f2f5bd3 (Wakayama notice): mail bid 2026-10-26 17:00, in-person bid 2026-10-27 14:00,
// cited sentences p2_s8 and p2_s2. The sentence text here is shortened around the real date text.
import assert from "node:assert/strict";
import { test } from "node:test";
import { valueFirst } from "../src/fieldview.ts";
import { deadlineRows } from "../src/deadlines.ts";
import { BOM, csvCell, deadlinesIcs, exportName, fieldsCsv, fold, type CsvDeps } from "../src/export.ts";
import { stateOf, STATE_TEXT } from "../src/status.ts";
import { deadlineLine, formatWhen } from "../src/summary.ts";

const DOC = "2f2f5bd332965253eed43d739e56e7859b149afa0d157ea3c89dfdd7d0d8b419";
const sent = (page: number, text_orig: string) => ({ page, text_orig, section_path: [], section_titles: [], boxes: [] });
const sentences = {
  p1_s1: sent(1, "件名 令和8年度 システム, 「保守」"),
  p2_s8: sent(2, "提出期限 令和8年10月26日（月）午後5時まで"),
  p2_s2: sent(2, "入札日時 令和8年10月27日（火）午後2時"),
};
const checks = [{ name: "schema_valid", passed: true }, { name: "value_in_citation", passed: true }];
const item = (kind: string | null, datetime: string | null, citations: string[], text_ja: string | null = null) => ({ text_ja, text_en: null, citations, kind, datetime });
const deadlines = (items: ReturnType<typeof item>[], over: object = {}) => ({ field: "deadlines", status: "present" as const, value_en: null, value_ja: null, items, citations: [], checks, ...over });
const title = { field: "title", status: "present" as const, value_en: null, value_ja: "令和8年度 システム, 「保守」", items: [], citations: ["p1_s1"], checks };
const absent = { field: "award_method", status: "absent" as const, value_en: null, value_ja: null, items: [], citations: [], checks: [] };
const fx = (fields: object[]) => ({ doc_id: DOC, pdf: "n.pdf", sentences, fields }) as Parameters<typeof fieldsCsv>[0];
const real = [item("mail_arrival", "2026-10-26T17:00:00+09:00", ["p2_s8"]), item("bid_in_person", "2026-10-27T14:00:00+09:00", ["p2_s2"])];
const rowsFor = (f: ReturnType<typeof fx>) => deadlineRows(f, (x) => stateOf(x, f.sentences), formatWhen, valueFirst);
const NOW = new Date("2026-11-22T10:00:00Z");
const deps = (f: ReturnType<typeof fx>): CsvDeps => ({
  state: (x) => stateOf(x, f.sentences), stateText: STATE_TEXT, label: (x) => x.field,
  scalar: (x) => (x.field === "title" && x.value_ja ? { text: x.value_ja, mt: false, ja: true } : x.value_en ? { text: x.value_en, mt: true } : null),
  itemLine: deadlineLine,
});
const unfold = (t: string) => t.replace(/\r\n /g, "");

test("CSV cell quoting: commas, quotes and newlines are quoted, quotes doubled; formula starters get an apostrophe", () => {
  assert.equal(csvCell("plain"), "plain");
  assert.equal(csvCell("a,b"), '"a,b"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(csvCell("two\nlines"), '"two\nlines"');
  assert.equal(csvCell("=1+1"), "'=1+1");
  assert.equal(csvCell("@x,y"), `"'@x,y"`);
  assert.equal(csvCell("令和8年、保守"), "令和8年、保守"); // the Japanese comma is not a delimiter
});

test("CSV starts with a BOM, uses CRLF, has one row per field and the seven columns", () => {
  const f = fx([title, absent, deadlines(real)]);
  const out = fieldsCsv(f, deps(f));
  assert.ok(out.startsWith(BOM + "Field,English value,Original Japanese value,State,Page,Source sentence ID,Source sentence (Japanese)\r\n"));
  const lines = out.slice(1).split("\r\n");
  assert.equal(lines.length, 5); // header, 3 fields, trailing empty
  assert.ok(lines[1]!.startsWith('title,,"令和8年度 システム, 「保守」",Verified,1,p1_s1,'));
  assert.ok(lines[2]!.startsWith("award_method,,,Not found,,,"));
});

test("a list field joins its items one per line, with the page and sentence ids of the cited sentences", () => {
  const f = fx([deadlines(real)]);
  const row = fieldsCsv(f, deps(f)).slice(1).split("\r\n")[1]!;
  assert.ok(row.includes('"Bids due 26 Oct 2026, 17:00 (by mail).\nBids due 27 Oct 2026, 14:00 (in person)."'));
  assert.ok(row.includes(',Verified,2,"p2_s8\np2_s2",'));
  assert.ok(row.includes("令和8年10月26日（月）午後5時まで\n入札日時 令和8年10月27日（火）午後2時"));
});

test("model English is marked as machine translation in the CSV", () => {
  const f = fx([{ ...title, value_en: "Title en" }]);
  assert.ok(fieldsCsv(f, { ...deps(f), scalar: () => ({ text: "Title en", mt: true }) }).includes("Title en [machine translation]"));
});

test("fold: lines are at most 75 octets, never split a character, and unfold to the original", () => {
  const long = "SUMMARY:" + "令和8年度システム、保守;".repeat(20) + "abc".repeat(40);
  const folded = fold(long);
  for (const l of folded.split("\r\n")) assert.ok(new TextEncoder().encode(l).length <= 75, l);
  assert.equal(unfold(folded), long);
  assert.equal(fold("short"), "short");
});

test(".ics of the two real 2f2f5bd3 items: Tokyo times, VTIMEZONE, CRLF, UIDs and the description", () => {
  const f = fx([title, deadlines(real)]);
  const { text, count } = deadlinesIcs(f, rowsFor(f), "Wakayama Financial System", NOW);
  assert.equal(count, 2);
  assert.ok(text.startsWith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"));
  assert.ok(text.endsWith("END:VCALENDAR\r\n"));
  assert.ok(!/(^|[^\r])\n/.test(text), "every line break is CRLF");
  assert.ok(text.includes("BEGIN:VTIMEZONE\r\nTZID:Asia/Tokyo\r\n") && text.includes("TZNAME:JST"));
  const u = unfold(text);
  assert.ok(u.includes("DTSTART;TZID=Asia/Tokyo:20261026T170000\r\n"));
  assert.ok(u.includes("DTSTART;TZID=Asia/Tokyo:20261027T140000\r\n"));
  assert.ok(u.includes("DTSTAMP:20261122T100000Z\r\n"));
  assert.ok(u.includes(`UID:2f2f5bd332965253-p2_s8-0@shiori.local\r\n`));
  assert.ok(u.includes("SUMMARY:[CHECK]") === false); // both rows are Verified
  assert.ok(u.includes("SUMMARY:Bid\\, by mail (must arrive): Wakayama Financial System\r\n"));
  assert.ok(u.includes("DESCRIPTION:Page 2\\nOriginal date text: 令和8年10月26日（月）午後5時\\nExtracted by Shiori. Check against the document.\r\n"));
});

test(".ics escapes commas, semicolons and backslashes in the title", () => {
  const f = fx([deadlines([real[0]!])]);
  const u = unfold(deadlinesIcs(f, rowsFor(f), "A, B; C \\ D", NOW).text);
  assert.ok(u.includes("Bid\\, by mail (must arrive): A\\, B\\; C \\\\ D\r\n"));
});

test("an item with no stored date is left out of the .ics", () => {
  const f = fx([deadlines([item("other", null, ["p2_s8"]), real[1]!])]);
  const { text, count } = deadlinesIcs(f, rowsFor(f), "T", NOW);
  assert.equal(count, 1);
  assert.equal((text.match(/BEGIN:VEVENT/g) ?? []).length, 1);
  assert.ok(text.includes("20261027T140000"));
  assert.equal(deadlinesIcs(fx([deadlines([item("other", null, ["p2_s8"])])]), [], "T", NOW).count, 0);
});

test("[CHECK] is added to the summary when the field is Needs review", () => {
  const f = fx([deadlines(real, { checks: [{ name: "value_in_citation", passed: false }] })]);
  const u = unfold(deadlinesIcs(f, rowsFor(f), "T", NOW).text);
  assert.equal((u.match(/SUMMARY:\[CHECK\] /g) ?? []).length, 2);
});

test("UIDs are the same in two exports; a second item in one sentence gets its own", () => {
  const f = fx([deadlines([...real, item("question", "2026-10-26T12:00:00+09:00", ["p2_s8"])])]);
  const uids = (t: string) => unfold(t).match(/^UID:.*$/gm)!;
  const a = uids(deadlinesIcs(f, rowsFor(f), "T", NOW).text);
  const b = uids(deadlinesIcs(f, rowsFor(f), "T", new Date("2027-01-01T00:00:00Z")).text);
  assert.deepEqual(a, b);
  assert.equal(new Set(a).size, 3);
});

test("a date-only item becomes an all-day event that ends the next day, across month ends", () => {
  const f = fx([deadlines([item("question", "2026-10-31", ["p2_s8"])])]);
  const u = deadlinesIcs(f, rowsFor(f), "T", NOW).text;
  assert.ok(u.includes("DTSTART;VALUE=DATE:20261031\r\nDTEND;VALUE=DATE:20261101\r\n"));
});

test("file names: the document name, no .pdf, characters file systems reject replaced", () => {
  assert.equal(exportName("tender.pdf", "fields.csv"), "tender_fields.csv");
  assert.equal(exportName("a/b:c.PDF", "deadlines.ics"), "a_b_c_deadlines.ics");
  assert.equal(exportName("和歌山.pdf", "deadlines.ics"), "和歌山_deadlines.ics");
  assert.equal(exportName(".pdf", "fields.csv"), "document_fields.csv");
});
