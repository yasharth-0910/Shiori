// The master key's keeper (docs/storage_design.md sections 2 and "When saving is not available", D-119): Electron
// safeStorage, synchronous calls. safeStorage is passed in, so tests run with a fake and plain `node --test`. No app
// code imports this file yet. It touches no file itself, and without a keeper no store can be made.
import type { Keeper } from "./store"; // type only: nothing of the store is loaded

export type SafeStorage = {
  isEncryptionAvailable(): boolean;
  getSelectedStorageBackend(): string; // Linux only
  encryptString(plain: string): Buffer;
  decryptString(encrypted: Buffer): string;
};

// Call after app ready, and only when saved documents are needed: it can raise a keyring prompt. "no_keyring" when
// encryption is unavailable, or on Linux when the backend is basic_text (a password built into the program) or unknown.
export function createKeeper(safe: SafeStorage, platform: string): Keeper | "no_keyring" {
  if (!safe.isEncryptionAvailable()) return "no_keyring";
  if (platform === "linux" && ["basic_text", "unknown"].includes(safe.getSelectedStorageBackend())) return "no_keyring";
  return { wrap: (plain) => safe.encryptString(plain), unwrap: (wrapped) => safe.decryptString(wrapped) };
}
