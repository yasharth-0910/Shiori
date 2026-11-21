// Dev-only highlight check, driven by SHIORI_HLCHECK=<dir> together with SHIORI_PICK (both ignored in a packaged
// app, see main.ts). Adds the picked PDF, waits for the Workspace, then for each target field opens its card, clicks
// the first citation chip, saves a window screenshot after the highlight is drawn and records what the page shows
// next to the sidecar's stored boxes. Writes <dir>/raw_<doc prefix>.json; scripts/highlight_check.py turns it into
// the table. No document text is logged or written: only ids, page numbers and rectangles.
import { app, type BrowserWindow } from "electron";
import * as fs from "node:fs";
import * as path from "node:path";
import { createHash } from "node:crypto";

type Bbox = [number, number, number, number];
type Box = { page: number; bbox: Bbox };
type Fx = {
  fields: { field: string; value_ja?: string | null; citations?: string[]; items?: { citations?: string[] }[] }[];
  sentences: Record<string, { page: number; text_orig: string; boxes: Box[] }>;
};

// Card labels, copied from app/src/fields.ts (only the fields this check can click).
const LABEL: Record<string, string> = {
  title: "Title", issuer_org: "Issuer", notice_date: "Notice date", performance_period: "Performance period",
  tax_basis: "Tax basis", bid_bond: "Bid bond", performance_bond: "Performance bond", eligibility: "Eligibility",
  deadlines: "Deadlines", required_documents: "Required documents", submission_modes: "Submission methods",
  contact: "Contact", contracting_officer: "Contracting officer", delivery_deadline: "Delivery deadline",
  delivery_location: "Delivery location", scope_summary: "Scope",
};
const MAX_CLICKS = 12;

// Read in the page after a click. No ${} in here: it is a plain page script. BASE 1.4 is PdfView's CSS px per point at 100%.
const READ = `(() => {
  const zoom = parseFloat(document.querySelector(".zoomno")?.textContent || "100");
  const scale = 1.4 * zoom / 100;
  const holder = document.querySelector(".pdf").getBoundingClientRect();
  return {
    toolbar: Number(document.querySelector(".pageno input")?.value),
    overlay: [...document.querySelectorAll(".hl")].map((h) => {
      const pg = h.closest(".page"), r = h.getBoundingClientRect();
      const l = parseFloat(h.style.left), t = parseFloat(h.style.top);
      return {
        page: Number(pg.dataset.page),
        bbox: [l / scale, t / scale, (l + parseFloat(h.style.width)) / scale, (t + parseFloat(h.style.height)) / scale],
        pw: parseFloat(pg.style.width) / scale, ph: parseFloat(pg.style.height) / scale,
        visible: r.bottom > holder.top && r.top < holder.bottom && r.right > holder.left && r.left < holder.right,
      };
    }),
  };
})()`;

export async function runHighlightCheck(
  win: BrowserWindow,
  dir: string,
  pdf: string,
  getFields: (docId: string) => Promise<unknown>,
): Promise<void> {
  const docId = createHash("sha256").update(fs.readFileSync(pdf)).digest("hex");
  const prefix = docId.slice(0, 8);
  fs.mkdirSync(dir, { recursive: true });
  const js = (code: string) => win.webContents.executeJavaScript(code) as Promise<any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
  const waitFor = (expr: string, ms: number) =>
    js(`new Promise((res, rej) => { const t0 = Date.now(); const t = setInterval(() => { if (${expr}) { clearInterval(t); res(true); } else if (Date.now() - t0 > ${ms}) { clearInterval(t); rej(new Error("wait_timeout")); } }, 200); })`);
  const rows: unknown[] = [];
  const save = () => fs.writeFileSync(path.join(dir, `raw_${prefix}.json`), JSON.stringify(rows, null, 1));
  try {
    await waitFor(`[...document.querySelectorAll("button")].some((x) => x.textContent === "Add document")`, 30000);
    await js(`[...document.querySelectorAll("button")].find((x) => x.textContent === "Add document").click()`);
    console.log(`hlcheck ${prefix}: added, waiting for extraction`);
    await waitFor(`document.querySelector(".fhead") && document.querySelector(".page canvas")`, 900000);
    await sleep(2000); // let the first pages draw
    const fx = (await getFields(docId)) as Fx;
    console.log(`hlcheck ${prefix}: workspace up, ${fx.fields.length} fields`);

    // A scalar's cited sentence that holds its value comes first in the card (app/src/fieldview.ts valueFirst).
    const idsOf = (f: Fx["fields"][number]) => {
      if (f.items?.length) return f.items.flatMap((i) => i.citations ?? []);
      const strip = (t: string) => t.replace(/\s+/g, "");
      const ids = f.citations ?? [];
      const v = f.value_ja ? strip(f.value_ja) : "";
      const i = v ? ids.findIndex((id) => strip(fx.sentences[id]?.text_orig ?? "").includes(v)) : -1;
      return i > 0 ? [ids[i]!, ...ids.slice(0, i), ...ids.slice(i + 1)] : ids;
    };
    const firstId = (f: Fx["fields"][number]) => idsOf(f).find((id) => id in fx.sentences);
    const by = new Map(fx.fields.map((f) => [f.field, f]));
    const answered = (names: string[], lists = false) =>
      names.flatMap((n) => { const f = by.get(n); return f && firstId(f) && (!lists || f.items?.length) ? [f] : []; });
    const targets = [
      ...answered(["title", "issuer_org", "notice_date", "performance_period", "tax_basis"]),
      ...answered(["bid_bond", "performance_bond"]).slice(0, 1),
      ...answered(["eligibility", "deadlines", "required_documents", "submission_modes", "contact"], true),
      ...answered(["contracting_officer", "delivery_deadline", "delivery_location", "scope_summary"]),
    ];

    const only = process.env.SHIORI_HLCHECK_FIELD;
    for (const f of targets) {
      if (only && f.field !== only) continue;
      if (rows.length >= MAX_CLICKS) break;
      const id = firstId(f) as string;
      const s = fx.sentences[id]!;
      const head = `[...document.querySelectorAll(".fhead")].find((x) => x.querySelector(".flabel")?.textContent === ${JSON.stringify(LABEL[f.field])})`;
      await js(`document.querySelector(".field.open .fhead")?.click()`); // close any open card: no highlight left over
      await sleep(200);
      const clicked = await js(
        `(() => { const h = ${head}; if (!h) return null; h.click(); return new Promise((r) => setTimeout(() => { ` +
          `const b = [...h.closest(".field").querySelectorAll(".src")].find((x) => !x.disabled); if (!b) return r(null); b.click(); ` +
          `r({ card: b.querySelector(".pgchip")?.textContent, ja: b.querySelector(".ja")?.textContent }); }, 300)); })()`,
      );
      if (!clicked) { console.log(`hlcheck ${prefix}: ${f.field} skipped (no card or no chip)`); continue; }
      await sleep(1500); // scroll to the highlight, then the toolbar page settles
      const seen = await js(READ);
      const shot = `${prefix}_${f.field}.png`;
      fs.writeFileSync(path.join(dir, shot), (await win.webContents.capturePage()).toPNG());
      rows.push({
        doc: prefix, field: f.field, sentence: id,
        card_page: Number(/\d+/.exec(clicked.card ?? "")?.[0]) || null,
        same_sentence: clicked.ja === s.text_orig, // the chip clicked is the sentence whose boxes are compared
        toolbar_page: seen.toolbar, overlay: seen.overlay,
        stored: s.boxes, stored_page: s.page, shot,
      });
      save();
      console.log(`hlcheck ${prefix}: ${f.field} clicked, overlay rects ${seen.overlay.length}`);
    }
    console.log(`hlcheck ${prefix}: done, ${rows.length} clicks`);
  } catch (e) {
    console.log(`hlcheck ${prefix}: error ${(e as Error).message}`);
    process.exitCode = 1;
  }
  save();
  app.quit(); // quit, not exit: will-quit stops llama-server and the sidecar
}
