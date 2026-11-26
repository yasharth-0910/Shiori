# ruff: noqa: E501
"""Dev-time only: download the pinned llama.cpp release, check SHA-256, unpack, report (D-112).
Never imported by the app. Run from the repo root:

    uv run python packaging/fetch_llama.py            # verify against packaging/llama_pins.json
    uv run python packaging/fetch_llama.py --record   # first time only: write the hashes into the pins file

Only llama-server, the shared libraries and the license files are unpacked (wanted()).
Archives go to packaging/build/llama/dl/, unpacked files to packaging/build/llama/<target>/
(both gitignored). The pinned release also has its LICENSE fetched once and its hash recorded.
"""

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = HERE / "llama_pins.json"
OUT = HERE / "build" / "llama"
TAG = "b12651"
BASE = f"https://github.com/ggml-org/llama.cpp/releases/download/{TAG}/"
LICENSE_URL = f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{TAG}/LICENSE"
TARGETS = {
    "macos-arm64": f"llama-{TAG}-bin-macos-arm64.tar.gz",
    "macos-x64": f"llama-{TAG}-bin-macos-x64.tar.gz",
    "win-cpu-x64": f"llama-{TAG}-bin-win-cpu-x64.zip",
    "ubuntu-x64": f"llama-{TAG}-bin-ubuntu-x64.tar.gz",
}
LIBS = (".dylib", ".dll", ".so")
SERVERS = ("llama-server", "llama-server.exe")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as r, tmp.open("wb") as f:  # noqa: S310 (pinned https URL)
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dest)


def is_lib(name: str) -> bool:
    return name.endswith(LIBS) or ".so." in name


def wanted(member: str) -> bool:
    """Allow-list for the installer: the server, shared libraries (and their symlinks), licenses."""
    name = Path(member).name
    return name in SERVERS or is_lib(name) or name.startswith("LICENSE")


def unpack(archive: Path, into: Path) -> None:
    """Extract the wanted() files without trusting member names: no absolute paths, no .., no links
    outside the folder. The folder is emptied first, so files from an older unpack do not stay."""
    if into.exists():
        shutil.rmtree(into)
    into.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            for n in z.namelist():
                if Path(n).is_absolute() or ".." in Path(n).parts:
                    sys.exit(f"unsafe path in archive: {n}")
            z.extractall(into, members=[n for n in z.namelist() if wanted(n)])  # noqa: S202 (names checked above)
    else:
        with tarfile.open(archive) as t:
            members = [m for m in t.getmembers() if not m.isdir() and wanted(m.name)]
            t.extractall(
                into, members=members, filter="data"
            )  # the "data" filter rejects unsafe members


def report(target: str, folder: Path) -> list[str]:
    files = sorted(p for p in folder.rglob("*") if p.is_file() or p.is_symlink())
    names = [str(p.relative_to(folder)) for p in files]
    server = [n for n in names if Path(n).name in SERVERS]
    libs = [n for n in names if is_lib(Path(n).name)]
    print(f"\n== {target}: {len(names)} files")
    print(f"llama-server: {server or 'MISSING'}")
    print(f"shared libraries: {len(libs)}")
    for n in names:
        print(f"  {n}")
    return server


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--record",
        action="store_true",
        help="write hashes for entries not in the pins file yet",
    )
    ap.add_argument("--target", choices=sorted(TARGETS), help="only this target (CI uses one per runner)")
    a = ap.parse_args()
    pins = (
        json.loads(PINS.read_text())
        if PINS.exists()
        else {"tag": TAG, "assets": {}, "license": {}}
    )
    if pins.get("tag") != TAG:
        sys.exit(f"pins file is for {pins.get('tag')}, this script for {TAG}")
    for target, name in TARGETS.items():
        if a.target and a.target != target:
            continue
        dest = OUT / "dl" / name
        download(BASE + name, dest)
        got = sha256(dest)
        want = pins["assets"].get(name)
        if want is None and a.record:
            pins["assets"][name] = want = got
        if want != got:
            sys.exit(
                f"{name}: SHA-256 {got} does not match the pin {want}. Not unpacked."
            )
        unpack(dest, OUT / target)
        report(target, OUT / target)
    lic = OUT / "dl" / "LICENSE"
    download(LICENSE_URL, lic)
    got = sha256(lic)
    if pins["license"].get("sha256") is None and a.record:
        pins["license"] = {"url": LICENSE_URL, "sha256": got}
    if pins["license"].get("sha256") != got:
        sys.exit("LICENSE hash does not match the pin")
    print(f"\nLICENSE at {TAG}: {lic} ({lic.stat().st_size} bytes, sha256 {got})")
    if a.record:
        PINS.write_text(json.dumps(pins, indent=2) + "\n")
        print(f"pins written to {PINS}")


if __name__ == "__main__":
    main()
