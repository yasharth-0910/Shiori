// What a field card says on its collapsed line. Pure logic, no runtime imports (node's test runner).
import type { Tr } from "./translate";
import type { Field, Item } from "./types";

// mt: a model wrote it, so the card labels it. tr: set when it is a translation, whose checks add a note.
// ja: the text is the Japanese value itself (shown until the English is ready, or when there is none).
export type En = { text: string; mt: boolean; tr?: Tr; ja?: boolean };
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

// Official English names of central ministries and agencies (D-91). The same eight as ISSUERS in
// core/shiori_core/glossary.py; a test fails if the two drift. Matched on the whole issuer value only.
export const ISSUERS: Record<string, string> = {
  法務省: "Ministry of Justice",
  厚生労働省: "Ministry of Health, Labour and Welfare",
  総務省: "Ministry of Internal Affairs and Communications",
  内閣府: "Cabinet Office",
  農林水産省: "Ministry of Agriculture, Forestry and Fisheries",
  国土交通省: "Ministry of Land, Infrastructure, Transport and Tourism",
  気象庁: "Japan Meteorological Agency",
  出入国在留管理庁: "Immigration Services Agency of Japan",
};

export const VALUE_KEY = "value:title"; // the queue key of the title value's translation (D-91)

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

/** An answer written by code from the stored normalized value: an ISO date, an enum code, or an officer's title and name. Null when there is none. */
function normalizedAnswer(f: Field): string | null {
  const n = f.normalized;
  if (!n) return null;
  if (f.field === "contracting_officer") {
    // The stored title and name, as the document wrote them (Japanese): shown as they are, never machine-translated.
    const parts = [n.title && `Title: ${String(n.title)}`, n.name && `Name: ${String(n.name)}`].filter(Boolean);
    return parts.length ? parts.join(" · ") : null;
  }
  const e = ENUM_BY_CODE[f.field];
  return e ? (e[1][String(n[e[0]])] ?? null) : isoDateEn(n.date);
}

/**
 * A deterministic answer for the top of a scalar card: built from the normalized value, else the quote's enum label,
 * else the stored English value. Title: its own translation (labelled) or, until that is ready, the Japanese value.
 * Issuer: the official name by code (no label) or the Japanese value (D-91). Never the whole sentence's English.
 */
export function scalarAnswer(f: Field, tr: Items | null = null): En | null {
  if (f.items.length) return null;
  const ja = f.value_ja?.trim();
  if (f.field === "title" && ja) {
    const t = f.value_en ? undefined : tr?.[VALUE_KEY];
    return f.value_en ? { text: f.value_en, mt: true } : t ? { text: t.en, mt: true, tr: t } : { text: ja, mt: false, ja: true };
  }
  if (f.field === "issuer_org" && ja) {
    const en = ISSUERS[ja.replace(/\s+/g, "")];
    return en ? { text: en, mt: false } : { text: ja, mt: false, ja: true };
  }
  const made = normalizedAnswer(f) ?? (f.value_en ? null : enumLabel(f));
  if (made) return { text: made, mt: false };
  return f.value_en ? { text: f.value_en, mt: true } : null;
}

const norm = (t: string) => t.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();

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
    return { count: null, en: scalarAnswer(f, tr) ?? firstTr(f.citations, tr) };
  }
  const n = f.items.length;
  const count = `${n} ${n === 1 ? "entry" : "entries"}`;
  const i = f.items[0]!;
  const made = code(i);
  if (made) return { count, en: { text: made, mt: false } };
  return { count, en: i.text_en ? { text: i.text_en, mt: true } : firstTr(i.citations, tr) };
}

// Which detected document types a field is looked for in: the same table as `applies_to` in core/shiori_core/fields.py
// (a test fails if they drift). Only the three types the sidecar can detect (D-92); tender_page is not one of them.
const NBS = ["notice", "bid_instructions", "spec"];
const NB = ["notice", "bid_instructions"];
const N = ["notice"];
export const APPLIES: Record<string, string[]> = {
  title: NBS, issuer_org: NBS, scope_summary: NBS, performance_period: NBS, delivery_deadline: NBS, delivery_location: NBS,
  contracting_officer: NB, procurement_type: NB, award_method: NB, eligibility: NB, unified_qualification: NB, deadlines: NB,
  submission_modes: NB, bid_bond: NB, performance_bond: NB, tax_basis: NB, language_currency: NB, required_documents: NB,
  contact: NB, wto_covered: NB, spec_access: NB,
  notice_date: N, item_category: N,
};

/** True when the document's type is known, the field is not looked for in that type, and it has no answer (D-93). A field with an answer is always shown. */
export const notApplicable = (f: Field, docType: string | undefined): boolean =>
  !!docType && f.status === "absent" && !!APPLIES[f.field] && !APPLIES[f.field]!.includes(docType);

/** Citation ids with the one whose sentence contains the displayed Japanese value first; the rest keep their order. */
export function valueFirst(ids: string[], valueJa: string | null, sentences: Record<string, { text_orig: string }>): string[] {
  const strip = (t: string) => t.replace(/\s+/g, "");
  const v = valueJa ? strip(valueJa) : "";
  const i = v ? ids.findIndex((id) => strip(sentences[id]?.text_orig ?? "").includes(v)) : -1;
  return i > 0 ? [ids[i]!, ...ids.slice(0, i), ...ids.slice(i + 1)] : ids;
}
