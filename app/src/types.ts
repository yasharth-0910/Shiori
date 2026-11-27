// Shape of fixture.json, written by scripts/export_app_fixture.py.
export type Box = { page: number; bbox: [number, number, number, number] }; // PDF points, top-left origin
export type Anchor = { start: number; end: number }; // character offsets into Fixture.text (HTML notices, D-37)
export type Sentence = { page: number; text_orig: string; section_path: string[]; section_titles: string[]; boxes: Box[]; anchor?: Anchor };
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
  normalized?: Record<string, unknown> | null; // the stored normalized value; absent in older fixtures
  items: Item[];
  citations: string[];
  checks: Check[];
};
export type Fixture = {
  doc_id: string;
  pdf: string;
  format?: "pdf" | "html"; // absent means pdf
  text?: string; // HTML only: the extracted text the anchors index into; shown as plain text, never parsed as HTML
  en_summary?: Anchor | null; // HTML only: the page's own English Summary section, when it has one
  model_id?: string | null; // registry id of the model that produced these answers (D-99); absent for the fixture
  saved?: boolean; // getFields only: main wrote this result to the store (D-121)
  doc_type?: string; // what the sidecar read from the first page (D-92); not part of the stored fields JSON
  fields: Field[];
  sentences: Record<string, Sentence>;
};
