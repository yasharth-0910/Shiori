import assert from "node:assert/strict";
import { test } from "node:test";
import { collapsedLine, valueFirst } from "../src/fieldview.ts";
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
  // the officer's stored title and name, as written in the document (2aa7506a), with no machine label
  const officer = { title: "支出負担行為担当官 気象衛星センター所長", name: "立川 英二" };
  assert.deepEqual(scalarAnswer(field({ field: "contracting_officer", normalized: officer })), { text: "Title: 支出負担行為担当官 気象衛星センター所長 · Name: 立川 英二", mt: false });
  assert.deepEqual(scalarAnswer(field({ field: "contracting_officer", normalized: { name: "立川 英二" } })), { text: "Name: 立川 英二", mt: false });
  assert.equal(scalarAnswer(field({ field: "contracting_officer", normalized: null, value_en: null })), null);
});

import { readFileSync } from "node:fs";
import { ISSUERS, notApplicable } from "../src/fieldview.ts";
import { idsOf } from "../src/translate.ts";

test("title: the translated value when ready (labelled), the Japanese value until then, never the sentence English", () => {
  const f = field({ field: "title", value_ja: "テスト件名", citations: ["s1"] });
  const sentence = { s1: { en: "(2) Procurement Item Name and Quantity: Test", numbers_match: true } };
  assert.deepEqual(collapsedLine(f, sentence, none).en, { text: "テスト件名", mt: false, ja: true });
  const ready = { ...sentence, "value:title": { en: "Test title", numbers_match: true } };
  assert.deepEqual(collapsedLine(f, ready, none).en, { text: "Test title", mt: true, tr: ready["value:title"] });
  assert.deepEqual(collapsedLine(f, null, none).en, { text: "テスト件名", mt: false, ja: true });
});

test("title: opening the card asks for the value key too, other fields do not", () => {
  const fx = { sentences: { s1: {} } } as never;
  assert.deepEqual(idsOf(field({ field: "title", value_ja: "x", citations: ["s1"] }), fx), ["value:title", "s1"]);
  assert.deepEqual(idsOf(field({ field: "title", value_ja: null, citations: ["s1"] }), fx), ["s1"]);
  assert.deepEqual(idsOf(field({ field: "issuer_org", value_ja: "法務省", citations: ["s1"] }), fx), ["s1"]);
});

test("issuer: official name by code with no label; unknown or longer names show the Japanese value", () => {
  const known = scalarAnswer(field({ field: "issuer_org", value_ja: "法務省" }), null); // dev doc 6b7142ab
  assert.deepEqual(known, { text: "Ministry of Justice", mt: false });
  assert.equal(scalarAnswer(field({ field: "issuer_org", value_ja: "法 務 省" }), null)?.text, "Ministry of Justice");
  assert.deepEqual(scalarAnswer(field({ field: "issuer_org", value_ja: "和歌山県" }), null), { text: "和歌山県", mt: false, ja: true }); // 4c40bbd8
  assert.equal(scalarAnswer(field({ field: "issuer_org", value_ja: "国土交通省 関東地方整備局" }), null)?.ja, true);
  assert.equal(scalarAnswer(field({ field: "issuer_org", value_ja: null }), null), null);
});

test("a Japanese answer is worth showing", () => {
  assert.equal(worthShowing("テスト件名", "Title", null), true);
});

test("the issuer list matches core/shiori_core/glossary.py", () => {
  const py = readFileSync(new URL("../../core/shiori_core/glossary.py", import.meta.url), "utf8");
  const block = py.slice(py.indexOf("ISSUERS: dict"), py.indexOf("def issuer_en"));
  const pairs = [...block.matchAll(/"([^"]+)": "([^"]+)"/g)].map((m) => [m[1], m[2]]);
  assert.equal(pairs.length, 8);
  assert.deepEqual(Object.fromEntries(pairs), ISSUERS);
});

test("notApplicable: only a field without an answer, in a known type that does not look for it", () => {
  const absent = field({ field: "bid_bond", status: "absent", value_ja: null, citations: [] });
  assert.equal(notApplicable(absent, "spec"), true);
  assert.equal(notApplicable(absent, "notice"), false);
  assert.equal(notApplicable(absent, undefined), false);
  assert.equal(notApplicable({ ...absent, status: "present" }, "spec"), false);
  assert.equal(notApplicable({ ...absent, field: "title" }, "spec"), false);
});

// 2f2f5bd3 performance_period: the heading (p1_s14) is cited before the value line (p1_s15).
test("valueFirst puts the sentence holding the value first and keeps the rest in order", () => {
  const sent = { p1_s14: { text_orig: "（5）業務の期間" }, p1_s15: { text_orig: "契約締結日から令和15年9月30日（金）まで" }, p1_s16: { text_orig: "他" } };
  const v = "契約締結日から令和15年9月30日（金）まで";
  assert.deepEqual(valueFirst(["p1_s14", "p1_s15", "p1_s16"], v, sent), ["p1_s15", "p1_s14", "p1_s16"]);
  assert.deepEqual(valueFirst(["p1_s15", "p1_s14"], v, sent), ["p1_s15", "p1_s14"]);
  assert.deepEqual(valueFirst(["p1_s14", "p1_s16"], v, sent), ["p1_s14", "p1_s16"]); // no match: unchanged
  assert.deepEqual(valueFirst(["p1_s14", "p1_s15"], null, sent), ["p1_s14", "p1_s15"]);
});
