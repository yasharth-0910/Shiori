// Shape of fixture.json, written by scripts/export_app_fixture.py.
export type Box = { page: number; bbox: [number, number, number, number] }; // PDF points, top-left origin
export type Citation = { id: string; page: number; text_ja: string; boxes: Box[] };
export type Field = {
  field: string;
  status: "present" | "absent" | "see_other_document";
  value_en: string | null;
  value_ja: string | null;
  citations: Citation[];
};
export type Fixture = { doc_id: string; pdf: string; fields: Field[] };
