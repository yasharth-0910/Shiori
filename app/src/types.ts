// Shape of fixture.json, written by scripts/export_app_fixture.py.
export type Box = { page: number; bbox: [number, number, number, number] }; // PDF points, top-left origin
export type Sentence = { page: number; text_orig: string; section_path: string[]; section_titles: string[]; boxes: Box[] };
export type Check = { name: string; passed: boolean }; // the pipeline's stored result, never recomputed here
export type Item = { text_ja: string | null; text_en: string | null; citations: string[]; datetime?: string | null };
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
