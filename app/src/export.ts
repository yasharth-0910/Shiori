// Export: a CSV of every field and an .ics of the dated deadline items. Pure functions, no I/O, no network, no logging.
// Anything the app already owns (state pill, label, answer line) is passed in so this file has no value imports
// node's test runner cannot resolve (see summary.ts, deadlines.ts).
import type { DeadlineRow } from "./deadlines";
import type { State } from "./status";
import type { Field, Fixture, Item } from "./types";

export type CsvDeps = {
  state: (f: Field) => State;
  stateText: Record<State, string>;
  label: (f: Field) => string;
  scalar: (f: Field) => { text: string; mt: boolean; ja?: boolean } | null; // scalarAnswer(f, translations)
  itemLine: (i: Item) => string | null; // deadlineLine
};

const NL = "\r\n";
export const BOM = "\uFEFF";

// RFC 4180 quoting. A cell that starts with = + - @ (or tab/CR) would run as a formula in Excel, and the text
// comes from an untrusted document, so it gets a leading apostrophe.
export function csvCell(v: string): string {
  const safe = /^[=+\-@\t\r]/.test(v) ? `'${v}` : v;
  return /[",\r\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export const CSV_HEADER = ["Field", "English value", "Original Japanese value", "State", "Page", "Source sentence ID", "Source sentence (Japanese)"];

const uniq = <T>(xs: T[]): T[] => [...new Set(xs)];

// One row per field. A list field joins its items, one per line; sentence ids and sentences line up one per line.
export function fieldsCsv(fx: Fixture, d: CsvDeps): string {
  const rows = fx.fields.map((f) => {
    const ids = uniq([...f.citations, ...f.items.flatMap((i) => i.citations)]);
    const found = ids.filter((id) => id in fx.sentences);
    const pages = uniq(found.map((id) => fx.sentences[id]!.page)).sort((a, b) => a - b);
    let en = "";
    let ja = f.value_ja ?? "";
    if (f.items.length) {
      en = f.items.map((i) => d.itemLine(i) ?? i.text_en ?? "").filter(Boolean).join("\n");
      ja = f.items.map((i) => i.text_ja ?? "").filter(Boolean).join("\n");
    } else {
      const a = d.scalar(f);
      if (a && !a.ja) en = a.mt ? `${a.text} [machine translation]` : a.text;
    }
    return [
      d.label(f), en, ja, d.stateText[d.state(f)], pages.join("; "), ids.join("\n"),
      found.map((id) => fx.sentences[id]!.text_orig).join("\n"),
    ];
  });
  return BOM + [CSV_HEADER, ...rows].map((r) => r.map(csvCell).join(",")).join(NL) + NL;
}

// ---- .ics ----

const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");

// Fold at 75 octets (RFC 5545 3.1): never inside a UTF-8 character, and the leading space of a continuation line counts.
export function fold(line: string): string {
  const enc = new TextEncoder();
  const out: string[] = [];
  let cur = "";
  let n = 0;
  for (const ch of line) {
    const b = enc.encode(ch).length;
    if (n + b > 75) {
      out.push(cur);
      cur = " ";
      n = 1;
    }
    cur += ch;
    n += b;
  }
  out.push(cur);
  return out.join("\r\n");
}

const TZ = ["BEGIN:VTIMEZONE", "TZID:Asia/Tokyo", "BEGIN:STANDARD", "DTSTART:19700101T000000", "TZOFFSETFROM:+0900", "TZOFFSETTO:+0900", "TZNAME:JST", "END:STANDARD", "END:VTIMEZONE"];

const stamp = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");

// "2026-10-16T17:00:00+09:00" -> timed in Asia/Tokyo; "2026-10-02" -> an all-day event. The stored time is Japan time
// as written, so the clock part is taken as it is. ponytail: a stored offset other than +09:00 is not checked (the extractor only writes +09:00).
function when(iso: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(iso);
  if (!m) return null;
  if (m[4]) return `DTSTART;TZID=Asia/Tokyo:${m[1]}${m[2]}${m[3]}T${m[4]}${m[5]}00`;
  const next = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + 1)).toISOString().slice(0, 10).replace(/-/g, "");
  return `DTSTART;VALUE=DATE:${m[1]}${m[2]}${m[3]}\r\nDTEND;VALUE=DATE:${next}`;
}

// One event per row that has a stored date; rows without one are left out. rows come from deadlineRows.
export function deadlinesIcs(fx: Fixture, rows: DeadlineRow[], title: string, now: Date): { text: string; count: number } {
  const seen = new Map<string, number>();
  const events: string[] = [];
  for (const r of rows) {
    const start = r.iso ? when(r.iso) : null;
    if (!start) continue;
    // Stable across exports: document hash + sentence id (+ a counter when one sentence holds several items).
    const base = `${fx.doc_id.slice(0, 16)}-${r.sid ?? "nosid"}`;
    const k = seen.get(base) ?? 0;
    seen.set(base, k + 1);
    const desc = [r.page ? `Page ${r.page}` : null, r.ja ? `Original date text: ${r.ja}` : null, "Extracted by Shiori. Check against the document."].filter(Boolean).join("\n");
    events.push(
      [
        "BEGIN:VEVENT",
        `UID:${base}-${k}@shiori.local`,
        `DTSTAMP:${stamp(now)}`,
        start,
        `SUMMARY:${esc(`${r.state === "needs_review" ? "[CHECK] " : ""}${r.kind}: ${title}`)}`,
        `DESCRIPTION:${esc(desc)}`,
        "END:VEVENT",
      ].join("\r\n"),
    );
  }
  const body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Shiori//Deadlines//EN", "CALSCALE:GREGORIAN", ...TZ, ...events, "END:VCALENDAR"].join("\r\n");
  return { text: body.split("\r\n").map(fold).join("\r\n") + "\r\n", count: events.length };
}

// "<document name>_fields.csv": the PDF's name without .pdf, with characters file systems reject replaced.
export const exportName = (pdf: string, suffix: "fields.csv" | "deadlines.ics"): string =>
  `${pdf.replace(/\.pdf$/i, "").replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_").trim() || "document"}_${suffix}`;
