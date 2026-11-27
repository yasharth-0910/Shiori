// Run: npm test. A failed file operation on a user's path logs and throws the error type only (docs/privacy.md).
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { test } from "node:test";
import { userFile } from "../electron/userfile.ts";

const missing = path.join(os.tmpdir(), "shiori-no-such-dir", "入札公告_secret.pdf");

for (const [name, op] of [
  ["read", () => fs.readFileSync(missing)],
  ["stat", () => fs.statSync(missing)],
  ["write", () => fs.writeFileSync(missing, "本文")],
] as const) {
  test(`a failed ${name} logs and throws the error type, never the path or the text`, () => {
    const lines: string[] = [];
    assert.throws(
      () => userFile("x", op, (l) => lines.push(l)),
      (e: Error) => e.message === "ENOENT" && e.cause === undefined && !("path" in e),
    );
    assert.deepEqual(lines, ["x failed: ENOENT"]);
  });
}

test("an error without a code gives its name, not its message", () => {
  const lines: string[] = [];
  const op = () => {
    throw new RangeError(`too big: ${missing}`);
  };
  assert.throws(() => userFile("x", op, (l) => lines.push(l)), { message: "RangeError" });
  assert.deepEqual(lines, ["x failed: RangeError"]);
});

test("success passes the value through and logs nothing", () => {
  const lines: string[] = [];
  assert.equal(userFile("x", () => 7, (l) => lines.push(l)), 7);
  assert.deepEqual(lines, []);
});
