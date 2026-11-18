import { stateOf, type State } from "./status";
import type { Field, Fixture } from "./types";

// UI labels only. Groups follow docs/field_schema.md; the pipeline stores no section per field.
const META: Record<string, [label: string, group: string]> = {
  title: ["Title", "Overview"],
  issuer_org: ["Issuer", "Overview"],
  contracting_officer: ["Contracting officer", "Overview"],
  notice_date: ["Notice date", "Overview"],
  procurement_type: ["Procurement type", "Overview"],
  award_method: ["Award method", "Overview"],
  item_category: ["Item category", "Overview"],
  scope_summary: ["Scope", "Overview"],
  spec_access: ["Specification access", "Overview"],
  eligibility: ["Eligibility", "Eligibility"],
  unified_qualification: ["Unified qualification", "Eligibility"],
  wto_covered: ["WTO agreement", "Eligibility"],
  performance_period: ["Performance period", "Schedule"],
  delivery_deadline: ["Delivery deadline", "Schedule"],
  delivery_location: ["Delivery location", "Schedule"],
  deadlines: ["Deadlines", "Schedule"],
  submission_modes: ["Submission methods", "Submission"],
  required_documents: ["Required documents", "Submission"],
  contact: ["Contact", "Submission"],
  bid_bond: ["Bid bond", "Terms"],
  performance_bond: ["Performance bond", "Terms"],
  tax_basis: ["Tax basis", "Terms"],
  language_currency: ["Language and currency", "Terms"],
};

export const labelOf = (f: Field): string => META[f.field]?.[0] ?? f.field.replace(/_/g, " ");
export const groupOf = (f: Field): string => META[f.field]?.[1] ?? "Other";

export const STATES: State[] = ["verified", "needs_review", "not_found", "other_document"];

export function countStates(fx: Fixture): Record<State, number> {
  const out: Record<State, number> = { verified: 0, needs_review: 0, not_found: 0, other_document: 0 };
  for (const f of fx.fields) out[stateOf(f, fx.sentences)]++;
  return out;
}

const field = (fx: Fixture, id: string) => fx.fields.find((f) => f.field === id);
export const titleOf = (fx: Fixture) => ({ en: field(fx, "title")?.value_en ?? null, ja: field(fx, "title")?.value_ja ?? null });
export const issuerOf = (fx: Fixture) => field(fx, "issuer_org")?.value_en ?? null;

// The current fixture export keeps no date text for deadlines, only citations. When an export adds an
// ISO `datetime` to a bid item, it shows up here; until then the library shows a dash.
export function deadlineOf(fx: Fixture): string | null {
  for (const i of field(fx, "deadlines")?.items ?? []) {
    const d = i.datetime?.slice(0, 10);
    if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) return d;
  }
  return null;
}

export function daysLeft(iso: string, today = new Date()): number {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  const start = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((Date.UTC(y, m - 1, d) - start) / 86400000);
}
