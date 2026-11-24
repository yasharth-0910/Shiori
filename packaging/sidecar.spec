# PyInstaller spec for the sidecar (D-112). Build from the repo root:
#   uv run pyinstaller packaging/sidecar.spec --noconfirm
# Output: dist/shiori-sidecar/shiori-sidecar (onedir). The frozen sidecar does not need the repo:
# shiori_core has no data files, and OCR is not bundled (scans are refused with scan_not_supported).
# Dev-time code (collector, eval, training) is never imported by the sidecar and is excluded.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent  # repo root; SPECPATH is this file's folder

hidden = [
    *collect_submodules("uvicorn"),  # loops, protocols and lifespan are chosen by name at run time
    *collect_submodules("starlette"),
    *collect_submodules("fastapi"),
    *collect_submodules("pydantic"),
    *collect_submodules("pydantic_core"),
    *collect_submodules("shiori_core"),
    *collect_submodules("sidecar"),
    "pymupdf",
    "anyio._backends._asyncio",
]

a = Analysis(
    [str(root / "sidecar" / "__main__.py")],
    pathex=[str(root), str(root / "core")],
    hiddenimports=hidden,
    excludes=["collector", "eval", "training", "tkinter", "pytest", "httpx", "bs4", "openpyxl"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="shiori-sidecar",
    console=True,  # stdout carries the {"port","token"} line the app reads
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="shiori-sidecar", upx=False)
