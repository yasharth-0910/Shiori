// Offset math for the text viewer, TextView.tsx (HTML notices, D-37). Offsets are Unicode code points, the way Python counts
// them in Document.text, not UTF-16 units: a rare kanji outside the BMP (𠮷) is one position here and two in a JS string.
export type Range = { start: number; end: number };
export type Mark = Range & { kind: "hl" | "hit" | "cur" };
export type Slice = Range & { text: string; kinds: Mark["kind"][] };

export const codepoints = (text: string): string[] => Array.from(text);

// Paragraphs are the lines of Document.text (one per element or <br>), with their offsets. Empty lines are skipped.
export function paragraphs(cps: string[]): Range[] {
  const out: Range[] = [];
  let start = 0;
  for (let i = 0; i <= cps.length; i++) {
    if (i === cps.length || cps[i] === "\n") {
      if (i > start) out.push({ start, end: i });
      start = i + 1;
    }
  }
  return out;
}

// One paragraph cut at every mark edge inside it. A mark that spans two paragraphs gives one slice run in each; the
// newline between them is not part of any paragraph. Slices are plain strings: the caller renders them as text nodes.
export function slices(cps: string[], p: Range, marks: Mark[]): Slice[] {
  const cuts = new Set([p.start, p.end]);
  for (const m of marks) {
    for (const x of [m.start, m.end]) if (x > p.start && x < p.end) cuts.add(x);
  }
  const at = [...cuts].sort((a, b) => a - b);
  const out: Slice[] = [];
  for (let k = 0; k + 1 < at.length; k++) {
    const [a, b] = [at[k]!, at[k + 1]!];
    out.push({ start: a, end: b, text: cps.slice(a, b).join(""), kinds: marks.filter((m) => m.start <= a && m.end >= b).map((m) => m.kind) });
  }
  return out;
}

// NFKC per character so full-width digits and letters match what a person types; each folded character keeps its offset.
const fold = (ch: string) => ch.normalize("NFKC").toLowerCase();

export function findAll(cps: string[], query: string): Range[] {
  const q = Array.from(query.trim()).map(fold).join("");
  if (!q) return [];
  let flat = "";
  const owner: number[] = [];
  cps.forEach((ch, i) => {
    const g = fold(ch);
    flat += g;
    for (let k = 0; k < g.length; k++) owner.push(i);
  });
  const out: Range[] = [];
  for (let at = flat.indexOf(q); at >= 0; at = flat.indexOf(q, at + q.length)) {
    out.push({ start: owner[at]!, end: owner[at + q.length - 1]! + 1 });
  }
  return out;
}
