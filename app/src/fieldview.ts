// What a field card says on its collapsed line. Pure logic, no runtime imports (node's test runner).
import type { Tr } from "./translate";
import type { Field, Item } from "./types";

// mt: a model wrote it, so the card labels it. tr: set when it is a sentence translation, whose checks add a note.
export type En = { text: string; mt: boolean; tr?: Tr };
export type Line = { count: string | null; en: En | null };

type Items = Record<string, Tr>;

const firstTr = (ids: string[], tr: Items | null): En | null => {
  const t = tr && ids.map((i) => tr[i]).find((x) => x);
  return t ? { text: t.en, mt: true, tr: t } : null;
};

// Fallback only, for a field with no normalized value: the Japanese quote in value_ja is matched against the wording
// the rules extractor itself looks for. The English names are the ones in core/shiori_core/glossary.py.
const ENUM_LABELS: Record<string, [RegExp, string][]> = {
  procurement_type: [
    [/一般競争入札/, "Open competitive bidding"],
    [/指名競争入札/, "Selective bidding"],
    [/プロポーザル|企画競争/, "Proposal competition"],
    [/オープンカウンター/, "Open counter"],
  ],
  award_method: [
    [/総合評価/, "Best-value award"],
    [/最低価格/, "Lowest-price award"],
  ],
  tax_basis: [
    [/含まない|含まず|除く|税抜/, "Bid excludes tax"],
    [/含む|含め|税込/, "Bid includes tax"],
  ],
};

export function enumLabel(f: Field): string | null {
  const hit = f.value_ja ? ENUM_LABELS[f.field]?.find(([re]) => re.test(f.value_ja!)) : undefined;
  return hit ? hit[1] : null;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

// Enum answers by the extractor's stored code (docs/field_schema.md). Same English names as glossary.py.
const ENUM_BY_CODE: Record<string, [key: string, labels: Record<string, string>]> = {
  procurement_type: ["type", { open_competitive: "Open competitive bidding", designated_competitive: "Selective bidding", proposal_competition: "Proposal competition", open_counter: "Open counter" }],
  award_method: ["method", { best_value: "Best-value award", lowest_price: "Lowest-price award" }],
};

/** "2024-06-05" -> "June 5, 2024"; null when the string is not a plain ISO date. */
export function isoDateEn(iso: unknown): string | null {
  const m = typeof iso === "string" ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso) : null;
  const month = m ? MONTHS[Number(m[2]) - 1] : undefined;
  return m && month ? `${month} ${Number(m[3])}, ${m[1]}` : null;
}

/** An answer written by code from the stored normalized value: an ISO date or an enum code. Null when there is none. */
function normalizedAnswer(f: Field): string | null {
  const n = f.normalized;
  if (!n) return null;
  const e = ENUM_BY_CODE[f.field];
  return e ? (e[1][String(n[e[0]])] ?? null) : isoDateEn(n.date);
}

/** A deterministic answer for the top of a scalar card: built from the normalized value, else the quote's enum label, else the stored English value. */
export function scalarAnswer(f: Field): En | null {
  if (f.items.length) return null;
  const made = normalizedAnswer(f) ?? (f.value_en ? null : enumLabel(f));
  if (made) return { text: made, mt: false };
  return f.value_en ? { text: f.value_en, mt: true } : null;
}

const norm = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

/** Show an answer line only when it adds something: not the field's own name, not a repeat of the sentence English. */
export function worthShowing(answer: string, fieldLabel: string, sentenceEn: string | null): boolean {
  const a = norm(answer);
  return a !== "" && a !== norm(fieldLabel) && a !== (sentenceEn ? norm(sentenceEn) : null);
}

/**
 * Scalar field: the English value, else the enum label, else the English of its first cited sentence once ready.
 * List field: the entry count plus the first item's English (written by code when `code` gives one,
 * else the item's text_en, else its first cited sentence's English once ready). en null = not ready.
 */
export function collapsedLine(f: Field, tr: Items | null, code: (i: Item) => string | null): Line {
  if (!f.items.length) {
    return { count: null, en: scalarAnswer(f) ?? firstTr(f.citations, tr) };
  }
  const n = f.items.length;
  const count = `${n} ${n === 1 ? "entry" : "entries"}`;
  const i = f.items[0]!;
  const made = code(i);
  if (made) return { count, en: { text: made, mt: false } };
  return { count, en: i.text_en ? { text: i.text_en, mt: true } : firstTr(i.citations, tr) };
}
