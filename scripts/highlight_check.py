# ruff: noqa: E501
"""Dev-only highlight check for the desktop app (open-license documents only, no network, no git).

For each document: launches the app with SHIORI_PICK, the model on and SHIORI_HLCHECK (app/electron/hlcheck.ts),
which clicks up to 12 citation chips and saves a screenshot per click. This script then reads the raw records and
writes data/cache/highlight_check/results.tsv and prints the summary. After the field cards it also opens the Deadlines tab and clicks up to 4 rows (rows named deadlines_tab:N, screenshots <prefix>_deadlines_tab_N.png). Run: uv run python scripts/highlight_check.py
[--no-build] [--only <doc prefix>[:<field>]]. Quit any other running Shiori app first (a second llama-server is refused).
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cache" / "highlight_check"
DOCS = [
    "data/raw/wakayama_pref/4965207bb115546f7918a638a1cd15c99a5e7263fd7a2213a6837426cc5d5e46.pdf",
    "data/raw/_samples/wakayama_pref/2f2f5bd332965253eed43d739e56e7859b149afa0d157ea3c89dfdd7d0d8b419.pdf",
    "data/raw/digital/74aed2a543b8a0af2e09f02b9887244c8c1d1f67f7bdca8f31af2ff68e812873.pdf",
    "data/raw/wakayama_pref/53320d90cf87d7db2f0caef75e1b10061f26f67d00af1f8597e4be9dbbf4d9bb.pdf",
]
MODEL = ROOT / "models" / "Qwen3.5-9B-Q4_K_M.gguf"
COLS = [
    "doc", "field", "card_page", "opened_page", "overlay_rect", "stored_box", "iou", "in_page", "screenshot",
    "sentence", "overlay_page", "toolbar_page", "in_view", "n_overlay", "n_stored", "same_sentence",
]  # fmt: skip


def union(boxes: list[list[float]]) -> list[float] | None:
    return (
        [
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        ]
        if boxes
        else None
    )


def iou(a: list[float], b: list[float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(w, 0) * max(h, 0)
    total = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / total if total > 0 else 0.0


def fmt(b: list[float] | None) -> str:
    return "" if b is None else "[" + ", ".join(f"{v:.1f}" for v in b) + "]"


def row_of(r: dict) -> dict:
    ov = r["overlay"]
    opage = ov[0]["page"] if ov else None
    opened = opage if opage is not None else r["toolbar_page"]
    o = union([x["bbox"] for x in ov if x["page"] == opage]) if ov else None
    stored_here = [
        b["bbox"] for b in r["stored"] if b["page"] == (opage or r["stored_page"])
    ]
    s = union(stored_here)
    inside = None
    if o:
        pw, ph = ov[0]["pw"], ov[0]["ph"]
        inside = o[0] >= -0.5 and o[1] >= -0.5 and o[2] <= pw + 0.5 and o[3] <= ph + 0.5
    return {
        "doc": r["doc"], "field": r["field"], "card_page": r["card_page"], "opened_page": opened,
        "overlay_rect": fmt(o), "stored_box": fmt(s),
        "iou": "" if o is None else f"{iou(o, s) if s else 0.0:.3f}",
        "in_page": "" if inside is None else str(inside).lower(), "screenshot": r["shot"],
        "sentence": r["sentence"], "overlay_page": opage if opage is not None else "",
        "toolbar_page": r["toolbar_page"],
        "in_view": "" if not ov else str(any(x["visible"] for x in ov)).lower(),
        "n_overlay": len(ov), "n_stored": len(r["stored"]), "same_sentence": str(r["same_sentence"]).lower(),
    }  # fmt: skip


def main() -> int:
    if (
        subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True).returncode
        == 0
    ):
        print("a llama-server is already running; quit the other Shiori app first")
        return 2
    llama = shutil.which("llama-server")
    if not llama or not MODEL.exists():
        print("need llama-server on PATH and", MODEL)
        return 2
    app = ROOT / "app"
    if "--no-build" not in sys.argv:
        subprocess.run(
            ["npm", "run", "build"], cwd=app, check=True, stdout=subprocess.DEVNULL
        )
    only = (
        sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    )  # doc prefix[:field]
    if not only:
        shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    docs = [d for d in DOCS if Path(d).name.startswith(only.split(":")[0])]
    for d in docs:
        env = {**os.environ, "SHIORI_PICK": str(ROOT / d), "SHIORI_HLCHECK": str(OUT),
               "SHIORI_LLAMA_SERVER": llama, "SHIORI_MODEL": str(MODEL),
               "SHIORI_HLCHECK_FIELD": only.partition(":")[2]}  # fmt: skip
        print("running", Path(d).name[:8], flush=True)
        p = subprocess.run(
            [str(app / "node_modules" / ".bin" / "electron"), "."],
            cwd=app,
            env=env,
            timeout=1800,
            capture_output=True,
            text=True,
        )
        (OUT / f"run_{Path(d).name[:8]}.log").write_text(
            p.stdout
        )  # hlcheck lines only carry ids and counts
        print(
            "\n".join(x for x in p.stdout.splitlines() if x.startswith("hlcheck")),
            "exit",
            p.returncode,
            flush=True,
        )
    raws = [OUT / f"raw_{Path(d).name[:8]}.json" for d in docs]
    rows = [row_of(r) for f in raws if f.exists() for r in json.loads(f.read_text())]
    (OUT / "results.tsv").write_text(
        "\t".join(COLS)
        + "\n"
        + "".join("\t".join(str(r[c]) for c in COLS) + "\n" for r in rows)
    )
    wrong = [r for r in rows if r["opened_page"] != r["card_page"]]
    low = [r for r in rows if r["iou"] != "" and float(r["iou"]) < 0.5]
    none = [r for r in rows if r["n_overlay"] == 0]
    print(
        f"clicks {len(rows)} | wrong page {len(wrong)} | overlap below 0.5 {len(low)} | no overlay {len(none)}"
    )
    print(
        f"toolbar page differs from card page: {sum(r['toolbar_page'] != r['card_page'] for r in rows)}"
    )
    print(
        f"overlay outside page: {sum(r['in_page'] == 'false' for r in rows)} | not in view: {sum(r['in_view'] == 'false' for r in rows)} | chip not the compared sentence: {sum(r['same_sentence'] == 'false' for r in rows)}"
    )  # noqa: E501
    return 0


if __name__ == "__main__":
    sys.exit(main())
