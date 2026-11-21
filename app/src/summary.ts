import type { State } from "./status";
import type { Field, Fixture, Item } from "./types";

// Summary lines are fixed templates filled with a Verified field's own stored values (D-77, D-80).
// No model, no free text. Order is the order of SLOTS. The state function is passed in so this file
// stays free of imports that node's test runner cannot resolve (see test/summary.test.ts).
export type Line = { key: string; text: string; sid: string; page: number };
export type Summary = { lines: Line[]; unused: { field: string; note: string | null }[] };

// A slot gives one line from the field's value (value) or one line per list item (item). item returns
// null when the item has nothing to say, and then it gives no line.
type Slot = { field: string; value?: (en: string) => string; item?: (i: Item) => string | null };

const tidy = (s: string) => s.trim().replace(/[.。]+$/, "");
const text = (template: (en: string) => string) => (i: Item) => (i.text_en ? template(tidy(i.text_en)) : null);

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// "2026-10-16T17:00:00+09:00" -> "16 Oct 2026, 17:00"; a date-only value has no time. Read from the
// string as stored (Japan time); no Date object, so the machine's time zone cannot move it.
export function formatWhen(iso: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/.exec(iso);
  if (!m) return null;
  const date = `${Number(m[3])} ${MONTHS[Number(m[2]) - 1] ?? "?"} ${m[1]}`;
  return m[4] ? `${date}, ${m[4]}` : date;
}

// One template per deadline kind (field_schema.md). Bid kinds say how bids come in.
const BID_HOW: Record<string, string> = { bid_in_person: "in person", mail_arrival: "by mail", electronic: "electronic" };
const DEADLINE: Record<string, (when: string) => string> = {
  bid_in_person: (w) => `Bids due ${w} (${BID_HOW.bid_in_person}).`,
  mail_arrival: (w) => `Bids due ${w} (${BID_HOW.mail_arrival}).`,
  electronic: (w) => `Bids due ${w} (${BID_HOW.electronic}).`,
  bid_opening: (w) => `Bid opening ${w}.`,
  application: (w) => `Applications due ${w}.`,
  question: (w) => `Questions due ${w}.`,
  briefing: (w) => `Briefing ${w}.`,
  document_request: (w) => `Document requests due ${w}.`,
  other: (w) => `Other deadline ${w}.`,
};
export const BID_KINDS = ["bid_in_person", "mail_arrival", "electronic", "application"]; // D-97: the dates that count as the deadline

export function deadlineLine(i: Item): string | null {
  const when = i.datetime ? formatWhen(i.datetime) : null;
  if (!when) return null;
  return (DEADLINE[i.kind ?? "other"] ?? DEADLINE.other!)(when);
}

// "Must: ..." for a requirement, "Cannot bid if: ..." for a disqualification. An item with no stored
// polarity keeps the neutral wording rather than guessing.
export function eligibilityLine(i: Item): string | null {
  const t = (en: string) => (i.polarity === "requirement" ? `Must: ${en}.` : i.polarity === "disqualification" ? `Cannot bid if: ${en}.` : `Eligibility item: ${en}.`);
  return text(t)(i);
}

// issuer, what is procured, deadline, eligibility, how it is awarded, how to submit
const SLOTS: Slot[] = [
  { field: "issuer_org", value: (en) => `Issued by ${en}.` },
  { field: "title", value: (en) => `The RFP is for: ${en}.` },
  { field: "procurement_type", value: (en) => `Procurement type: ${en}.` },
  { field: "deadlines", item: deadlineLine },
  { field: "eligibility", item: eligibilityLine },
  { field: "award_method", value: (en) => `Award method: ${en}.` },
  { field: "submission_modes", item: text((en) => `How to submit: ${en}.`) },
];

// Earliest bid deadline that is today or later; if all are past, the latest one (shown as Closed).
// Only Verified deadlines count. daysLeft counts calendar days from today's date.
export function daysLeft(iso: string, today = new Date()): number {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  const start = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((Date.UTC(y, m - 1, d) - start) / 86400000);
}

export type Due = { when: string; days: number };
export function bidDeadline(fx: Fixture, state: (f: Field) => State, today = new Date()): Due | null {
  const f = fx.fields.find((x) => x.field === "deadlines");
  if (!f || state(f) !== "verified") return null;
  const dates = f.items
    .filter((i) => i.kind && BID_KINDS.includes(i.kind) && i.datetime)
    .map((i) => i.datetime as string)
    .filter((d) => formatWhen(d))
    .sort();
  const upcoming = dates.find((d) => daysLeft(d.slice(0, 10), today) >= 0);
  const pick = upcoming ?? dates[dates.length - 1];
  return pick ? { when: formatWhen(pick) as string, days: daysLeft(pick.slice(0, 10), today) } : null;
}

export function buildSummary(fx: Fixture, state: (f: Field) => State): Summary {
  const lines: Line[] = [];
  const unused: Summary["unused"] = [];
  for (const slot of SLOTS) {
    const f = fx.fields.find((x) => x.field === slot.field);
    if (!f) continue;
    if (state(f) !== "verified") {
      unused.push({ field: f.field, note: null });
      continue;
    }
    // One entry per item for list fields; otherwise one entry from the field's own value.
    const entries = slot.item
      ? f.items.map((i) => ({ line: slot.item!(i), ids: i.citations.length ? i.citations : f.citations }))
      : [{ line: f.value_en && slot.value ? slot.value(tidy(f.value_en)) : null, ids: f.citations }];
    const before = lines.length;
    entries.forEach((e, n) => {
      const sid = e.ids.find((id) => id in fx.sentences);
      const s = sid ? fx.sentences[sid] : undefined;
      if (e.line && sid && s) lines.push({ key: `${f.field}:${n}`, text: e.line, sid, page: s.page });
    });
    if (lines.length === before) unused.push({ field: f.field, note: "Verified, but no line could be built from the stored values" });
  }
  return { lines, unused };
}
