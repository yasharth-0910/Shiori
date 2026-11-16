"""Phase 2 part A: ingest, extract_text, clean and debug_render on committed fixtures
(tests/fixtures/pdf/README.md lists where each page comes from)."""

from pathlib import Path

import pymupdf
import pytest
from shiori_core.clean import flag_furniture
from shiori_core.debug_render import render
from shiori_core.ingest import PasswordProtectedError, classify, load_document
from shiori_core.models import Document, Line, Page

PDF_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pdf"


def _load(name: str) -> Document:
    return load_document(PDF_FIXTURES / f"{name}.pdf", ocr=False)


def _texts(page: Page) -> list[str]:
    return [line.text.strip() for line in page.lines]


def _check_invariants(doc: Document) -> None:
    for page in doc.pages:
        for n, line in enumerate(page.lines, start=1):
            assert line.id == f"p{page.number}_l{n}"
            assert line.text == "".join(ch.c for ch in line.chars)
            for x0, y0, x1, y1 in [line.bbox] + [ch.bbox for ch in line.chars]:
                assert -1 <= x0 <= x1 <= page.width + 1
                assert -1 <= y0 <= y1 <= page.height + 1


@pytest.mark.parametrize(
    "name",
    [
        "digital_text",
        "wakayama_table",
        "jma_spaced_digits",
        "wakayama_paren_numbers",
        "okayama_scanned",
        "okayama_rotated_vertical",
    ],
)
def test_lines_keep_every_char_with_a_box_on_the_page(name: str) -> None:
    _check_invariants(_load(name))


# --- ingest: page kinds -------------------------------------------------------


def test_text_and_table_pages_are_text() -> None:
    assert [p.kind for p in _load("digital_text").pages] == ["text", "text"]
    assert _load("wakayama_table").pages[0].kind == "text"


def test_okayama_image_page_is_scanned() -> None:
    # doc 7fb45ac7dec4..., a PC layout drawing published as one image (D-23)
    page = _load("okayama_scanned").pages[0]
    assert page.kind == "scanned"
    assert page.char_count == 0
    assert page.image_cover > 0.9


@pytest.mark.parametrize(
    ("chars", "suspect", "cover", "paths", "kind"),
    [
        (0, 0, 0.0, 36108, "outlined"),  # Toyama 7c76af66d35d p1, Print To PDF
        (18, 0, 0.0, 30395, "outlined"),  # Asahikawa aeedf544969c p1: a few real chars
        (0, 0, 1.0, 0, "scanned"),  # Nara e102e3ce787c, copier scan
        (2, 0, 0.51, 1, "scanned"),  # Asahikawa 01204a43ed1d p7, scan inside text PDF
        (76, 0, 0.62, None, "mixed"),  # Niigata 69bb4a0580c8 p4, drawing with text
        (0, 0, 0.0, 0, "blank"),  # Wakayama 12f50d0602ce p3
        (5, 0, 0.0, 0, "text"),  # Hokkaido fc885fc55e07 p2, a short page
        (1097, 0, 0.0, None, "text"),
        (40, 30, 0.0, 0, "text"),  # garbled but not empty: stays text, report flags it
    ],
)
def test_classify_corpus_cases(
    chars: int, suspect: int, cover: float, paths: int | None, kind: str
) -> None:
    assert classify(chars, suspect, cover, paths) == kind


def test_blank_and_outlined_pages_end_to_end(tmp_path: Path) -> None:
    doc = pymupdf.open()
    doc.new_page()
    page = doc.new_page()
    shape = page.new_shape()
    for i in range(2500):  # vector strokes, like text drawn as outlines
        shape.draw_line((50 + i % 50, 50 + i // 50), (51 + i % 50, 51 + i // 50))
    shape.finish(color=(0, 0, 0))
    shape.commit()
    path = tmp_path / "synthetic.pdf"
    doc.save(path)
    assert [p.kind for p in load_document(path, ocr=False).pages] == [
        "blank",
        "outlined",
    ]


def test_password_protected_pdf_raises(tmp_path: Path) -> None:
    doc = pymupdf.open(PDF_FIXTURES / "jma_spaced_digits.pdf")
    path = tmp_path / "locked.pdf"
    aes = pymupdf.PDF_ENCRYPT_AES_256  # pyright: ignore[reportAttributeAccessIssue]
    doc.save(path, encryption=aes, user_pw="x", owner_pw="y")
    with pytest.raises(PasswordProtectedError):
        load_document(path, ocr=False)


# --- extract_text ------------------------------------------------------------


def test_no_synthetic_spaces_between_digits() -> None:
    # TXT-9, doc 209ff2190e47 (JMA) p1: MuPDF's default inserts spaces at glyph
    # gaps and gives `1 6 日`; the PDF itself has no spaces there.
    texts = _texts(_load("jma_spaced_digits").pages[0])
    assert "令和８年６月16日" in texts
    assert not any("1 6" in t for t in texts)


def test_real_spaces_are_kept() -> None:
    # TXT-9, doc 2a4dacf5624b (Digital) p3: these spaces are glyphs in the PDF.
    texts = _texts(_load("digital_text").pages[0])
    assert any(t.startswith("令和 2 年 12 月 25 日に閣議決定") for t in texts)


def test_pua_bullets_are_kept() -> None:
    # TXT-11, doc 2a4dacf5624b p22: U+F09F bullets at line starts, never dropped.
    texts = _texts(_load("digital_text").pages[1])
    assert sum(t.startswith(" ") for t in texts) == 5


def test_parenthesized_number_glyphs_are_kept() -> None:
    # TXT-13, doc 0f7b9667dcd5 (Wakayama) p6: one glyph each, not "(1)".
    texts = _texts(_load("wakayama_paren_numbers").pages[0])
    assert [t[0] for t in texts if t.startswith(("⑴", "⑵", "⑶"))] == ["⑴", "⑵", "⑶"]


def test_table_cells_stay_separate_lines() -> None:
    # doc 0caedcbd7355 (Wakayama) p1: row 実施体制 | 5 | ×2 | 10 is four lines.
    texts = _texts(_load("wakayama_table").pages[0])
    assert "実施体制" in texts
    assert texts.count("×2") >= 2


def test_rotated_page_boxes_are_on_the_displayed_page() -> None:
    # doc 6b36d69abc0d (Okayama) p6 has /Rotate 90: displayed landscape, text reads
    # horizontally, so lines are wide, not tall, and not vertical.
    page = _load("okayama_rotated_vertical").pages[0]
    assert (page.rotation, page.width > page.height) == (90, True)
    title = next(
        line for line in page.lines if line.text.strip() == "委 任 状 の 記 入 要 領"
    )
    x0, y0, x1, y1 = title.bbox
    assert x1 - x0 > 5 * (y1 - y0)
    assert y1 < page.height / 4  # top of the displayed page
    assert not title.vertical


def test_rotating_a_page_rotates_boxes_not_text(tmp_path: Path) -> None:
    src = pymupdf.open(PDF_FIXTURES / "digital_text.pdf")
    src.select([0])
    src[0].set_rotation(90)
    path = tmp_path / "rotated.pdf"
    src.save(path)
    upright = _load("digital_text").pages[0]
    rotated = load_document(path, ocr=False).pages[0]
    assert (rotated.width, rotated.height) == pytest.approx(
        (upright.height, upright.width)
    )
    assert sorted(_texts(rotated)) == sorted(_texts(upright))
    # Shown turned 90 degrees, the text now runs top to bottom.
    assert all(line.vertical for line in rotated.lines if line.text.strip())
    _check_invariants(load_document(path, ocr=False))


def test_letter_spaced_vertical_text_is_not_joined() -> None:
    # Known limitation. doc 6b36d69abc0d p9, envelope: 岡山県知事 is written
    # vertically with gaps of 0.7 characters, wider than table rows, so each
    # character stays its own line. Solid vertical text is joined (corpus test).
    texts = _texts(_load("okayama_rotated_vertical").pages[1])
    assert "岡山県知事" not in texts
    assert {"岡", "山", "県", "知", "事"} <= set(texts)


def test_mismapped_vertical_glyphs_are_counted_not_dropped() -> None:
    # Same page: vertical-form brackets and ー come out as CJK Ext A / Phonetic
    # Extensions code points (䥹 for （, ᶌ for ー). Kept, and counted as suspect.
    page = _load("okayama_rotated_vertical").pages[1]
    assert page.suspect_chars == 6
    assert any("ᶌ" in line.text for line in page.lines)


# --- clean -------------------------------------------------------------------


def _line(
    page: int, n: int, text: str, bbox: tuple[float, float, float, float]
) -> Line:
    return Line(id=f"p{page}_l{n}", page=page, text=text, chars=[], bbox=bbox)


def _page(number: int, lines: list[Line]) -> Page:
    return Page(
        number=number,
        width=600,
        height=800,
        rotation=0,
        kind="text",
        char_count=0,
        suspect_chars=0,
        image_cover=0,
        drawing_count=None,
        lines=lines,
    )


@pytest.mark.parametrize(
    "text",
    [
        "- 3 -",
        "3/12",
        "３／１２",
        "－３－",
        "P.3",
        "3ページ",
        "別-5",
        "Ⅱ調査 - 12",
        "7",
    ],
)
def test_page_numbers_near_the_bottom_are_flagged(text: str) -> None:
    page = _page(1, [_line(1, 1, text, (290, 760, 310, 770))])
    flag_furniture([page])
    assert page.lines[0].furniture == "page_number"


@pytest.mark.parametrize("text", ["第1", "様式1", "(1)", "令和8年", "1 調達内容"])
def test_section_numbers_are_not_page_numbers(text: str) -> None:
    page = _page(1, [_line(1, 1, text, (290, 760, 310, 770))])
    flag_furniture([page])
    assert page.lines[0].furniture is None


def test_page_number_in_mid_page_is_not_flagged() -> None:
    page = _page(1, [_line(1, 1, "3", (290, 400, 300, 410))])
    flag_furniture([page])
    assert page.lines[0].furniture is None


def test_repeated_header_is_flagged_but_form_labels_are_not() -> None:
    pages = [
        _page(
            n,
            [
                _line(n, 1, "＜別添２＞", (500, 30, 560, 42)),  # doc 133bbf88 (Nara)
                _line(
                    n, 2, f"（様式{'１２３４'[n - 1]}）", (40, 30, 100, 42)
                ),  # 706d5a67
                _line(n, 3, "仕様書", (280, 400, 320, 412)),  # mid-page, repeats too
            ],
        )
        for n in range(1, 5)
    ]
    flag_furniture(pages)
    assert [[line.furniture for line in p.lines] for p in pages] == [
        ["header_footer", None, None]
    ] * 4


def test_real_page_numbers_are_flagged() -> None:
    doc = _load("digital_text")
    flagged = [
        (line.id, line.text.strip())
        for p in doc.pages
        for line in p.lines
        if line.furniture
    ]
    assert flagged == [("p1_l37", "3"), ("p2_l43", "22")]


# --- debug_render ------------------------------------------------------------


def test_debug_render_writes_one_png_per_page(tmp_path: Path) -> None:
    path = PDF_FIXTURES / "okayama_rotated_vertical.pdf"
    written = render(path, load_document(path, ocr=False), tmp_path)
    assert [p.name for p in written] == ["page-001.png", "page-002.png"]
    assert all(p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" for p in written)
