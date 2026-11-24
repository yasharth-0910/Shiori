"""OCR: the engine interface, how OCR lines enter the pipeline, and (when the models
are on this machine) a real read. Fake engines make the pipeline tests independent of
the models."""

from datetime import date, time
from pathlib import Path

import numpy as np
import pymupdf
import pytest
from shiori_core.ingest import load_document
from shiori_core.ocr import OCR_DPI, OcrLine, drop_regions, ocr_page
from shiori_core.ocr.ndlocr import ndlocr_dir
from shiori_core.pdf import PdfFile
from shiori_core.value_normalize import find_dates, find_times

PDF_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pdf"
_NDL = ndlocr_dir()
HAVE_NDLOCR = _NDL is not None and (_NDL / "src" / "ocr.py").is_file()
needs_ndlocr = pytest.mark.skipif(not HAVE_NDLOCR, reason="NDLOCR-Lite not in models/")


class FakeEngine:
    """Two fixed lines, in pixels of the 200 dpi render (1 point = 2.78 px)."""

    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        self.calls += 1
        assert image.dtype == np.uint8 and image.ndim == 3 and image.shape[2] == 3
        return [
            OcrLine(
                "令和8年10月13日17時までに提出すること。", (100, 100, 900, 140), False
            ),
            OcrLine("", (100, 150, 200, 160), False),  # an empty read is dropped
            OcrLine("(1) 入札書の受領期限", (100, 200, 700, 240), False),
        ]


def _image_page(doc: pymupdf.Document) -> None:
    """An A4 page that is one picture: no text layer, 100% image cover."""
    page = doc.new_page(width=595, height=842)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 80), False)
    pix.clear_with(255)
    page.insert_image(page.rect, pixmap=pix)


def _text_page(doc: pymupdf.Document, with_image: bool = False) -> None:
    page = doc.new_page(width=595, height=842)
    # A long line and a short last one: the short one is not "full", so the sentence
    # does not run on into the next page.
    page.insert_text(
        (72, 100),
        "This page has a normal text layer with enough characters to be text.",
    )
    page.insert_text((72, 120), "End of the page.")
    if with_image:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 80), False)
        pix.clear_with(255)
        page.insert_image(pymupdf.Rect(0, 150, 595, 842), pixmap=pix)


def _save(doc: pymupdf.Document, tmp_path: Path) -> Path:
    path = tmp_path / "doc.pdf"
    doc.save(path)
    return path


def test_ocr_page_returns_lines_in_points_with_one_box_per_character(
    tmp_path: Path,
) -> None:
    doc = pymupdf.open()
    _image_page(doc)
    with PdfFile(_save(doc, tmp_path)) as pdf:
        lines = ocr_page(FakeEngine(), pdf, 0)
    assert [ln.id for ln in lines] == ["p1_l1", "p1_l2"]
    first = lines[0]
    k = 72 / OCR_DPI
    assert first.bbox == pytest.approx((100 * k, 100 * k, 900 * k, 140 * k))
    assert first.source == "ocr" and not first.vertical
    assert first.text == "".join(c.c for c in first.chars)
    # boxes tile the line box left to right; half-width characters are narrower
    assert first.chars[0].bbox[0] == pytest.approx(first.bbox[0])
    assert first.chars[-1].bbox[2] == pytest.approx(first.bbox[2])
    assert all(
        a.bbox[2] == pytest.approx(b.bbox[0])
        for a, b in zip(first.chars, first.chars[1:], strict=False)
    )
    width = {c.c: c.bbox[2] - c.bbox[0] for c in first.chars}
    assert width["8"] == pytest.approx(width["令"] / 2)


def test_scanned_page_goes_through_ocr_and_segmentation(tmp_path: Path) -> None:
    doc = pymupdf.open()
    _image_page(doc)
    engine = FakeEngine()
    d = load_document(_save(doc, tmp_path), ocr=engine)
    assert [p.kind for p in d.pages] == ["scanned"] and engine.calls == 1
    assert [s.text_orig for s in d.sentences] == [
        "令和8年10月13日17時までに提出すること。",
        "(1) 入札書の受領期限",
    ]
    assert all(s.source == "ocr" and s.language == "ja" for s in d.sentences)
    assert d.sentences[1].section_path == ["(1)"]  # numbering works on OCR text too
    assert d.sentences[0].boxes[0].page == 1


def test_a_scanned_page_inside_a_text_pdf_is_the_only_one_read(tmp_path: Path) -> None:
    # The Asahikawa case (D-23): doc 01204a43ed1d, p7 is a scan inside a text PDF.
    doc = pymupdf.open()
    _text_page(doc)
    _image_page(doc)
    engine = FakeEngine()
    d = load_document(_save(doc, tmp_path), ocr=engine)
    assert [p.kind for p in d.pages] == ["text", "scanned"] and engine.calls == 1
    assert {ln.source for ln in d.pages[0].lines} == {"text_layer"}
    assert {ln.source for ln in d.pages[1].lines} == {"ocr"}
    assert [s.source for s in d.sentences if s.page == 1] == ["text_layer"]
    assert {s.source for s in d.sentences if s.page == 2} == {"ocr"}


def test_mixed_and_text_pages_keep_their_text_layer(tmp_path: Path) -> None:
    doc = pymupdf.open()
    _text_page(doc)
    _text_page(doc, with_image=True)  # image over half the page, text layer present
    engine = FakeEngine()
    d = load_document(_save(doc, tmp_path), ocr=engine)
    assert [p.kind for p in d.pages] == ["text", "mixed"]
    assert engine.calls == 0
    assert all(ln.source == "text_layer" for p in d.pages for ln in p.lines)


def test_ocr_can_be_switched_off(tmp_path: Path) -> None:
    doc = pymupdf.open()
    _image_page(doc)
    d = load_document(_save(doc, tmp_path), ocr=False)
    assert d.pages[0].kind == "scanned" and d.pages[0].lines == [] and d.sentences == []


@needs_ndlocr
def test_real_engine_reads_a_rendered_notice_page(tmp_path: Path) -> None:
    # hokkaido_bid_notice.pdf p1 (doc fb226cbd..., open licence) rendered to a picture:
    # the date, time and the 業務処理要領 line must come back intact.
    src = pymupdf.open(PDF_FIXTURES / "hokkaido_bid_notice.pdf")
    pix = src[0].get_pixmap(dpi=OCR_DPI)
    doc = pymupdf.open()
    page = doc.new_page(width=src[0].rect.width, height=src[0].rect.height)
    page.insert_image(page.rect, pixmap=pix)
    d = load_document(_save(doc, tmp_path), ocr=True)
    assert d.pages[0].kind == "scanned" and len(d.sentences) > 10
    assert all(s.source == "ocr" for s in d.sentences)
    [bid] = [s for s in d.sentences if "入札日時" in s.text_norm]
    dates = [f.value for f in find_dates(bid.text_norm)]
    assert dates == [date(2026, 9, 10)]
    assert [f.value for f in find_times(bid.text_norm)] == [time(13, 30)]
    assert any("業務処理要領" in s.text_norm for s in d.sentences)


def test_a_region_boxed_as_one_line_is_dropped() -> None:
    # Nara e102e3ce787c p4 and Niigata 4c51f1da8161 p2: the detector boxed a whole
    # drawing as one line and the recogniser filled it with `the comple the the`.
    page_w, page_h = 1654, 2339  # A4 at 200 dpi
    region = OcrLine("the comple the the the the", (100, 100, 1500, 1000), False)
    title = OcrLine("別紙", (700, 100, 900, 380), False)  # a 100 pt title is a line
    line = OcrLine("入札公告", (100, 500, 900, 540), False)
    column = OcrLine("縦書きの行", (1500, 100, 1540, 900), True)  # tall but narrow
    kept = drop_regions([region, title, line, column], page_w, page_h)
    assert kept == [title, line, column]
