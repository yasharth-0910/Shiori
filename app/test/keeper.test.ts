// Run: npm test. The safeStorage keeper and the store's base folder (docs/storage_design.md section 6, step 3).
// safeStorage is a fake: the real one runs only inside Electron. All Japanese text is invented.
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { test, type TestContext } from "node:test";
import { createKeeper, type SafeStorage } from "../electron/keeper.ts";
import { storageBase } from "../electron/paths.ts";
import { createStore } from "../electron/store.ts";

const flip = (b: Buffer) => Buffer.from(b.map((x) => x ^ 0x5a));

function fake(available: boolean, backend = "gnome_libsecret") {
  const calls = { encrypt: 0, decrypt: 0, backend: 0 };
  const safe: SafeStorage = {
    isEncryptionAvailable: () => available,
    getSelectedStorageBackend: () => (calls.backend++, backend),
    encryptString: (s) => (calls.encrypt++, flip(Buffer.from(s))),
    decryptString: (b) => (calls.decrypt++, flip(b).toString()),
  };
  return { safe, calls };
}

function tempDir(t: TestContext): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "shiori-keeper-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

// What a caller does: a store exists only when there is a keeper. HTML, so there is no source file to read.
function saveIfKept(base: string, safe: SafeStorage, platform: string) {
  const keeper = createKeeper(safe, platform);
  if (keeper === "no_keyring") return keeper;
  const result = { doc_id: "a".repeat(64), format: "html" as const, text: "入札公告 invented", fields: [], sentences: {} };
  createStore(base, keeper, () => {}).save(result, "", "0.0.0");
  return keeper;
}

for (const [name, platform, available, backend] of [
  ["unavailable on macOS", "darwin", false, "gnome_libsecret"],
  ["unavailable on Windows", "win32", false, "gnome_libsecret"],
  ["unavailable on Linux", "linux", false, "gnome_libsecret"],
  ["basic_text", "linux", true, "basic_text"],
  ["unknown", "linux", true, "unknown"],
] as const) {
  test(`${name}: no_keyring, nothing encrypted, no file`, (t) => {
    const base = tempDir(t);
    const { safe, calls } = fake(available, backend);
    assert.equal(saveIfKept(base, safe, platform), "no_keyring");
    assert.equal(calls.encrypt + calls.decrypt, 0);
    assert.deepEqual(fs.readdirSync(base), []);
  });
}

test("a real Linux keyring is accepted, and the backend is asked on Linux only", () => {
  for (const backend of ["gnome_libsecret", "kwallet", "kwallet5", "kwallet6"]) {
    assert.notEqual(createKeeper(fake(true, backend).safe, "linux"), "no_keyring");
  }
  for (const platform of ["darwin", "win32"]) {
    const { safe, calls } = fake(true, "unknown");
    assert.notEqual(createKeeper(safe, platform), "no_keyring");
    assert.equal(calls.backend, 0);
  }
});

test("wrap then unwrap round-trips through safeStorage", () => {
  const { safe, calls } = fake(true);
  const keeper = createKeeper(safe, "darwin");
  assert.ok(keeper !== "no_keyring");
  const plain = Buffer.alloc(32, 7).toString("base64");
  const wrapped = keeper.wrap(plain);
  assert.ok(!wrapped.includes(plain));
  assert.equal(keeper.unwrap(wrapped), plain);
  assert.deepEqual([calls.encrypt, calls.decrypt], [1, 1]);
});

test("the store makes a master key with the keeper and a new store object opens it", (t) => {
  const base = tempDir(t);
  const { safe } = fake(true);
  const keeper = saveIfKept(base, safe, "darwin");
  assert.ok(keeper !== "no_keyring");
  assert.ok(fs.existsSync(path.join(base, "store", "master.key")));
  const { documents, unreadable } = createStore(base, keeper, () => {}).list();
  assert.deepEqual([documents.length, unreadable], [1, 0]);
});

const roaming = "C:\\Users\\a\\AppData\\Roaming\\shiori-app";

test("Windows: LOCALAPPDATA joined with the last part of userData", () => {
  assert.equal(storageBase("win32", { LOCALAPPDATA: "C:\\Users\\a\\AppData\\Local" }, roaming), "C:\\Users\\a\\AppData\\Local\\shiori-app");
});

test("Windows: a missing or relative LOCALAPPDATA gives no_local_folder, never the roaming folder", () => {
  for (const value of [undefined, "", "AppData\\Local", ".\\Local", "C:Local", "\\Users\\a\\AppData\\Local", "/tmp"]) {
    assert.equal(storageBase("win32", { LOCALAPPDATA: value }, roaming), "no_local_folder", String(value));
  }
  assert.equal(storageBase("win32", {}, roaming), "no_local_folder");
});

test("macOS and Linux use userData, whatever LOCALAPPDATA says", () => {
  for (const [platform, userData] of [
    ["darwin", "/Users/a/Library/Application Support/shiori-app"],
    ["linux", "/home/a/.config/shiori-app"],
  ] as const) {
    assert.equal(storageBase(platform, {}, userData), userData);
    assert.equal(storageBase(platform, { LOCALAPPDATA: "C:\\x" }, userData), userData);
  }
});
