// Run: npm test. The saved answer in settings.json (docs/storage_design.md section 3, D-120).
import assert from "node:assert/strict";
import * as fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
import * as os from "node:os";
import * as path from "node:path";
import { test, type TestContext } from "node:test";
import { readSaveDocuments, writeSaveDocuments } from "../electron/settings.ts";

function tempDir(t: TestContext): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "shiori-settings-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

const file = (base: string) => path.join(base, "settings.json");

test("default is unanswered, and reading creates nothing", (t) => {
  const base = tempDir(t);
  assert.equal(readSaveDocuments(base), "unanswered");
  assert.equal(readSaveDocuments(path.join(base, "missing", "folder")), "unanswered");
  assert.deepEqual(fs.readdirSync(base), []);
});

test("yes and no round-trip, each replacing the one before", (t) => {
  const base = tempDir(t);
  for (const value of ["yes", "no", "yes"] as const) {
    assert.equal(writeSaveDocuments(base, value), "saved");
    assert.equal(readSaveDocuments(base), value);
  }
});

test("writing creates the folder", (t) => {
  const base = path.join(tempDir(t), "a", "shiori-app");
  assert.equal(writeSaveDocuments(base, "no"), "saved");
  assert.equal(readSaveDocuments(base), "no");
});

test("anything but a stored yes or no gives unanswered", (t) => {
  const base = tempDir(t);
  for (const content of [
    "", // empty file
    "{",
    '{"saveDocuments":"yes"', // cut off
    "yes",
    "null",
    "[]",
    '"yes"',
    "{}",
    '{"saveDocuments":true}', // wrong type
    '{"saveDocuments":1}',
    '{"saveDocuments":null}',
    '{"saveDocuments":["yes"]}',
    '{"saveDocuments":"Yes"}', // unknown string
    '{"saveDocuments":"true"}',
    '{"saveDocuments":"unanswered"}',
    '{"keepDocuments":true}', // the name in the first draft of the design
  ]) {
    fs.writeFileSync(file(base), content);
    assert.equal(readSaveDocuments(base), "unanswered", content);
  }
});

test("a settings.json that cannot be read gives unanswered", (t) => {
  const base = tempDir(t);
  fs.mkdirSync(file(base)); // a folder where the file should be
  assert.equal(readSaveDocuments(base), "unanswered");
});

test("a crash between the temp write and the rename leaves the old value", (t) => {
  const base = tempDir(t);
  writeSaveDocuments(base, "no");
  const rename = t.mock.method(fs.default, "renameSync", () => {
    throw new Error("crash");
  });
  syncBuiltinESMExports();
  t.after(() => {
    rename.mock.restore();
    syncBuiltinESMExports();
  });
  assert.equal(writeSaveDocuments(base, "yes"), "failed");
  assert.equal(rename.mock.callCount(), 1);
  assert.equal(fs.readFileSync(`${file(base)}.tmp`, "utf8"), '{"saveDocuments":"yes"}'); // the new value got this far
  assert.equal(readSaveDocuments(base), "no");

  rename.mock.restore();
  syncBuiltinESMExports();
  assert.equal(writeSaveDocuments(base, "yes"), "saved"); // the leftover does not block the next write
  assert.equal(readSaveDocuments(base), "yes");
});

test("a leftover temp file never turns saving on", (t) => {
  const base = tempDir(t);
  fs.writeFileSync(`${file(base)}.tmp`, '{"saveDocuments":"yes"}');
  assert.equal(readSaveDocuments(base), "unanswered");
});

test("a folder that cannot be made gives failed, not an error", (t) => {
  const blocker = path.join(tempDir(t), "blocker");
  fs.writeFileSync(blocker, "");
  assert.equal(writeSaveDocuments(path.join(blocker, "shiori-app"), "yes"), "failed");
});

test("no_local_folder: nothing is read or created", (t) => {
  const dir = tempDir(t);
  const before = process.cwd();
  process.chdir(dir); // a write that took the word for a relative path would land here
  t.after(() => process.chdir(before));
  assert.equal(writeSaveDocuments("no_local_folder", "yes"), "not_available");
  assert.deepEqual(fs.readdirSync(dir), []);

  fs.mkdirSync("no_local_folder");
  fs.writeFileSync(path.join("no_local_folder", "settings.json"), '{"saveDocuments":"yes"}');
  assert.equal(readSaveDocuments("no_local_folder"), "unanswered");
});

test("the file holds the answer and nothing else: no names, paths or text", (t) => {
  const base = tempDir(t);
  fs.writeFileSync(file(base), '{"saveDocuments":"no","path":"/Users/a/invented.pdf"}');
  writeSaveDocuments(base, "yes");
  assert.equal(fs.readFileSync(file(base), "utf8"), '{"saveDocuments":"yes"}');
  assert.deepEqual(fs.readdirSync(base), ["settings.json"]);
});
