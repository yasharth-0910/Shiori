// Main process. Serves the built renderer from a local shiori:// scheme (PDF.js needs
// fetch, which file:// blocks) and cancels every request that is not shiori://.
// The renderer gets three IPC functions (preload.ts); main owns the file picker, the
// sidecar and its token (D-83).
import { app, BrowserWindow, dialog, ipcMain, protocol, session, type IpcMainInvokeEvent } from "electron";
import * as fs from "node:fs";
import * as path from "node:path";
import { createHash } from "node:crypto";
import * as llama from "./llama";
import * as sidecar from "./sidecar";

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
const SENTENCE = /^(?:p\d+_s\d+|h_s\d+)$/; // a sentence id, as core makes them
type Translated =
  | { ok: true; items: Record<string, { en: string; numbers_match: boolean; protected_lost?: boolean }>; done: number; total: number; failed: string[] }
  | { ok: false; reason: "no_model" | "no_document" | "failed" };
const picked = new Map<string, string>(); // document id -> the PDF the user chose; main only
// SHIORI_PICK replaces the picker in dev checks only; a packaged app ignores it (D-84).
const PICK = app.isPackaged ? undefined : process.env.SHIORI_PICK;

// One backend for the session: llama-server (when SHIORI_LLAMA_SERVER and SHIORI_MODEL are set)
// and the sidecar. Started on the first Add document, stopped when the app quits.
type Backend = { state: "starting" | "ready" | "failed"; model: boolean; note: string | null; error: string | null };
let backend: Backend | null = null;
const jobs = new Map<string, { posted: boolean; error: string | null }>();

function ensureBackend(): Backend {
  if (backend) return backend;
  const b: Backend = { state: "starting", model: false, note: null, error: null };
  backend = b;
  void (async () => {
    const cfg = llama.config();
    let l: llama.Llama | null = null;
    if (!cfg) b.note = "Model not set up";
    else {
      b.model = true;
      try {
        l = await llama.start(cfg);
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

async function createWindow(): Promise<void> {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    show: !process.env.SHIORI_SHOT,
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

  // Dev check only: SHIORI_SHOT=<png> clicks chip number SHIORI_CHIP (default 0), saves the window, quits.
  const shot = app.isPackaged ? undefined : process.env.SHIORI_SHOT;
  if (shot) {
    win.webContents.on("console-message", (e) => console.log("renderer:", e.message));
    setTimeout(() => { console.log("shot timeout"); void win.webContents.executeJavaScript(`document.body.innerText.slice(0,300) + " canvases=" + document.querySelectorAll("canvas").length`).then((t) => { console.log(t); app.exit(1); }); }, process.env.SHIORI_MODEL ? 900000 : 30000);
    if (PICK) {
      // With SHIORI_PICK also set: click "Add document", log the stage shown on the Processing screen each time it changes.
      await win.webContents.executeJavaScript(
        `new Promise(r => { const t = setInterval(() => { const b = [...document.querySelectorAll("button")].find(x => x.textContent === "Add document"); if (b) { clearInterval(t); b.click(); r(); } }, 100); }); ` +
          `window.__seen = []; setInterval(() => { const m = document.querySelector(".processing .meta:last-of-type"); ` +
          `const t = m && m.textContent.replace(/ · \\d+ s$/, ""); if (t && window.__seen.at(-1) !== t) { window.__seen.push(t); console.log("screen: " + t); } }, 20);`,
      );
    }
    const chip = Number(process.env.SHIORI_CHIP ?? 0);
    await win.webContents.executeJavaScript(
      `new Promise(r => { const t = setInterval(() => { const c = document.querySelectorAll(".chip"); ` +
        `if ((c.length || ${!!PICK}) && document.querySelectorAll("canvas").length) { clearInterval(t); c[${chip}]?.click(); ` +
        `console.log("rows: " + document.querySelectorAll(".field").length + " | " + [...document.querySelectorAll(".counts button")].map(b => b.textContent).join(" / ") + " pills: " + document.querySelectorAll(".pill").length); setTimeout(r, 1500); } }, 200); })`,
    );
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

function registerIpc(): void {
  // Asks the user for a PDF (native picker), posts its path to the sidecar, returns the id.
  // SHIORI_PICK=<pdf> stands in for the picker in dev checks (like SHIORI_SHOT); the renderer cannot set it.
  ipcMain.handle("shiori:start", async (e) => {
    own(e);
    let file = PICK;
    if (!file) {
      const win = BrowserWindow.fromWebContents(e.sender);
      const opts = { properties: ["openFile" as const], filters: [{ name: "PDF", extensions: ["pdf"] }] };
      const r = win ? await dialog.showOpenDialog(win, opts) : await dialog.showOpenDialog(opts);
      file = r.canceled ? undefined : r.filePaths[0];
    }
    if (!file) return null;
    // The id is the file's SHA-256, the same one the sidecar makes, so the screen can start
    // before the model and the sidecar are up.
    const doc_id = createHash("sha256").update(fs.readFileSync(file)).digest("hex");
    picked.set(doc_id, file);
    jobs.set(doc_id, { posted: false, error: null });
    const b = ensureBackend();
    void (async () => {
      while (b.state === "starting") await new Promise((r) => setTimeout(r, 200));
      const job = jobs.get(doc_id);
      if (!job || b.state === "failed") return;
      try {
        await sidecar.call("POST", "/documents", { path: file });
        job.posted = true;
      } catch (err) {
        job.error = (err as Error).message;
      }
    })();
    return { doc_id, name: path.basename(file) };
  });
  ipcMain.handle("shiori:status", async (e, id: unknown) => {
    own(e);
    const doc = docId(id);
    const job = jobs.get(doc);
    if (!job) throw new Error("unknown_document");
    // No backend means the sidecar died (it is only cleared then); the next Add document starts a new one.
    if (!backend) return { doc_id: doc, pages: null, detail: null, stage: "failed", error: "sidecar_exited" };
    const b = backend;
    const base = { doc_id: doc, pages: null, detail: b.note, error: null };
    if (b.state === "starting") return { ...base, stage: b.model ? "loading_model" : "queued" };
    if (b.state === "failed" || job.error) return { ...base, stage: "failed", error: b.error ?? job.error };
    if (!job.posted) return { ...base, stage: "queued" };
    const s = await sidecar.call<{ stage: string; detail: string | null }>("GET", `/documents/${doc}/status`);
    const running = s.stage !== "done" && s.stage !== "failed";
    return { ...s, detail: s.detail ?? (running ? b.note : null) };
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
  ipcMain.handle("shiori:fields", (e, id: unknown) => {
    own(e);
    return sidecar.call("GET", `/documents/${docId(id)}/fields`);
  });
}

void app.whenReady().then(() => {
  registerIpc();
  protocol.handle("shiori", serve);
  // Belt and braces next to the CSP: nothing but shiori:// (and devtools) leaves the process.
  session.defaultSession.webRequest.onBeforeRequest((d, cb) =>
    cb({ cancel: !/^(shiori|devtools|data|blob):/.test(d.url) }),
  );
  session.defaultSession.setPermissionRequestHandler((_wc, _p, cb) => cb(false));
  void createWindow();
});
app.on("window-all-closed", () => app.quit());
// The sidecar ends with the app: quit, Ctrl+C in the terminal, or a terminate.
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
