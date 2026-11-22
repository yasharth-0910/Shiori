import type { State } from "./status";
import type { Field, Fixture } from "./types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Pure logic for the Deadlines tab. One row per stored deadline item; nothing is computed from today's date.
// formatWhen and the state function are passed in so this file has no value imports node's test runner cannot resolve (see summary.ts).
export const KIND_LABEL: Record<string, string> = {
  bid_in_person: "Bid, in person",
  mail_arrival: "Bid, by mail (must arrive)",
  electronic: "Bid, electronic",
  bid_opening: "Bid opening",
  question: "Questions",
  briefing: "Briefing session",
  document_request: "Document request",
  application: "Application or proposal due",
  other: "Other",
};
export const kindLabel = (k: string | null | undefined): string => KIND_LABEL[k ?? "other"] ?? KIND_LABEL.other!;

// The stored value (Japan time, "+09:00") as date and time in an IANA zone. A date-only value has no time to convert: null.
// Intl does the zone and daylight-saving rules; the stored string is parsed by hand so the machine zone cannot touch it.
export function localWhen(iso: string, zone: string): { date: string; time: string } | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(iso)) return null;
  const d = new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(iso) ? iso : `${iso}+09:00`);
  if (Number.isNaN(d.getTime())) return null;
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
      .formatToParts(d).map((x) => [x.type, x.value]),
  );
  return { date: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}` };
}

// "13:30 your time"; "02:00 on 25 Oct, your time" when the local date differs from the Japan date.
export function yourTime(iso: string, zone: string): string | null {
  const l = localWhen(iso, zone);
  if (!l) return null;
  const jp = /^\d{4}-\d{2}-\d{2}/.exec(iso)?.[0];
  if (l.date === jp) return `${l.time} your time`;
  const [, m, day] = l.date.split("-").map(Number);
  return `${l.time} on ${day} ${MONTHS[(m ?? 1) - 1]}, your time`;
}

export type DeadlineRow = {
  key: string;
  kind: string; // the readable label
  when: string | null; // "16 Oct 2026, 17:00 JST", or null when the item stores no date
  iso: string | null;
  local: string | null; // "13:30 your time"; null for a date-only item or no date
  ja: string | null; // the date text as written in the cited sentence
  sid: string | null; // the cited sentence the click opens; null when none is in the export
  page: number | null;
  state: State; // the deadlines field's pill, the same one the Fields view shows
};

// Date text as written: 令和6年10月16日(水) 午後5時00分, 2026年10月16日 17時, with full-width digits too.
const JA_DATE = /(?:令和|平成|昭和)?[0-9０-９元]+年[0-9０-９]+月[0-9０-９]+日(?:[（(][^）)]{1,3}[）)])?(?:\s*(?:午前|午後)?\s*[0-9０-９]+時(?:\s*[0-9０-９]+分)?)?/g;
const digits = (s: string) => s.replace(/[０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0));

// First date in the cited sentences whose month and day equal the stored date's; else the first date found.
// Substring of the original text, never rewritten.
export function jaDateText(texts: string[], iso: string | null): string | null {
  const hits = texts.flatMap((t) => t.match(JA_DATE) ?? []);
  const md = iso ? /^\d{4}-(\d{2})-(\d{2})/.exec(iso) : null;
  const same = md
    ? hits.find((h) => {
        const m = /([0-9]+)月([0-9]+)日/.exec(digits(h));
        return m && Number(m[1]) === Number(md[1]) && Number(m[2]) === Number(md[2]);
      })
    : undefined;
  return same ?? hits[0] ?? null;
}

// order is valueFirst from fieldview.ts, passed in for the same reason.
export type Order = (ids: string[], valueJa: string | null, sentences: Fixture["sentences"]) => string[];
export function deadlineRows(fx: Fixture, state: (f: Field) => State, formatWhen: (iso: string) => string | null, order: Order): DeadlineRow[] {
  const f = fx.fields.find((x) => x.field === "deadlines");
  if (!f || f.status === "absent") return [];
  const st = state(f);
  const rows = f.items.map((i, n): DeadlineRow => {
    const when = i.datetime ? formatWhen(i.datetime) : null;
    const texts = i.citations.flatMap((id) => fx.sentences[id]?.text_orig ?? []);
    const ja = jaDateText(texts, when ? (i.datetime ?? null) : null);
    // The sentence that holds the date text opens first (a heading like 公募期間 may be cited before it).
    const sid = order(i.citations, ja, fx.sentences).find((id) => id in fx.sentences) ?? null;
    return {
      key: `d${n}`,
      kind: kindLabel(i.kind),
      when: when ? (i.datetime?.includes("T") ? `${when} JST` : when) : null,
      iso: when ? (i.datetime ?? null) : null,
      local: when && i.datetime ? yourTime(i.datetime, Intl.DateTimeFormat().resolvedOptions().timeZone) : null,
      ja,
      sid,
      page: sid ? (fx.sentences[sid]?.page ?? null) : null,
      state: st,
    };
  });
  // By date; items with no stored date go last. Array.sort is stable, so ties keep the extractor's order.
  return rows.sort((a, b) => (a.iso && b.iso ? (a.iso < b.iso ? -1 : a.iso > b.iso ? 1 : 0) : a.iso ? -1 : b.iso ? 1 : 0));
}
