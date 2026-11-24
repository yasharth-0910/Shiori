// Run: npm test. Onboarding rules (D-115): when it shows, the privacy sentence, the copy notice, the plural line.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { REGISTRY } from "../electron/registry.ts";
import { copyNotice, othersText, PRIVACY_TEXT, showOnboarding } from "../src/firstrun.ts";
import type { ModelList } from "../src/shiori.d.ts";

const list = (installed: string[], skipPicker = false): ModelList => ({
  models: REGISTRY.map((m) => ({ ...m, installed: installed.includes(m.id) })),
  recommended: null,
  default: null,
  running: null,
  binaryFound: true,
  expected: [],
  skipPicker,
});

test("onboarding shows only when no model is installed", () => {
  assert.equal(showOnboarding(list([])), true);
  assert.equal(showOnboarding(list(["gemma-4-e4b"])), false);
  assert.equal(showOnboarding(list(["qwen3.5-9b", "gemma-4-e4b"])), false);
  assert.equal(showOnboarding(list([], true)), false); // dev check mode
});

test("the privacy sentence is the README footnote word for word, minus its docs pointer", () => {
  const readme = readFileSync(new URL("../../README.md", import.meta.url), "utf8");
  const foot = readme.split("\n").find((l) => l.startsWith("\\*Privacy in Shiori means this:")) as string;
  assert.ok(foot, "footnote found");
  assert.equal(foot.slice(2).replace(" (docs/decisions.md, D-111)", ""), PRIVACY_TEXT);
  assert.match(PRIVACY_TEXT, /The app does not call any cloud service\.$/);
  assert.ok(!PRIVACY_TEXT.includes("—"));
});

test("copy notice: shows size and free space, and blocks when there is not enough room", () => {
  assert.deepEqual(copyNotice(5e9, 20e9), { text: "This copies the model (5.00 GB) into Shiori's models folder. Free space there: 20.00 GB.", enough: true });
  assert.equal(copyNotice(5e9, 1e9).enough, false);
  assert.match(copyNotice(5e9, 1e9).text, /not enough/);
  assert.equal(copyNotice(5e9, null).enough, true);
});

test("other-files line: a count only, nothing for zero", () => {
  assert.equal(othersText(0), "");
  assert.equal(othersText(1), "1 other model file was found that this version does not support.");
  assert.equal(othersText(3), "3 other model files were found that this version does not support.");
});
