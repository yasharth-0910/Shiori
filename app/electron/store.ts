// Seals and opens one blob of the document store (docs/storage_design.md section 2, D-119). Nothing here touches the
// disk. A blob is "SHI1" | 12-byte nonce | ciphertext | 16-byte tag, AES-256-GCM. The folder name and the role are
// authenticated too, so a file moved to another folder or renamed to another role does not open.
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

export type Role = "key" | "record" | "source";

type Code = "seal_failed" | "open_failed";

// A code and nothing else (no cause, path, data or key bytes), because it may end up in a log.
export class StoreError extends Error {
  readonly code: Code;
  constructor(code: Code) {
    super(code);
    this.name = "StoreError";
    this.code = code;
  }
}

const MAGIC = Buffer.from("SHI1");
const BODY = MAGIC.length + 12; // after the nonce
const TAG = 16;

const aad = (folder: string, role: Role) => Buffer.from(`shiori-store-v1|${folder}|${role}`);

export function seal(key: Uint8Array, folder: string, role: Role, plain: Uint8Array): Buffer {
  try {
    const nonce = randomBytes(BODY - MAGIC.length); // new on every write: a key must never reuse one
    const c = createCipheriv("aes-256-gcm", key, nonce, { authTagLength: TAG });
    c.setAAD(aad(folder, role));
    return Buffer.concat([MAGIC, nonce, c.update(plain), c.final(), c.getAuthTag()]);
  } catch {
    throw new StoreError("seal_failed");
  }
}

// Returns the plain bytes only after the tag check has passed.
export function open(key: Uint8Array, folder: string, role: Role, blob: Uint8Array): Buffer {
  try {
    const b = Buffer.from(blob.buffer, blob.byteOffset, blob.byteLength);
    if (b.length < BODY + TAG || !b.subarray(0, MAGIC.length).equals(MAGIC)) throw new StoreError("open_failed");
    const d = createDecipheriv("aes-256-gcm", key, b.subarray(MAGIC.length, BODY), { authTagLength: TAG });
    d.setAAD(aad(folder, role));
    d.setAuthTag(b.subarray(b.length - TAG));
    return Buffer.concat([d.update(b.subarray(BODY, b.length - TAG)), d.final()]);
  } catch {
    throw new StoreError("open_failed");
  }
}
