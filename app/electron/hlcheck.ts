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
type Anchor = { start: number; end: number };
type Fx = {
  fields: { field: string; value_ja?: string | null; citations?: string[]; items?: { citations?: string[] }[] }[];
  sentences: Record<string, { page: number; text_orig: string; boxes: Box[]; anchor?: Anchor }>;
  text?: string;
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

// The HTML text viewer: each highlighted piece is a .thl span with data-start and data-end, offsets in code points
// (app/src/textmath.ts). Returns the pieces' offsets, their text, and whether the first one is on screen.
const READ_TEXT = `(() => {
  const holder = document.querySelector(".textscroll").getBoundingClientRect();
  const pieces = [...document.querySelectorAll(".thl")];
  const r = pieces[0]?.getBoundingClientRect();
  return {
    toolbar: null, overlay: [],
    pieces: pieces.map((x) => ({ start: Number(x.dataset.start), end: Number(x.dataset.end), text: x.textContent })),
    visible: !!r && r.bottom > holder.top && r.top < holder.bottom,
  };
})()`;

// Exact comparison against the stored anchor. Pieces must cover every character of [start, end) except the line breaks
// between paragraphs, start where the anchor starts and end where it ends, and spell the cited sentence. Only booleans
// and offsets leave this function, never text.
function htmlRow(seen: { pieces: { start: number; end: number; text: string }[]; visible: boolean }, fx: Fx, s: { text_orig: string; anchor?: Anchor } | undefined) {
  const a = s?.anchor ?? null;
  const cps = Array.from(fx.text ?? "");
  const ps = seen.pieces;
  const got = ps.length ? { start: Math.min(...ps.map((x) => x.start)), end: Math.max(...ps.map((x) => x.end)) } : null;
  const want = a ? cps.slice(a.start, a.end).filter((c) => c !== "\n").length : 0;
  const have = ps.reduce((n, x) => n + (x.end - x.start), 0);
  const strip = (t: string) => t.replace(/\n/g, "");
  return {
    html: {
      highlighted: got, stored: a, pieces: ps.length, visible: seen.visible,
      offsets_exact: !!a && !!got && got.start === a.start && got.end === a.end && have === want,
      text_matches: !!s && strip(ps.map((x) => x.text).join("")) === strip(s.text_orig),
    },
  };
}

export async function runHighlightCheck(
  win: BrowserWindow,
  dir: string,
  pdf: string,
  getFields: (docId: string) => Promise<unknown>,
): Promise<void> {
  const isHtml = /\.html?$/i.test(pdf);
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
    await waitFor(`document.querySelector(".fhead") && document.querySelector("${isHtml ? ".textdoc" : ".page canvas"}")`, 900000);
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
      const seen = await js(isHtml ? READ_TEXT : READ);
      const shot = `${prefix}_${f.field}.png`;
      fs.writeFileSync(path.join(dir, shot), (await win.webContents.capturePage()).toPNG());
      rows.push({
        doc: prefix, field: f.field, sentence: id,
        card_page: Number(/\d+/.exec(clicked.card ?? "")?.[0]) || null,
        same_sentence: clicked.ja === s.text_orig, // the chip clicked is the sentence whose boxes are compared
        toolbar_page: seen.toolbar, overlay: seen.overlay,
        stored: s.boxes, stored_page: s.page, shot,
        ...(isHtml ? htmlRow(seen, fx, s) : {}),
      });
      save();
      console.log(`hlcheck ${prefix}: ${f.field} clicked, ${isHtml ? `pieces ${seen.pieces.length}` : `overlay rects ${seen.overlay.length}`}`);
    }
    // Deadlines tab: click up to 4 rows. A row carries the compared sentence id in data-sid and its page in the p. chip.
    if (!only || only === "deadlines") {
      await js(`document.querySelector(".field.open .fhead")?.click()`);
      await js(`[...document.querySelectorAll("[role=tab]")].find((x) => x.textContent === "Deadlines")?.click()`);
      await sleep(500);
      const n = await js(`document.querySelectorAll(".dlrow").length`);
      for (let k = 0; k < n; k++) console.log(`hlcheck ${prefix}: deadlines row ${k} text: ${await js(`document.querySelectorAll(".dlrow")[${k}]?.innerText.replace(/\\s+/g, " | ")`)}`);
      console.log(`hlcheck ${prefix}: deadlines tab rows ${n}, empty state ${await js(`!!document.querySelector(".empty")`)}`);
      for (let k = 0; k < Math.min(n, 4); k++) {
        const got = await js(
          `(() => { const b = document.querySelectorAll(".dlrow")[${k}]; if (!b || b.disabled) return null; b.click(); ` +
            `return { sid: b.dataset.sid, card: b.querySelector(".pgchip")?.textContent, kind: b.querySelector(".dlkind")?.textContent }; })()`,
        );
        if (!got) { console.log(`hlcheck ${prefix}: deadlines row ${k} skipped (disabled)`); continue; }
        await sleep(1500);
        const seen = await js(isHtml ? READ_TEXT : READ);
        const shot = `${prefix}_deadlines_tab_${k}.png`;
        fs.writeFileSync(path.join(dir, shot), (await win.webContents.capturePage()).toPNG());
        const s = fx.sentences[got.sid];
        rows.push({
          doc: prefix, field: `deadlines_tab:${k}`, sentence: got.sid,
          card_page: Number(/\d+/.exec(got.card ?? "")?.[0]) || null,
          same_sentence: !!s && (isHtml ? !!s.anchor : s.page === (Number(/\d+/.exec(got.card ?? "")?.[0]) || null)),
          toolbar_page: seen.toolbar, overlay: seen.overlay,
          stored: s?.boxes ?? [], stored_page: s?.page ?? null, shot,
          ...(isHtml ? htmlRow(seen, fx, s) : {}),
        });
        save();
        console.log(`hlcheck ${prefix}: deadlines row ${k} (${got.kind}) clicked, ${isHtml ? `pieces ${seen.pieces.length}` : `overlay rects ${seen.overlay.length}`}`);
      }
    }
    // With SHIORI_EXPORT_DIR set (main.ts writes there instead of opening the dialog), click Export and report the note shown.
    if (process.env.SHIORI_EXPORT_DIR) {
      await js(`document.querySelector(".exportbtn")?.click()`);
      await sleep(2500);
      console.log(`hlcheck ${prefix}: export note: ${await js(`document.querySelector("[role=status]")?.textContent ?? ""`)}`);
    }
    // SHIORI_HLCHECK_OPENCAL=1 also clicks Open in Calendar (opens the saved .ics with the default app).
    if (process.env.SHIORI_EXPORT_DIR && process.env.SHIORI_HLCHECK_OPENCAL) {
      const r = await js(`(() => { const b = [...document.querySelectorAll("button")].find((x) => x.textContent?.trim() === "Open in Calendar"); if (!b) return "button hidden"; b.click(); return "clicked"; })()`);
      await sleep(3000);
      console.log(`hlcheck ${prefix}: open in calendar: ${r}`);
    }
    console.log(`hlcheck ${prefix}: done, ${rows.length} clicks`);
  } catch (e) {
    console.log(`hlcheck ${prefix}: error ${(e as Error).message}`);
    process.exitCode = 1;
  }
  save();
  app.quit(); // quit, not exit: will-quit stops llama-server and the sidecar
}
