// Run: npm test. Seal and open one blob of the document store (docs/storage_design.md sections 2 and 6 step 1).
// Everything stays in memory.
import assert from "node:assert/strict";
import { createDecipheriv, randomBytes } from "node:crypto";
import { test } from "node:test";
import { open, type Role, seal, StoreError } from "../electron/store.ts";

const key = randomBytes(32);
const folder = "0123456789abcdef0123456789abcdef";
const plain = Buffer.from("入札公告 invented test text");
const blob = seal(key, folder, "record", plain);
const HEADER = 4;
const BODY = 4 + 12;
const TAG = 16;

// The error carries its code and nothing else: no cause, no path, no data, no key bytes.
function failsClosed(op: () => unknown, code: "seal_failed" | "open_failed" = "open_failed"): void {
  assert.throws(op, (e: unknown) => {
    assert.ok(e instanceof StoreError);
    assert.equal(e.code, code);
    assert.equal(e.message, code);
    assert.equal(e.cause, undefined);
    assert.deepEqual(Object.keys(e).sort(), ["code", "name"]);
    return true;
  });
}

test("round trip", () => {
  for (const role of ["key", "record", "source"] as Role[]) {
    assert.deepEqual(open(key, folder, role, seal(key, folder, role, plain)), plain);
  }
});

test("empty and 20 MB input", () => {
  for (const input of [Buffer.alloc(0), randomBytes(20 * 1024 * 1024)]) {
    const sealed = seal(key, folder, "source", input);
    assert.equal(sealed.length, BODY + input.length + TAG);
    assert.ok(open(key, folder, "source", sealed).equals(input));
  }
});

test("a plain Uint8Array view with an offset opens", () => {
  const padded = new Uint8Array(blob.length + 10);
  padded.set(blob, 5);
  assert.deepEqual(open(key, folder, "record", padded.subarray(5, 5 + blob.length)), plain);
});

test("the file shape and the authenticated data are the ones in the design", () => {
  assert.equal(blob.subarray(0, HEADER).toString("latin1"), "SHI1");
  const d = createDecipheriv("aes-256-gcm", key, blob.subarray(HEADER, BODY), { authTagLength: TAG });
  d.setAAD(Buffer.from(`shiori-store-v1|${folder}|record`));
  d.setAuthTag(blob.subarray(blob.length - TAG));
  assert.deepEqual(Buffer.concat([d.update(blob.subarray(BODY, blob.length - TAG)), d.final()]), plain);
});

for (const [part, from, to] of [
  ["header", 0, HEADER],
  ["nonce", HEADER, BODY],
  ["body", BODY, blob.length - TAG],
  ["tag", blob.length - TAG, blob.length],
] as const) {
  test(`one flipped byte anywhere in the ${part} fails`, () => {
    for (let i = from; i < to; i++) {
      const bad = Buffer.from(blob);
      bad[i]! ^= 1;
      failsClosed(() => open(key, folder, "record", bad));
    }
  });
}

test("a short tag or a cut file fails", () => {
  // The empty blob is only header, nonce and tag, so every cut of it shortens the tag.
  for (const whole of [blob, seal(key, folder, "record", Buffer.alloc(0))]) {
    for (let n = 0; n < whole.length; n++) failsClosed(() => open(key, folder, "record", whole.subarray(0, n)));
  }
  failsClosed(() => open(key, folder, "record", Buffer.concat([blob, Buffer.alloc(1)])));
});

test("wrong key, wrong folder and wrong role fail", () => {
  failsClosed(() => open(randomBytes(32), folder, "record", blob));
  failsClosed(() => open(key, "f".repeat(32), "record", blob));
  failsClosed(() => open(key, folder, "source", blob));
  failsClosed(() => open(key, folder, "key", blob));
});

test("a key of the wrong length fails closed", () => {
  for (const bad of [Buffer.alloc(0), randomBytes(16), randomBytes(31), randomBytes(33)]) {
    failsClosed(() => seal(bad, folder, "record", plain), "seal_failed");
    failsClosed(() => open(bad, folder, "record", blob));
  }
});

test("two seals of the same input differ", () => {
  const a = seal(key, folder, "record", plain);
  const b = seal(key, folder, "record", plain);
  assert.ok(!a.subarray(HEADER, BODY).equals(b.subarray(HEADER, BODY)), "same nonce");
  assert.ok(!a.subarray(BODY).equals(b.subarray(BODY)), "same ciphertext");
});
