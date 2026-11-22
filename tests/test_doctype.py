# ruff: noqa: E501
"""Document type from the first page (D-92). Every example is the real first lines of an open document
(doc id prefix in the test name); lines are as the ingest step gives them, with their spaces."""

import pytest
from shiori_core.doctype import detect_doc_type

# 2f2f5bd33296 (和歌山県, notice)
N_2F2F = [
    "入 札 公 告 ",
    "令和8年度和歌山県財務会計システム構築委託・運用保守及び機器等賃貸借について、次のとおり一般",
    "規定に基づき公告する。 ",
]
# 4965207bb115 (和歌山県, spec)
S_4965 = [
    "委託業務仕様書（案） ",
    "１．業務の名称 ",
    "わかやま空き家ポータルサイト構築及び保守管理運営業務 ",
]
# 53320d90cf87 (和歌山県, bid_instructions, a proposal call)
B_5332 = [
    "わかやま空き家ポータルサイト構築及び保守管理運営業務委託に係る ",
    "公募要領 ",
    " 和歌山県（以下「県」という。）では、県に所在する空き家と空き家利活用",
]
# 081d27569eac (和歌山県, bid_instructions): 入札説明書 is the heading, 入札公告 is only inside a long body line
B_081D = [
    "                              和歌山県会計局会計課 ",
    "入 札 説 明 書 ",
    " 令和8年度和歌山県財務会計システム構築委託・運用保守及び機器等賃貸借に係る入札公告に",
    "基づく一般競争入札については、関係法令に定めるもののほか、この入札説明書によるものとす",
]
# 28ad40ea4b1f (bid_instructions): the heading is the second line
B_28AD = [
    "令和８年度ひだかクラウドファンディング活用推進プロジェクト ",
    "事業委託に係る公募要領 ",
    "１ 委託業務の概要 ",
]
# b04d58bd (デジタル庁, bid_instructions): 応募要領
B_B04D = [
    "応募要領 ",
    "１．公募件名 ",
    "防災庁のガバメントソリューションサービスへの移行に係るネットワーク環境構築及",
]
# 2baf6023 (デジタル庁, manifest bid_instructions): 申請書記載要領 is a form guide, not a heading cue
A_2BAF = [
    "令和８年度ガバメントクラウド利用料に関する ",
    "ダイレクト方式納付の取扱業務 ",
    "申請書記載要領（新規） ",
    "令和８年２月  ",
]
# 52bba5f9 (北海道, bid_instructions): 企画提案指示書 is the second line
B_52BB = [
    "令和８年度宇宙関連産業振興事業（衛星データ利活用実証事業）委託業務 ",
    "企画提案指示書 ",
    "１ 委託業務名 ",
]


def test_52bba5f9_kikaku_teian_shijisho_is_bid_instructions():
    assert detect_doc_type(B_52BB) == "bid_instructions"


def test_2f2f5bd3_spaced_heading_is_notice():
    assert detect_doc_type(N_2F2F) == "notice"


def test_4965207b_spec_heading():
    assert detect_doc_type(S_4965) == "spec"


def test_53320d90_koubo_youryou_is_bid_instructions():
    assert detect_doc_type(B_5332) == "bid_instructions"


def test_081d2756_heading_beats_cue_inside_a_long_line():
    assert detect_doc_type(B_081D) == "bid_instructions"


def test_28ad40ea_heading_on_the_second_line():
    assert detect_doc_type(B_28AD) == "bid_instructions"


@pytest.mark.parametrize("lines", [B_B04D], ids=["b04d58bd_oubo_youryou"])
def test_oubo_youryou(lines):
    assert detect_doc_type(lines) == "bid_instructions"


def test_2baf6023_ambiguous_youryou_falls_back_to_notice():
    assert detect_doc_type(A_2BAF) == "notice"


def test_long_body_line_with_a_cue_is_ignored():
    # Built from 2f2f5bd3's wording (the real page has 仕様書による。 as a short body line, after the heading): a long body line that mentions 仕様書 does not make a spec
    body = [
        "令和8年度和歌山県財務会計システム構築委託・運用保守及び機器等賃貸借に係る業務の内容は、仕様書による。"
    ]
    assert detect_doc_type(body) == "notice"


def test_earliest_cue_wins():
    # a spec heading followed by a short line naming 公告 stays a spec
    assert detect_doc_type(["委託業務仕様書（案）", "公告"]) == "spec"


def test_no_text_or_blank_lines_fall_back_to_notice():
    assert detect_doc_type([]) == "notice"
    assert detect_doc_type(["", "  "]) == "notice"
