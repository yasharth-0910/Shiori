# ruff: noqa: E501
"""Dev-time only: build THIRD_PARTY_NOTICES.txt for the installer (D-113). Never imported by the app.

    uv sync && (cd app && npm ci)
    uv run python packaging/fetch_llama.py          # optional: adds the llama.cpp licenses
    uv run python packaging/third_party_notices.py  # writes packaging/build/THIRD_PARTY_NOTICES.txt

Sources: the runtime closure of uv.lock (what the frozen sidecar contains), the runtime packages of
app/package-lock.json, Electron, pdf.js and the pinned llama.cpp release. Each license text is read
from the package's own files. A package whose license file cannot be found is listed under
"NOT FOUND" with whatever its metadata says, never skipped silently.
"""

import json
import sys
import sysconfig
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packaging" / "build" / "THIRD_PARTY_NOTICES.txt"
LICENSE_WORDS = ("licen", "copying", "notice")
APP = ROOT / "app"


def runtime_python_packages() -> list[str]:
    """Names reachable from the project's own (non-group) dependencies in uv.lock."""
    pkgs = {
        p["name"]: p for p in tomllib.loads((ROOT / "uv.lock").read_text())["package"]
    }
    todo, seen = [d["name"] for d in pkgs["shiori"].get("dependencies", [])], set()
    while todo:
        n = todo.pop()
        if n not in seen and n in pkgs:
            seen.add(n)
            todo += [d["name"] for d in pkgs[n].get("dependencies", [])]
    return sorted(seen)


def python_entry(name: str) -> tuple[str, str, list[str]]:
    """(label, license from metadata, license texts found)."""
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return (
            f"{name} (lock file only)",
            "unknown",
            [],
        )  # a platform-only dependency not installed here
    meta = dist.metadata
    lic = (
        meta.get("License-Expression")
        or (meta.get("License") or "").splitlines()[0:1]
        or [""]
    )
    lic = lic if isinstance(lic, str) else lic[0]
    lic = (
        lic
        or "; ".join(
            c.split("::")[-1].strip()
            for c in meta.get_all("Classifier", [])
            if c.startswith("License ::")
        )
        or "unknown"
    )
    texts = []
    for f in dist.files or []:
        if (
            any(w in f.name.lower() for w in LICENSE_WORDS)
            and f.name.lower() != "licenses.txt"
            or "licenses" in f.parts[-2:-1]
        ):
            p = Path(str(dist.locate_file(f)))
            if p.is_file() and p.suffix in ("", ".txt", ".md", ".rst"):
                texts.append(p.read_text(errors="replace"))
    return f"{name} {meta['Version']}", lic, texts


def npm_runtime_packages() -> list[str]:
    lock = json.loads((APP / "package-lock.json").read_text())["packages"]
    return sorted(
        {
            k.split("node_modules/")[-1]
            for k, v in lock.items()
            if k and not v.get("dev") and not v.get("optional")
        }
    )


def folder_entry(folder: Path, label: str) -> tuple[str, str, list[str]]:
    texts = (
        [
            p.read_text(errors="replace")
            for p in sorted(folder.glob("*"))
            if p.is_file() and any(w in p.name.lower() for w in LICENSE_WORDS)
        ]
        if folder.is_dir()
        else []
    )
    lic = "unknown"
    pj = folder / "package.json"
    if pj.exists():
        j = json.loads(pj.read_text())
        lic, label = (
            str(j.get("license", "unknown")),
            f"{j['name']} {j.get('version', '')}",
        )
    return label, lic, texts


def build() -> tuple[str, list[str]]:
    entries: list[tuple[str, str, list[str]]] = [
        python_entry(n) for n in runtime_python_packages()
    ]
    py_lic = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
    entries.append(
        (
            "Python (runtime inside the sidecar)",
            "PSF-2.0",
            [py_lic.read_text()] if py_lic.exists() else [],
        )
    )
    nm = APP / "node_modules"
    entries += [folder_entry(nm / n, n) for n in npm_runtime_packages()]
    entries.append(
        folder_entry(nm / "electron", "electron")
    )  # Chromium's own notices ship in the app as LICENSES.chromium.html
    if not any(e[0].startswith("pdfjs-dist") for e in entries):
        entries.append(folder_entry(nm / "pdfjs-dist", "pdfjs-dist (pdf.js)"))
    llama = ROOT / "packaging" / "build" / "llama"
    entries.append(
        folder_entry(llama / "dl", "llama.cpp (llama-server, release b12651)")
    )
    for extra in sorted(llama.glob("win-cpu-x64/LICENSE*")):
        entries.append(
            (
                f"llama.cpp Windows build: {extra.name}",
                "see text",
                [extra.read_text(errors="replace")],
            )
        )
    missing = [f"{label} [{lic}]" for label, lic, texts in entries if not texts]
    out = [
        "Shiori is licensed AGPL-3.0-only (see the LICENSE file next to this one).",
        "It bundles the software below. Each license text is copied from the package's own files.",
        "Chromium and Electron notices are in the Electron runtime of this app (LICENSE, LICENSES.chromium.html).",
        "PyInstaller (GPL-2.0-or-later with the Bootloader Exception) built the sidecar; its bootloader inside the sidecar is covered by that exception.",
        "",
    ]
    if missing:
        out += [
            "NOT FOUND (no license file located; the metadata license is shown):",
            *[f"  - {m}" for m in missing],
            "",
        ]
    for label, lic, texts in entries:
        out += ["=" * 78, f"{label}   [{lic}]", "=" * 78]
        out += [t.strip() + "\n" for t in dict.fromkeys(texts)] or [
            "(license file not found)\n"
        ]
    return "\n".join(out) + "\n", missing


if __name__ == "__main__":
    text, missing = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(
        f"wrote {OUT} ({len(text)} bytes); license file not found for {len(missing)}:",
        *missing,
        sep="\n  ",
    )
    sys.exit(0)
