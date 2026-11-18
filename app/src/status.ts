import type { Field, Fixture } from "./types";

export type State = "verified" | "unverified" | "not_found" | "other_document";
export const STATE_TEXT: Record<State, string> = {
  verified: "verified",
  unverified: "found, not verified",
  not_found: "not found",
  other_document: "see other document",
};

// Reads results the pipeline already stored; checks nothing itself.
// verified = a value exists, there is at least one stored check, all passed, every cited id is in the fixture.
// A present field with no stored checks is not verified: nothing vouches for it.
export function stateOf(f: Field, sentences: Fixture["sentences"]): State {
  if (f.status === "absent") return "not_found";
  if (f.status === "see_other_document") return "other_document";
  const ids = [...f.citations, ...f.items.flatMap((i) => i.citations)];
  const ok = f.checks.length > 0 && f.checks.every((c) => c.passed) && ids.every((id) => id in sentences);
  return ok ? "verified" : "unverified";
}
