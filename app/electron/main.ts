// Main process. Serves the built renderer from a local shiori:// scheme (PDF.js needs
// fetch, which file:// blocks) and cancels every request that is not shiori://.
// The renderer gets eleven IPC functions (preload.ts); main owns the file picker, the
// sidecar and its token (D-83), and the model download (D-100).
import { app, BrowserWindow, dialog, ipcMain, protocol, session, shell, type IpcMainInvokeEvent } from "electron";
import * as fs from "node:fs";
import * as path from "node:path";
import { createHash } from "node:crypto";
import * as llama from "./llama";
import { CUSTOM_ID, defaultChoice, discover, modelDirs, realWhere, systemFacts, type Found } from "./discover";
import { recommend, REGISTRY, type ModelEntry } from "./registry";
import * as sidecar from "./sidecar";
import { bundledLlama } from "./paths";
import { runHighlightCheck } from "./hlcheck";
import { createDownloader } from "./download";
import { requestFilter } from "./netfilter";
import { savedCalendar } from "./saved";

const DIST = path.join(__dirname, "..", "dist");
const MIME: Record<string, string> = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".pdf": "application/pdf",
  ".bcmap": "application/octet-stream",
};

protocol.registerSchemesAsPrivileged([
  { scheme: "shiori", privileges: { standard: true, secure: true, supportFetchAPI: true } },
]);

const ID = /^[0-9a-f]{64}$/;
const SENTENCE = /^(?:p\d+_s\d+|h_s\d+|value:title)$/; // a sentence id, as core makes them, or the title value's queue key (D-91)
type Translated =
  | { ok: true; items: Record<string, { en: string; numbers_match: boolean; protected_lost?: boolean }>; done: number; total: number; failed: string[] }
  | { ok: false; reason: "no_model" | "no_document" | "failed" };
const picked = new Map<string, string>(); // document id -> the PDF the user chose; main only
// SHIORI_PICK replaces the picker in dev checks only; a packaged app ignores it (D-84).
const PICK = app.isPackaged ? undefined : process.env.SHIORI_PICK;
// SHIORI_EXPORT_DIR=<dir> makes the export write there instead of opening the save dialog; dev only, like SHIORI_PICK.
const EXPORT_DIR = app.isPackaged ? undefined : process.env.SHIORI_EXPORT_DIR;
// SHIORI_HLCHECK=<dir> (with SHIORI_PICK) runs the highlight check in hlcheck.ts; dev only, like SHIORI_SHOT.
const HLCHECK = app.isPackaged ? undefined : process.env.SHIORI_HLCHECK;

// One backend for the session: llama-server (when it and a model are found, D-99) and the sidecar.
// Started on the first Add document, restarted when the user picks another model, stopped when the app quits.
type Backend = { state: "starting" | "ready" | "failed"; model: boolean; modelId: string | null; modelFile: string | null; note: string | null; error: string | null };
let backend: Backend | null = null;
const jobs = new Map<string, { posted: boolean; error: string | null; cancelled: boolean; finished: boolean }>();
const busy = () => [...jobs.values()].some((j) => !j.finished && !j.cancelled);

// Where model files are looked for: the repo's models/ in dev, the user data folder when packaged.
// SHIORI_MODELS_DIR=<dir> replaces that folder in dev runs only (ignored when packaged), so a download can be tried in an empty one.
const MODELS_DIR = app.isPackaged ? undefined : process.env.SHIORI_MODELS_DIR;
const here = () => {
  const dirs = MODELS_DIR ? [MODELS_DIR] : modelDirs(app.isPackaged, path.join(__dirname, "..", ".."), app.getPath("userData"));
  return { found: discover(realWhere(bundledLlama({ isPackaged: app.isPackaged, platform: process.platform, resourcesPath: process.resourcesPath, userData: app.getPath("userData"), repoRoot: "" })), dirs, app.isPackaged ? "models/ in the app's user data folder" : "models/ in the repo", REGISTRY), dirs };
};
const customEntry = (file: string): ModelEntry => {
  const size = (() => { try { return fs.statSync(file).size; } catch { return 0; } })();
  const nr = "not yet recorded";
  return { id: CUSTOM_ID, name: path.basename(file), file: path.basename(file), parameters: nr, quantization: nr, sizeBytes: size, license: nr, minRamGb: 0, recommendedRamGb: 0, platformNotes: [], bestFor: "Set with SHIORI_MODEL", rank: 99, url: "", sha256: "", measured: [] };
};

function ensureBackend(choice: string | null, found: Found): Backend {
  if (backend && backend.modelId === choice) return backend;
  const previous = backend;
  const b: Backend = { state: "starting", model: false, modelId: choice, modelFile: null, note: null, error: null };
  backend = b;
  if (previous) jobs.clear(); // a new sidecar does not know the old documents; nothing of the old model is reused
  void (async () => {
    if (previous) {
      sidecar.stop(); // only processes this app started
      await llama.stopAndWait();
    }
    const file = choice === CUSTOM_ID ? found.custom : choice ? found.installed[choice] : undefined;
    let l: llama.Llama | null = null;
    if (!found.binary || !file) b.note = "Model not set up";
    else {
      b.model = true;
      b.modelFile = path.basename(file);
      try {
        l = await llama.start({ binary: found.binary, model: file });
      } catch (e) {
        b.model = false;
        b.note = `Model failed to start (${(e as Error).message})`; // a short code, no path
      }
    }
    try {
      await sidecar.start(l);
      b.state = "ready";
    } catch (e) {
      llama.stop();
      b.state = "failed";
      b.error = (e as Error).message;
    }
  })();
  return b;
}

function serve(request: Request): Response {
  const rel = decodeURIComponent(new URL(request.url).pathname);
  // A chosen PDF is served by its document id, never by path (nothing is copied into dist).
  const doc = /^\/doc\/([0-9a-f]{64})\.pdf$/.exec(rel);
  if (doc) {
    const file = picked.get(doc[1] as string);
    if (!file || !fs.existsSync(file)) return new Response("not found", { status: 404 });
    return new Response(new Uint8Array(fs.readFileSync(file)), { headers: { "content-type": "application/pdf" } });
  }
  const file = path.normalize(path.join(DIST, rel === "/" ? "index.html" : rel));
  if (!file.startsWith(DIST + path.sep) || !fs.existsSync(file)) return new Response("not found", { status: 404 });
  const type = MIME[path.extname(file)] ?? "application/octet-stream";
  return new Response(new Uint8Array(fs.readFileSync(file)), { headers: { "content-type": type } });
}

// Dev checks only (off in a packaged app, like SHIORI_SHOT): SHIORI_SHOT_SIZE=640x860 sets the window size.
const devSize = (app.isPackaged ? undefined : process.env.SHIORI_SHOT_SIZE)?.split("x").map(Number) as [number, number] | undefined;

async function createWindow(): Promise<void> {
  const win = new BrowserWindow({
    width: devSize?.[0] ?? 1280,
    height: devSize?.[1] ?? 860,
    show: !process.env.SHIORI_SHOT && !HLCHECK,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (e) => e.preventDefault());
  await win.loadURL("shiori://app/");
  if (HLCHECK && PICK) void runHighlightCheck(win, HLCHECK, PICK, (id) => sidecar.call("GET", `/documents/${id}/fields`));

  // Dev check only: SHIORI_SHOT=<png> clicks chip number SHIORI_CHIP (default 0), saves the window, quits.
  const shot = app.isPackaged ? undefined : process.env.SHIORI_SHOT;
  // Two more dev checks, off in a packaged app like SHIORI_PICK and SHIORI_SHOT:
  // SHIORI_SHOT_STAGE=extract (or a comma list) also saves <shot>-extract.png when the Processing screen first reaches that stage;
  // SHIORI_SHOT_OPEN=<field label or id> waits until the translation queue is empty (or 400 s), saves <shot>-list.png,
  // opens that field and then saves the usual shot.
  const shotStage = app.isPackaged ? undefined : process.env.SHIORI_SHOT_STAGE;
  const shotOpen = app.isPackaged ? undefined : process.env.SHIORI_SHOT_OPEN;
  // SHIORI_SHOT_WHEN="label::<js expression>|||label2::<expr>": saves <shot>-<label>.png the first time each expression is
  // true in the page, in order, logs a layout and animation probe, then quits (or, with SHIORI_SHOT_STAGE too, goes on to the end). SHIORI_SHOT_CANCEL=<seconds>: clicks Cancel that many seconds after the
  // first "Now reading" card shows, logs how long the Library takes to come back, saves <shot>-cancelled.png, waits 25 s, quits.
  // SHIORI_SHOT_MEDIA=reduce emulates prefers-reduced-motion.
  const shotWhen = app.isPackaged ? undefined : process.env.SHIORI_SHOT_WHEN;
  const shotCancel = app.isPackaged ? undefined : process.env.SHIORI_SHOT_CANCEL;
  const shotMedia = app.isPackaged ? undefined : process.env.SHIORI_SHOT_MEDIA;
  if (shot) {
    win.webContents.on("console-message", (e) => console.log("renderer:", e.message));
    setTimeout(() => { console.log("shot timeout"); void win.webContents.executeJavaScript(`document.body.innerText.slice(0,300) + " canvases=" + document.querySelectorAll("canvas").length`).then((t) => { console.log(t); app.exit(1); }); }, PICK ? 900000 : 30000);
    if (shotMedia === "reduce") {
      win.webContents.debugger.attach("1.3");
      await win.webContents.debugger.sendCommand("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
    }
    if (PICK) {
      // With SHIORI_PICK also set: click "Add document", log the stage shown on the Processing screen each time it changes.
      await win.webContents.executeJavaScript(
        `new Promise(r => { const t = setInterval(() => { const b = [...document.querySelectorAll("button")].find(x => x.textContent === "Add document"); if (b) { clearInterval(t); b.click(); r(); } }, 100); }); ` +
          `window.__seen = []; setInterval(() => { const m = document.querySelector(".stepper .step.active"); ` +
          `const t = m && m.textContent; if (t && window.__seen.at(-1) !== t) { window.__seen.push(t); console.log("screen: " + t); } }, 20);`,
      );
    }
    // A comma list works too (loading_model,extract,done): one shot per stage, each saved the first time it shows.
    for (const stg of shotStage?.split(",") ?? []) {
      const png = shot.replace(/(\.png)?$/, "-" + stg + ".png");
      const t = setInterval(() => {
        void win.webContents.executeJavaScript(`document.querySelector(".stepper")?.dataset.stage`).then(async (st) => {
          if (st !== stg) return;
          clearInterval(t);
          fs.writeFileSync(png, (await win.webContents.capturePage()).toPNG());
          console.log("stage shot saved: " + stg);
        });
      }, 300);
    }
    const waitFor = (expr: string) =>
      win.webContents.executeJavaScript(`new Promise(r => { const t = setInterval(() => { if (${expr}) { clearInterval(t); r(true); } }, 200); })`);
    const probe = `JSON.stringify({ width: innerWidth, columns: getComputedStyle(document.querySelector(".processing")).gridTemplateColumns, ` +
      `reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches, evAnimation: document.querySelector(".ev:not(.scan)") && getComputedStyle(document.querySelector(".ev:not(.scan)")).animationName, ` +
      `skeletonAnimation: document.querySelector(".sk") && getComputedStyle(document.querySelector(".sk")).animationName, ` +
      `nameLines: document.querySelector(".pname") && Math.round(document.querySelector(".pname").getBoundingClientRect().height / parseFloat(getComputedStyle(document.querySelector(".pname")).lineHeight)), ` +
      `cards: [...document.querySelectorAll(".evlist > .ev")].map(c => c.className + ":" + (c.dataset.field ?? "")), pageScrollsSideways: document.documentElement.scrollWidth > innerWidth })`;
    for (const item of shotWhen ? shotWhen.split("|||") : []) {
      const [label, expr] = item.split("::") as [string, string];
      await waitFor(expr);
      await new Promise((r) => setTimeout(r, 600)); // let the card finish arriving
      fs.writeFileSync(shot.replace(/(\.png)?$/, "-" + label + ".png"), (await win.webContents.capturePage()).toPNG());
      console.log("when shot saved: " + label + " " + (await win.webContents.executeJavaScript(probe)));
    }
    if (shotWhen && !shotStage) return app.quit(); // quit, not exit: will-quit stops the llama-server and the sidecar; with SHIORI_SHOT_STAGE too the run goes on to the end
    if (shotCancel) {
      await waitFor(`document.querySelector(".ev.read.now")`);
      await new Promise((r) => setTimeout(r, (Number(shotCancel) || 0) * 1000)); // SHIORI_SHOT_CANCEL=<seconds to wait into the model call>
      const t0 = Date.now();
      console.log("cancel: clicking, screen shows: " + (await win.webContents.executeJavaScript(`document.querySelector(".stepper .step.active")?.textContent`)));
      await win.webContents.executeJavaScript(`[...document.querySelectorAll("button")].find((b) => b.textContent === "Cancel")?.click()`);
      await new Promise((r) => setTimeout(r, 1000));
      console.log("cancel: 1 s later the button says: " + (await win.webContents.executeJavaScript(`[...document.querySelectorAll(".pfoot button")].map((b) => b.textContent).join()`)));
      await waitFor(`[...document.querySelectorAll("button")].some((b) => b.textContent === "Add document")`);
      console.log(`cancel: Library is back after ${((Date.now() - t0) / 1000).toFixed(1)} s`);
      fs.writeFileSync(shot.replace(/(\.png)?$/, "-cancelled.png"), (await win.webContents.capturePage()).toPNG());
      await new Promise((r) => setTimeout(r, 25000));
      console.log("cancel: 25 s later the screen shows: " + (await win.webContents.executeJavaScript(`document.body.innerText.slice(0, 120).replace(/\\n/g, " | ")`)));
      return app.quit();
    }
    const chip = Number(process.env.SHIORI_CHIP ?? 0);
    await win.webContents.executeJavaScript(
      `new Promise(r => { const t = setInterval(() => { const c = document.querySelectorAll(".chip"); ` +
        `if ((c.length || ${!!PICK}) && document.querySelectorAll("canvas").length) { clearInterval(t); c[${chip}]?.click(); ` +
        `console.log("rows: " + document.querySelectorAll(".field").length + " | " + [...document.querySelectorAll(".counts button")].map(b => b.textContent).join(" / ") + " pills: " + document.querySelectorAll(".pill").length); setTimeout(r, 1500); } }, 200); })`,
    );
    if (shotOpen) {
      // Wait for "English: n of m sentences" to appear and then go (a finished queue shows nothing), at most 400 s.
      await win.webContents.executeJavaScript(
        `new Promise(r => { const t0 = Date.now(); let seen = false; const t = setInterval(() => { const on = document.body.innerText.includes("English: "); seen = seen || on; ` +
          `if ((seen && !on) || (!seen && Date.now() - t0 > 20000) || Date.now() - t0 > 400000) { clearInterval(t); r(); } }, 1000); })`,
      );
      fs.writeFileSync(shot.replace(/(\.png)?$/, "-list.png"), (await win.webContents.capturePage()).toPNG());
      const want = JSON.stringify(shotOpen.toLowerCase().replace(/_/g, " "));
      await win.webContents.executeJavaScript(
        `(() => { const h = [...document.querySelectorAll(".fhead")].find(x => x.querySelector(".flabel")?.textContent.toLowerCase() === ${want}); ` +
          `console.log("open: " + (h ? "found" : "no such field")); h?.click(); setTimeout(() => h?.scrollIntoView({ block: "start" }), 100); })()`,
      );
      await new Promise((r) => setTimeout(r, 1500));
    }
    fs.writeFileSync(shot, (await win.webContents.capturePage()).toPNG());
    app.quit();
  }
}

// Only our own window's page may use the bridge.
const own = (e: IpcMainInvokeEvent) => {
  if (!e.senderFrame?.url.startsWith("shiori://app/")) throw new Error("ipc_sender_refused");
};
const docId = (id: unknown): string => {
  if (typeof id !== "string" || !ID.test(id)) throw new Error("bad_doc_id");
  return id;
};

// The model download (D-100): the only network use in the app. Partial files live in the user data folder; a verified
// model is moved into the first models folder. The renderer can only name a registry id.
let downloader: ReturnType<typeof createDownloader> | null = null;
const dl = () => (downloader ??= createDownloader({ registry: REGISTRY, modelsDir: here().dirs[0] as string, tempDir: path.join(app.getPath("userData"), "downloads") }));

const calendar = savedCalendar((f) => shell.openPath(f));

function registerIpc(): void {
  // Asks the user for a PDF (native picker), posts its path to the sidecar, returns the id.
  // SHIORI_PICK=<pdf> stands in for the picker in dev checks (like SHIORI_SHOT); the renderer cannot set it.
  ipcMain.handle("shiori:start", async (e, modelId: unknown) => {
    own(e);
    const { found } = here();
    const rec = recommend(systemFacts());
    let choice: string | null;
    if (modelId === undefined || modelId === null) choice = defaultChoice(found, rec, REGISTRY);
    else if (typeof modelId === "string" && (found.installed[modelId] || (modelId === CUSTOM_ID && found.custom))) choice = modelId;
    else throw new Error("model_not_installed");
    // Switching stops the llama-server this app started, so it waits until nothing is processing.
    if (backend && backend.modelId !== choice && busy()) return { error: "busy" as const };
    let file = PICK;
    if (!file) {
      const win = BrowserWindow.fromWebContents(e.sender);
      const opts = { properties: ["openFile" as const], filters: [{ name: "Tender notice (PDF or saved HTML)", extensions: ["pdf", "html", "htm"] }] };
      const r = win ? await dialog.showOpenDialog(win, opts) : await dialog.showOpenDialog(opts);
      file = r.canceled ? undefined : r.filePaths[0];
    }
    if (!file) return null;
    // The id is the file's SHA-256, the same one the sidecar makes, so the screen can start
    // before the model and the sidecar are up.
    const doc_id = createHash("sha256").update(fs.readFileSync(file)).digest("hex");
    picked.set(doc_id, file);
    const b = ensureBackend(choice, found); // before jobs.set: a model switch clears the old jobs
    jobs.set(doc_id, { posted: false, error: null, cancelled: false, finished: false });
    void (async () => {
      while (b.state === "starting") await new Promise((r) => setTimeout(r, 200));
      const job = jobs.get(doc_id);
      if (!job || job.cancelled || b.state === "failed") return;
      try {
        await sidecar.call("POST", "/documents", { path: file });
        job.posted = true;
        if (job.cancelled) await sidecar.call("POST", `/documents/${doc_id}/cancel`); // cancelled while the post was in flight
      } catch (err) {
        job.error = (err as Error).message;
      }
    })();
    return { doc_id, name: path.basename(file) };
  });
  // `since` is the event cursor from the last call (D-90); the sidecar returns only newer events.
  ipcMain.handle("shiori:status", async (e, id: unknown, since: unknown) => {
    own(e);
    const doc = docId(id);
    const cursor = typeof since === "number" && Number.isInteger(since) && since >= 0 ? since : 0;
    const job = jobs.get(doc);
    if (!job) throw new Error("unknown_document");
    // No backend means the sidecar died (it is only cleared then); the next Add document starts a new one.
    if (!backend) return { doc_id: doc, pages: null, detail: null, stage: "failed", error: "sidecar_exited", events: [], cursor };
    const b = backend;
    // The model's file name and registry id, as the backend was started with them. Nothing else about the model is known here.
    const model = b.model ? b.modelFile : null;
    const base = { doc_id: doc, pages: null, detail: b.note, error: null, model, model_id: b.model ? b.modelId : null, events: [], cursor };
    const fin = <T extends { stage: string }>(r: T): T => {
      if (r.stage === "done" || r.stage === "failed" || r.stage === "cancelled") job.finished = true;
      return r;
    };
    if (job.cancelled && !job.posted) return fin({ ...base, stage: "cancelled" });
    if (b.state === "starting") return { ...base, stage: b.model ? "loading_model" : "queued" };
    if (b.state === "failed" || job.error) return fin({ ...base, stage: "failed", error: b.error ?? job.error });
    if (!job.posted) return { ...base, stage: "queued" };
    const s = await sidecar.call<{ stage: string; detail: string | null }>("GET", `/documents/${doc}/status?since=${cursor}`);
    const running = s.stage !== "done" && s.stage !== "failed" && s.stage !== "cancelled";
    return fin({ ...s, model, model_id: base.model_id, detail: s.detail ?? (running ? b.note : null) });
  });
  // Cancel (D-90): a flag. Before the post it stops the post; after it the sidecar stops at its next stage or model call.
  ipcMain.handle("shiori:cancel", async (e, id: unknown) => {
    own(e);
    const doc = docId(id);
    const job = jobs.get(doc);
    if (!job) throw new Error("unknown_document");
    job.cancelled = true;
    if (job.posted) await sidecar.call("POST", `/documents/${doc}/cancel`);
  });
  // The translation queue (D-85, D-88): `ids` are the sentences of the field just opened, moved to the front; an empty
  // list is a plain poll. Returns what is ready and the counts. Never throws for "no model".
  ipcMain.handle("shiori:translate", async (e, id: unknown, ids: unknown): Promise<Translated> => {
    own(e);
    const doc = docId(id);
    if (!Array.isArray(ids) || ids.length > 200 || !ids.every((i) => typeof i === "string" && SENTENCE.test(i))) throw new Error("bad_sentence_ids");
    if (!jobs.has(doc)) return { ok: false, reason: "no_document" }; // e.g. the fixture demo
    if (!backend?.model) return { ok: false, reason: "no_model" };
    try {
      return { ok: true, ...(await sidecar.call<Omit<Extract<Translated, { ok: true }>, "ok">>("POST", `/documents/${doc}/translate`, { ids })) };
    } catch (err) {
      return { ok: false, reason: (err as Error).message === "sidecar_http_503" ? "no_model" : "failed" };
    }
  });
  // Export (D-98): the renderer builds the text (src/export.ts); main only asks where to save it and writes it.
  // Returns false when the user cancels. Nothing is opened afterwards, and the path and text are never logged.
  ipcMain.handle("shiori:save", async (e, kind: unknown, name: unknown, content: unknown): Promise<boolean> => {
    own(e);
    if (kind !== "csv" && kind !== "ics") throw new Error("bad_export_kind");
    if (typeof name !== "string" || typeof content !== "string" || content.length > 5_000_000) throw new Error("bad_export");
    const safe = path.basename(name).replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_") || `export.${kind}`;
    let file: string | undefined;
    if (EXPORT_DIR) file = path.join(EXPORT_DIR, safe);
    else {
      const win = BrowserWindow.fromWebContents(e.sender);
      const opts = { defaultPath: safe, filters: [kind === "csv" ? { name: "CSV", extensions: ["csv"] } : { name: "Calendar", extensions: ["ics"] }] };
      const r = win ? await dialog.showSaveDialog(win, opts) : await dialog.showSaveDialog(opts);
      file = r.canceled ? undefined : r.filePath;
    }
    if (!file) return false;
    fs.writeFileSync(file, content, "utf8"); // the BOM is U+FEFF in the string and becomes EF BB BF
    calendar.remember(file, kind);
    return true;
  });
  // Open in Calendar (D-98): no arguments. Opens the .ics this session saved, with the default app, and nothing else.
  ipcMain.handle("shiori:open-calendar", async (e): Promise<boolean> => {
    own(e);
    return calendar.openLast();
  });
  // The picker's data (D-99): the registry with what is installed, this machine's recommendation, the default, and
  // what is missing. Local file checks and os facts only. skipPicker is the dev-check path (SHIORI_PICK).
  ipcMain.handle("shiori:models", (e) => {
    own(e);
    const { found } = here();
    const rec = recommend(systemFacts());
    const models = REGISTRY.map((m) => ({ ...m, installed: !!found.installed[m.id] }));
    if (found.custom) models.push({ ...customEntry(found.custom), installed: true });
    return { models, recommended: rec, default: defaultChoice(found, rec, REGISTRY), running: backend?.model ? backend.modelId : null, binaryFound: !!found.binary, expected: found.expected, skipPicker: !!PICK };
  });
  // Download (D-100): one click in the Setup screen. The argument is a registry id and nothing else; the URL is the registry's.
  // Returns at once; progress comes from shiori:download-status. A bad id, a model with no url or a second download throws.
  ipcMain.handle("shiori:download", (e, id: unknown) => {
    own(e);
    void dl().start(id);
  });
  ipcMain.handle("shiori:download-status", (e) => {
    own(e);
    return dl().status();
  });
  // "Choose a model file from disk": main shows the picker; the copy happens only when the file's SHA-256 is a registry entry's.
  ipcMain.handle("shiori:import-model", async (e) => {
    own(e);
    const win = BrowserWindow.fromWebContents(e.sender);
    const opts = { properties: ["openFile" as const], filters: [{ name: "Model", extensions: ["gguf"] }] };
    const r = win ? await dialog.showOpenDialog(win, opts) : await dialog.showOpenDialog(opts);
    const file = r.canceled ? undefined : r.filePaths[0];
    return file ? dl().importFile(file) : null;
  });
  ipcMain.handle("shiori:fields", (e, id: unknown) => {
    own(e);
    return sidecar.call("GET", `/documents/${docId(id)}/fields`);
  });
}

const filter = requestFilter();
void app.whenReady().then(() => {
  registerIpc();
  protocol.handle("shiori", serve);
  // Belt and braces next to the CSP: nothing a page asks for but shiori:// (and devtools, data, blob) goes out. Blocked
  // requests are counted, never listed. The download is main-process code, outside this filter (D-100).
  session.defaultSession.webRequest.onBeforeRequest(filter.onBeforeRequest);
  session.defaultSession.setPermissionRequestHandler((_wc, _p, cb) => cb(false));
  void createWindow();
});
app.on("window-all-closed", () => app.quit());
// The sidecar ends with the app: quit, Ctrl+C in the terminal, or a terminate.
app.on("will-quit", () => console.log(`renderer requests blocked: ${filter.blockedCount()}`));
const stopAll = () => {
  sidecar.stop();
  llama.stop();
};
sidecar.onDeath(() => {
  llama.stop(); // no llama-server without the sidecar it serves
  backend = null; // the next Add document starts both again
});
app.on("will-quit", stopAll);
process.on("exit", stopAll);
for (const sig of ["SIGINT", "SIGTERM"] as const) process.on(sig, () => app.quit());
