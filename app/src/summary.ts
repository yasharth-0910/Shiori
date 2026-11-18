import type { State } from "./status";
import type { Field, Fixture } from "./types";

// Summary lines are fixed templates filled with a Verified field's own stored English text (D-77).
// No model, no free text. Order is the order of SLOTS. The state function is passed in so this file
// stays free of imports that node's test runner cannot resolve (see test/summary.test.ts).
export type Line = { key: string; text: string; sid: string; page: number };
export type Summary = { lines: Line[]; unused: { field: string; note: string | null }[] };

type Slot = { field: string; template: (en: string) => string; items: boolean };

// issuer, what is procured, deadline, eligibility, how it is awarded, how to submit
const SLOTS: Slot[] = [
  { field: "issuer_org", items: false, template: (en) => `Issued by ${en}.` },
  { field: "title", items: false, template: (en) => `The RFP is for: ${en}.` },
  { field: "procurement_type", items: false, template: (en) => `Procurement type: ${en}.` },
  { field: "deadlines", items: true, template: (en) => `Deadline: ${en}.` },
  { field: "eligibility", items: true, template: (en) => `Eligibility item: ${en}.` },
  { field: "award_method", items: false, template: (en) => `Award method: ${en}.` },
  { field: "submission_modes", items: true, template: (en) => `How to submit: ${en}.` },
];

const tidy = (s: string) => s.trim().replace(/[.。]+$/, "");

// The English text of one list item, with its ISO datetime in front when the export has one.
const itemText = (i: Field["items"][number]) => [i.datetime, i.text_en && tidy(i.text_en)].filter(Boolean).join(" ");

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
    const entries = slot.items && f.items.length
      ? f.items.map((i) => ({ en: itemText(i), ids: i.citations.length ? i.citations : f.citations }))
      : [{ en: f.value_en ? tidy(f.value_en) : "", ids: f.citations }];
    const before = lines.length;
    entries.forEach((e, n) => {
      const sid = e.ids.find((id) => id in fx.sentences);
      const s = sid ? fx.sentences[sid] : undefined;
      if (e.en && sid && s) lines.push({ key: `${f.field}:${n}`, text: slot.template(e.en), sid, page: s.page });
    });
    if (lines.length === before) unused.push({ field: f.field, note: "Verified, but no English text stored" });
  }
  return { lines, unused };
}
