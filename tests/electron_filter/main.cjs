// Run by tests/test_app_filter_electron.py with the app's own electron. Installs the app's request filter
// (app/dist-electron/netfilter.js, built by `npm run build`) on a session, then makes a page fetch an outside host.
// A local server on 127.0.0.1 stands in for "outside": the filter must cancel before any connection is made.
const { app, BrowserWindow, session } = require("electron");
const http = require("node:http");
const path = require("node:path");
const { requestFilter } = require(path.join(process.env.APP_DIR, "dist-electron", "netfilter.js"));

app.whenReady().then(async () => {
  let hits = 0;
  const server = http.createServer((_q, r) => { hits++; r.writeHead(200, { "access-control-allow-origin": "*" }).end("x"); });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const filter = requestFilter();
  session.defaultSession.webRequest.onBeforeRequest(filter.onBeforeRequest);
  const win = new BrowserWindow({ show: false });
  await win.loadURL("data:text/html,<html><body>page</body></html>");
  const port = server.address().port;
  const tryFetch = (u) => win.webContents.executeJavaScript(`fetch(${JSON.stringify(u)}).then(() => "reached", () => "cancelled")`);
  const out = {
    loopback: await tryFetch(`http://127.0.0.1:${port}/x`),
    outside: await tryFetch("https://shiori-check.invalid/x"),
    sameSchemeData: await tryFetch("data:text/plain,ok"),
    hits,
    blocked: filter.blockedCount(),
  };
  console.log("RESULT " + JSON.stringify(out));
  server.close();
  app.exit(0);
});
