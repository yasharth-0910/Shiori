// Model registry (D-99): one entry per local model the app knows, a validator, and the pure
// recommendation function. No imports, so tests and the renderer (types only) can use it.
// Every figure under `measured` comes from a report in this repo; `source` names it. A model
// with nothing measured shows "not measured on this machine type" in the picker. Never put a
// speed or quality number here that no report has. `url` is the pinned download URL (repo
// and revision from docs/sources.md section 5; D-100) and `sha256` is the file's SHA-256: the
// hub's own LFS hash, checked equal to `shasum -a 256` of the file in models/ on 2026-11-22.
// An entry with an empty url shows "download not available yet" on the Setup screen.

export type Measured = { text: string; source: string };
export type ModelEntry = {
  id: string;
  name: string;
  file: string; // file name expected in the models folder
  parameters: string;
  quantization: string;
  sizeBytes: number;
  license: string; // "not yet recorded" when the notes do not say
  licenseNote?: string;
  minRamGb: number;
  recommendedRamGb: number;
  platformNotes: string[];
  bestFor: string;
  rank: number; // preference when several fit a machine: 1 is best (dev list-field rows, D-74)
  url: string; // pinned https URL, "" when none is recorded
  sha256: string; // always set: 64 lowercase hex
  measured: Measured[];
};
export type Facts = { totalRamGb: number; arch: string; platform: string };
export type Recommendation = { id: string; reason: string };

const DEV = "M4 Mac"; // the only machine anything was measured on

export const REGISTRY: ModelEntry[] = [
  {
    id: "qwen3.5-9b",
    name: "Qwen3.5-9B",
    file: "Qwen3.5-9B-Q4_K_M.gguf",
    parameters: "9B",
    quantization: "Q4_K_M",
    sizeBytes: 5680522464,
    license: "Apache-2.0",
    minRamGb: 16,
    recommendedRamGb: 24,
    platformNotes: ["Apple Silicon with 24 GB or more (where it was measured)", "Windows 16 GB without GPU: runs, but a short document took 211 s on the M4 CPU, which is optimistic for a laptop CPU"],
    bestFor: "Most accurate on the dev set; the model the extractor was tuned with",
    rank: 1,
    url: "https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q4_K_M.gguf",
    sha256: "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8",
    measured: [
      { text: `Median 70 s per document on 50 short tenders (${DEV})`, source: "data/cache/gemini_compare/lists_report.md (local, not committed)" },
      { text: "19 of 42 list-field rows right on the 14 dev documents (a fit, not a forecast)", source: "D-74" },
      { text: "Peak RAM 6.6 GB on the GPU, 6.9 GB CPU only", source: "D-34" },
    ],
  },
  {
    id: "gemma-4-e4b",
    name: "Gemma 4 E4B-it",
    file: "gemma-4-E4B-it-Q4_K_M.gguf",
    parameters: "E4B",
    quantization: "Q4_K_M",
    sizeBytes: 4977171584,
    license: "Apache-2.0",
    licenseNote: "From the upstream model card; the Unsloth GGUF repo was not re-checked (D-70 open question)",
    minRamGb: 16,
    recommendedRamGb: 16,
    platformNotes: ["Windows 16 GB without GPU (a short document took 139 s on the M4 CPU, optimistic)", "Apple Silicon 16 GB or more"],
    bestFor: "Smaller and faster; one row behind Qwen3.5-9B on dev",
    rank: 2,
    url: "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/bfc15c382204943c3a8fff0c750b94ae2364d7a3/gemma-4-E4B-it-Q4_K_M.gguf",
    sha256: "85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87",
    measured: [
      { text: "18 of 42 list-field rows right on the 14 dev documents (a fit, not a forecast)", source: "D-74" },
      { text: "Peak RAM 5.6 GB on the GPU, 5.2 GB CPU only", source: "D-34" },
    ],
  },
  {
    id: "qwen3-swallow-8b",
    name: "Qwen3-Swallow-8B-RL-v0.2",
    file: "Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf",
    parameters: "8B",
    quantization: "Q4_K_M",
    sizeBytes: 5027785312,
    license: "Apache-2.0",
    minRamGb: 16,
    recommendedRamGb: 24,
    platformNotes: ["Needs 8.8 GB peak on CPU, over the 8 GB budget for a 16 GB laptop (D-34)"],
    bestFor: "Japanese-tuned; kept as a cross-check model, not for everyday use",
    rank: 3,
    url: "https://huggingface.co/mmnga-o/Qwen3-Swallow-8B-RL-v0.2-gguf/resolve/3fc755c6ab3780ebad6671130fc1b630bbd1575b/Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf",
    sha256: "1d76889f8626ab2d03e8feab8a9d394f6d91039fa6225bd27509e4334e78fa9a",
    measured: [
      { text: "2 of 39 list-field rows verified in the same run where Qwen3.5-9B had 10 of 39", source: "eval/reports/model_compare_list_fields.md" },
      { text: "Peak RAM 7.8 GB on the GPU, 8.8 GB CPU only", source: "D-34" },
    ],
  },
];

/** Problems with a registry, empty when it is fine. */
export function validateRegistry(list: ModelEntry[]): string[] {
  const bad: string[] = [];
  const seen = new Set<string>();
  for (const m of list) {
    const at = m.id || "(no id)";
    for (const k of ["id", "name", "file", "parameters", "quantization", "license", "bestFor"] as const) if (!m[k]) bad.push(`${at}: ${k} is empty`);
    if (seen.has(m.id) || seen.has(`file:${m.file}`)) bad.push(`${at}: id or file repeated`);
    seen.add(m.id);
    seen.add(`file:${m.file}`);
    if (!(m.sizeBytes > 0)) bad.push(`${at}: sizeBytes must be positive`);
    if (!(m.minRamGb > 0) || m.recommendedRamGb < m.minRamGb) bad.push(`${at}: RAM figures do not add up`);
    if (!m.sha256) bad.push(`${at}: sha256 is empty`);
    else if (!/^[0-9a-f]{64}$/.test(m.sha256)) bad.push(`${at}: sha256 is not 64 lowercase hex characters`);
    if (m.url && !m.sha256) bad.push(`${at}: a download url needs a sha256`);
    if (m.url && !/^https:\/\/[^/\s]+\//.test(m.url)) bad.push(`${at}: url must be https`);
    for (const x of m.measured) if (!x.text || !x.source) bad.push(`${at}: a measured figure needs text and a source`);
  }
  return bad;
}

const gb = (bytes: number) => `${(bytes / 1e9).toFixed(2)} GB`;
export { gb as sizeText };

/** Default model for a machine: the best-ranked one whose recommended RAM fits, else one whose minimum fits, else the smallest file. Local facts only. */
export function recommend(f: Facts, list: ModelEntry[] = REGISTRY): Recommendation | null {
  if (!list.length) return null;
  const ram = Math.round(f.totalRamGb);
  const byRank = [...list].sort((a, b) => a.rank - b.rank);
  const where = `${ram} GB RAM, ${f.platform === "darwin" && f.arch === "arm64" ? "Apple Silicon" : `${f.platform} ${f.arch}, expect CPU only`}`;
  const roomy = byRank.find((m) => m.recommendedRamGb <= ram);
  if (roomy) return { id: roomy.id, reason: `${where}: ${roomy.name} is the best-scoring model that fits its recommended ${roomy.recommendedRamGb} GB.` };
  const tight = byRank.find((m) => m.minRamGb <= ram);
  if (tight) return { id: tight.id, reason: `${where}: below the recommended RAM of the larger models, so ${tight.name}, which needs at least ${tight.minRamGb} GB.` };
  const small = [...list].sort((a, b) => a.sizeBytes - b.sizeBytes)[0] as ModelEntry;
  return { id: small.id, reason: `${where}: under the ${small.minRamGb} GB every model here was planned for. ${small.name} is the smallest file; it may be slow or fail to load.` };
}
