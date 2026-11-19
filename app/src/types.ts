// Shape of fixture.json, written by scripts/export_app_fixture.py.
export type Box = { page: number; bbox: [number, number, number, number] }; // PDF points, top-left origin
export type Sentence = { page: number; text_orig: string; section_path: string[]; section_titles: string[]; boxes: Box[] };
export type Check = { name: string; passed: boolean }; // the pipeline's stored result, never recomputed here
// datetime, kind and polarity are copied from the label by the export (D-80); absent when the label has none.
// datetime is "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:00+09:00". kind is the label's code (bid_in_person, electronic, ...).
export type Polarity = "requirement" | "disqualification";
export type Item = {
  text_ja: string | null;
  text_en: string | null;
  citations: string[];
  datetime?: string | null;
  kind?: string | null;
  polarity?: Polarity | null;
};
export type Field = {
  field: string;
  status: "present" | "absent" | "see_other_document";
  value_en: string | null;
  value_ja: string | null;
  items: Item[];
  citations: string[];
  checks: Check[];
};
export type Fixture = { doc_id: string; pdf: string; fields: Field[]; sentences: Record<string, Sentence> };
