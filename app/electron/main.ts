// Main process. Serves the built renderer from a local shiori:// scheme (PDF.js needs
// fetch, which file:// blocks) and cancels every request that is not shiori://.
// The renderer gets three IPC functions (preload.ts); main owns the file picker, the
// sidecar and its token (D-83).
import { app, BrowserWindow, dialog, ipcMain, protocol, session, type IpcMainInvokeEvent } from "electron";
import * as fs from "node:fs";
import * as path from "node:path";
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
const picked = new Map<string, string>(); // document id -> the PDF the user chose; main only

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
  const shot = process.env.SHIORI_SHOT;
  if (shot) {
    win.webContents.on("console-message", (e) => console.log("renderer:", e.message));
    setTimeout(() => { console.log("shot timeout"); void win.webContents.executeJavaScript(`document.body.innerText.slice(0,300) + " canvases=" + document.querySelectorAll("canvas").length`).then((t) => { console.log(t); app.exit(1); }); }, 30000);
    if (process.env.SHIORI_PICK) {
      // With SHIORI_PICK also set: click "Add document", log the stage shown on the Processing screen each time it changes.
      await win.webContents.executeJavaScript(
        `new Promise(r => { const t = setInterval(() => { const b = [...document.querySelectorAll("button")].find(x => x.textContent === "Add document"); if (b) { clearInterval(t); b.click(); r(); } }, 100); }); ` +
          `window.__seen = []; setInterval(() => { const m = document.querySelector(".processing .meta:last-of-type"); ` +
          `if (m && window.__seen.at(-1) !== m.textContent) { window.__seen.push(m.textContent); console.log("screen: " + m.textContent); } }, 20);`,
      );
    }
    const chip = Number(process.env.SHIORI_CHIP ?? 0);
    await win.webContents.executeJavaScript(
      `new Promise(r => { const t = setInterval(() => { const c = document.querySelectorAll(".chip"); ` +
        `if ((c.length || ${!!process.env.SHIORI_PICK}) && document.querySelectorAll("canvas").length) { clearInterval(t); c[${chip}]?.click(); ` +
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
    let file = process.env.SHIORI_PICK;
    if (!file) {
      const win = BrowserWindow.fromWebContents(e.sender);
      const opts = { properties: ["openFile" as const], filters: [{ name: "PDF", extensions: ["pdf"] }] };
      const r = win ? await dialog.showOpenDialog(win, opts) : await dialog.showOpenDialog(opts);
      file = r.canceled ? undefined : r.filePaths[0];
    }
    if (!file) return null;
    const { doc_id } = await sidecar.call<{ doc_id: string }>("POST", "/documents", { path: file });
    picked.set(doc_id, file);
    return { doc_id, name: path.basename(file) };
  });
  ipcMain.handle("shiori:status", (e, id: unknown) => {
    own(e);
    return sidecar.call("GET", `/documents/${docId(id)}/status`);
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
app.on("will-quit", sidecar.stop);
process.on("exit", sidecar.stop);
for (const sig of ["SIGINT", "SIGTERM"] as const) process.on(sig, () => app.quit());
