# ruff: noqa: E501
"""core/shiori_core/extract/rules.py. The sentences are wording from collected open
documents (doc id prefix in each test name), split the way the extractor split them."""

from shiori_core.extract import rules
from shiori_core.models import Sentence
from shiori_core.normalize import normalize


def sents(*texts: str, prefix: str = "h_s") -> list[Sentence]:
    out = []
    for n, t in enumerate(texts, 1):
        norm, m = normalize(t)
        out.append(Sentence(id=f"{prefix}{n}", page=0, section_path=[], section_titles=[], text_orig=t,
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
