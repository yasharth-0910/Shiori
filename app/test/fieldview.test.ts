import assert from "node:assert/strict";
import { test } from "node:test";
import { collapsedLine } from "../src/fieldview.ts";
import type { Field } from "../src/types.ts";

const field = (over: Partial<Field>): Field => ({ field: "x", status: "present", value_en: null, value_ja: null, items: [], citations: [], checks: [], ...over });
const item = (over: object) => ({ text_ja: null, text_en: null, citations: [], ...over });
const none = () => null;

test("scalar: the English value, labelled as machine text", () => {
  assert.deepEqual(collapsedLine(field({ value_en: "Open competitive bidding" }), null, none), { count: null, en: { text: "Open competitive bidding", mt: true } });
});

test("scalar with no value falls back to the first cited sentence's English, once ready", () => {
  const f = field({ citations: ["s1", "s2"] });
  assert.equal(collapsedLine(f, {}, none).en, null);
  const tr = { s2: { en: "Tax included.", numbers_match: false } };
  assert.deepEqual(collapsedLine(f, tr, none).en, { text: "Tax included.", mt: true, tr: tr.s2 });
});

test("list: the count and the first item's English; code-made text is not labelled", () => {
  const f = field({ items: [item({ datetime: "2026-10-16" }), item({})] });
  assert.deepEqual(collapsedLine(f, null, () => "Bids due 16 Oct 2026"), { count: "2 entries", en: { text: "Bids due 16 Oct 2026", mt: false } });
  assert.deepEqual(collapsedLine(field({ items: [item({ text_en: "Be a company" })] }), null, none), { count: "1 entry", en: { text: "Be a company", mt: true } });
  assert.deepEqual(collapsedLine(field({ items: [item({ citations: ["s1"] })] }), null, none), { count: "1 entry", en: null });
});

import { enumLabel, scalarAnswer, worthShowing } from "../src/fieldview.ts";

test("enum label by code from the stored Japanese quote; unknown wording gets none", () => {
  assert.equal(enumLabel(field({ field: "procurement_type", value_ja: "一般競争入札に付します" })), "Open competitive bidding");
  assert.equal(enumLabel(field({ field: "procurement_type", value_ja: "公募型プロポーザル" })), "Proposal competition");
  assert.equal(enumLabel(field({ field: "tax_basis", value_ja: "消費税及び地方消費税を含む" })), "Bid includes tax");
  assert.equal(enumLabel(field({ field: "tax_basis", value_ja: "消費税を含まない" })), "Bid excludes tax");
  assert.equal(enumLabel(field({ field: "spec_access", value_ja: "電子調達システムにて交付する" })), null);
  assert.deepEqual(scalarAnswer(field({ field: "procurement_type", value_ja: "オープンカウンター方式" })), { text: "Open counter", mt: false });
  assert.equal(scalarAnswer(field({ value_en: "x", items: [item({})] })), null); // lists have no top answer
});

test("an answer line is hidden when it repeats the field name or the sentence English", () => {
  assert.equal(worthShowing("Contracting officer", "Contracting officer", null), false);
  assert.equal(worthShowing("The bid is due, May 5.", "Deadline", "the bid is due May 5"), false);
  assert.equal(worthShowing("Open competitive bidding", "Procurement type", "Bids are open."), true);
});

import { isoDateEn } from "../src/fieldview.ts";

test("date and enum answers are built by code from the normalized value, with no machine label", () => {
  assert.equal(isoDateEn("2024-06-05"), "June 5, 2024");
  assert.equal(isoDateEn("2024-13-05"), null);
  assert.deepEqual(scalarAnswer(field({ field: "notice_date", normalized: { date: "2024-06-05" } })), { text: "June 5, 2024", mt: false });
  assert.deepEqual(scalarAnswer(field({ field: "award_method", normalized: { method: "lowest_price" }, value_ja: "x" })), { text: "Lowest-price award", mt: false });
  assert.deepEqual(scalarAnswer(field({ field: "procurement_type", normalized: { type: "open_competitive" } })), { text: "Open competitive bidding", mt: false });
  assert.equal(scalarAnswer(field({ field: "contracting_officer", normalized: { title: "x", name: "y" } })), null);
});
