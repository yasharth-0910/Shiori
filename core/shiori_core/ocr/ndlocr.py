"""NDLOCR-Lite (National Diet Library, CC BY 4.0, ONNX models, CPU only), D-36.

Its code and models are not part of this package. They live in a checkout of
github.com/ndl-lab/ndlocr-lite (`src/ocr.py`, `src/model/*.onnx`, `src/config/`), found
in `$SHIORI_NDLOCR_DIR` or `models/ndlocr-lite/` in the repo. The packaged app bundles
that checkout and sets the variable. Its modules are imported by their own top-level
names (`ocr`, `deim`, `parseq`, `reading_order`), so the directory is appended to
sys.path, never put first: nothing of ours can be shadowed.

Detection (DEIM) finds text lines and puts them in reading order; three PARSeq
recognizers (up to 30, 50 and 100 characters) read them. We call its per-page function
`_run_ocr_on_image_array`, the same one its own command line uses.
"""

import contextlib
import io
import os
import sys
import types
from pathlib import Path

import numpy as np

from shiori_core.ocr import OcrLine, OcrUnavailableError

ENV_VAR = "SHIORI_NDLOCR_DIR"


def ndlocr_dir() -> Path | None:
    """`$SHIORI_NDLOCR_DIR`, else models/ndlocr-lite in the repo when run from source.
    None in a frozen (PyInstaller) build without the variable: no repo to look in, and
    OCR is not shipped in v0.1 (D-112)."""
    if os.environ.get(ENV_VAR):
        return Path(os.environ[ENV_VAR])
    if getattr(sys, "frozen", False):
        return None
    return Path(__file__).resolve().parents[3] / "models" / "ndlocr-lite"


class NdlocrEngine:
    name = "ndlocr-lite"

    def __init__(self) -> None:
        root = ndlocr_dir()
        src = (root or Path()) / "src"
        if (
            root is None
            or not (src / "ocr.py").is_file()
            or not (src / "model").is_dir()
        ):
            raise OcrUnavailableError(
                f"NDLOCR-Lite not found at {root}. Clone "
                "https://github.com/ndl-lab/ndlocr-lite there or set "
                f"{ENV_VAR} (see docs/decisions.md, D-36)."
            )
        if str(src) not in sys.path:
            sys.path.append(str(src))
        import ocr as ndl  # pyright: ignore[reportMissingImports]

        model, config = src / "model", src / "config"
        args = types.SimpleNamespace(
            det_weights=str(model / "deim-s-1024x1024.onnx"),
            det_classes=str(config / "ndl.yaml"),
            det_score_threshold=0.2,
            det_conf_threshold=0.25,
            det_iou_threshold=0.2,
            device="cpu",
            rec_weights=str(
                model / "parseq-ndl-24x768-100-tiny-153epoch-tegaki3-r8data-202604.onnx"
            ),
            rec_weights30=str(
                model / "parseq-ndl-24x256-30-tiny-189epoch-tegaki3-r8data-202604.onnx"
            ),
            rec_weights50=str(
                model / "parseq-ndl-24x384-50-tiny-300epoch-tegaki3-r8data-202604.onnx"
            ),
            rec_classes=str(config / "NDLmoji.yaml"),
            enable_tcy=False,
        )
        self._ndl = ndl
        self._detector = ndl.get_detector(args)
        self._rec30 = ndl.get_recognizer(args, args.rec_weights30)
        self._rec50 = ndl.get_recognizer(args, args.rec_weights50)
        self._rec100 = ndl.get_recognizer(args)

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        # The library prints progress; keep anything it says out of our logs.
        with contextlib.redirect_stdout(io.StringIO()):
            result = self._ndl._run_ocr_on_image_array(
                self._detector,
                self._rec30,
                self._rec50,
                self._rec100,
                "page",
                image,
                "",
            )
        return [
            OcrLine(
                text=ln["text"],
                bbox=(
                    float(ln["x"]),
                    float(ln["y"]),
                    float(ln["x"] + ln["width"]),
                    float(ln["y"] + ln["height"]),
                ),
                vertical=bool(ln["is_vertical"]),
            )
            for ln in result["text_layer_lines"]
        ]
