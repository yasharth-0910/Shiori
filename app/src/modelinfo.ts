// Plain functions behind the model picker (D-99): what the "i" card says, and the key a result is stored under.
// Only figures a report in the repo has are shown; with none the card says so.
import type { ModelInfo } from "./shiori.d.ts";

export const NOT_MEASURED = "not measured on this machine type";

const gb = (bytes: number) => (bytes > 0 ? `${(bytes / 1e9).toFixed(2)} GB` : "not yet recorded");

/** Label and value rows of the tooltip card, in display order. */
export function infoRows(m: ModelInfo): [string, string][] {
  const ram = m.minRamGb > 0 ? `at least ${m.minRamGb} GB, ${m.recommendedRamGb} GB recommended` : "not yet recorded";
  return [
    ["Model", m.name],
    ["Parameters", m.parameters],
    ["Quantization", m.quantization],
    ["File size", gb(m.sizeBytes)],
    ["License", m.licenseNote ? `${m.license} (${m.licenseNote})` : m.license],
    ["RAM needed", ram],
    ["Best for", m.bestFor],
    ["Measured", m.measured.length ? m.measured.map((x) => `${x.text} [${x.source}]`).join("; ") : NOT_MEASURED],
  ];
}

/** The option's visible text: installed ones are plain, the others say why they cannot be picked. */
export const optionLabel = (m: ModelInfo) => (m.installed ? m.name : `${m.name} (not installed)`);

/** A document's result is stored per document and per model, so another model's answers are never shown as this one's. */
export const resultKey = (docId: string, modelId: string | null | undefined) => `${docId}:${modelId ?? "none"}`;
