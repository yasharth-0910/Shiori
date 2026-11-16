"""segment: sentences, IDs, boxes and section paths (TXT-6, DOC-1, DOC-2), and the
header/footer exclusion rule (D-30). Fixtures are listed in fixtures/pdf/README.md."""

from collections.abc import Callable
from datetime import date, time
from pathlib import Path

import pytest
from shiori_core.debug_render import sentences_txt, write_debug
from shiori_core.ingest import load_document
from shiori_core.models import Document, Sentence
from shiori_core.segment import is_english, parse_marker
from shiori_core.value_normalize import find_dates, find_times

PDF_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pdf"
CorpusPdf = Callable[[str], Path]
ALL = [
    "digital_draft_header",
    "hokkaido_notice",
    "digital_text",
    "jma_notice",
    "jma_split_line",
    "okayama_table_spec",
    "wakayama_contract",
    "wakayama_paren_numbers",
    "wakayama_qa_table",
    "wakayama_table",
    "wakayama_summary",
    "hokkaido_bid_notice",
]


def _load(name: str) -> Document:
    return load_document(PDF_FIXTURES / f"{name}.pdf", ocr=False)


def _find(doc: Document, start: str) -> Sentence:
    return next(s for s in doc.sentences if s.text_orig.startswith(start))


def _paths(doc: Document) -> dict[str, list[str]]:
    return {s.text_norm[:12]: s.section_path for s in doc.sentences}


@pytest.mark.parametrize("name", ALL)
def test_sentence_invariants(name: str) -> None:
    doc = _load(name)
    lines = {line.id: line for p in doc.pages for line in p.lines}
    counters: dict[int, int] = {}
    for s in doc.sentences:
        counters[s.page] = counters.get(s.page, 0) + 1
        assert s.id == f"p{s.page}_s{counters[s.page]}"
        assert s.boxes and s.boxes[0].page == s.page
        # text_orig is exactly the original characters of its line spans.
        assert s.text_orig == "".join(
            lines[b.line_id].text[b.start : b.end] for b in s.boxes
        )
        assert s.text_orig == s.text_orig.strip()
        assert len(s.section_path) == len(s.section_titles)
    # Every non-blank line that is not furniture lands in exactly one sentence.
    used = [b.line_id for s in doc.sentences for b in s.boxes]
    body = [
        line.id
        for p in doc.pages
        for line in p.lines
        if line.text.strip() and not line.furniture
    ]
    assert sorted(set(used)) == sorted(body)


# --- list markers --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "style", "label"),
    [
        ("５ １次選考「企画", "num", "5"),  # doc ab5e74f19ac1 (Yokosuka) p6
        ("１．品名及び数量", "num", "1"),  # doc 2aa7506afc08 (JMA) p1
        ("(１) 品目分類番号 71，27", "paren_num", "(1)"),  # 2aa7506afc08 p2
        ("（１）事前登録における", "paren_num", "(1)"),
        ("⑴ 業務名", "paren_num", "(1)"),  # TXT-13, doc 0f7b9667dcd5 (Wakayama)
        ("① 提出方法  持参", "circled", "①"),  # ab5e74f19ac1 p6
        ("㋐ 令和６年４月１日から", "circled_kata", "㋐"),  # doc 6c7ed844e973
        ("ア 本業務の遂行に", "kata", "ア"),  # doc 2a4dacf5624b (Digital) p22
        ("（ア）要件定義", "paren_kata", "(ア)"),
        ("（ａ）電子調達システムにより", "paren_alpha", "(a)"),  # 2aa7506afc08
        ("a 情報取扱者等の異動を", "alpha", "a"),  # 2a4dacf5624b
        ("第１条 甲は、", "dai条", "第1条"),  # 0f7b9667dcd5 p1
        ("第２条（契約期間）", "dai条", "第2条"),
        ("第１章 運用基本事項", "dai章", "第1章"),  # doc fd1a4b7d9a7a (Digital)
        ("1.1 運用の分類", "dotted1", "1.1"),  # fd1a4b7d9a7a
        ("一 当該契約を締結する能力", "kanji", "一"),  # doc 2baf6023 (law-style 号)
        ("（ⅳ）論理設定等", "paren_roman", "(ⅳ)"),  # doc 3fc2a22e507d (Okayama)
        ("・技術審査あり", "bullet", "・"),
        (" 本業務全体を統括し", "bullet", ""),  # TXT-11, 2a4dacf5624b
    ],
)
def test_markers(text: str, style: str, label: str) -> None:
    m = parse_marker(text)
    assert m is not None
    assert (m.style, m.label) == (style, label)


@pytest.mark.parametrize(
    "text",
    [
        "1 6 日",  # spaced digits, not section 1
        "12 月 25 日に",  # a date wrapped onto a line start
        "10 件程度",  # a quantity
        "アイデア",  # a katakana word
        "第一報は",  # "the first report"
        "1.0 版制定",  # a version number, doc fd1a4b7d9a7a
        "3.0秒以内",  # a measurement, doc 8666347d881d
        "2024",
        's etc" in terms',  # English continuation, doc 2aa7506afc08
    ],
)
def test_not_markers(text: str) -> None:
    assert parse_marker(text) is None


# --- sentence boundaries -------------------------------------------------------


def test_sentences_split_on_maru_but_not_inside_brackets() -> None:
    # doc 2aa7506afc08 (JMA notice) p2: the bracketed 。 does not end the sentence.
    doc = _load("jma_notice")
    s = _find(doc, "落札決定に当たっては")
    assert "切り捨てるものとする。）をもって落札価格とする" in s.text_orig
    assert s.text_orig.endswith("記載すること。")


def test_label_value_items_are_their_own_sentences() -> None:
    # TXT-6: items without 。, doc 2aa7506afc08 (JMA notice) p2.
    doc = _load("jma_notice")
    assert _find(doc, "(１) 品目分類番号").text_orig == "(１) 品目分類番号 71，27"
    assert _find(doc, "令和６年６月５日").text_orig == "令和６年６月５日"


def test_right_aligned_signature_does_not_swallow_the_next_line() -> None:
    doc = _load("jma_notice")
    assert (
        _find(doc, "気象衛星センター所長").text_orig == "気象衛星センター所長 立川 英二"
    )


def test_a_visual_line_cut_in_two_is_joined_back() -> None:
    # The extractor gives two lines on one baseline here, which split a date into
    # （令和８年３月 | 31日付官報）. doc 209ff2190e47 (JMA notice) p4.
    s = _find(_load("jma_split_line"), "(10)  競争参加資格の申請")
    assert "「競争参加者の資格に関する公示」（令和８年３月31日付官報）" in s.text_orig
    assert s.text_orig.endswith("申請を受け付ける。")


def test_sentence_runs_across_a_page_break() -> None:
    # doc 2aa7506afc08 p3 -> p4 (fixture pages 3 and 4); the page number between
    # them would break it if it weren't excluded.
    s = _find(_load("jma_notice"), "(７) 警察当局から")
    assert s.id.startswith("p3_")
    assert {b.page for b in s.boxes} == {3, 4}
    assert s.text_orig.endswith("継続しているものでないこと。")


def test_table_cells_are_separate_sentences() -> None:
    # doc 0caedcbd7355 (Wakayama) p1: row 実施体制 | 5 | ×2 | 10.
    doc = _load("wakayama_table")
    texts = [s.text_orig for s in doc.sentences]
    i = texts.index("実施体制")
    assert texts[i + 1 : i + 4] == ["5", "×2", "10"]
    assert all(s.in_table for s in doc.sentences[i : i + 4])


def test_lines_of_one_cell_stay_together() -> None:
    # MuPDF's block order interleaves two cells of one row here, which cut the
    # question 委託業務の上限額（税込1,100 | 千円）とは別に... in two. doc
    # 3f8e45974117 (Wakayama Q&A) p1.
    s = _find(_load("wakayama_qa_table"), "SNS広告及びWeb広告に係る経費は")
    assert (
        "上限額（税込1,100千円）とは別に予算が確保されているものでしょうか。"
        in s.text_orig
    )
    assert s.in_table


def test_bullet_items_in_a_table_cell_split() -> None:
    # TXT-11 PUA bullets inside one cell, doc 2a4dacf5624b (Digital) p22.
    doc = _load("digital_text")
    s = _find(doc, " 本業務全体を統括し")
    assert s.in_table
    assert s.text_orig.endswith("必要な意思決定を行う。")


# --- section paths -------------------------------------------------------------


def test_notice_numbering() -> None:
    # DOC-2 on a national notice: 1 -> (1). doc 2aa7506afc08 (JMA).
    doc = _load("jma_notice")
    assert _find(doc, "次のとおり一般競争入札").section_path == []
    assert _find(doc, "(２) 調達件名及び数量").section_path == ["1", "(2)"]
    item = _find(doc, "(２) 調達件名及び数量")
    assert item.section_titles == ["調達内容", "調達件名及び数量"]
    # A sentence without a marker stays in the section above it.
    assert _find(doc, "なお、電子調達システムによりがたい").section_path == ["1", "(7)"]
    assert _find(doc, "(１) 予算決算及び会計令").section_path == ["2", "(1)"]
    assert _find(doc, "３ 入札書の提出場所等").section_titles == ["入札書の提出場所等"]


def test_spec_numbering() -> None:
    # A Digital Agency spec: (2) -> ア イ ウ. doc 2a4dacf5624b p22.
    doc = _load("digital_text")
    assert _find(doc, "ウ 受注者は").section_path[-2:] == ["(2)", "ウ"]
    assert _find(doc, "また、それが確認できる").section_path[-1] == "ア"
    assert _find(doc, "(３) 業務実施者の適格性").section_path[-1] == "(3)"


def test_contract_articles_and_paragraphs() -> None:
    # 第N条, then ２ ３ for the second and third paragraphs (the first has no
    # number), and ⑴ ⑵ items. doc 0f7b9667dcd5 (Wakayama draft contract) p1.
    doc = _load("wakayama_contract")
    assert _find(doc, "⑵ 業務の内容及び経費").section_path == ["第1条", "(2)"]
    assert _find(doc, "第７条 甲は").section_path == ["第7条"]
    assert _find(doc, "２ 甲は、前項の検査").section_path == ["第7条", "2"]
    assert _find(doc, "３ 甲は、その責め").section_path == ["第8条", "3"]


def test_chapter_then_article() -> None:
    # doc 75a0c52799f9 (Digital draft contract) p2.
    doc = _load("digital_draft_header")
    assert _find(doc, "第３条 甲は").section_path == ["第1章", "第3条"]


def test_ki_starts_the_body() -> None:
    # DOC-1: 記, then ⑴ ア. doc 0f7b9667dcd5 (Wakayama) p6, a form.
    doc = _load("wakayama_paren_numbers")
    assert _find(doc, "令和８年 月 日付けで").section_path == []
    assert _find(doc, "記").section_path == []
    assert _find(doc, "イ 商号又は名称").section_path == ["(1)", "イ"]
    assert _find(doc, "⑵ 再委託する業務内容").section_path == ["(2)"]


def test_numbering_inside_a_table_nests_and_ends_with_the_table() -> None:
    # A spec laid out as one table: 1. then 1.1 in cells. doc 3fc2a22e507d
    # (Okayama) p2. The table's own levels go under the body path.
    doc = _load("okayama_table_spec")
    s = _find(doc, "1.2 10GBASE-R")
    assert s.in_table
    assert s.section_path == ["1", "1.2"]
    assert _find(doc, "2.3 10GBASE-R").section_path == ["2", "2.3"]


def test_heading_inside_a_phantom_one_row_table_still_numbers() -> None:
    # find_tables reports a one-row, three-cell table around this plain heading
    # (invisible drawings). One-row tables are ignored (D-31), so (4) is a body
    # heading. doc fb226cbdd14b (Hokkaido notice) p2. The fixture starts at that
    # page, so 9, 10 and 11 above it can't open a level (a new level starts at
    # 1): the path has no top level.
    doc = _load("hokkaido_notice")
    s = _find(doc, "(4) 入札金額等に係る消費税")
    assert not s.in_table
    assert s.section_path == ["(4)"]
    assert _find(doc, "ア 落札決定に当たっては").section_path == ["(4)", "ア"]


# --- headers and footers (D-30) ----------------------------------------------


def test_repeated_page_header_is_left_out() -> None:
    # （案） ("draft") at the top of every page, doc 75a0c52799f9 (Digital).
    doc = _load("digital_draft_header")
    assert all(p.lines[0].furniture == "header_footer" for p in doc.pages)
    assert not any("（案）" == s.text_orig for s in doc.sentences)


def test_repeated_table_header_row_stays_in() -> None:
    # The table header 項 目 | 必要とする数値等 repeats at the top of each
    # continuation page, doc 3fc2a22e507d (Okayama) p2 to p5. It is inside the
    # table, so it is kept (D-30).
    doc = _load("okayama_table_spec")
    headers = [s for s in doc.sentences if s.text_orig == "必要とする数値等"]
    assert [s.page for s in headers] == [1, 2, 3, 4]
    assert all(s.in_table for s in headers)


# --- corpus (restricted documents, skipped when missing) ---------------------


@pytest.mark.corpus
def test_yokosuka_section_number_and_early_line_break(corpus_pdf: CorpusPdf) -> None:
    doc = load_document(corpus_pdf("ab5e74f19ac1"), ocr=False)
    s = _find(doc, "５ １次選考")
    assert s.section_path == ["5"]
    assert s.text_norm.startswith("5 1次選考")
    # The source breaks 行い / ます。 early; a line starting with hiragana joins.
    assert _find(doc, "審査は、横須賀市").text_orig.endswith("厳正に行います。")
    # An inline (a) ... (b) list wrapped onto a line start opens no level.
    assert _find(doc, "① 提出部数  各１部").section_path == ["4", "(1)", "①"]


@pytest.mark.corpus
def test_table_of_contents_entries_are_separate(corpus_pdf: CorpusPdf) -> None:
    # doc 8a00ce8d8cae (Digital spec) p2: dot leaders, no 。
    doc = load_document(corpus_pdf("8a00ce8d8cae"), ocr=False)
    toc = [s for s in doc.sentences if s.page == 2]
    assert len(toc) > 20
    assert all(len(s.text_orig) < 200 for s in toc)


# --- debug output ------------------------------------------------------------


def test_sentences_txt_and_renders(tmp_path: Path) -> None:
    path = PDF_FIXTURES / "wakayama_paren_numbers.pdf"
    doc = load_document(path, ocr=False)
    written = write_debug(path, doc, tmp_path)
    assert [p.name for p in written] == ["page-001.png", "sentences.txt"]
    lines = (tmp_path / "sentences.txt").read_text(encoding="utf-8").splitlines()
    assert lines == sentences_txt(doc).splitlines()
    assert lines[0] == "p1_s1 | - | 別紙様式（第12条関係）"
    assert "p1_s12 | (1) > イ | イ 商号又は名称" in lines


# --- joining across line breaks, English Summary (items 6 and 7) ---------------------


def test_lowercase_start_continues_the_sentence() -> None:
    # doc 2f2f5bd3... (Wakayama) p3_s31/s32: `...system and` / `lease of equipment`.
    s = _find(_load("wakayama_summary"), "Design, development")
    assert s.id == "p3_s31"
    assert s.text_orig.endswith("system andlease of equipment")  # exact characters
    assert s.text_norm.endswith("financial accounting system and lease of equipment")


def test_unclosed_bracket_continues_the_sentence() -> None:
    # p3_s34/s35: `（Deadline for bids submitted by mail : 5:00 p.m. 26` /
    # `October 2026）`
    s = _find(_load("wakayama_summary"), "2:00 p.m. 27 October 2026")
    assert s.text_norm == (
        "2:00 p.m. 27 October 2026(Deadline for bids submitted by mail : "
        "5:00 p.m. 26 October 2026)"
    )
    assert [len(s.boxes), s.boxes[0].line_id == s.boxes[1].line_id] == [2, False]


def test_japan_and_tel_do_not_fuse_in_text_norm() -> None:
    # p4_s1: `...640-8585, Japan` / `TEL 073-441-3288`
    doc = _load("wakayama_summary")
    s = _find(doc, "1-1 Komatsubaradori")
    assert s.text_norm.endswith("640-8585, Japan TEL 073-441-3288")
    assert "JapanTEL" in s.text_orig  # the original is untouched
    # the space maps back to the line break: the first character of `TEL`
    k = s.text_norm.index(" TEL")
    assert s.text_orig[s.norm_to_orig[k]] == "T"


def test_label_value_lines_that_follow_a_digit_stay_apart() -> None:
    # `FAX 073-423-3502` / `e-mail ...`: lowercase start, but the line before ends in a
    # digit, so they are two items.
    doc = _load("wakayama_summary")
    assert _find(doc, "FAX 073").text_norm == "FAX 073-423-3502"
    assert _find(doc, "e-mail").text_norm.startswith("e-mail e1201003@")


def test_summary_sentences_are_english_with_the_heading_path_only() -> None:
    doc = _load("wakayama_summary")
    ids = [s.id for s in doc.sentences]
    summary = doc.sentences[ids.index("p3_s29") :]
    assert summary[0].text_norm == "14 Summary"
    assert {s.language for s in summary} == {"en"}
    assert {tuple(s.section_path) for s in summary} == {("14",)}  # not (1), (2), (3)
    assert {tuple(s.section_titles) for s in summary} == {("Summary",)}
    before = doc.sentences[: ids.index("p3_s29")]
    assert {s.language for s in before} == {"ja"}
    assert all(s.section_path != ["14"] for s in before)


@pytest.mark.parametrize(
    ("text", "english"),
    [
        ("(1) Contracting entity : SAKAMOTO Katsuhiko, Director-General", True),
        ("Accounting Division, Wakayama Prefectural Government,", True),
        ("FAX 073-423-3502", False),
        ("e-mail contact-b@example.invalid", False),
        ("https://www.pref.wakayama.lg.jp/prefg/ index", False),
        ("category/work/work inheritance", False),  # a URL path, doc 4965207b...
        ("TEL  03-XXXX-XXXX", False),  # a template, doc fd1a4b7d...
        ("TEL", False),
        ("入札公告 Summary of the notice is below", False),  # has Japanese
        ("令和8年度", False),
    ],
)
def test_is_english(text: str, english: bool) -> None:
    assert is_english(text) is english


def test_hokkaido_fused_heading_and_body_is_a_known_limitation() -> None:
    # doc fb226cbd... (Hokkaido) p3_s9: `(10)入札の取りやめ又は延期` and the sentence
    # under it are one line in the text layer (no space, no break). Not split, on
    # purpose (open question): there is no reliable cut point.
    doc = _load("hokkaido_bid_notice")
    s = _find(doc, "(10)入札の取りやめ又は延期")
    fused = (
        "(10)入札の取りやめ又は延期この入札は、取りやめること又は延期することがある。"
    )
    assert s.text_orig == fused
    assert s.section_path == ["8"]


def test_hokkaido_deadline_sentence_reads_back_as_the_bid_time() -> None:
    # D-34 answer: p1_s22 of fb226cbd... is the bid date and time, and the weekday
    # agrees (10 September 2026 is a Thursday).
    s = _find(_load("hokkaido_bid_notice"), "(2) 入札日時")
    assert s.id == "p1_s22"
    [d] = find_dates(s.text_norm)
    assert (d.value, d.warning) == (date(2026, 9, 10), None)
    [t] = find_times(s.text_norm)
    assert t.value == time(13, 30)


def test_hokkaido_spec_is_the_work_processing_procedure() -> None:
    # p1_s10: the specification is `委託業務処理要領による。` (D-34 follow-up)
    s = _find(_load("hokkaido_bid_notice"), "委託業務処理要領による")
    assert s.id == "p1_s10"
