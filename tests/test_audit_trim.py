"""Checks for eval/audit_trim.py. Invented rows; reads no real data."""

import json
from collections import Counter
from types import SimpleNamespace

import pytest

from eval.audit_trim import (
    AUDIT_KEYWORDS,
    AUTO_CONFIRMED,
    HEADERS,
    NOT_FOUND_ANSWER,
    NOT_FOUND_Q,
    build_rows,
    candidates,
    clean_en,
    drop_duplicates,
    finish_sentence,
    not_found_rows,
    pick,
    read_absent,
    sheet_values,
    write_xlsx,
)


def row(no: int, doc: str, field: str, ja: str, en: str = "ok", src: str = "") -> dict:
    return {"no": no, "doc": doc, "source": "s", "field": field,
            "field_label": field, "ja": ja, "en": en,
            "src": src or f"[h_s{no}] {ja}"}  # fmt: skip


class Fake:
    """Stands in for the extractor cache."""

    def __init__(
        self,
        nxt: tuple[str, str] | None = None,
        sents: dict[str, list[tuple[str, str, str]]] | None = None,
    ) -> None:
        self.nxt = nxt
        self.sents = sents or {}

    def all_of(self, doc: str) -> list[tuple[str, str, str]]:
        return self.sents.get(doc, [])

    def get(self, doc: str, sid: str) -> tuple[str, str] | None:
        return ("1 > (2)", "text")

    def next_of(self, doc: str, sid: str) -> tuple[str, str] | None:
        return self.nxt


def test_prefixes_become_plain_english():
    assert clean_en("other/requirement: Must be X.") == "Requirement: Must be X."
    assert clean_en("legal/disqualification: Owes tax.") == "Cannot bid if: Owes tax."
    assert (
        clean_en("bid_opening: 2026-10-05T14:00:00+09:00")
        == "Bid opening: 2026-10-05 14:00"
    )


def test_json_becomes_english_or_drops():
    modes = '{"modes": ["in_person", "mail", "electronic"], "mail_not_allowed": false}'
    assert clean_en(modes) == "Can submit in person, by mail or electronically"
    ref = '{"ref": {"kind": "spec", "text_ja": "仕様書のとおり"}}'
    assert clean_en(ref) == "See the specification."
    assert clean_en(f"As in the specification. {ref}") == "As in the specification."
    assert clean_en('{"weird": 1}') is None


def test_next_sentence_goes_to_source_only_4b0b9d82():
    # Audit row 75: doc 4b0b9d82, h_s1 is a title ending in て, h_s2 is the issuer.
    r = row(
        75, "4b0b9d82", "procurement_type", "公募型プロポーザル",
        src="[h_s1] " + "「令和8年度和歌山県データを利活用した公募型研究事業」"
        "に係る公募型プロポーザルの実施について",
    )  # fmt: skip
    finish_sentence(r, Fake(("h_s2", "和歌山県")))
    assert r["ja"] == "公募型プロポーザル"
    assert r["src"].endswith("\n[h_s2] 和歌山県")
    done = row(2, "d1", "eligibility", "完結する。")
    finish_sentence(done, Fake(("x", "y")))
    assert "\n" not in done["src"]


def test_same_sentence_once_per_doc_unified_qualification_wins():
    a = row(64, "136dfba9", "eligibility", "Ａの等級に格付されている者であること。")
    b = row(68, "136dfba9", "unified_qualification", a["ja"])
    got = drop_duplicates([a, b])
    assert [r["no"] for r in got] == [68]


def test_waived_bond_rows_capped_at_one():
    rows = [row(i, f"d{i}", "performance_bond", "免除", en="Waived") for i in range(4)]
    rows.append(row(9, "d9", "performance_bond", "金額の10分の1", en="10 percent"))
    got = drop_duplicates(rows)
    assert sum(r["en"] == "Waived" for r in got) == 1
    assert any(r["en"] == "10 percent" for r in got)


def test_pick_keeps_forced_and_eligibility_quota():
    rows = [row(i, f"d{i % 9}", "eligibility", f"条件{i}。") for i in range(100, 130)]
    rows += [row(i, f"d{i % 9}", "deadlines", f"期限{i}。") for i in range(200, 230)]
    rows += [
        row(83, "d1", "eligibility", "第70条。"),
        row(88, "d2", "eligibility", "第71条。"),
    ]
    got = pick(rows, keep=20)
    nos = {r["no"] for r in got}
    assert {83, 88} <= nos
    assert sum(r["field"] == "eligibility" for r in got) >= 10
    assert len(got) == 20


def labels(tmp_path, doc: str, absent: list[str]) -> None:
    lines = [{"doc_id": doc + "f" * 56, "field": f, "status": "absent"} for f in absent]
    (tmp_path / f"{doc}{'f' * 56}.jsonl").write_text(
        "\n".join(json.dumps(x) for x in lines)
    )


def test_not_found_rows_one_per_doc(tmp_path):
    labels(tmp_path, "aaaaaaaa", ["contact", "deadlines"])
    labels(tmp_path, "bbbbbbbb", ["contact"])
    labels(tmp_path, "dddddddd", ["bid_bond"])
    labels(tmp_path, "cccccccc", ["delivery_location"])
    absent = read_absent({"aaaaaaaa", "bbbbbbbb", "cccccccc", "dddddddd"}, tmp_path)
    nf = not_found_rows(absent, Counter())
    assert {r["field"] for r in nf} >= {"deadlines", "contact", "bid_bond"}
    assert len({r["doc"] for r in nf}) == len(nf)  # each from a different document


S = {
    "d0": [
        ("p1_s1", "1 > 入札", "本件の連絡先は総務課。電話 03-0000-0000。"),
        ("p1_s2", "1", "担当者は別途通知する。"),
        ("p1_s3", "2", "関係のない文。"),
        ("p1_s4", "2", "問い合わせ先はこちら。"),
        ("p1_s5", "2", "担当へ電話すること。"),
        ("p1_s6", "2", "連絡先を記入する。"),
    ],
    "d1": [("p1_s1", "1", "期限と関係ない文")],  # 期限 hits deadlines
    "d2": [("p1_s1", "1", "何も関係がない")],
}


def test_candidates_rank_by_hits_then_order_and_stay_verbatim():
    got = candidates("d0", "contact", Fake(sents=S))
    assert len(got) == 4
    assert got[0][0] == "p1_s1"  # 連絡先 + 電話 = 2 hits, first in order
    # p1_s4 and p1_s5 also have 2 hits (問い合わせ先 contains 問い合わせ); p1_s2 has 1
    assert [c[0] for c in got[1:]] == ["p1_s4", "p1_s5", "p1_s2"]
    texts = {t for _, _, t in S["d0"]}
    assert all(c[2] in texts for c in got)  # original text, not normalized
    assert all(w for w in AUDIT_KEYWORDS["bid_bond"])
    assert candidates("d2", "contact", Fake(sents=S)) == []


def test_not_found_rows_show_candidates_and_zero_hits_are_auto_confirmed():
    raw = [row(i, f"d{i % 9}", "eligibility", f"条件{i}。") for i in range(100, 130)]
    absent = {
        "contact": {"d0": "d0" + "x" * 62},
        "deadlines": {"d1": "d1" + "x" * 62},
        "bid_bond": {"d2": "d2" + "x" * 62},
    }
    rows, auto = build_rows(raw, Fake(sents=S), absent)
    nf = [r for r in rows if r.get("_not_found")]
    assert {r["doc"] for r in nf} == {"d0", "d1"}
    assert all(r["candidates"] for r in nf)  # none left with an empty list
    assert [(r["doc"], r["field"]) for r in auto] == [("d2", "bid_bond")]
    assert [r["no"] for r in rows] == list(range(1, len(rows) + 1))
    docs = {d: SimpleNamespace(title_ja="題") for d in ("d0", "d1")}
    vals = sheet_values(next(r for r in nf if r["doc"] == "d0"), docs)
    assert len(vals) == len(HEADERS)
    assert vals[3].startswith("1) [p1_s1] 1 > 入札 > 本件の連絡先は総務課")
    assert vals[3].count("\n") == 3  # 4 candidates
    assert vals[4] == NOT_FOUND_ANSWER and vals[5] == NOT_FOUND_Q
    assert vals[6].startswith("Which number?")
    assert AUTO_CONFIRMED == "auto_confirmed_no_keyword_hit"


def test_build_rows_numbers_and_counts():
    raw = [row(i, f"d{i % 9}", "eligibility", f"条件{i}。") for i in range(100, 130)]
    raw += [row(i, f"d{i % 9}", "deadlines", f"期限{i}。") for i in range(200, 215)]
    absent = {"contact": {"d0": "d0" + "x" * 62}}
    rows, _ = build_rows(raw, Fake(sents=S), absent)
    assert [r["no"] for r in rows] == list(range(1, len(rows) + 1))
    assert sum(1 for r in rows if r.get("_not_found")) == 1
    assert all(
        r["src"].startswith("Section: ") for r in rows if not r.get("_not_found")
    )
    # the sentence rows keep their ten columns, minus the removed Where column
    docs = {f"d{i}": SimpleNamespace(title_ja="題") for i in range(9)}
    plain = next(r for r in rows if not r.get("_not_found"))
    assert len(sheet_values(plain, docs)) == len(HEADERS) == 10


def test_xlsx_dropdowns_and_freeze(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    docs = {"d1": SimpleNamespace(title_ja="題")}
    rows = [
        {**row(1, "d1", "eligibility", "あ。"), "no": 1},
        {
            **row(2, "d1", "contact", ""),
            "no": 2,
            "_not_found": True,
            "candidates": [("p1_s1", "1", "連絡先")],
        },
    ]
    p = tmp_path / "a.xlsx"
    write_xlsx(rows, docs, p)
    ws = openpyxl.load_workbook(p).active
    assert ws.freeze_panes == "A2"
    assert [c.value for c in ws[1]] == HEADERS
    sqref = str(ws.data_validations.dataValidation[0].sqref)
    assert "F2:G2" in sqref and "F3" in sqref
    assert not ws.merged_cells.ranges
