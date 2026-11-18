import type { Field, Fixture } from "./types";

export type State = "verified" | "needs_review" | "not_found" | "other_document";
export const STATE_TEXT: Record<State, string> = {
  verified: "Verified",
  needs_review: "Needs review",
  not_found: "Not found",
  other_document: "See other document",
};

// Checks that decide "verified". Any other stored check (field_applicable, ...) is shown, not gated on.
// heading_cue is not in this set, but a failed one still blocks "verified" below (D-76).
const HARD = new Set(["citations_exist", "value_in_citation", "schema_valid", "values_roundtrip"]);

// Reads results the pipeline already stored; checks nothing itself.
// verified = a value exists, at least one hard check is stored, every stored hard check passed,
// every cited id is in the fixture, and no stored heading_cue failed (D-76: a green pill with a hidden note misled).
// With no hard check stored nothing vouches for the field.
export function stateOf(f: Field, sentences: Fixture["sentences"]): State {
  if (f.status === "absent") return "not_found";
  if (f.status === "see_other_document") return "other_document";
  const ids = [...f.citations, ...f.items.flatMap((i) => i.citations)];
  const hard = f.checks.filter((c) => HARD.has(c.name));
  const ok = hard.length > 0 && hard.every((c) => c.passed) && ids.every((id) => id in sentences) && !unusualSection(f);
  return ok ? "verified" : "needs_review";
}

export function unusualSection(f: Field): boolean {
  return f.checks.some((c) => c.name === "heading_cue" && !c.passed);
}
