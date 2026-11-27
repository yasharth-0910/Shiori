// The saved answer to "keep documents between sessions?" (docs/storage_design.md section 3, D-119, D-120):
// <base>/settings.json, one value. `base` is what storageBase() in paths.ts returned. Not encrypted, and it holds
// nothing about any document. Only Node modules, and no app code imports it yet.
import * as fs from "node:fs";
import * as path from "node:path";

export type SaveDocuments = "unanswered" | "yes" | "no";

const fileIn = (base: string) => path.join(base, "settings.json");

/** Never throws. Anything but a stored "yes" or "no" is "unanswered", so a problem never turns saving on. */
export function readSaveDocuments(base: string): SaveDocuments {
  if (base === "no_local_folder") return "unanswered"; // not a folder name: never read it from the working directory
  try {
    const value: unknown = JSON.parse(fs.readFileSync(fileIn(base), "utf8"))?.saveDocuments;
    return value === "yes" || value === "no" ? value : "unanswered";
  } catch {
    return "unanswered";
  }
}

/** Never throws, so no error with a path in it gets out. A crash or "failed" leaves the old file or the new one. */
export function writeSaveDocuments(base: string, value: "yes" | "no"): "saved" | "not_available" | "failed" {
  if (base === "no_local_folder") return "not_available";
  try {
    const file = fileIn(base);
    fs.mkdirSync(base, { recursive: true });
    fs.writeFileSync(`${file}.tmp`, JSON.stringify({ saveDocuments: value }), { flush: true });
    fs.renameSync(`${file}.tmp`, file);
    return "saved";
  } catch {
    return "failed";
  }
}
