// Run: npm test. Offset math of the text viewer (HTML notices, D-37): what a highlight covers, in code points.
import assert from "node:assert/strict";
import { test } from "node:test";
import { codepoints, findAll, paragraphs, slices, type Mark } from "../src/textmath.ts";

// Invented text, shaped like extract_lines output: one line per element, joined with "\n".
const TEXT = "入札公告\n令和８年１０月１５日（木）１３時３０分\nまでに提出すること。\n𠮷野家に関する件\nSummary";
const cps = codepoints(TEXT);
const hl = (start: number, end: number): Mark[] => [{ start, end, kind: "hl" }];
const lit = (marks: Mark[]) => paragraphs(cps).flatMap((p) => slices(cps, p, marks).filter((s) => s.kinds.includes("hl")));

test("paragraphs are the lines, with code point offsets", () => {
  const ps = paragraphs(cps);
  assert.equal(ps.length, 5);
  assert.equal(cps.slice(ps[1]!.start, ps[1]!.end).join(""), "令和８年１０月１５日（木）１３時３０分");
  assert.equal(ps[1]!.start, 5); // 入札公告 is 4 characters, then "\n"
});

test("a sentence with full-width characters is highlighted on exactly its characters", () => {
  const a = TEXT.indexOf("令和");
  const b = TEXT.indexOf("分") + 1;
  const got = lit(hl(a, b));
  assert.equal(got.length, 1);
  assert.deepEqual([got[0]!.start, got[0]!.end], [a, b]);
  assert.equal(got[0]!.text, "令和８年１０月１５日（木）１３時３０分"); // original text, full-width digits kept
});

test("a sentence spanning two paragraphs gives a piece in each and no piece for the line break", () => {
  const a = TEXT.indexOf("１３時");
  const b = TEXT.indexOf("こと。") + 3;
  const got = lit(hl(a, b));
  assert.equal(got.length, 2);
  assert.equal(got[0]!.end, TEXT.indexOf("\n", a)); // ends at the paragraph's end
  assert.equal(got[1]!.start, got[0]!.end + 1); // next one starts after the "\n"
  assert.deepEqual([got[0]!.start, got[1]!.end], [a, b]);
  assert.equal(got.map((s) => s.text).join(""), "１３時３０分までに提出すること。");
  assert.equal(got.reduce((n, s) => n + s.end - s.start, 0), b - a - 1); // every character but the "\n"
});

test("offsets count code points, so a character outside the BMP is one position", () => {
  assert.equal(TEXT.length - cps.length, 1); // 𠮷 is two UTF-16 units, one code point
  const a = cps.indexOf("𠮷");
  const got = lit(hl(a, a + 3));
  assert.equal(got[0]!.text, "𠮷野家");
  assert.equal(TEXT.slice(a, a + 3) === "𠮷野家", false); // UTF-16 slicing would be wrong here
});

test("slices carry plain strings: markup in the text stays text", () => {
  const c = codepoints('<img src="http://example.invalid/x" onerror="alert(1)"><script>1</script>');
  const [s] = slices(c, { start: 0, end: c.length }, hl(5, 20));
  assert.equal(slices(c, { start: 0, end: c.length }, []).map((x) => x.text).join(""), c.join(""));
  assert.ok(typeof s!.text === "string");
});

test("find folds full-width letters and digits and maps back to original offsets", () => {
  const hits = findAll(cps, "2026".replace("2026", "８年"));
  assert.equal(hits.length, 1);
  assert.equal(cps.slice(hits[0]!.start, hits[0]!.end).join(""), "８年");
  assert.deepEqual(findAll(cps, "1０月").map((h) => cps.slice(h.start, h.end).join("")), ["１０月"]);
  assert.deepEqual(findAll(cps, "  "), []);
});
