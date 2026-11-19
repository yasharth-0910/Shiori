# ruff: noqa: E501
"""core/shiori_core/translate.py against a fake llama-server (loopback, fixed English). The
Japanese sentences are invented; no model, no network beyond 127.0.0.1."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from shiori_core import glossary, translate
from shiori_core.extract.llm import Client

JA = "(4) 入札書の受領期限　令和８年10月15日13時30分"
GOOD = "(4) Bid form receipt deadline: October 15, Reiwa 8 (2026), 13:30"
WRONG = "(4) Bid form receipt deadline: October 16, Reiwa 8 (2026), 13:30"


def fake_llama(en):
    """A server that answers every chat request with {"en": ...} and keeps what it was sent.
    `en` is a string, or a function of the user message (to echo placeholders)."""
    seen: list[dict] = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen.append(
                json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            )
            text = en(seen[-1]["messages"][1]["content"]) if callable(en) else en
            body = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"en": text})}}]}).encode()  # fmt: skip
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a: object) -> None:
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def test_translation_comes_back_with_a_matching_numbers_check() -> None:
    srv, seen = fake_llama(GOOD)
    try:
        got = translate.translate(Client(srv.server_port), JA)
    finally:
        srv.shutdown()
    assert got.en == GOOD and got.numbers_match is True
    (req,) = seen
    assert req["temperature"] == 0  # one sentence per request, temperature 0
    user = req["messages"][1]["content"]
    assert JA.replace("　", " ") in user.replace("　", " ")
    assert "Do not explain" in user and "Keep numbers, dates and names exactly" in user


def test_a_wrong_number_is_flagged_and_the_translation_is_kept() -> None:
    srv, _ = fake_llama(WRONG)
    try:
        got = translate.translate(Client(srv.server_port), JA)
    finally:
        srv.shutdown()
    assert got.en == WRONG  # never hidden or fixed
    assert got.numbers_match is False


def test_the_glossary_terms_in_the_sentence_go_into_the_prompt() -> None:
    p = translate.prompt("入札保証金及び契約保証金は免除する。")
    assert "入札保証金 = Bid bond" in p and "契約保証金 = Performance bond" in p
    assert "一般競争入札" not in p  # only terms that occur
    assert "Use these renderings" not in translate.prompt("無関係な文")


def test_glossary_matches_the_vocabulary_table() -> None:
    from pathlib import Path

    table = (
        Path(__file__).resolve().parent.parent / "docs" / "japanese_rules.md"
    ).read_text()
    for ja, en in glossary.GLOSSARY.items():
        assert f"| {ja} |" in table and f"| {en} |" in table, ja
    for (
        ja,
        en,
    ) in (
        glossary.REGIONS.items()
    ):  # regions share rows ("A / B"), so only the English is exact
        assert en in table, ja


# --- fix 2: terms ------------------------------------------------------------------------------


def test_bidding_terms_say_bid_and_bidder_not_tender() -> None:
    assert glossary.GLOSSARY["一般競争入札"] == "Open competitive bidding"
    assert (
        glossary.GLOSSARY["予算決算及び会計令"]
        == "Order for Budgets, Settlement of Accounts and Accounting"
    )
    assert not any("tender" in en.lower() for en in glossary.GLOSSARY.values())
    assert (
        "tender" not in translate.prompt("次のとおり一般競争入札に付します。").lower()
    )  # 2aa7506a p2_s2


def test_a_region_block_is_one_name_2aa7506a_p4_s3() -> None:
    p = translate.prompt(P4_S3)
    assert "関東・甲信越 = Kanto-Koshinetsu" in p
    assert "do not add a region and do not drop one" in p
    assert "Hokkaido" not in p  # only the regions that occur
    assert "do not add a region" not in translate.prompt("無関係な文")


def test_the_glossary_has_no_bare_china() -> None:
    assert "中国" not in glossary.REGIONS  # ambiguous: see Open questions


# --- fix 1: abbreviations the document defines -------------------------------------------------

P3_S6 = "(１) 予算決算及び会計令（以下「予決令」という。）第70条の規定に該当しない者であること。"
P4_S2 = "(２) 予決令第71条の規定に該当しない者であること。"
P2_S3 = "本件は、競争参加資格確認のための証明書等（以下、「証明書等」という。）の提出、入札及び契約を電子調達システム（ＧＥＰＳ）で行う対象案件です。"
P1_S5 = "気象庁ではひまわり8号及び9号の観測画像を配信するに当たり、研究系ネットワークを含むインターネットとコンテンツデリバリーネットワーク（以下「CDN」という。）を利用して、「ひまわりクラウド」というデータ配信サービスを行っている。"
P4_S3 = "(３) 令和４･５･６年度国土交通省競争参加資格（全省庁統一資格）「役務の提供等」において、「A」又は「B」等級に格付けされ関東・甲信越地域の競争参加資格を有する者であること。"
P1_S14 = "・証明書等（技術審査資料含む）の提出期限 令和6年7月16日 16時まで"


def norm(t: str) -> str:
    from shiori_core.normalize import normalize

    return normalize(t)[0]


def test_yoketsurei_is_read_from_its_definition_2aa7506a_p3_s6() -> None:
    assert translate.find_abbreviations([norm(P3_S6)]) == {
        "予決令": "予算決算及び会計令"
    }


def test_the_definition_reaches_the_prompt_of_another_sentence_2aa7506a_p4_s2() -> None:
    abbrs = translate.find_abbreviations(norm(t) for t in (P3_S6, P4_S2))
    p = translate.prompt(P4_S2, abbrs)
    assert (
        "予決令 = short for 予算決算及び会計令, write it as: Order for Budgets, Settlement of Accounts and Accounting"
        in p
    )
    assert "Abbreviations this document defines" not in translate.prompt(
        P4_S2
    )  # no definition read: nothing guessed
    assert "Abbreviations this document defines" not in translate.prompt(
        P4_S3, abbrs
    )  # abbreviation not in the sentence


def test_a_definition_that_cannot_be_read_off_the_text_is_not_guessed_2aa7506a() -> (
    None
):
    assert (
        translate.find_abbreviations([norm(P1_S5)]) == {}
    )  # CDN: Latin letters, long form not recoverable
    assert (
        translate.find_abbreviations([norm(P2_S3)]) == {}
    )  # 証明書等 defines itself: nothing to add


def test_an_abbreviation_with_no_definition_is_never_added() -> None:
    assert (
        translate.find_abbreviations([norm(P4_S2)]) == {}
    )  # 予決令 used, never defined here


# --- fix 3: era dates --------------------------------------------------------------------------


def test_era_date_becomes_a_gregorian_hint_2aa7506a_p1_s14() -> None:
    assert translate.era_dates(norm(P1_S14)) == [("令和6年7月16日", "July 16, 2024")]
    p = translate.prompt(P1_S14)
    assert "令和6年7月16日 = July 16, 2024" in p and 'for example "July 16, 2024"' in p


def test_era_dates_are_converted_by_the_date_code() -> None:
    assert translate.era_dates(norm("令和６年６月５日")) == [
        ("令和6年6月5日", "June 5, 2024")
    ]  # p2_s4
    assert translate.era_dates(norm("平成30年3月31日")) == [
        ("平成30年3月31日", "March 31, 2018")
    ]
    assert (
        translate.era_dates(norm("令和8年10月")) == []
    )  # year and month only: not a complete date, no hint
    assert (
        translate.era_dates(norm("2024年7月16日")) == []
    )  # a Gregorian date needs no hint
    assert "Write each date" not in translate.prompt("無関係な文")


# --- fix 4: era year lists ---------------------------------------------------------------------


def test_era_year_list_counts_as_each_year_2aa7506a_p4_s3() -> None:
    assert translate.needed(P4_S3) == [{"4", "2022"}, {"5", "2023"}, {"6", "2024"}]
    assert translate.numbers_match(
        P4_S3, "(3) FY2022, 2023 and 2024 qualification, grade A or B, Kanto-Koshinetsu"
    )
    assert translate.numbers_match(P4_S3, "(3) Reiwa 4, 5 and 6 qualification")
    assert translate.numbers_match(
        P4_S3, "(3) Reiwa 4, 5, 6 (2022, 2023, 2024) qualification"
    )
    assert not translate.numbers_match(
        P4_S3, "(3) FY2022 and 2023 qualification"
    )  # the 6 is gone


# --- fix 5: personal names ---------------------------------------------------------------------


def test_the_prompt_keeps_a_person_name_in_its_own_script() -> None:
    p = translate.prompt("支出負担行為担当官　気象衛星センター所長　山田　太郎")
    assert "Leave a person's name in its original script, with no romanization" in p
    assert "Director of the Example Center, 山田 太郎" in p


@pytest.mark.parametrize(
    "ja,en,ok",
    [
        ("令和６年４月１日", "April 1, Reiwa 6", True),  # era year as written
        ("令和６年４月１日", "April 1, 2024", True),  # era year as the Gregorian year
        ("令和６年４月１日", "April 1, 2025", False),
        ("令和６年４月１日", "4/1/2024", True),  # month as a number
        ("予定価格は100万円", "The ceiling price is 1,000,000 yen", True),
        ("金690千円", "JPY 690 thousand", True),  # 690 as written
        ("第167条の4第1項", "Article 167-4, paragraph 1", True),
        ("第167条の4第1項", "Article 167, paragraph 1", False),  # the 4 is gone
        (
            "(2) 提案書を提出すること。",
            "Submit the proposal.",
            True,
        ),  # a leading (2) is a marker
        ("午後５時00分まで", "by 5:00 p.m.", True),
        ("無関係な文", "An unrelated sentence.", True),  # no numbers: nothing to differ
    ],
)
def test_numbers_check(ja: str, en: str, ok: bool) -> None:
    assert translate.numbers_match(ja, en) is ok


def test_a_broken_answer_raises() -> None:
    srv, _ = fake_llama("x")
    srv.shutdown()
    srv.server_close()  # nothing listens any more: the call fails at once
    with pytest.raises(OSError):
        translate.translate(Client(srv.server_port), JA)


# --- protected spans (D-87) --------------------------------------------------------------------
# Structure of 2aa7506a p2_s6 with an invented name; p3_s6 as it is in the document.

OFFICER = "気象衛星センター所長 鈴木 花子"
NAME = "鈴木 花子"


def run(en, text, names=(), abbrs=None):
    srv, seen = fake_llama(en)
    try:
        return translate.translate(Client(srv.server_port), text, abbrs, names), seen[
            0
        ]["messages"][1]["content"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_a_name_is_masked_before_the_model_and_restored_after_2aa7506a_p2_s6() -> None:
    got, sent = run(
        "Director of the Meteorological Satellite Center, ⟦P1⟧", OFFICER, [NAME]
    )
    assert "鈴木" not in sent and "⟦P1⟧" in sent  # the model never sees the name
    assert "Copy each placeholder" in sent
    assert (
        got.en == "Director of the Meteorological Satellite Center, 鈴木 花子"
    )  # original script
    assert got.protected_lost is False


def test_the_quoted_term_of_a_hereinafter_clause_stays_japanese_2aa7506a_p3_s6() -> (
    None
):
    got, sent = run(lambda u: 'Not a person subject to Article 70 of the Order (hereinafter "' + u[u.index("⟦") : u.index("⟧") + 1] + '").', P3_S6)  # fmt: skip
    assert "予決令" not in sent.split("Japanese sentence:")[1]  # masked in the sentence
    assert (
        got.en
        == 'Not a person subject to Article 70 of the Order (hereinafter "予決令").'
    )
    assert got.protected_lost is False and got.numbers_match is True


def test_a_dropped_placeholder_is_flagged_and_not_repaired() -> None:
    got, _ = run("Director of the Meteorological Satellite Center", OFFICER, [NAME])
    assert got.protected_lost is True
    assert (
        got.en == "Director of the Meteorological Satellite Center"
    )  # as the model wrote it


def test_a_duplicated_or_unknown_placeholder_is_flagged() -> None:
    assert run("Director ⟦P1⟧ ⟦P1⟧", OFFICER, [NAME])[0].protected_lost is True
    assert run("Director ⟦P1⟧ and ⟦P2⟧", OFFICER, [NAME])[0].protected_lost is True


def test_nothing_is_masked_without_a_given_name_or_a_definition() -> None:
    assert translate.protect(OFFICER) == (
        OFFICER,
        {},
    )  # no name passed: no guessing from the text
    got, sent = run("Director of the Center, 鈴木 花子", OFFICER)
    assert (
        "鈴木 花子" in sent
        and "Copy each placeholder" not in sent
        and got.protected_lost is False
    )


def test_a_name_written_with_other_spacing_is_still_found() -> None:
    assert (
        translate.protect("所長　鈴木花子", [NAME])[0] == "所長　⟦P1⟧"
    )  # full-width space, none between
    assert (
        translate.protect("所長 鈴木 花子 と 鈴木 花子", [NAME])[0]
        == "所長 ⟦P1⟧ と ⟦P2⟧"
    )


def test_a_name_inside_a_definition_quote_is_one_span() -> None:
    text = "契約担当官（以下「鈴木 花子」という。）"
    masked, mapping = translate.protect(text, [NAME])
    assert masked == "契約担当官（以下「⟦P1⟧」という。）" and list(
        mapping.values()
    ) == ["鈴木 花子"]
