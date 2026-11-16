"""Extraction checks on collected files in data/raw/ (gitignored). Each test skips when
its file is missing, so a fresh clone passes. Run only these with `pytest -m corpus`.

Most of these documents are restricted or unknown (D-22), which is why they can't be
committed as fixtures."""

from collections.abc import Callable
from pathlib import Path

import pytest
from shiori_core.ingest import load_document

pytestmark = pytest.mark.corpus
CorpusPdf = Callable[[str], Path]


@pytest.mark.parametrize(
    ("doc_id", "pages"),
    [
        ("7c76af66d35d", 11),  # Toyama, Microsoft: Print To PDF (D-23)
        ("aeedf544969c", 5),  # Asahikawa 仕様書, Print To PDF (D-23)
        ("12e3ac14da00", 4),  # Hachioji, Print To PDF, found in Phase 2
        ("6df340ac7a35", 1),  # Hachioji, Print To PDF, found in Phase 2
    ],
)
def test_outlined_documents(corpus_pdf: CorpusPdf, doc_id: str, pages: int) -> None:
    assert [p.kind for p in load_document(corpus_pdf(doc_id), ocr=False).pages] == [
        "outlined"
    ] * pages


@pytest.mark.parametrize(
    ("doc_id", "pages"),
    [
        ("e102e3ce787c", 5),  # Nara, KONICA MINOLTA copier (D-23)
        ("7fb45ac7dec4", 1),  # Okayama, one image (D-23)
        ("4c51f1da8161", 4),  # Niigata, DocuCentre copier, found in Phase 2
    ],
)
def test_scanned_documents(corpus_pdf: CorpusPdf, doc_id: str, pages: int) -> None:
    assert [p.kind for p in load_document(corpus_pdf(doc_id), ocr=False).pages] == [
        "scanned"
    ] * pages


@pytest.mark.parametrize(
    ("doc_id", "scanned_page"),
    [("01204a43ed1d", 7), ("e81e9338bfca", 11)],  # Asahikawa, JUST Note (D-23)
)
def test_one_scanned_page_inside_a_text_pdf(
    corpus_pdf: CorpusPdf, doc_id: str, scanned_page: int
) -> None:
    doc = load_document(corpus_pdf(doc_id), ocr=False)
    assert [p.number for p in doc.pages if p.kind == "scanned"] == [scanned_page]
    assert all(p.kind == "text" for p in doc.pages if p.number != scanned_page)


def test_wmode_vertical_text_is_one_flagged_line(corpus_pdf: CorpusPdf) -> None:
    # Asahikawa 1cfb7dc75bbb p1: a table label in a vertical font (wmode 1), one
    # MuPDF line per character.
    page = load_document(corpus_pdf("1cfb7dc75bbb"), ocr=False).pages[0]
    line = next(line for line in page.lines if "企画提案内容" in line.text)
    assert line.vertical


def test_solid_vertical_labels_are_joined(corpus_pdf: CorpusPdf) -> None:
    # Hachioji ac58cfb92021 p19, a resume-style form: labels set vertically with
    # gaps of 0.1 character, each character its own fragment.
    page = load_document(corpus_pdf("ac58cfb92021"), ocr=False).pages[18]
    vertical = {line.text.strip() for line in page.lines if line.vertical}
    assert {"生年月日", "現住所", "最寄駅"} <= vertical


@pytest.mark.parametrize(
    ("doc_id", "page", "cell"),
    [("d97dc236d8fc", 10, "○"), ("a0f13100504f", 4, "４")],
)
def test_one_character_table_cells_stay_apart(
    corpus_pdf: CorpusPdf, doc_id: str, page: int, cell: str
) -> None:
    # Table rows with one character per cell are 0.35 to 0.49 characters apart;
    # joining them would merge values from different rows.
    lines = load_document(corpus_pdf(doc_id), ocr=False).pages[page - 1].lines
    assert cell in {line.text.strip() for line in lines}
    assert not any(line.vertical and line.text.count(cell) > 1 for line in lines)


def test_pua_bullets_kept_in_digital_spec(corpus_pdf: CorpusPdf) -> None:
    # TXT-11, doc 756d17c84006 (Digital spec): 31 U+F09E bullets.
    doc = load_document(corpus_pdf("756d17c84006"), ocr=False)
    text = "".join(line.text for p in doc.pages for line in p.lines)
    assert text.count("\uf09e") == 31


def test_gaiji_kept_in_nara_spec(corpus_pdf: CorpusPdf) -> None:
    # TXT-12, doc faef6e6a09d9 (Nara City spec) p3: 都 + U+E27D (外字 for 祁)
    # + 南之庄町. The 外字 is an image with /ActualText, recovered by pdf.py.
    doc = load_document(corpus_pdf("faef6e6a09d9"), ocr=False)
    assert any("都" in line.text for line in doc.pages[2].lines)
