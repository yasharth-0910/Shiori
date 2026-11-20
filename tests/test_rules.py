# ruff: noqa: E501
"""core/shiori_core/extract/rules.py. The sentences are wording from collected open
documents (doc id prefix in each test name), split the way the extractor split them."""

from shiori_core.extract import rules
from shiori_core.models import Sentence
from shiori_core.normalize import normalize


def sents(*texts: str, prefix: str = "h_s", page: int = 0) -> list[Sentence]:
    out = []
    for n, t in enumerate(texts, 1):
        norm, m = normalize(t)
        out.append(Sentence(id=f"{prefix}{n}", page=page, section_path=[], section_titles=[], text_orig=t,
                            text_norm=norm, norm_to_orig=m, boxes=[]))  # fmt: skip
    return out


def got(doc_type: str, ss: list[Sentence], field: str):
    return rules.extract(doc_type, ss).get(field)


# --- notice_date -----------------------------------------------------------------------


def test_notice_date_f19cddbd4cba_date_above_the_officer() -> None:
    ss = sents("次のとおり一般競争入札に付します。", "令和８年８月28日", "支出負担行為担当官", "出入国在留管理庁次長　内藤惣一郎")  # fmt: skip
    a = got("notice", ss, "notice_date")
    assert a and a.normalized == {"date": "2026-08-28"} and a.citations == ["h_s2"]
    assert (
        a.value_ja == "令和８年８月28日"
    )  # the original wording, full-width digit kept


def test_notice_date_563042df9941_portal_date_under_its_label_is_not_the_notice_date() -> (
    None
):
    ss = sents(
        "公開開始日", "令和08年08月19日", "支出負担行為担当官", "内閣府大臣官房会計課長"
    )
    assert got("notice", ss, "notice_date") is None


def test_notice_date_needs_an_officer_below() -> None:
    assert got("notice", sents("令和８年８月21日", "件名"), "notice_date") is None


def test_notice_date_is_not_asked_of_a_spec() -> None:
    ss = sents("令和８年８月21日", "支出負担行為担当官")
    assert got("spec", ss, "notice_date") is None


# --- procurement_type ------------------------------------------------------------------


def test_procurement_type_136dfba9ee59_open_competitive() -> None:
    a = got("notice", sents("次のとおり一般競争入札に付します。"), "procurement_type")
    assert a and a.normalized == {"type": "open_competitive"}


def test_procurement_type_563042df9941_statement_beats_the_title_line() -> None:
    ss = sents(
        "一般競争入札の入札公告（WTO対象外）", "下記のとおり一般競争入札に付します。"
    )
    a = got("notice", ss, "procurement_type")
    assert a and a.citations == ["h_s2"]


def test_procurement_type_4b0b9d8229c7_proposal_competition() -> None:
    ss = sents("［審査結果掲載］「令和8年度和歌山県データを利活用した公募型研究事業」に係る公募型プロポーザルの実施について")  # fmt: skip
    a = got("tender_page", ss, "procurement_type")
    assert a and a.normalized == {"type": "proposal_competition"}


def test_procurement_type_4b0b9d8229c7_public_research_project_is_not_a_public_call() -> (
    None
):
    assert (
        got("notice", sents("公募型研究事業の募集について"), "procurement_type") is None
    )


def test_procurement_type_two_types_in_one_document_answer_nothing() -> None:
    ss = sents(
        "次のとおり一般競争入札に付します。", "公募型プロポーザル方式により選定する。"
    )
    assert got("notice", ss, "procurement_type") is None


# --- bid_bond and performance_bond -----------------------------------------------------


def test_bonds_136dfba9ee59_waived_in_one_sentence_for_both() -> None:
    ss = sents("(2) 入札保証金及び契約保証金　免除。")
    for f in ("bid_bond", "performance_bond"):
        a = got("notice", ss, f)
        assert (
            a
            and a.normalized == {"status": "waived", "rate_percent": None}
            and a.citations == ["h_s1"]
        )


def test_bonds_563042df9941_heading_and_value_in_two_sentences() -> None:
    a = got("notice", sents("（２）入札保証金及び契約保証金", "免除"), "bid_bond")
    assert a and a.normalized["status"] == "waived" and a.citations == ["h_s1", "h_s2"]
    assert a.value_ja == "入札保証金及び契約保証金\n免除"


def test_bonds_a13baac55c8_waived_with_する() -> None:
    a = got(
        "notice",
        sents("11　入札保証金及び契約保証金　　免除する。"),
        "performance_bond",
    )
    assert a and a.normalized["status"] == "waived"


def test_performance_bond_28ad40ea4b1f_required_with_rate() -> None:
    ss = sents("委託契約締結前に、原則として契約金額の１００分の１０以上を契約保証金として納付してください。", prefix="p6_s")  # fmt: skip
    a = got("bid_instructions", ss, "performance_bond")
    assert a and a.normalized == {"status": "required", "rate_percent": 10.0}
    assert got("bid_instructions", ss, "bid_bond") is None  # only 契約保証金 is in it


def test_bond_with_a_condition_answers_nothing() -> None:
    ss = sents("契約保証金は、ただし書の場合に限り免除する。")
    assert got("notice", ss, "performance_bond") is None


# --- tax_basis -------------------------------------------------------------------------


def test_tax_basis_136dfba9ee59_award_clause_split_over_sentences() -> None:
    ss = sents("なお、落", "札決定に当たっては、入札書に記載された金", "額に当該金額の10パーセントに相当する額を", "加算した金額（当該金額に１円未満の端数があるときは、その端数金額を切り捨てるものとする。）をもって落札価格とする")  # fmt: skip
    a = got("notice", ss, "tax_basis")
    assert (
        a
        and a.normalized == {"basis": "bid_excludes_tax"}
        and a.citations == ["h_s3", "h_s4"]
    )


def test_tax_basis_28ad40ea4b1f_amount_with_tax() -> None:
    a = got(
        "bid_instructions",
        sents("金６９０千円（消費税及び地方消費税を含む。）"),
        "tax_basis",
    )
    assert a and a.normalized == {"basis": "bid_includes_tax"}


def test_tax_basis_two_readings_answer_nothing() -> None:
    ss = sents("金６９０千円（消費税及び地方消費税を含む。）", "入札書に記載された金額に当該金額の100分の10に相当する額を加算した金額をもって落札価格とする")  # fmt: skip
    assert got("notice", ss, "tax_basis") is None


# --- unified_qualification -------------------------------------------------------------


def test_uq_f19cddbd4cba_two_grades_three_categories() -> None:
    ss = sents("(3)　令和７・８・９年度法務省競争参加資格（全省庁統一資格）「物品の製造」、「物品の販売」又は「役務の提供等」においてＡ又はＢの等級に格付けされた者であること。")  # fmt: skip
    a = got("notice", ss, "unified_qualification")
    assert a and a.normalized == {"grades": ["A", "B"], "category": "「物品の製造」、「物品の販売」又は「役務の提供等」", "region": None}  # fmt: skip


def test_uq_a13baac55c8_grades_in_the_next_sentence() -> None:
    ss = sents("（３）令和７・８・９年度農林水産省競争参加資格（全省庁統一資格）の「役務の提供等」において、", "「Ｂ」、「Ｃ」又は「Ｄ」等級に格付されている者であること。")  # fmt: skip
    a = got("notice", ss, "unified_qualification")
    assert (
        a
        and a.normalized["grades"] == ["B", "C", "D"]
        and a.citations == ["h_s1", "h_s2"]
    )


def test_uq_563042df9941_grade_after_the_category() -> None:
    ss = sents("（３）令和７・８・９年度内閣府所管競争参加資格審査（全省庁統一資格）において、「役務の提供等」のＡ、Ｂ、Ｃ又はＤの等級に格付けされている者であること。")  # fmt: skip
    a = got("notice", ss, "unified_qualification")
    assert a and a.normalized["grades"] == ["A", "B", "C", "D"]


def test_uq_without_a_category_answers_nothing() -> None:
    assert (
        got(
            "notice",
            sents("全省庁統一資格においてＡ等級に格付けされた者"),
            "unified_qualification",
        )
        is None
    )


# --- language_currency -----------------------------------------------------------------


def test_language_136dfba9ee59() -> None:
    ss = sents(
        "(1) 入札及び契約手続において使用する言語及び通貨　日本語及び日本国通貨。"
    )
    a = got("notice", ss, "language_currency")
    assert (
        a
        and a.normalized == {"language": "ja", "currency": "JPY"}
        and a.value_ja == "日本語及び日本国通貨"
    )


def test_language_d40000275df6_yen_by_name() -> None:
    ss = sents("ア 提出書類の記入等に当たり使用する言語は日本語とし、通貨は日本円とし、単位は日本の標準時及び計量法（平成４年法律第51号）によること。")  # fmt: skip
    assert got("bid_instructions", ss, "language_currency")


def test_language_that_allows_english_answers_nothing() -> None:
    assert (
        got(
            "notice",
            sents("日本語及び日本国通貨。ただし英語による提出も認める。"),
            "language_currency",
        )
        is None
    )


# --- wto_covered -----------------------------------------------------------------------


def test_wto_136dfba9ee59_covered_and_563042df9941_not_covered() -> None:
    yes = got("notice", sents("一般競争入札の入札公告（WTO対象）"), "wto_covered")
    no = got("notice", sents("一般競争入札の入札公告（WTO対象外）"), "wto_covered")
    assert yes and yes.normalized == {"covered": True} and yes.value_ja == "WTO対象"
    assert no and no.normalized == {"covered": False}


def test_wto_silence_is_not_found() -> None:
    assert (
        got("notice", sents("次のとおり一般競争入札に付します。"), "wto_covered")
        is None
    )


# --- v4: award_method ------------------------------------------------------------------


def test_award_method_58f13b9c_best_value() -> None:
    ss = sents("(6) 入札方法　総合評価落札方式をもって行うので、入札金額を記載した入札書及び提案書等を提出すること。")  # fmt: skip
    a = got("notice", ss, "award_method")
    assert a and a.normalized == {"method": "best_value"}


def test_award_method_136dfba9ee59_phrase_cut_by_the_segmenter() -> None:
    ss = sents("(6) 入札方法　落札者の決定は総合評価落札方", "式をもって行うので、提案に係る性能、機能、")  # fmt: skip
    a = got("notice", ss, "award_method")
    assert a and a.citations == ["h_s1", "h_s2"]


def test_award_method_6b7142ab_evaluation_method_clause() -> None:
    ss = sents("(6)　落札者の決定方法　予算決算及び会計令第79条の規定に基づいて作成された予定価格の制限の範囲内であり、入札説明書で定める総合評価の方法をもって落札者を決定する。")  # fmt: skip
    assert got("notice", ss, "award_method").normalized == {"method": "best_value"}  # type: ignore[union-attr]


def test_award_method_f19cddbd4cba_lowest_price() -> None:
    ss = sents("(6)　落札者の決定方法　予算決算及び会計令第79条の規定に基づいて作成された予定価格の制限の範囲内で最低価格をもって有効な入札を行った者を落札者とする。")  # fmt: skip
    assert got("notice", ss, "award_method").normalized == {"method": "lowest_price"}  # type: ignore[union-attr]


def test_award_method_563042df9941_documents_for_evaluation_alone_say_nothing() -> None:
    ss = sents(
        "なお、入札者の作成した総合評価のための書類は、内閣府において審査するものとする。"
    )
    assert got("notice", ss, "award_method") is None


def test_award_method_two_methods_answer_nothing() -> None:
    ss = sents("落札者の決定は、総合評価落札方式をもって行う。", "最低価格をもって有効な入札を行った者を落札者とする。")  # fmt: skip
    assert got("notice", ss, "award_method") is None


# --- v4: spec_access -------------------------------------------------------------------


def test_spec_access_d230e51e_system_posting_wins_over_the_spec_pointer() -> None:
    ss = sents("(3)　調達案件の仕様等　入札説明書による。", "(2)　入札説明書の交付方法　本公告の日から原則、「電子調達システム」に掲載する。")  # fmt: skip
    a = got("notice", ss, "spec_access")
    assert a and a.normalized == {"mode": "public"} and a.citations == ["h_s2"]


def test_spec_access_58f13b9c_at_the_counter() -> None:
    ss = sents("(3) 入札説明書の交付方法　本公告の日から上記(1)の場所にて交付する。")
    assert got("notice", ss, "spec_access").normalized == {"mode": "at_counter"}  # type: ignore[union-attr]


def test_spec_access_563042df9941_heading_in_the_sentence_above() -> None:
    a = got("notice", sents("（２）仕　　様", "入札説明書による。"), "spec_access")
    assert a and a.status == "see_other_document"
    assert a.normalized == {"ref": {"kind": "bid_instructions", "text_ja": "入札説明書による。"}}  # fmt: skip


def test_spec_access_a13baaac55c8_pointer_in_the_heading_sentence() -> None:
    a = got("notice", sents("（２）仕様　　仕様書のとおり"), "spec_access")
    assert a and a.normalized["ref"]["kind"] == "spec"


def test_spec_access_f19cddbd4cba_two_documents_named_answer_nothing() -> None:
    ss = sents("(3)　調達案件の仕様等　入札説明書及び仕様書による。")
    assert got("notice", ss, "spec_access") is None


def test_spec_access_6b7142ab_a_special_features_line_is_not_the_spec_line() -> None:
    ss = sents("(3)　調達件名の特質等　入札説明書及び仕様書による。")
    assert got("notice", ss, "spec_access") is None


def test_spec_access_84e9d0c8325c_unreadable_delivery_line_blocks_the_pointer() -> None:
    ss = sents("（３）仕様", "入札説明書による。", "（２）入札説明書の交付方法", "入札説明書の郵送での交付を希望する場合は、返信用封筒を同封の上、上記（１）まで送付すること。")  # fmt: skip
    assert got("notice", ss, "spec_access") is None


# --- v4: submission_modes --------------------------------------------------------------


def test_modes_f19cddbd4cba_system_only() -> None:
    ss = sents("(2)　入札説明書の交付方法　電子調達システム及び上記３の(1)の場所にて公告日より交付する。", "(8)　電子調達システムの利用　本件は、電子調達システムを利用することができる案件である。")  # fmt: skip
    a = got("notice", ss, "submission_modes")
    assert a and a.normalized == {"modes": ["electronic"], "mail_not_allowed": False}
    assert a.citations == ["h_s2"]


def test_modes_a81e99fecea5_system_paper_and_mail() -> None:
    ss = sents("本案件は、電子調達システムで行う。", "なお、電子調達システムにより難い者は、支出負担行為担当官に書面により申し出た場合に限り、紙入札方式に代えることができる。", "入札説明書の郵送での交付を希望する場合は、返信用封筒を同封の上、上記（１）まで送付すること。", "（４）郵送による入札")  # fmt: skip
    a = got("notice", ss, "submission_modes")
    assert a and a.normalized == {"modes": ["in_person", "mail", "electronic"], "mail_not_allowed": False}  # fmt: skip
    assert a.citations == [
        "h_s1",
        "h_s2",
        "h_s4",
    ]  # the mailed-copy line is not a bid way


def test_modes_563042df9941_mail_and_paper_refused() -> None:
    ss = sents("本案件は、電子調達システム（政府電子調達（GEPS））（以下、「システム」という。）を利用して行う調達案件である。", "※紙媒体及び郵送等による入札は受け付けない。")  # fmt: skip
    a = got("notice", ss, "submission_modes")
    assert a and a.normalized == {"modes": ["electronic"], "mail_not_allowed": True}
    assert a.citations == ["h_s1", "h_s2"]


def test_modes_d40000275df6_bring_or_post_without_the_system() -> None:
    ss = sents(
        "（ア）直接持参する方法",
        "（イ）郵便（書留郵便その他）による方法",
        prefix="p4_s",
    )
    a = got("bid_instructions", ss, "submission_modes")
    assert a and a.normalized["modes"] == ["in_person", "mail"]


def test_modes_28ad40ea4b1f_mail_or_email_answers_nothing() -> None:
    ss = sents("持参の場合 月曜日から金曜日 ９時から１７時４５分まで", "郵送又はメールの場合 上記の提出期限及び提出時間内必着にて提出してください。", prefix="p3_s")  # fmt: skip
    assert got("bid_instructions", ss, "submission_modes") is None


def test_modes_a13baaac55c8_paper_excluded_is_not_a_paper_bid() -> None:
    ss = sents("入札は、紙入札方式を除き、電子調達システムによる。")
    a = got("notice", ss, "submission_modes")
    assert a and a.normalized["modes"] == ["electronic"]


def test_modes_262e3a41_paper_clause_alone_answers_nothing() -> None:
    ss = sents("担当官の承諾を得た場合に限り、紙入札方式により参加し、又は紙入札方式へ変更することができる。")  # fmt: skip
    assert got("notice", ss, "submission_modes") is None


def test_modes_0cc5aec9_electronic_contract_is_not_electronic_bidding() -> None:
    ss = sents(
        "落札者に対して、電子調達システムを利用した電子契約締結の可否を確認する。"
    )
    assert got("notice", ss, "submission_modes") is None


# --- v4: performance_period ------------------------------------------------------------


def test_period_a13baaac55c8_from_signing_to_a_date() -> None:
    a = got("notice", sents("（３）履行期間　　契約締結日から令和９年２月２６日まで"), "performance_period")  # fmt: skip
    assert a and a.normalized == {"start": None, "end": "2027-02-26", "relative_text": "契約締結日"}  # fmt: skip


def test_period_a81e99fecea5_tilde_and_heading_in_the_sentence_above() -> None:
    a = got("notice", sents("（４）契約期間", "契約締結日～令和１０年３月３１日"), "performance_period")  # fmt: skip
    assert a and a.normalized["end"] == "2028-03-31" and a.citations == ["h_s1", "h_s2"]


def test_period_d40000275df6_the_wording_of_the_start_is_kept() -> None:
    a = got("bid_instructions", sents("（５）契約期間", "契約締結の日から令和９年３月31日まで", prefix="p1_s"), "performance_period")  # fmt: skip
    assert a and a.normalized["relative_text"] == "契約締結の日"


def test_period_4b0b9d8229c7_longest_up_to_month_end() -> None:
    a = got(
        "notice", sents("3.履行期限", "最長 令和9年9月末まで"), "performance_period"
    )
    assert a and a.normalized == {"start": None, "end": "2027-09-30", "relative_text": "最長 令和9年9月末まで"}  # fmt: skip


def test_period_f19cddbd4cba_and_6b7142ab_pointers() -> None:
    a = got("notice", sents("(4)　履行期限　仕様書のとおり。"), "performance_period")
    assert a and a.status == "see_other_document" and a.normalized["ref"]["kind"] == "spec"  # fmt: skip
    b = got("notice", sents("(4)　借入期間　仕様書による。"), "performance_period")
    assert b and b.normalized["ref"]["kind"] == "spec"


def test_period_136dfba9ee59_date_cut_by_the_segmenter_answers_nothing() -> None:
    ss = sents("(4) 履行期間　契約締結日から令和９年３月31", "日。")
    assert got("notice", ss, "performance_period") is None


def test_period_d40000275df6_a_period_inside_a_sentence_is_not_the_heading() -> None:
    ss = sents("ｂ 調達業務により制作したウェブサイトの保守管理業務（業務期間：令和９年４月１日から令和10年３月31日まで）に要する費用", prefix="p7_s")  # fmt: skip
    assert got("bid_instructions", ss, "performance_period") is None


# --- v4: delivery_deadline -------------------------------------------------------------


def test_delivery_deadline_c2f9213c_date() -> None:
    a = got("notice", sents("2. 機器納入期限については令和９年３月３０日(火)とする。"), "delivery_deadline")  # fmt: skip
    assert a and a.normalized == {"date": "2027-03-30"}


def test_delivery_deadline_070b894e_heading_above_the_date() -> None:
    a = got(
        "notice", sents("（３）納入期限", "令和９年３月18日（木）"), "delivery_deadline"
    )
    assert a and a.normalized == {"date": "2027-03-18"}


def test_delivery_deadline_08558fc7_pointer() -> None:
    a = got("notice", sents("(4)　納入期限　別途仕様書のとおり"), "delivery_deadline")
    assert a and a.status == "see_other_document" and a.normalized["ref"]["kind"] == "spec"  # fmt: skip


def test_delivery_deadline_f19cddbd4cba_fulfilment_deadline_is_not_read() -> None:
    assert got("notice", sents("(4)　履行期限　仕様書のとおり。"), "delivery_deadline") is None  # fmt: skip


def test_delivery_deadline_94b7145f_a_deadline_mentioned_in_passing() -> None:
    ss = sents("なお、納入期限日の30日前から納入期限日までに検定を取得すること。")
    assert got("notice", ss, "delivery_deadline") is None


# --- v4: contracting_officer -----------------------------------------------------------


def test_officer_f19cddbd4cba_post_and_name_in_one_sentence() -> None:
    ss = sents(
        "令和８年８月28日", "支出負担行為担当官", "出入国在留管理庁次長　内藤惣一郎"
    )
    a = got("notice", ss, "contracting_officer")
    assert a and a.normalized == {"title": "支出負担行為担当官 出入国在留管理庁次長", "name": "内藤惣一郎"}  # fmt: skip
    assert a.citations == ["h_s2", "h_s3"]


def test_officer_58f13b9c_post_and_name_in_two_sentences() -> None:
    ss = sents(
        "支出負担行為担当官", "総務省政策統括官（統計制度・恩給担当）", "阪本　克彦"
    )
    a = got("notice", ss, "contracting_officer")
    assert a and a.normalized == {"title": "支出負担行為担当官 総務省政策統括官（統計制度・恩給担当）", "name": "阪本 克彦"}  # fmt: skip
    assert a.value_ja.count("\n") == 2


def test_officer_594c3cb6_given_name_split_by_a_space() -> None:
    ss = sents("支出負担行為担当官", "内閣府大臣官房会計担当参事官　井出　英次")
    assert got("notice", ss, "contracting_officer").normalized["name"] == "井出 英次"  # type: ignore[union-attr]


def test_officer_a13baaac55c8_page_text_stuck_to_the_post_answers_nothing() -> None:
    ss = sents("支出負担行為担当官", "農林水産省大臣官房参事官（経理）お知らせ")
    assert got("notice", ss, "contracting_officer") is None


def test_officer_84e9d0c8325c_title_inside_a_sentence_is_not_the_signature() -> None:
    ss = sents("なお、電子調達システムにより難い者は、支出負担行為担当官に書面により申し出た場合に限り、紙入札方式に代えることができる。", "本案件は、電子調達システムで行う。")  # fmt: skip
    assert got("notice", ss, "contracting_officer") is None


def test_officer_two_different_signers_answer_nothing() -> None:
    ss = sents("支出負担行為担当官", "法務省大臣官房会計課長　藤田　正人", "支出負担行為担当官", "内閣府大臣官房会計担当参事官　井出　英次")  # fmt: skip
    assert got("notice", ss, "contracting_officer") is None


# --- the guard -------------------------------------------------------------------------


# --- title -----------------------------------------------------------------------------


def test_title_f19cddbd4cba_portal_header_label_then_the_title() -> None:
    ss = sents("物品・役務", "調達案件名称", "オンライン在留申請処理促進対応に伴う外国人出入国情報システム用端末機器等の供給一式", "公開開始日")  # fmt: skip
    a = got("notice", ss, "title")
    assert a and a.normalized == {} and a.citations == ["h_s2", "h_s3"]
    assert a.value_ja == "オンライン在留申請処理促進対応に伴う外国人出入国情報システム用端末機器等の供給一式"  # fmt: skip


def test_title_a81e99fecea5_case_name_label_alone_on_its_line() -> None:
    ss = sents("７１、２７", "（２）案件名", "ハローワークシステムの次々期更改に係る調査研究業務及び要件定義書案作成業務等一式", "（３）仕様")  # fmt: skip
    a = got("notice", ss, "title")
    assert a and a.citations == ["h_s2", "h_s3"] and a.value_ja.endswith("業務等一式")


def test_title_a13baaac55c8_inline_after_the_number_and_label() -> None:
    ss = sents("１　競争入札に付する事項", "（１）件名　　令和８年度特殊土壌地帯推進調査（データ収集・分析・変換等）業務", "（電子入札・電子契約方式対象案件）")  # fmt: skip
    a = got("notice", ss, "title")
    assert a and a.citations == ["h_s2"]
    assert (
        a.value_ja == "令和８年度特殊土壌地帯推進調査（データ収集・分析・変換等）業務"
    )


def test_title_594c3cb6e0ea_quantity_is_not_part_of_the_name_and_portal_line_agrees() -> (
    None
):
    ss = sents("調達案件名称", "令和８年度国境離島の合理的・効果的な状況把握手法構築業務", "(2)\u3000購入等件名及び数量\u3000令和８年度国境離島の合理的・効果的な状況把握手法構築業務\u3000一式")  # fmt: skip
    a = got("notice", ss, "title")
    assert a and a.citations == ["h_s1", "h_s2", "h_s3"]
    assert a.value_ja == "令和８年度国境離島の合理的・効果的な状況把握手法構築業務"


def test_title_2aa7506a_quantity_and_flag_after_the_name_are_cut_off() -> None:
    ss = sents("(２) 調達件名及び数量  インターネット等による静止気象衛星画像データ航空配信サービス構築等 １式（電子入札対象案件）")  # fmt: skip
    a = got("notice", ss, "title")
    assert (
        a
        and a.value_ja
        == "インターネット等による静止気象衛星画像データ航空配信サービス構築等"
    )


def test_title_136dfba9ee59_a_line_wrap_that_cut_the_name_agrees_with_the_full_one() -> (
    None
):
    full = "農林水産統計システム次期システム移行・構築に係る調達支援及び技術検討業務"
    ss = sents(
        "調達案件名称", full, "(2)\u3000購入等件名及び数量\u3000農林水産統計システ"
    )
    a = got("notice", ss, "title")
    assert a and a.value_ja == full


def test_title_4c40bbd831fe_spec_label_alone() -> None:
    ss = sents("仕様書", "1. 業務名", "「きのくに県民カレッジ」・「出張まなび講座」ウェブサイト制作及び講座検索システム構築業務", "2. 業務目的", prefix="p1_s")  # fmt: skip
    a = got("spec", ss, "title")
    assert (
        a and a.citations == ["p1_s2", "p1_s3"] and a.value_ja.startswith("「きのくに")
    )


def test_title_6b7142ab_special_features_line_is_not_a_title_label() -> None:
    ss = sents("(3)\u3000調達件名の特質等\u3000入札説明書及び仕様書による。")
    assert got("notice", ss, "title") is None


def test_title_two_different_titles_answer_nothing() -> None:
    # two names from collected notices (a81e99fecea5, 84e9d0c8325c) in one document: ambiguous, so not found
    ss = sents("（２）案件名", "ハローワークシステムの次々期更改に係る調査研究業務及び要件定義書案作成業務等一式", "(2)\u3000調達件名及び数量\u3000公的個人認証サービスを用いた受付システムの運用・保守業務一式")  # fmt: skip
    assert got("notice", ss, "title") is None


def test_title_bf99e8ba_case_number_in_front_of_the_name_answers_nothing() -> None:
    ss = sents(
        "調達案件名称", "07-0049-0230\u3000令和７年度 国際データ取引市場創出事業の請負"
    )
    assert got("notice", ss, "title") is None


def test_title_a_label_with_no_value_does_not_take_the_next_heading() -> None:
    ss = sents("（２）案件名", "（３）仕様")
    assert got("notice", ss, "title") is None


def test_title_is_not_asked_of_other_document_types() -> None:
    ss = sents(
        "調達案件名称", "令和８年度国境離島の合理的・効果的な状況把握手法構築業務"
    )
    assert got("eligibility_list", ss, "title") is None


# --- issuer_org ------------------------------------------------------------------------


def test_issuer_58f13b9c878a_portal_line_under_procuring_body() -> None:
    ss = sents("令和09年10月27日", "調達機関", "総務省", "調達機関所在地")
    a = got("notice", ss, "issuer_org")
    assert a and a.value_ja == "総務省" and a.citations == ["h_s3"]


def test_issuer_58f13b9c878a_procuring_body_number_line_is_not_the_name() -> None:
    ss = sents("◎調達機関番号　013　◎所在地番号　13")
    assert got("notice", ss, "issuer_org") is None


def test_issuer_6b7142ab_name_is_the_start_of_the_officers_post() -> None:
    ss = sents("令和８年９月14日", "支出負担行為担当官", "法務省大臣官房会計課長\u3000藤田\u3000正人", "◎調達機関番号\u3000013\u3000◎所在地番号\u300013")  # fmt: skip
    a = got("notice", ss, "issuer_org")
    assert a and a.value_ja == "法務省" and a.citations == ["h_s3"]


def test_issuer_f19cddbd4cba_agency_name_before_the_post() -> None:
    ss = sents(
        "令和８年８月28日", "支出負担行為担当官", "出入国在留管理庁次長\u3000内藤惣一郎"
    )
    a = got("notice", ss, "issuer_org")
    assert a and a.value_ja == "出入国在留管理庁"


def test_issuer_f19cddbd4cba_portal_ministry_and_signing_agency_differ_so_nothing() -> (
    None
):
    ss = sents("調達機関", "法務省", "調達機関所在地", "令和８年８月28日", "支出負担行為担当官", "出入国在留管理庁次長\u3000内藤惣一郎")  # fmt: skip
    assert got("notice", ss, "issuer_org") is None


def test_issuer_portal_line_and_officer_line_that_agree_cite_both() -> None:
    ss = sents("調達機関", "内閣府", "調達機関所在地", "令和８年７月28日", "支出負担行為担当官", "内閣府大臣官房会計担当参事官\u3000井出\u3000英次")  # fmt: skip
    a = got("notice", ss, "issuer_org")
    assert a and a.value_ja == "内閣府" and a.citations == ["h_s2", "h_s6"]


def test_issuer_2aa7506a_a_post_that_does_not_start_with_a_ministry_answers_nothing() -> (
    None
):
    ss = sents("支出負担行為担当官", "気象衛星センター所長 立川 英二")
    assert got("notice", ss, "issuer_org") is None


def test_an_answer_not_in_its_cited_sentence_is_dropped() -> None:
    ss = sents("令和８年８月28日")
    by_id = {s.id: s for s in ss}
    assert (
        rules.verified(
            "notice_date", ({"date": "2026-08-28"}, "令和９年９月１日", ["h_s1"]), by_id
        )
        is None
    )
    assert (
        rules.verified(
            "notice_date", ({"date": "2026-08-28"}, "令和８年８月28日", ["h_s9"]), by_id
        )
        is None
    )
    assert rules.verified(
        "notice_date", ({"date": "2026-08-28"}, "令和８年８月28日", ["h_s1"]), by_id
    )


def test_english_sentences_are_never_cited() -> None:
    ss = sents("(WTO対象)")
    ss[0].language = "en"
    assert rules.extract("notice", ss) == {}


# --- spec documents (D-93): 業務の名称 title, 委託期間 with a ただし clause --------------


def test_spec_4965207bb115_title_merged_with_the_業務の名称_heading() -> None:
    ss = sents("委託業務仕様書（案）", "１．業務の名称わかやま空き家ポータルサイト構築及び保守管理運営業務", "２．業務の目的")  # fmt: skip
    a = got("spec", ss, "title")
    assert a and a.value_ja == "わかやま空き家ポータルサイト構築及び保守管理運営業務"
    assert a.citations == ["h_s2"]


def test_spec_cd1a1936865a_title_on_the_line_under_業務の名称() -> None:
    ss = sents("１ 業務の名称", "令和８年度和歌山県ICT・PHRを活用した特定保健指導基盤整備事業委託業務", "２ 目的")  # fmt: skip
    a = got("spec", ss, "title")
    assert a and a.value_ja.endswith("事業委託業務") and a.citations == ["h_s1", "h_s2"]


def test_spec_業務の名称_is_not_a_title_label_on_a_notice() -> None:
    ss = sents("１．業務の名称わかやま空き家ポータルサイト構築及び保守管理運営業務")
    assert got("notice", ss, "title") is None


def test_spec_4965207bb115_a_connector_after_業務の名称_is_not_a_title() -> None:
    ss = sents("１．業務の名称及び内容について")
    assert got("spec", ss, "title") is None


def test_spec_4965207bb115_period_cuts_the_ただし_clause() -> None:
    ss = sents("３．委託期間", "契約締結日から令和１１年３月３１日までただし、「４－２．各種サイト保守管理」については、令和８年７月１日より業務開始とする。")  # fmt: skip
    a = got("spec", ss, "performance_period")
    assert a and a.normalized == {
        "start": None,
        "end": "2029-03-31",
        "relative_text": "契約締結日",
    }
    assert (
        a.value_ja == "契約締結日から令和１１年３月３１日まで"
        and "ただし" not in a.value_ja
    )
    assert a.citations == ["h_s1", "h_s2"]


def test_spec_870f1f2ec726_period_under_委託期間_without_a_clause() -> None:
    ss = sents("３ 委託期間", "契約締結日から令和９年３月３１日まで", "４ 支援対象")
    a = got("spec", ss, "performance_period")
    assert a and a.normalized["end"] == "2027-03-31"


def test_spec_4965207bb115_period_with_an_unclear_part_before_ただし_is_not_found() -> (
    None
):
    ss = sents(
        "３．委託期間", "別途協議して定めるただし、令和８年７月１日より業務開始とする。"
    )
    assert got("spec", ss, "performance_period") is None


def test_notice_委託期間_and_ただし_are_not_read_on_a_notice() -> None:
    ss = sents("３．委託期間", "契約締結日から令和１１年３月３１日までただし、令和８年７月１日より業務開始とする。")  # fmt: skip
    assert got("notice", ss, "performance_period") is None


# --- heading_cue accepts 業務の名称 and 委託期間 (D-94) ----------------------------------


def _cue(doc_type: str, ss: list[Sentence], field: str) -> bool | None:
    from shiori_core.checks import heading_cue

    a = got(doc_type, ss, field)
    assert a
    return heading_cue(a, {s.id: s for s in ss})


def test_heading_cue_4965207bb115_業務の名称_is_a_title_cue() -> None:
    ss = sents("１．業務の名称わかやま空き家ポータルサイト構築及び保守管理運営業務")
    assert _cue("spec", ss, "title") is True


def test_heading_cue_4965207bb115_委託期間_is_a_period_cue() -> None:
    ss = sents("３．委託期間", "契約締結日から令和１１年３月３１日まで")
    assert _cue("spec", ss, "performance_period") is True


def test_heading_cue_4965207bb115_a_title_far_from_any_heading_is_still_unusual() -> (
    None
):
    from shiori_core.checks import heading_cue
    from shiori_core.extract.rules import Extracted

    ss = sents(
        "本事業の実施に当たり、受託者は次の各号に掲げる業務の名称を遵守すること。"
    )
    a = Extracted(field="title", value_ja="業務", normalized={}, citations=["h_s1"])
    assert heading_cue(a, {s.id: s for s in ss}) is False


# --- page-1 signature block: issuer_org and notice_date ---------------------------------------
# 2f2f5bd3 (和歌山県, open): the date line, then the governor's line. Spacing inside the name is how the
# PDF text came out. The 市長 and other-post cases are made-up wording in the same layout (the
# collected examples are restricted documents, so none of their text is used here).

WAKAYAMA = ["令和8年9月15日", "和歌山県知事 宮 崎   泉", "1 一般競争入札に付する事項"]


def test_issuer_and_date_2f2f5bd3_wakayama_signature_block() -> None:
    ss = sents(*WAKAYAMA, page=1)
    org, date = got("notice", ss, "issuer_org"), got("notice", ss, "notice_date")
    assert org and org.value_ja == "和歌山県" and org.citations == ["h_s2"]
    assert date and date.normalized == {"date": "2026-09-15"} and date.citations == ["h_s1"]  # fmt: skip


def test_issuer_city_mayor_line_gives_the_city_name() -> None:
    ss = sents("令和8年4月1日", "サンプル市長 山田 太郎", "第1 業務概要", page=1)
    org = got("notice", ss, "issuer_org")
    assert org and org.value_ja == "サンプル市" and org.citations == ["h_s2"]


def test_signature_rules_only_read_page_1_near_the_top() -> None:
    assert got("notice", sents(*WAKAYAMA, page=2), "issuer_org") is None
    assert got("notice", sents(*WAKAYAMA, page=2), "notice_date") is None
    late = sents(*(["本文"] * 12), *WAKAYAMA, page=1)
    assert got("notice", late, "issuer_org") is None and got("notice", late, "notice_date") is None  # fmt: skip


def test_signature_line_must_be_the_whole_sentence_and_not_a_deputy_or_addressee() -> (
    None
):
    for line in ("和歌山県知事は、次のとおり公告する。", "副市長 山田 太郎", "サンプル市長 山田 太郎 殿", "都道府県知事又は市長が認定した者"):  # fmt: skip
        assert (
            got("notice", sents("令和8年4月1日", line, page=1), "issuer_org") is None
        ), line


def test_notice_date_not_taken_when_a_heading_stands_between_date_and_signature() -> (
    None
):
    ss = sents("令和7年7月24日", "質問回答書", "サンプル市長 山田 太郎", page=1)
    assert got("notice", ss, "notice_date") is None


def test_notice_date_before_a_named_post_other_than_governor_or_mayor() -> None:
    ss = sents("令和8年10月2日", "サンプル県サンプル事務所長 山田 太郎", "地方自治法第234条の規定により", page=1)  # fmt: skip
    a = got("notice", ss, "notice_date")
    assert a and a.normalized == {"date": "2026-10-02"}


# --- title: column labels and run-together project names -------------------------------------


def test_title_is_never_a_table_column_label() -> None:
    # a list page: the 件名 cell is empty, the next cell is the next column's label
    for label in ("契約種別", "契約番号", "開札日", "備考", "営業種目・取扱品目"):
        assert got("notice", sents("件名", label), "title") is None, label


def test_title_with_several_defined_projects_is_not_found() -> None:
    ss = sents("(1) 件名", "サンプル市A業務委託（以下「業務A」という。）サンプル市B業務委託（以下「業務B」という。）")  # fmt: skip
    assert got("bid_instructions", ss, "title") is None


def test_title_with_one_trailing_definition_still_found() -> None:
    ss = sents("(1) 件名", "サンプル市A業務委託（以下「業務A」という。）")
    a = got("bid_instructions", ss, "title")
    assert a and a.value_ja == "サンプル市A業務委託"


# --- performance_period: more headings and start forms; title: 公募件名 -------------------------
# Real wording: 2f2f5bd3 (和歌山県), 10be3ae3, 45f0a917, 74aed2a5 (デジタル庁). The 契約の日,
# 翌日, spaced 件 名 and two-heading cases are made-up wording in the same layout (the collected
# examples are restricted documents).


def test_period_2f2f5bd3_業務の期間_heading_alone_then_the_value() -> None:
    ss = sents("(5)業務の期間", "契約締結日から令和15年9月30日(金)まで", "2 一般競争入札に参加する者に必要な資格")  # fmt: skip
    a = got("notice", ss, "performance_period")
    assert a and a.normalized == {"start": None, "end": "2033-09-30", "relative_text": "契約締結日"}  # fmt: skip
    assert a.citations == ["h_s1", "h_s2"]


def test_period_10be3ae3_start_with_a_parenthetical_before_日() -> None:
    ss = sents("3.契約期間", "契約締結(請書提出)日から令和9年3月31日", "4.業務要件")
    a = got("spec", ss, "performance_period")
    assert a and a.normalized["end"] == "2027-03-31" and a.normalized["start"] is None


def test_period_45f0a917_two_dates_without_まで() -> None:
    ss = sents(
        "3.契約期間", "令和8年4月1日から令和9年3月31日", "4.契約の相手方に求める条件"
    )
    a = got("spec", ss, "performance_period")
    assert a and a.normalized == {"start": "2026-04-01", "end": "2027-03-31", "relative_text": None}  # fmt: skip


def test_period_契約の日_and_翌日_starts_and_賃貸借期間_heading() -> None:
    a = got(
        "notice",
        sents("(3)業務期間 契約の日から令和9年3月12日まで"),
        "performance_period",
    )
    assert a and a.normalized["end"] == "2027-03-12" and a.normalized["relative_text"] == "契約の日"  # fmt: skip
    b = got("bid_instructions", sents("(4)委託期間", "契約締結日の翌日~令和9年(2027年)3月31日"), "performance_period")  # fmt: skip
    assert b and b.normalized["end"] == "2027-03-31"
    c = got("notice", sents("(3) 賃貸借期間  令和8年12月1日から令和13年11月30日まで"), "performance_period")  # fmt: skip
    assert c and c.normalized["start"] == "2026-12-01"


def test_period_two_headings_one_unreadable_is_not_answered() -> None:
    # 契約期間 reads, 履行期間 has dates and a clause we do not read: which period is asked is unclear
    ss = sents("(3)契約期間", "令和8年4月1日から令和9年3月31日まで", "(4)履行期間", "令和8年4月1日から令和11年3月31日まで(年度ごとの契約により3年間)")  # fmt: skip
    assert got("bid_instructions", ss, "performance_period") is None


def test_period_same_end_prefers_the_reading_with_a_start_date() -> None:
    ss = sents("(3)履行期間", "契約締結の日から令和9年2月28日まで", "(4)業務期間", "令和8年6月1日から令和9年2月28日まで")  # fmt: skip
    a = got("bid_instructions", ss, "performance_period")
    assert a and a.normalized["start"] == "2026-06-01"


def test_period_a_heading_line_without_a_date_is_only_prose() -> None:
    ss = sents("(3)履行期間", "契約締結の日から令和9年3月31日まで", "契約期間の延長)")
    a = got("bid_instructions", ss, "performance_period")
    assert a and a.normalized["end"] == "2027-03-31"


def test_title_74aed2a5_公募件名_label_alone_then_the_title() -> None:
    ss = sents(
        "1.公募件名",
        "企業保有情報の新しい提出方法に係るシステム保守等",
        "2.目的及び概要",
    )
    a = got("bid_instructions", ss, "title")
    assert a and a.value_ja == "企業保有情報の新しい提出方法に係るシステム保守等"
    assert a.citations == ["h_s1", "h_s2"]


def test_title_件_名_with_spaces_inside_the_label() -> None:
    a = got("spec", sents("1件  名", "サンプル品の購入", "2品目・数量"), "title")
    assert a and a.value_ja == "サンプル品の購入"
