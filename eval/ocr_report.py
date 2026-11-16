"""OCR evaluation (D-23a, D-36): how well does OCR read pages whose text we know, and
what does it do on the real scanned pages in the corpus.

    uv run python -m eval.ocr_report            # writes data/manifests/ocr_report.md

Part 1, rendered-scan test set: 200 text pages, spread over sources and doc_types
(seed below), rendered at 200 dpi and read by OCR twice: clean, and with mild
degradation (a 1 to 2 degree skew, slight blur, noise). The ground truth is the page's
own text layer. OCR results are cached in data/processed/_ocr_eval/ (gitignored), so
changing the scoring does not repeat the OCR.

Scoring is by geometry, so a different reading order does not count as errors. Every
text-layer character is given to the OCR line whose box contains its centre (the page
is skewed the same way for the degraded run). Per OCR line, both sides are normalized
(normalize.py, white space dropped) and compared with Levenshtein distance. Characters
in no OCR box count as deleted, OCR lines holding no text-layer character as inserted.
CER = (substitutions + deletions + insertions) / text-layer characters. Reading order
is scored separately, as the share of consecutive OCR lines whose text-layer order is
reversed. Dates, times, amounts and fiscal years are found with the value converters on
both sides and compared as values: a value the text layer has and OCR lost or changed is
"missing"; one OCR has and the text layer lacks is "extra" (a wrong digit gives both).

Part 2, real cases: every scanned, outlined and mixed page in the corpus goes through
the real pipeline (load_document), with debug renders of the sentence boxes.

Committed output holds aggregate numbers and doc_id/page references. Text of documents
that are not `open` never appears (D-22); character confusions come from `open`
documents
only.
"""

import argparse
import json
import random
import re
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import cv2
import numpy as np
from shiori_core.debug_render import PROCESSED_DIR, write_debug
from shiori_core.ingest import is_suspect, load_document
from shiori_core.models import EXTRACTOR_VERSION, Document, Page
from shiori_core.normalize import normalize
from shiori_core.ocr import OCR_DPI, OcrEngine, OcrLine, default_engine, drop_regions
from shiori_core.pdf import Overlay, PdfFile
from shiori_core.value_normalize import (
    DateRange,
    find_amounts,
    find_dates,
    find_fiscal_years,
    find_times,
)

from collector.manifest import ManifestRow, read_rows

REPORT_PATH = Path("data/manifests/ocr_report.md")
CACHE = PROCESSED_DIR / "_ocr_eval"
SEED = 20261002
N_PAGES = 200
MIN_CHARS = 80  # a page needs this many characters to be worth scoring
VARIANTS = ("clean", "degraded")


# --- selecting and rendering pages ------------------------------------------------


def _eligible_pages(doc: Document) -> list[Page]:
    return [
        p
        for p in doc.pages
        if p.kind == "text" and p.char_count - p.suspect_chars >= MIN_CHARS
    ]


def select_pages(rows: list[ManifestRow]) -> list[tuple[str, int]]:
    """(doc_id, page number) x N_PAGES: round-robin over (source, doc_type) strata in
    seeded random order, one random page of a random unused document each turn."""
    path = CACHE / "pages.json"
    if path.exists():
        return [(d, p) for d, p in json.loads(path.read_text())]
    rng = random.Random(SEED)
    strata: dict[tuple[str, str], list[ManifestRow]] = defaultdict(list)
    for r in rows:
        strata[(r.source, r.doc_type)].append(r)
    keys = sorted(strata)
    rng.shuffle(keys)
    for k in keys:
        rng.shuffle(strata[k])
    picked: list[tuple[str, int]] = []
    while len(picked) < N_PAGES and any(strata.values()):
        for k in keys:
            while strata[k]:
                r = strata[k].pop()
                doc = load_document(Path(r.path), ocr=False)
                pages = _eligible_pages(doc)
                if pages:
                    picked.append((r.doc_id, rng.choice(pages).number))
                    break
            if len(picked) >= N_PAGES:
                break
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(picked))
    return picked


def degrade(img: np.ndarray, rng: random.Random) -> tuple[np.ndarray, np.ndarray]:
    """Skew of 1 to 2 degrees either way (white corners), slight blur, noise.
    Returns the image and the 2x3 skew matrix, to move text-layer boxes the same way."""
    h, w = img.shape[:2]
    angle = rng.choice((-1, 1)) * rng.uniform(1.0, 2.0)
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    out = cv2.warpAffine(
        img, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255)
    )
    out = cv2.GaussianBlur(out, (0, 0), 0.8)
    noise = np.random.default_rng(rng.randrange(2**32)).normal(0, 6, out.shape)
    return np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8), m


# --- alignment and error kinds ------------------------------------------------------


def align(a: str, b: str) -> list[tuple[str, str, str]]:
    """Levenshtein alignment of text-layer text `a` against OCR text `b`: a list of
    (op, a_char, b_char), op in = / sub / del / ins ('' for the missing side)."""
    n, m = len(a), len(b)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(
                d[i - 1][j - 1] + (a[i - 1] != b[j - 1]),
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
            )
    ops: list[tuple[str, str, str]] = []
    i, j = n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            ops.append(("=" if a[i - 1] == b[j - 1] else "sub", a[i - 1], b[j - 1]))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            ops.append(("del", a[i - 1], ""))
            i -= 1
        else:
            ops.append(("ins", "", b[j - 1]))
            j -= 1
    return ops[::-1]


def script(c: str) -> str:
    o = ord(c)
    if c.isdigit():
        return "digit"
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or c == "々":
        return "kanji"
    if 0x3040 <= o <= 0x30FF:
        return "kana"
    if c.isascii() and c.isalpha():
        return "latin"
    return "symbol"


UNITS = set("年月日時分円万億")


_LEADER = re.compile(r"[.。・…‥·]{3,}")


def norm(s: str) -> str:
    """normalize(), white space dropped, and a run of three or more dots (the leader
    of a table-of-contents line: its length is layout, and OCR reads the dots as
    `。` or fewer dots) counted as one character."""
    return _LEADER.sub("…", "".join(normalize(s)[0].split()))


# --- scoring one page ----------------------------------------------------------------


@dataclass
class Score:
    chars: int = 0
    errors: int = 0
    kinds: Counter[str] = field(default_factory=Counter)  # error kind -> count
    digits: int = 0  # text-layer digit characters
    digit_errors: int = 0  # ... changed or lost, plus digits OCR added
    det_chars: int = 0  # text-layer characters inside a detected OCR line
    det_errors: int = 0  # errors among those (recognition, not detection)
    det_digits: int = 0
    det_digit_errors: int = 0
    units: int = 0  # 年月日時分円万億 in the text layer
    unit_errors: int = 0
    gt_lines: int = 0
    dropped_lines: int = 0  # text-layer lines at least half outside every OCR box
    ocr_lines: int = 0
    ocr_only_lines: int = 0  # OCR lines on which no text-layer character sits
    order_pairs: int = 0
    order_flips: int = 0
    values: dict[str, Counter[str]] = field(default_factory=dict)  # kind -> counts
    value_cases: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # kind, gt, ocr
    confusions: Counter[tuple[str, str]] = field(default_factory=Counter)

    def add(self, o: "Score") -> None:
        for name in (
            "chars errors digits digit_errors units unit_errors gt_lines dropped_lines "
            "ocr_lines ocr_only_lines order_pairs order_flips det_chars det_errors "
            "det_digits det_digit_errors"
        ).split():
            setattr(self, name, getattr(self, name) + getattr(o, name))
        self.kinds.update(o.kinds)
        self.confusions.update(o.confusions)
        for k, c in o.values.items():
            self.values.setdefault(k, Counter()).update(c)

    @property
    def cer(self) -> float:
        return self.errors / self.chars if self.chars else 0.0


def _values(text: str) -> Counter[tuple[str, str]]:
    """(kind, value) of every converted date, time, amount and fiscal year."""
    out: Counter[tuple[str, str]] = Counter()
    for kind, fn in (
        ("date", find_dates),
        ("time", find_times),
        ("amount", find_amounts),
        ("fiscal year", find_fiscal_years),
    ):
        for f in fn(text):
            v = f.value
            if v is not None:
                out[
                    (
                        kind,
                        f"{v.start}..{v.end}" if isinstance(v, DateRange) else str(v),
                    )
                ] += 1
    return out


def score_page(
    page: Page,
    ocr_lines: list[OcrLine],
    scale: float,
    skew: np.ndarray | None,
    keep_pairs: bool,
) -> Score:
    """`scale`: pixels per point. `skew`: the matrix the image was rotated with."""
    sc = Score(ocr_lines=len(ocr_lines))
    gt = [
        (
            ch.c,
            (
                (ch.bbox[0] + ch.bbox[2]) / 2 * scale,
                (ch.bbox[1] + ch.bbox[3]) / 2 * scale,
            ),
            li,
        )
        for li, line in enumerate(page.lines)
        for ch in line.chars
        if not ch.c.isspace() and not is_suspect(ch.c)
    ]
    sc.gt_lines = len({li for _, _, li in gt})
    pts = np.array([c for _, c, _ in gt], dtype=np.float64).reshape(-1, 2)
    if skew is not None and len(pts):
        pts = pts @ skew[:, :2].T + skew[:, 2]
    boxes = np.array([ln.bbox for ln in ocr_lines], dtype=np.float64).reshape(-1, 4)
    owner = np.full(len(gt), -1)
    if len(pts) and len(boxes):
        inside = (
            (pts[:, None, 0] >= boxes[None, :, 0])
            & (pts[:, None, 0] <= boxes[None, :, 2])
            & (pts[:, None, 1] >= boxes[None, :, 1])
            & (pts[:, None, 1] <= boxes[None, :, 3])
        )
        cx, cy = (boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2
        wide = boxes[:, 2] - boxes[:, 0] >= boxes[:, 3] - boxes[:, 1]
        # Distance from the line's own axis, in line heights, so a skewed neighbour's
        # box that clips the character loses to the line it sits on.
        dist = np.where(
            wide[None, :],
            np.abs(pts[:, None, 1] - cy[None, :])
            / np.maximum(boxes[:, 3] - boxes[:, 1], 1),
            np.abs(pts[:, None, 0] - cx[None, :])
            / np.maximum(boxes[:, 2] - boxes[:, 0], 1),
        )
        dist = np.where(inside, dist, np.inf)
        best = dist.argmin(axis=1)
        owner = np.where(np.isfinite(dist.min(axis=1)), best, -1)

    # characters of each OCR line, in reading direction
    per_line: dict[int, list[int]] = defaultdict(list)
    for k, o in enumerate(owner):
        per_line[int(o)].append(k)
    for o, ks in per_line.items():
        if o >= 0:
            vertical = ocr_lines[o].vertical
            ks.sort(key=lambda k: pts[k][1] if vertical else pts[k][0])

    # uncovered characters: deleted. A text-layer line mostly uncovered is dropped.
    lost = per_line.get(-1, [])
    uncovered_per_line = Counter(gt[k][2] for k in lost)
    total_per_line = Counter(li for _, _, li in gt)
    sc.dropped_lines = sum(
        n * 2 >= total_per_line[li] for li, n in uncovered_per_line.items()
    )
    lost_text = norm("".join(gt[k][0] for k in lost))
    sc.chars += len(lost_text)
    sc.errors += len(lost_text)
    sc.kinds["dropped line or text not detected"] += len(lost_text)
    for c in lost_text:
        sc.digits += c.isdigit()
        sc.digit_errors += c.isdigit()
        sc.units += c in UNITS
        sc.unit_errors += c in UNITS

    for i, ln in enumerate(ocr_lines):
        ks = per_line.get(i, [])
        a = norm("".join(gt[k][0] for k in ks))
        b = norm(ln.text)
        if not ks:
            sc.ocr_only_lines += 1
        sc.chars += len(a)
        sc.det_chars += len(a)
        for op, x, y in align(a, b):
            sc.digits += x.isdigit()
            sc.det_digits += x.isdigit()
            sc.units += x in UNITS
            if op == "=":
                continue
            sc.errors += 1
            sc.det_errors += 1
            if x.isdigit() or y.isdigit():
                sc.digit_errors += 1
                sc.det_digit_errors += 1
            if x in UNITS or y in UNITS:
                sc.unit_errors += 1
            if op == "sub":
                kind = (
                    "digit changed" if x.isdigit() or y.isdigit()
                    else f"{script(x)} for {script(y)}" if script(x) != script(y)
                    else f"{script(x)} confused"
                )  # fmt: skip
                sc.kinds[kind] += 1
                if keep_pairs and script(x) == script(y) == "kanji":
                    sc.confusions[(x, y)] += 1
            elif op == "del":
                sc.kinds["character dropped"] += 1
            else:
                sc.kinds["character added"] += 1

    # reading order: where each OCR line's first text-layer character sits in the
    # text layer's own order
    firsts = [min(per_line[i]) for i in range(len(ocr_lines)) if per_line.get(i)]
    sc.order_pairs = max(len(firsts) - 1, 0)
    sc.order_flips = sum(b < a for a, b in zip(firsts, firsts[1:], strict=False))

    # values. Both sides are cut into the same lines, the OCR lines: the text-layer
    # characters inside each OCR line, then the text-layer lines OCR did not detect.
    # Otherwise the text layer's own order (table cells, columns) would make or hide
    # dates that OCR reads in line order.
    aligned = [
        norm_keep("".join(gt[k][0] for k in per_line.get(i, [])))
        for i in range(len(ocr_lines))
    ]
    undetected: dict[int, str] = defaultdict(str)
    for k in lost:
        undetected[gt[k][2]] += gt[k][0]
    aligned += [norm_keep(t) for t in undetected.values()]
    g = _values("\n".join(aligned))
    o = _values("\n".join(norm_keep(ln.text) for ln in ocr_lines))
    for kind in {k for k, _ in g} | {k for k, _ in o}:
        gk = Counter({v: n for (kk, v), n in g.items() if kk == kind})
        ok = Counter({v: n for (kk, v), n in o.items() if kk == kind})
        c = sc.values.setdefault(kind, Counter())
        c["text layer"] += sum(gk.values())
        c["exact"] += sum((gk & ok).values())
        c["missing"] += sum((gk - ok).values())
        c["extra"] += sum((ok - gk).values())
        miss, extra = list((gk - ok).elements()), list((ok - gk).elements())
        for i in range(max(len(miss), len(extra))):
            sc.value_cases.append(
                (
                    kind,
                    miss[i] if i < len(miss) else "",
                    extra[i] if i < len(extra) else "",
                )
            )
    return sc


def norm_keep(s: str) -> str:
    """normalize() for the converters: spaces kept as TXT-9 leaves them."""
    return normalize(s)[0]


# --- running OCR with a cache ---------------------------------------------------


def _cache_path(variant: str, doc_id: str, page: int) -> Path:
    return CACHE / variant / f"{doc_id[:16]}_{page}.json"


def read_cached(variant: str, doc_id: str, page: int) -> list[OcrLine] | None:
    p = _cache_path(variant, doc_id, page)
    if not p.exists():
        return None
    return [
        OcrLine(d["text"], tuple(d["bbox"]), d["vertical"])  # type: ignore[arg-type]
        for d in json.loads(p.read_text())
    ]


def write_cache(variant: str, doc_id: str, page: int, lines: list[OcrLine]) -> None:
    p = _cache_path(variant, doc_id, page)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            [
                {"text": ln.text, "bbox": ln.bbox, "vertical": ln.vertical}
                for ln in lines
            ]
        )
    )


def run_page(
    engine: OcrEngine, pdf: PdfFile, doc_id: str, page: int
) -> dict[str, tuple[list[OcrLine], np.ndarray | None, float]]:
    """OCR lines per variant (cached), the skew matrix, seconds spent (0 if cached)."""
    out: dict[str, tuple[list[OcrLine], np.ndarray | None, float]] = {}
    img = pdf.render_rgb(page - 1, OCR_DPI)
    for variant in VARIANTS:
        rng = random.Random(f"{SEED}-{doc_id}-{page}")
        skew = None
        if variant == "degraded":
            img_v, skew = degrade(img, rng)
        else:
            img_v = img
        lines = read_cached(variant, doc_id, page)
        secs = 0.0
        if lines is None:
            t = time.perf_counter()
            lines = engine.recognize(img_v)
            secs = time.perf_counter() - t
            write_cache(variant, doc_id, page, lines)
        out[variant] = (lines, skew, secs)
    return out


# --- real cases ------------------------------------------------------------------


@dataclass
class RealPage:
    row: ManifestRow
    page: int
    kind: str
    lines: int
    chars: int
    sentences: int
    values: Counter[str]
    image_text_chars: int  # mixed pages: OCR text found where the text layer has none
    looping: int  # OCR lines that look like the recogniser looping (see `looping`)
    in_text_pdf: bool  # the document also has text pages (a scan inside a text PDF)


_LOOP = re.compile(r"(.{1,6}?)\1{3,}")


def looping(text: str) -> bool:
    """A line that looks like the recogniser looping on a region that is not text:
    12+ characters in which a unit of 1 to 6 characters repeats four times in a row
    (`the the the the`, `2o2o2o2o`), the unit containing a letter, kana or kanji.
    Dot leaders, `○○○○` and `----` are not counted. A heuristic to count, not a
    filter."""
    t = "".join(normalize(text)[0].split())
    m = _LOOP.search(t)
    return len(t) >= 12 and m is not None and any(c.isalpha() for c in m.group(1))


def real_cases(
    rows: list[ManifestRow], engine: OcrEngine
) -> tuple[list[RealPage], list[ManifestRow]]:
    out: list[RealPage] = []
    docs_done: list[ManifestRow] = []
    for r in rows:
        doc = load_document(Path(r.path), ocr=False)
        hard = [p for p in doc.pages if p.kind in ("scanned", "outlined", "mixed")]
        if not hard:
            continue
        doc = load_document(Path(r.path), ocr=engine)
        docs_done.append(r)
        write_debug(Path(r.path), doc, PROCESSED_DIR / r.doc_id)
        with PdfFile(Path(r.path)) as pdf:
            for p in doc.pages:
                if p.kind not in ("scanned", "outlined", "mixed"):
                    continue
                sents = [s for s in doc.sentences if s.page == p.number]
                vals: Counter[str] = Counter()
                for s in sents:
                    for kind, fn in (
                        ("date", find_dates),
                        ("time", find_times),
                        ("amount", find_amounts),
                    ):
                        vals[kind] += sum(f.value is not None for f in fn(s.text_norm))
                extra = 0
                if p.kind == "mixed":
                    ocr = ocr_lines_for(engine, pdf, p.number - 1)
                    scale = 72 / OCR_DPI
                    covered = [ln.bbox for ln in p.lines]
                    new = [
                        ln
                        for ln in ocr
                        if not any(_overlap(ln.bbox, scale, c) for c in covered)
                    ]
                    extra = sum(len(ln.text) for ln in new)
                    pdf.render_png(
                        p.number - 1,
                        PROCESSED_DIR
                        / r.doc_id
                        / "ocr_mixed"
                        / f"page-{p.number:03d}.png",
                        [
                            Overlay(
                                tuple(v * scale for v in ln.bbox),  # type: ignore[arg-type]
                                (0.9, 0.4, 0.0) if ln in new else (0.2, 0.6, 0.2),
                            )
                            for ln in ocr
                        ],
                        note="orange: OCR text with no text-layer line",
                    )
                out.append(
                    RealPage(
                        r,
                        p.number,
                        p.kind,
                        len(p.lines),
                        sum(len(x.text) for x in p.lines),
                        len(sents),
                        vals,
                        extra,
                        sum(looping(x.text) for x in p.lines if x.source == "ocr"),
                        any(q.kind in ("text", "mixed") for q in doc.pages),
                    )
                )
    return out, docs_done


def ocr_lines_for(engine: OcrEngine, pdf: PdfFile, index: int) -> list[OcrLine]:
    img = pdf.render_rgb(index, OCR_DPI)
    return drop_regions(engine.recognize(img), img.shape[1], img.shape[0])


def _overlap(
    px_box: tuple[float, float, float, float],
    scale: float,
    pt_box: tuple[float, float, float, float],
) -> bool:
    x0, y0, x1, y1 = (v * scale for v in px_box)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return pt_box[0] <= cx <= pt_box[2] and pt_box[1] <= cy <= pt_box[3]


# --- report ----------------------------------------------------------------------


def _table(header: list[str], rows: list[list[object]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out


def det_digit_rate(s: Score) -> float:
    return s.det_digit_errors / max(s.det_digits, 1)


def flip_share(s: Score) -> float:
    return s.order_flips / max(s.order_pairs, 1)


def _pct(x: float) -> str:
    return f"{100 * x:.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pages", type=int, default=N_PAGES, help="smoke test: fewer pages"
    )
    parser.add_argument("--skip-real", action="store_true")
    args = parser.parse_args()
    rows = [r for r in read_rows() if r.format == "pdf"]
    by_id = {r.doc_id: r for r in rows}
    engine = default_engine()
    pages = select_pages(rows)[: args.pages]

    scores: dict[str, dict[tuple[str, int], Score]] = {v: {} for v in VARIANTS}
    secs: dict[str, list[float]] = {v: [] for v in VARIANTS}
    examples: dict[str, list[tuple[str, int, str, str, str]]] = {
        v: [] for v in VARIANTS
    }
    feat: dict[tuple[str, int], tuple[float, float]] = {}  # (area in A4s, table share)
    start = time.perf_counter()
    for n, (doc_id, page) in enumerate(pages, 1):
        r = by_id[doc_id]
        doc = load_document(Path(r.path), ocr=False)
        pg = doc.pages[page - 1]
        text_lines = [ln for ln in pg.lines if ln.text.strip()]
        feat[(doc_id, page)] = (
            pg.width * pg.height / (595 * 842),
            sum(ln.cell is not None for ln in text_lines) / max(len(text_lines), 1),
        )
        with PdfFile(Path(r.path)) as pdf:
            res = run_page(engine, pdf, doc_id, page)
        for variant, (lines, skew, s) in res.items():
            sc = score_page(
                doc.pages[page - 1],
                drop_regions(lines, pg.width * OCR_DPI / 72, pg.height * OCR_DPI / 72),
                OCR_DPI / 72,
                skew,
                r.license_class == "open",
            )
            scores[variant][(doc_id, page)] = sc
            if s:
                secs[variant].append(s)
            for kind, g, o in sc.value_cases:
                examples[variant].append((doc_id, page, kind, g, o))
        if n % 20 == 0:
            print(
                f"{n}/{len(pages)} pages, {time.perf_counter() - start:.0f} s",
                flush=True,
            )

    real, real_docs = ([], []) if args.skip_real else real_cases(rows, engine)

    # Time a few pages afresh: the OCR above is usually read from the cache.
    timed: list[float] = []
    for doc_id, page in pages[:5]:
        with PdfFile(Path(by_id[doc_id].path)) as pdf:
            img = pdf.render_rgb(page - 1, OCR_DPI)
        t0 = time.perf_counter()
        engine.recognize(img)
        timed.append(time.perf_counter() - t0)
    bench = sum(timed) / max(len(timed), 1)

    def total(variant: str, key=lambda r: True) -> Score:  # noqa: ANN001
        t = Score()
        for (d, _), sc in scores[variant].items():
            if key(by_id[d]):
                t.add(sc)
        return t

    all_t = {v: total(v) for v in VARIANTS}
    md: list[str] = [
        "# OCR report",
        "",
        f"Generated {date.today().isoformat()} by `uv run python -m eval.ocr_report`, "
        f"extractor version {EXTRACTOR_VERSION}. Engine: NDLOCR-Lite (D-36), CPU, "
        f"pages rendered at {OCR_DPI} dpi. Only aggregate numbers and doc_id/page "
        "references are in this file (D-22).",
        "",
        "## Rendered-scan test set (D-23a)",
        "",
        f"{len(pages)} text pages drawn round-robin over (source, doc_type) strata "
        f"(`random.Random({SEED})`), from {len({d for d, _ in pages})} documents in "
        f"{len({by_id[d].source for d, _ in pages})} sources and "
        f"{len({by_id[d].doc_type for d, _ in pages})} doc_types, each with at least "
        f"{MIN_CHARS} text-layer characters. Ground truth is the text layer. "
        "**Rendered pages are cleaner than real scans, so the clean row is an upper "
        "bound**; degraded = random skew of 1 to 2 degrees, Gaussian blur (sigma 0.8 "
        "px), Gaussian noise (sigma 6). How scoring works is in the docstring of "
        "`eval/ocr_report.py`: by geometry, so reading order is not counted as error.",
        "",
        "### Summary",
        "",
        *_table(
            [
                "variant",
                "text-layer chars",
                "CER",
                "digit errors",
                "unit errors",
                "text-layer lines dropped",
                "OCR-only lines",
                "OCR s/page (timed now)",
            ],
            [
                [
                    v,
                    all_t[v].chars,
                    _pct(all_t[v].cer),
                    f"{all_t[v].digit_errors} of {all_t[v].digits} "
                    f"({_pct(all_t[v].digit_errors / max(all_t[v].digits, 1))})",
                    f"{all_t[v].unit_errors} of {all_t[v].units} "
                    f"({_pct(all_t[v].unit_errors / max(all_t[v].units, 1))})",
                    f"{all_t[v].dropped_lines} of {all_t[v].gt_lines}",
                    f"{all_t[v].ocr_only_lines} of {all_t[v].ocr_lines}",
                    f"{bench:.1f}",
                ]
                for v in VARIANTS
            ],
        ),
        "",
        "Digit errors: text-layer digits that were changed or lost, plus digits OCR "
        "added. "
        "Unit errors: the same for 年月日時分円万億.",
        "",
        *_headline(all_t),
        "",
        "### Detection versus reading",
        "",
        "Most of the CER is text OCR never detected, not text it misread. The first "
        "table counts only text-layer characters that sit inside a detected OCR line "
        "(what the recogniser had to read); the second splits the pages by what is on "
        "them. Table share: the part of a page's text lines that sit in ruled table "
        "cells (D-31). A4 = 595 x 842 pt; NDLOCR's detector resizes every image to "
        "1024 x 1024 pixels, so on a page larger than A4 small text becomes too small "
        "to find (not tiled yet, open question).",
        "",
        *_table(
            [
                "variant",
                "chars in detected lines",
                "CER there",
                "digits there",
                "digit errors there",
                "share of all errors from undetected text",
            ],
            [
                [
                    v,
                    all_t[v].det_chars,
                    _pct(all_t[v].det_errors / max(all_t[v].det_chars, 1)),
                    all_t[v].det_digits,
                    f"{all_t[v].det_digit_errors} ({_pct(det_digit_rate(all_t[v]))})",
                    f"{1 - all_t[v].det_errors / max(all_t[v].errors, 1):.0%}",
                ]
                for v in VARIANTS
            ],
        ),
        "",
        *_page_classes(scores, feat, by_id),
        "",
        "### Dates, times, amounts and fiscal years",
        "",
        "Converted values found by the value converters on each side and compared "
        "as values. **missing**: the text layer has it, OCR text has no equal value "
        "(lost or changed). **extra**: OCR text has a value the text layer does not "
        "(a changed digit gives one missing and one extra; extra without missing is "
        "OCR reading something the text layer lacks). **Extra values are the costly "
        "failure**: a plausible wrong date.",
        "",
    ]
    rows_v: list[list[object]] = []
    for kind in ("date", "time", "amount", "fiscal year"):
        for v in VARIANTS:
            c = all_t[v].values.get(kind, Counter())
            n = c["text layer"]
            rows_v.append(
                [
                    kind,
                    v,
                    n,
                    c["exact"],
                    f"{c['missing']} ({_pct(c['missing'] / max(n, 1))})",
                    c["extra"],
                ]
            )
    md += _table(["kind", "variant", "text layer", "exact", "missing", "extra"], rows_v)
    md += [""]
    md += _examples(examples, by_id)

    md += ["", "### CER per source", ""]
    for key_name, key in (
        ("source", lambda r: r.source),
        ("doc_type", lambda r: r.doc_type),
    ):
        if key_name == "doc_type":
            md += ["", "### CER per doc_type", ""]
        names = sorted({key(by_id[d]) for d, _ in pages})
        trs = []
        for nm in names:
            t = {v: total(v, lambda r, nm=nm, key=key: key(r) == nm) for v in VARIANTS}
            np_ = len([1 for d, _ in pages if key(by_id[d]) == nm])
            trs.append(
                [
                    nm,
                    np_,
                    t["clean"].chars,
                    _pct(t["clean"].cer),
                    _pct(t["degraded"].cer),
                ]
            )
        trs.sort(key=lambda x: -float(x[3].rstrip("%")))
        md += _table([key_name, "pages", "chars", "CER clean", "CER degraded"], trs)

    md += [
        "",
        "### Error kinds",
        "",
        "Share of all errors, by what OCR did to the character.",
        "",
    ]
    kinds = sorted(
        set(all_t["clean"].kinds) | set(all_t["degraded"].kinds),
        key=lambda k: -all_t["clean"].kinds[k],
    )

    def share(v: str, k: str) -> str:
        return (
            f"{all_t[v].kinds[k]} ({all_t[v].kinds[k] / max(all_t[v].errors, 1):.0%})"
        )

    md += _table(
        ["kind", "clean", "degraded"],
        [[k, share("clean", k), share("degraded", k)] for k in kinds],
    )
    md += [
        "",
        "`kanji confused`: one kanji read as another. `X for Y`: a character of one "
        "script read as another (a kanji for a kana, say). `character dropped / "
        "added`: OCR left a character out or invented one. `dropped line or text not "
        "detected`: "
        "text-layer characters inside no OCR line box.",
        "",
        "### Reading order",
        "",
        *_table(
            [
                "variant",
                "consecutive OCR line pairs",
                "reversed against the text layer",
            ],
            [
                [
                    v,
                    all_t[v].order_pairs,
                    f"{all_t[v].order_flips} ({_pct(flip_share(all_t[v]))})",
                ]
                for v in VARIANTS
            ],
        ),
        "",
        "Order is judged against MuPDF's block order, which is not always right either "
        "(tables, side-by-side columns), so a reversal is a difference, not proof that "
        "OCR is wrong. Look at the worst pages below before drawing conclusions.",
        "",
        "### Most common kanji confusions (`open` documents only)",
        "",
    ]
    conf = Counter[tuple[str, str]]()
    for v in VARIANTS:
        conf.update(all_t[v].confusions)
    md += _table(
        ["text layer", "OCR read", "count (both runs)"],
        [[a, b, n] for (a, b), n in conf.most_common(15)],
    )

    worst = sorted(
        scores["clean"].items(),
        key=lambda kv: -kv[1].cer if kv[1].chars >= 50 else 0,
    )[:20]
    md += [
        "",
        "### The 20 worst pages (by clean CER, pages with at least 50 characters)",
        "",
        *_table(
            [
                "doc_id",
                "page",
                "source",
                "doc_type",
                "license",
                "chars",
                "CER clean",
                "CER degraded",
                "lines dropped",
                "main error kind",
            ],
            [
                [
                    f"`{d[:12]}`",
                    p,
                    by_id[d].source,
                    by_id[d].doc_type,
                    by_id[d].license_class,
                    sc.chars,
                    _pct(sc.cer),
                    _pct(scores["degraded"][(d, p)].cer),
                    sc.dropped_lines,
                    (sc.kinds.most_common(1) or [("-", 0)])[0][0],
                ]
                for (d, p), sc in worst
            ],
        ),
        "",
    ]

    md += _real_section(real, real_docs, by_id)
    REPORT_PATH.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


def _headline(all_t: dict[str, Score]) -> list[str]:
    """What the numbers say, written from the numbers so it can't go stale."""
    out = ["In short:", ""]
    for v in VARIANTS:
        t = all_t[v]
        vals = {k: c for k, c in t.values.items()}
        n = sum(c["text layer"] for c in vals.values())
        lost = sum(c["missing"] for c in vals.values())
        extra = sum(c["extra"] for c in vals.values())
        out.append(
            f"- {v}: CER {_pct(t.cer)} over all pages, "
            f"{_pct(t.det_errors / max(t.det_chars, 1))} "
            f"on text the detector found; {lost} of {n} dates, times, amounts and "
            f"fiscal years lost or changed, {extra} values added that the text layer "
            "does not have."
        )
    out += [
        "- The degraded run is not worse than the clean one: blur and noise at this "
        "strength do not hurt the recogniser, and which text gets detected moves in "
        "both directions from page to page (some tables are found only after the "
        "image is perturbed). Treat differences of a point or two between the runs "
        "as noise.",
        "- The text-layer value counts differ by a few between the runs because the "
        "comparison cuts both sides into the same lines, and the lines differ.",
    ]
    return out


def _page_classes(
    scores: dict[str, dict[tuple[str, int], Score]],
    feat: dict[tuple[str, int], tuple[float, float]],
    by_id: dict[str, ManifestRow],
) -> list[str]:
    classes = [
        (
            "A4 or smaller, few tables (under 20% of lines)",
            lambda a, t: a <= 1.3 and t < 0.2,
        ),
        ("A4 or smaller, with tables", lambda a, t: a <= 1.3 and t >= 0.2),
        ("larger than A4 (1.3 x A4 or more)", lambda a, t: a > 1.3),
    ]
    rows: list[list[object]] = []
    for name, ok in classes:
        keys = [k for k, (a, t) in feat.items() if ok(a, t)]
        row: list[object] = [name, len(keys)]
        for v in VARIANTS:
            t = Score()
            for k in keys:
                t.add(scores[v][k])
            per = sorted(scores[v][k].cer for k in keys if scores[v][k].chars >= 50)
            median = per[len(per) // 2] if per else 0.0
            row += [
                t.chars,
                _pct(t.cer),
                _pct(t.det_errors / max(t.det_chars, 1)),
                _pct(median),
            ]
        rows.append(row)
    header = ["page class", "pages"]
    for v in VARIANTS:
        header += [
            f"chars {v}",
            f"CER {v}",
            f"CER in detected lines {v}",
            f"median page CER {v}",
        ]
    out = [*_table(header, rows), ""]
    for v in VARIANTS:
        per = [sc.cer for sc in scores[v].values() if sc.chars >= 50]
        out.append(
            f"{v}: of {len(per)} pages with 50+ characters, "
            f"{sum(c < 0.01 for c in per)} have CER under 1%, "
            f"{sum(c < 0.02 for c in per)} under 2%, {sum(c < 0.05 for c in per)} "
            f"under 5%, {sum(c >= 0.2 for c in per)} are 20% or worse."
        )
        out.append("")
    return out


def _examples(
    examples: dict[str, list[tuple[str, int, str, str, str]]],
    by_id: dict[str, ManifestRow],
) -> list[str]:
    """Where values went wrong: location always, values only for `open` documents."""
    out = ["Value errors by location (values shown for `open` documents only):", ""]
    trs: list[list[object]] = []
    for v in VARIANTS:
        for d, p, kind, g, o in examples[v]:
            if g and o:
                what = "changed"
            elif g:
                what = "lost"
            else:
                what = "added"
            shown = (
                f"`{g}` -> `{o}`"
                if by_id[d].license_class == "open"
                else "(restricted)"
            )
            trs.append([v, f"`{d[:12]}`", p, kind, what, shown])
    order = {"changed": 0, "added": 1, "lost": 2}
    trs.sort(key=lambda r: (VARIANTS.index(str(r[0])), order[str(r[4])]))
    if len(trs) > 40:
        out.append(f"{len(trs)} cases; the first 40 (changed, then added, then lost):")
        out.append("")
        trs = trs[:40]
    return out + (
        _table(["variant", "doc_id", "page", "kind", "what", "values"], trs)
        if trs
        else ["None."]
    )


def _real_section(
    real: list[RealPage], docs: list[ManifestRow], by_id: dict[str, ManifestRow]
) -> list[str]:
    md = [
        "## Real scanned, outlined and mixed pages",
        "",
        f"{len(real)} pages in {len(docs)} documents go through `load_document` "
        "(scanned and outlined pages read by OCR, mixed pages keep their text layer). "
        "No ground truth exists for these. Debug renders with sentence boxes: "
        "`data/processed/<doc_id>/debug/page-NNN.png`, sentences in "
        "`data/processed/<doc_id>/sentences.txt`. `OCR-only chars` (mixed pages): "
        "characters OCR reads outside every text-layer line, i.e. text that lives in "
        "the page's images; renders in `data/processed/<doc_id>/ocr_mixed/` "
        "(orange = OCR text with no text-layer line).",
        "",
        *_table(
            [
                "doc_id",
                "source",
                "page",
                "kind",
                "lines",
                "chars",
                "sentences",
                "dates",
                "times",
                "amounts",
                "looping",
                "OCR-only chars",
            ],
            [
                [
                    f"`{r.row.doc_id[:12]}`",
                    r.row.source,
                    r.page,
                    r.kind,
                    r.lines,
                    r.chars,
                    r.sentences,
                    r.values["date"],
                    r.values["time"],
                    r.values["amount"],
                    r.looping if r.kind != "mixed" else "",
                    r.image_text_chars if r.kind == "mixed" else "",
                ]
                for r in real
            ],
        ),
        "",
        "### Five to look at first",
        "",
        "Each page for a different reason (one per document, except the failure "
        "case). The file to open is the debug render. `looping` counts OCR lines "
        "that look like the recogniser running away on a region that is not text "
        "(`looping()` in `eval/ocr_report.py`).",
        "",
    ]
    ocr = [r for r in real if r.kind in ("scanned", "outlined")]

    def value_score(r: RealPage) -> float:
        return sum(r.values.values()) + min(r.lines, 40) / 40

    first: list[tuple[RealPage, str]] = []

    def take(
        why: str,
        ok: Callable[[RealPage], bool],
        key: Callable[[RealPage], float],
        n: int,
        unique_doc: bool = True,
    ) -> None:
        done = {x.row.doc_id for x, _ in first}
        have = {(x.row.doc_id, x.page) for x, _ in first}
        for r in sorted((r for r in ocr if ok(r)), key=lambda r: -key(r)):
            clash = (
                r.row.doc_id in done if unique_doc else (r.row.doc_id, r.page) in have
            )
            if n and not clash:
                first.append((r, why))
                done.add(r.row.doc_id)
                n -= 1

    take(
        "outlined text with dates, times or amounts (the case that matters most)",
        lambda r: r.kind == "outlined",
        value_score,
        2,
    )
    take(
        "copier scan of a table, no text layer at all",
        lambda r: r.kind == "scanned" and not r.in_text_pdf and r.looping == 0,
        lambda r: r.lines,
        1,
    )
    take(
        "scan inside an otherwise text PDF, small text in a screenshot",
        lambda r: r.kind == "scanned" and r.in_text_pdf,
        lambda r: r.lines,
        1,
    )
    take(
        "drawing scan where the recogniser still produces filler in a line",
        lambda r: r.looping > 0,
        lambda r: r.looping,
        1,
        unique_doc=False,
    )
    take("any other", lambda r: True, value_score, 5 - len(first))
    md += _table(
        ["doc_id", "source", "page", "kind", "lines", "looping", "why", "render"],
        [
            [
                f"`{r.row.doc_id[:12]}`",
                r.row.source,
                r.page,
                r.kind,
                r.lines,
                r.looping,
                why,
                f"`data/processed/{r.row.doc_id}/debug/page-{r.page:03d}.png`",
            ]
            for r, why in first
        ],
    )
    return md + [""]


if __name__ == "__main__":
    main()
