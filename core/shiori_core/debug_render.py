"""Draw every sentence on its page so segmentation can be checked by eye.

    uv run python -m shiori_core.debug_render <doc_id | path to pdf>

Writes data/processed/<doc_id>/debug/page-NNN.png and
data/processed/<doc_id>/sentences.txt.

Render colors: sentence boxes alternate blue and purple so neighbouring sentences
can be told apart; orange = sentence in a table cell; green = vertical; red = a line
left out of sentences (header/footer or page number, D-30). The small label above
each sentence's first box is `s{n} {section path}` (the n of p{page}_s{n}). The
magenta note in the top-right corner is the page kind and the measurements it was
decided from.

sentences.txt has one line per sentence: `<id> | <section path> | <text_orig>`, with
the path written `1 > (2) > ア` and `-` when empty. It is meant for a Japanese
reader checking segmentation by hand.

Dev tool: it looks up doc_ids under data/raw/, which the shipped app never has.
"""

import sys
from pathlib import Path

from shiori_core.ingest import load_document
from shiori_core.models import Document, Sentence
from shiori_core.pdf import Color, Overlay, PdfFile

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

BLUE: Color = (0.1, 0.3, 0.9)
PURPLE: Color = (0.55, 0.1, 0.75)
ORANGE: Color = (0.95, 0.5, 0.0)
GREEN: Color = (0.0, 0.6, 0.2)
RED: Color = (0.9, 0.1, 0.1)


def find_pdf(doc_id: str) -> Path:
    matches = sorted(RAW_DIR.rglob(f"{doc_id}*.pdf"))
    if len(matches) != 1:
        raise SystemExit(
            f"expected one PDF for {doc_id!r} under {RAW_DIR}, found {len(matches)}"
        )
    return matches[0]


def path_text(s: Sentence) -> str:
    return " > ".join(s.section_path) or "-"


def sentences_txt(doc: Document) -> str:
    return "".join(f"{s.id} | {path_text(s)} | {s.text_orig}\n" for s in doc.sentences)


def _overlays(doc: Document) -> dict[int, list[Overlay]]:
    by_page: dict[int, list[Overlay]] = {p.number: [] for p in doc.pages}
    vertical = {line.id for p in doc.pages for line in p.lines if line.vertical}
    for i, s in enumerate(doc.sentences):
        color = PURPLE if i % 2 else BLUE
        if s.in_table:
            color = ORANGE
        elif s.boxes[0].line_id in vertical:
            color = GREEN
        label = f"{s.id.rsplit('_s', 1)[1]} {path_text(s)}"
        for k, box in enumerate(s.boxes):
            by_page[box.page].append(Overlay(box.bbox, color, label if k == 0 else ""))
    for p in doc.pages:
        by_page[p.number] += [
            Overlay(line.bbox, RED) for line in p.lines if line.furniture
        ]
    return by_page


def render(path: Path, doc: Document, out_dir: Path) -> list[Path]:
    """Write one PNG per page and return their paths."""
    written: list[Path] = []
    overlays = _overlays(doc)
    with PdfFile(path) as pdf:
        for page in doc.pages:
            note = (
                f"{page.kind}  chars={page.char_count} suspect={page.suspect_chars} "
                f"img={page.image_cover:.2f} paths={page.drawing_count}"
            )
            out = out_dir / f"page-{page.number:03d}.png"
            pdf.render_png(page.number - 1, out, overlays[page.number], note)
            written.append(out)
    return written


def write_debug(path: Path, doc: Document, out_dir: Path) -> list[Path]:
    """Renders in out_dir/debug/ and out_dir/sentences.txt."""
    out_dir.mkdir(parents=True, exist_ok=True)
    txt = out_dir / "sentences.txt"
    txt.write_text(sentences_txt(doc), encoding="utf-8")
    return [*render(path, doc, out_dir / "debug"), txt]


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        raise SystemExit(__doc__)
    arg = argv[0]
    path = Path(arg) if arg.endswith(".pdf") else find_pdf(arg)
    doc = load_document(path)
    for p in write_debug(path, doc, PROCESSED_DIR / doc.id):
        print(p)


if __name__ == "__main__":
    main(sys.argv[1:])
