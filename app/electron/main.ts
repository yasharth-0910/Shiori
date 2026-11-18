// Main process. Serves the built renderer from a local shiori:// scheme (PDF.js needs
// fetch, which file:// blocks) and cancels every request that is not shiori://.
// No preload: the renderer needs nothing from Node.
import { app, BrowserWindow, protocol, session } from "electron";
import * as fs from "node:fs";
import * as path from "node:path";

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

function serve(request: Request): Response {
  const rel = decodeURIComponent(new URL(request.url).pathname);
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
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true },
  });
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (e) => e.preventDefault());
  await win.loadURL("shiori://app/");

  // Dev check only: SHIORI_SHOT=<png> clicks chip number SHIORI_CHIP (default 0), saves the window, quits.
  const shot = process.env.SHIORI_SHOT;
  if (shot) {
    win.webContents.on("console-message", (e) => console.log("renderer:", e.message));
    setTimeout(() => { console.log("shot timeout"); app.exit(1); }, 30000);
    const chip = Number(process.env.SHIORI_CHIP ?? 0);
    await win.webContents.executeJavaScript(
      `new Promise(r => { const t = setInterval(() => { const c = document.querySelectorAll(".chip"); ` +
        `if (c.length && document.querySelectorAll("canvas").length) { clearInterval(t); c[${chip}].click(); setTimeout(r, 1500); } }, 200); })`,
    );
    fs.writeFileSync(shot, (await win.webContents.capturePage()).toPNG());
    app.quit();
  }
}

void app.whenReady().then(() => {
  protocol.handle("shiori", serve);
  // Belt and braces next to the CSP: nothing but shiori:// (and devtools) leaves the process.
  session.defaultSession.webRequest.onBeforeRequest((d, cb) =>
    cb({ cancel: !/^(shiori|devtools|data|blob):/.test(d.url) }),
  );
  session.defaultSession.setPermissionRequestHandler((_wc, _p, cb) => cb(false));
  void createWindow();
});
app.on("window-all-closed", () => app.quit());
