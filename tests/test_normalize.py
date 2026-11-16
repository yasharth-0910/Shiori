"""normalize: text_norm and its offset map (japanese_rules.md section 1)."""

import random
from pathlib import Path

import pytest
from shiori_core.ingest import load_document
from shiori_core.normalize import normalize

PDF_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pdf"


def _check_map(text: str, norm: str, to_orig: list[int]) -> None:
    assert len(norm) == len(to_orig)
    assert all(0 <= i < len(text) for i in to_orig)
    assert to_orig == sorted(to_orig)  # never goes backwards


# Characters that change length or meaning under NFKC, plus the ones the rules
# single out. Random strings over this pool exercise every branch of normalize.
POOL = (
    "０１２３４５６７８９0123456789 　年月日時分円万億令和平成元"
    "①②⑳⑴⑵⒇㋐㋑㈱㍻㋿ｶﾞﾊﾟｼｽﾃﾑ゛゜〜～―－ー‐–—−髙﨑邊﴾﴿О"
    "ᵯ䣖ᶌ䥹䥺䣎⾧︓…・。、（）「」アイ再委託ａｂABC"
)


def test_offset_map_is_valid_and_monotonic_on_random_text() -> None:
    rng = random.Random(20261002)
    for _ in range(3000):
        text = "".join(rng.choice(POOL) for _ in range(rng.randint(0, 40)))
        marker_end = rng.randint(0, min(3, len(text)))
        joins = (
            [rng.randrange(len(text)) for _ in range(rng.randint(0, 3))] if text else []
        )
        _check_map(text, *normalize(text, marker_end, joins))


@pytest.mark.parametrize(
    "name",
    [
        "digital_text",
        "jma_notice",
        "okayama_rotated_vertical",
        "okayama_table_spec",
        "wakayama_contract",
        "wakayama_paren_numbers",
    ],
)
def test_offset_map_is_valid_for_every_fixture_sentence(name: str) -> None:
    for s in load_document(PDF_FIXTURES / f"{name}.pdf", ocr=False).sentences:
        _check_map(s.text_orig, s.text_norm, s.norm_to_orig)


def test_section_number_space_is_kept() -> None:
    # TXT-9 counterexample, open doc 22f7df9a (Okayama): item 2, then a reference
    # to item 1. Joining would give 21の各号 ("each item of 21").
    text = "２ １の各号に掲げる者が、当社又は当団体の経営に実質的に関与していません。"
    assert normalize(text, marker_end=1)[0] == (
        "2 1の各号に掲げる者が、当社又は当団体の経営に実質的に関与していません。"
    )


def test_spaces_between_digits_units_and_eras_are_removed() -> None:
    # TXT-9, doc 2a4dacf5624b (Digital) p3, fixture digital_text.pdf.
    norm, to_orig = normalize("令和 2 年 12 月 25 日に閣議決定")
    assert norm == "令和2年12月25日に閣議決定"
    assert to_orig[2] == 3  # "2" still points at its original glyph
    # doc 10be3ae3df34 (Digital) p5: a space between a number and its unit.
    assert normalize("100 円未満")[0] == "100円未満"


def test_wider_gaps_and_other_spaces_stay() -> None:
    # TXT-1: label-value padding, open doc e8ca985b (Hokkaido).
    assert normalize("（２）提出部数    企画提案書、付属資料とも７部", 3)[0] == (
        "(2)提出部数    企画提案書、付属資料とも7部"
    )
    # A blank form date keeps its blanks, doc 0f7b9667dcd5 (Wakayama) p6.
    assert normalize("令和８年 月 日付け")[0] == "令和8年 月 日付け"


def test_letter_spaced_heading_is_joined() -> None:
    # TXT-10, doc 56d0c0a1cc3f (Digital) p1.
    assert normalize("再 委 託 承 認 申 請 書")[0] == "再委託承認申請書"
    # The space after a list marker stays: doc 0f7b9667dcd5 (Wakayama) p6.
    assert normalize("ア 商 号 又 は", marker_end=1)[0] == "ア 商号又は"


def test_circled_numbers_are_not_flattened() -> None:
    # TXT-3, doc ab5e74f19ac1 (Yokosuka) p6: forms 3-1 to 3-3. NFKC would give
    # 様式31~3.
    assert normalize("「様式３①～③」")[0] == "「様式3①~③」"
    # Circled katakana list markers, doc 6c7ed844e973 (Kanazawa).
    assert normalize("㋐ 令和６年")[0] == "㋐ 令和6年"


def test_parenthesized_number_glyph_expands_to_three_chars() -> None:
    # TXT-13, doc 0f7b9667dcd5 (Wakayama) p1: ⑴ is one glyph.
    norm, to_orig = normalize("⑴ 業務名")
    assert norm == "(1) 業務名"
    assert to_orig[:3] == [0, 0, 0]


def test_nfkc_expansion_and_composition_map_back() -> None:
    norm, to_orig = normalize("㈱ｶﾞｲﾄﾞ")
    assert norm == "(株)ガイド"
    assert to_orig == [0, 0, 0, 1, 3, 4]  # ｶﾞ is two glyphs, one character


@pytest.mark.parametrize(
    ("orig", "norm"),
    [
        ("８時30分～17時", "8時30分~17時"),  # TXT-4, doc ab5e74f19ac1 p6
        ("令和7年3月1日〜令和7年3月31日", "令和7年3月1日~令和7年3月31日"),
        ("様式３―Ａ", "様式3-A"),  # doc ab5e74f19ac1 p6, U+2015
        ("〒204－0012", "〒204-0012"),  # doc 2aa7506afc08 (JMA) p5
        ("3ー5", "3-5"),  # long vowel mark between digits
        ("サーバー", "サーバー"),  # ... but not in a katakana word
        ("髙橋", "高橋"),  # TXT-4 kanji variant
        ("デバイスID﴾Device ID﴿", "デバイスID(Device ID)"),  # TXT-16, 6af28f88 p52
        ("ＣＤО", "CDO"),  # TXT-16 Cyrillic O, doc 52b0c72c1215 (Asahikawa)
        ("部⾧", "部長"),  # TXT-15, doc 520549b35c98 (Asahikawa) p1
        ("※URL︓https", "※URL:https"),  # TXT-16, doc d313a5093ec9 p18
    ],
)
def test_lookalikes(orig: str, norm: str) -> None:
    assert normalize(orig)[0] == norm


def test_misread_vertical_glyphs_are_mapped() -> None:
    # TXT-14, doc 6b36d69abc0d (Okayama) p9, fixture okayama_rotated_vertical.pdf.
    assert normalize("郵送の場合の内封筒䥹裏面は封印のこと䣎䥺")[0] == (
        "郵送の場合の内封筒(裏面は封印のこと。)"
    )
    assert normalize("ᵯiPad端末管理ツᶌルライセンス䣖の")[0] == (
        "「iPad端末管理ツールライセンス」の"
    )


def test_private_use_characters_are_kept() -> None:
    # TXT-11 bullet, doc 756d17c84006 (Digital); TXT-12 外字 for 祁, doc
    # 94521ecfd7f4 (Nara City).
    assert normalize(" 本業務")[0] == " 本業務"
    assert normalize("都南之庄町")[0] == "都南之庄町"


# --- joined lines (item 7, doc 2f2f5bd3..., Wakayama) -------------------------------


def test_joined_latin_lines_get_a_space_that_maps_to_the_line_break() -> None:
    # p4: the lines `...Wakayama City, 640-8585, Japan` and `TEL 073-441-3288` are one
    # sentence; text_orig has them joined with nothing.
    text = "1-1 Komatsubaradori, 640-8585, JapanTEL 073-441-3288"
    join = text.index("TEL")
    norm, to_orig = normalize(text, 0, [join])
    assert norm == "1-1 Komatsubaradori, 640-8585, Japan TEL 073-441-3288"
    k = norm.index(" TEL")
    assert to_orig[k] == to_orig[k + 1] == join
    _check_map(text, norm, to_orig)


def test_joined_digit_and_letter_lines_get_a_space_and_it_is_not_removed() -> None:
    # p3: `... 5:00 p.m. 26` / `October 2026）`; and two numbers (TXT-9 would
    # otherwise delete a space between digits).
    text = "5:00 p.m. 26October 2026"
    assert normalize(text, 0, [text.index("October")])[0] == "5:00 p.m. 26 October 2026"
    text = "100200"
    assert normalize(text, 0, [3])[0] == "100 200"


@pytest.mark.parametrize(
    "text",
    [
        "契約期間開始後",  # Japanese on both sides
        "令和8年10月13日",  # digit then a date unit
        "Japanです",  # Latin then kana
        "（Japan）TEL",  # a bracket between them
    ],
)
def test_joined_lines_without_latin_or_digit_on_both_sides_get_no_space(
    text: str,
) -> None:
    for join in range(1, len(text)):
        if (
            text[join - 1].isascii()
            and text[join - 1].isalnum()
            and text[join].isascii()
            and text[join].isalnum()
        ):
            continue
        assert " " not in normalize(text, 0, [join])[0]
