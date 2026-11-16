"""html_ingest: HTML notices -> sentences anchored in the extracted text (D-37)."""

from pathlib import Path

import pytest
from shiori_core.html_ingest import decode, load_html_document
from shiori_core.models import Document

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "collector"


def _doc(tmp_path: Path, html: str, enc: str = "utf-8") -> Document:
    path = tmp_path / "page.html"
    path.write_bytes(html.encode(enc))
    return load_html_document(path)


@pytest.fixture(scope="module")
def pportal() -> Document:
    # p-portal notice 331517 (WTO, 総務省), as served; open licence (D-18)
    return load_html_document(FIXTURES / "pportal_notice_331517.html")


def test_anchors_point_into_the_stored_text(pportal: Document) -> None:
    assert pportal.format == "html" and pportal.pages == [] and pportal.text
    assert [s.id for s in pportal.sentences] == [
        f"h_s{n}" for n in range(1, len(pportal.sentences) + 1)
    ]
    for s in pportal.sentences:
        assert s.anchor is not None and s.boxes == [] and s.page == 0
        assert s.source == "html"
        # text_orig is the slice; a sentence joined across a <br> has the break in it
        assert (
            pportal.text[s.anchor.start : s.anchor.end].replace("\n", "") == s.text_orig
        )
    # anchors run forward and never overlap
    spans = [(s.anchor.start, s.anchor.end) for s in pportal.sentences if s.anchor]
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:], strict=False))


def test_navigation_and_page_chrome_are_left_out(pportal: Document) -> None:
    assert pportal.text and "ポータルトップ" not in pportal.text
    assert pportal.sentences[0].text_orig == "調達情報の詳細"


def test_section_paths_follow_the_numbering(pportal: Document) -> None:
    by_start = {s.text_orig[:12]: s for s in pportal.sentences}
    assert by_start["(2) 入札書の受領期限"].section_path == ["3", "(2)"]
    assert by_start["２　競争参加資格"].section_path == ["2"]


def test_english_summary_is_english_with_the_heading_path(pportal: Document) -> None:
    i = next(
        n for n, s in enumerate(pportal.sentences) if s.text_orig.endswith("Summary")
    )
    j = next(n for n, s in enumerate(pportal.sentences) if s.text_orig == "調達資料１")
    summary = pportal.sentences[i:j]
    assert len(summary) >= 10
    assert {s.language for s in summary} == {"en"}
    assert {tuple(s.section_path) for s in summary} == {("5",)}  # not (1) ... (8), (a)
    assert {s.language for s in pportal.sentences[:i]} == {"ja"}
    assert pportal.sentences[j].language == "ja"  # Japanese again: the Summary ended


def test_a_br_inside_an_open_bracket_joins_the_lines(pportal: Document) -> None:
    # `...第一会議室（ <br> 418号室）`: the bracket is unclosed at the break.
    s = next(s for s in pportal.sentences if "418号室" in s.text_orig)
    assert s.text_orig.endswith("総務省第二庁舎第一会議室（418号室）")
    assert pportal.text and "\n" in pportal.text[s.anchor.start : s.anchor.end]  # type: ignore[union-attr]


def test_known_limit_weekday_after_a_br_is_not_rejoined(pportal: Document) -> None:
    # `令和４年12月27日 <br> （火）14時`: the date and its weekday end up in two
    # sentences (open question: no safe text rule joins them).
    texts = [s.text_orig for s in pportal.sentences]
    assert any(t.endswith("令和４年12月27日") for t in texts)
    assert any(t.startswith("（火）14時") for t in texts)


def test_stub_notice_gives_a_document_without_errors(tmp_path: Path) -> None:
    # p-portal stubs say only 別添のとおり ("as attached"); the notice is a GEPS file.
    doc = _doc(
        tmp_path, "<html><body><article><p>別添のとおり</p></article></body></html>"
    )
    assert [s.text_orig for s in doc.sentences] == ["別添のとおり"]
    assert doc.sentences[0].anchor is not None


@pytest.mark.parametrize(
    "html", ["", "<html><body></body></html>", "<article></article>", "<p>plain</p>"]
)
def test_pages_with_nothing_to_read_give_no_sentences(
    tmp_path: Path, html: str
) -> None:
    doc = _doc(tmp_path, html)
    assert doc.sentences == []


def test_hidden_and_navigation_elements_are_skipped(tmp_path: Path) -> None:
    doc = _doc(
        tmp_path,
        '<main><nav>メニュー</nav><p class="hide" id="skip">本文</p>'
        '<p aria-hidden="true">隠す</p><script>var x = "a";</script>'
        "<p>入札公告</p><footer>連絡先</footer></main>",
    )
    assert doc.text == "入札公告"


def test_the_first_container_in_the_priority_list_wins(tmp_path: Path) -> None:
    # Okayama-style: #main_body inside #main (breadcrumb outside main_body)
    html = (
        '<div id="main"><p>パンくず</p>'
        '<div id="main_body"><p>入札に係る公告</p></div></div>'
    )
    assert _doc(tmp_path, html).text == "入札に係る公告"


def test_lines_join_only_across_br_not_across_elements(tmp_path: Path) -> None:
    # A heading followed by a paragraph that starts with hiragana stays two sentences;
    # inside one paragraph a <br> before a hiragana tail joins.
    doc = _doc(
        tmp_path, "<main><h2>概要</h2><p>この業務は、</p><p>次の<br>とおり。</p></main>"
    )
    assert [s.text_orig for s in doc.sentences] == [
        "概要",
        "この業務は、",
        "次のとおり。",
    ]


def test_br_inside_an_element_starts_a_new_line(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "<main><p>(1) 品名<br />(2) 数量</p></main>")
    assert doc.text == "(1) 品名\n(2) 数量"
    assert [s.section_path for s in doc.sentences] == [["(1)"], ["(2)"]]


def test_decode_falls_back_to_japanese_encodings() -> None:
    text = "入札公告"
    assert decode(text.encode("utf-8")) == text
    assert decode(text.encode("cp932")) == text
    assert decode(text.encode("euc_jp")) == text


@pytest.mark.parametrize(
    "name",
    ["hokkaido_267662", "wakayama_d00222761", "okayama_1055020", "funabashi_p146281"],
)
def test_tender_pages_of_other_sites_give_sentences(name: str) -> None:
    doc = load_html_document(FIXTURES / f"{name}.html")
    assert len(doc.sentences) >= 5
    assert doc.text and "javascript" not in doc.text.lower()
    for s in doc.sentences:
        assert s.anchor is not None
        assert doc.text[s.anchor.start : s.anchor.end].replace("\n", "") == s.text_orig


def test_a_latin_heading_in_a_japanese_document_still_opens_a_level(
    tmp_path: Path,
) -> None:
    # `2 SLA(Service Level Agreement)` is English text and also a numbered heading
    # (doc 30a0c121..., p4, there numbered 10): outside a Summary, language does not
    # change numbering.
    doc = _doc(
        tmp_path,
        "<main><p>1 契約</p><p>2 SLA(Service Level Agreement)</p>"
        "<p>(1) 内容</p></main>",
    )
    assert [s.section_path for s in doc.sentences] == [["1"], ["2"], ["2", "(1)"]]
    assert [s.language for s in doc.sentences] == ["ja", "en", "ja"]
