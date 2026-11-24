// electron-builder config (D-112, D-113). Unsigned on purpose: no paid developer accounts.
// Inputs, built before this runs (see .github/workflows/release.yml):
//   packaging/build/sidecar/shiori-sidecar/   PyInstaller onedir build of the sidecar
//   packaging/build/llama/<target>/           llama.cpp release, from packaging/fetch_llama.py
//   packaging/build/THIRD_PARTY_NOTICES.txt   from packaging/third_party_notices.py
// The packaged app expects <resources>/sidecar/shiori-sidecar and <resources>/llama/llama-server (electron/paths.ts).
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const build = path.join(root, "packaging", "build");

const TARGET =
  process.platform === "darwin" ? (process.arch === "arm64" ? "macos-arm64" : "macos-x64")
  : process.platform === "win32" ? "win-cpu-x64"
  : "ubuntu-x64";
const SERVER = process.platform === "win32" ? "llama-server.exe" : "llama-server";

// The macOS and Linux archives unpack into a llama-b12651/ folder, the Windows one is flat.
function llamaDir() {
  const base = path.join(build, "llama", TARGET);
  for (const d of [base, ...fs.readdirSync(base, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => path.join(base, e.name))]) {
    if (fs.existsSync(path.join(d, SERVER))) return d;
  }
  throw new Error(`no ${SERVER} under ${base}; run: uv run python packaging/fetch_llama.py`);
}

const need = (p) => {
  if (!fs.existsSync(p)) throw new Error(`missing ${p}; see packaging notes in README (Build an installer)`);
  return p;
};

module.exports = {
  appId: "io.github.shiori",
  productName: "Shiori",
  copyright: "AGPL-3.0-only",
  directories: { output: "release" },
  // The renderer is bundled by vite, so node_modules is not shipped. fixture.json and doc.pdf are the
  // dev fixture (it holds document text) and must never end up in an installer.
  files: ["dist/**", "dist-electron/**", "package.json", "!dist/fixture.json", "!dist/doc.pdf", "!node_modules"],
  asar: true,
  extraResources: [
    { from: need(path.join(build, "sidecar", "shiori-sidecar")), to: "sidecar" },
    { from: llamaDir(), to: "llama" },
    { from: need(path.join(root, "LICENSE")), to: "LICENSE" },
    { from: need(path.join(build, "THIRD_PARTY_NOTICES.txt")), to: "THIRD_PARTY_NOTICES.txt" },
  ],
  artifactName: "Shiori-${version}-${os}-${arch}.${ext}",
  mac: { target: [{ target: "dmg" }], identity: null, category: "public.app-category.productivity" },
  dmg: { sign: false },
  win: { target: [{ target: "nsis", arch: ["x64"] }] },
  nsis: { oneClick: false, perMachine: false, allowToChangeInstallationDirectory: true },
  linux: { target: [{ target: "AppImage", arch: ["x64"] }], category: "Office", maintainer: "Yasharth Singh" },
  publish: null,
};
