import type { Field, Fixture } from "./types";

export type State = "verified" | "unverified" | "not_found" | "other_document";
export const STATE_TEXT: Record<State, string> = {
  verified: "verified",
  unverified: "found, not verified",
  not_found: "not found",
  other_document: "see other document",
};

// Checks that decide "verified". Any other stored check (field_applicable, ...) is shown, not gated on.
// heading_cue is soft: a failure is only a note (see unusualSection).
const HARD = new Set(["citations_exist", "value_in_citation", "schema_valid", "values_roundtrip"]);

// Reads results the pipeline already stored; checks nothing itself.
// verified = a value exists, at least one hard check is stored, every stored hard check passed,
// and every cited id is in the fixture. With no hard check stored nothing vouches for the field.
export function stateOf(f: Field, sentences: Fixture["sentences"]): State {
  if (f.status === "absent") return "not_found";
  if (f.status === "see_other_document") return "other_document";
  const ids = [...f.citations, ...f.items.flatMap((i) => i.citations)];
  const hard = f.checks.filter((c) => HARD.has(c.name));
  const ok = hard.length > 0 && hard.every((c) => c.passed) && ids.every((id) => id in sentences);
  return ok ? "verified" : "unverified";
}

export const unusualSection = (f: Field): boolean => f.checks.some((c) => c.name === "heading_cue" && !c.passed);
