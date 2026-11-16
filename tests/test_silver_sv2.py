# ruff: noqa: E501, E731, F811  (F811: the env fixture is imported)
# pyright: reportOptionalSubscript=false, reportOptionalMemberAccess=false
"""Silver pipeline sv2: independent providers, the ledger, backoff, parsing, chunk
merging, ellipsis tolerance, the heading-cue fix, agreement rules on the pilot replay,
candidate C, the mapping sidecar and review stats. No real API call; providers are the
scripted fakes of test_silver.py.

Sentence text: 支出負担行為担当官 / 契約担当官等の官職及び氏名 / 入札説明書による。 are from
doc 563042df9941 (内閣府 notice, h_s21, h_s22, h_s30); the NUM-6 clause is the standard
one quoted in test_silver.py (563042df9941 h_s35 has the same wording)."""

import json

import pytest
from shiori_core.fields import BY_ID

from eval.silver import checks, config, pipeline, review, run
from eval.silver.agree import ACTIVE, agree, union_items
from eval.silver.limiter import Ledger
from eval.silver.model import Candidate, canonical, from_row
from eval.silver.pipeline import BACKOFF, Pipeline, merge
from eval.silver.prompt import (
    applicable_fields,
    guide_rules,
    response_schema,
    rows_of,
    system_prompt,
)  # fmt: skip
from eval.silver.providers import ProviderError
from tests.test_silver import (  # noqa: F401  (env is a fixture)
    GOOD,
    LOCAL,
    SENTENCES,
    Fake,
    answer,
    env,
    labels_of,
    row,
    sent,
)

E503 = lambda: ProviderError("server", "HTTP 503", code=503)  # noqa: E731


def sv2_answer(over: dict | None = None, doc_type: str = "notice") -> str:
    """An answer in the sv2 shape: fields keyed by id, normalized beside them."""
    fields, norm = {}, {}
    for f in applicable_fields(doc_type):
        e = {
            "status": "absent",
            "ref": None,
            "value_ja": "",
            "value_en": "",
            "citations": [],
            "reason": "r",
        }
        o = dict((over or {}).get(f, {}))
        n = o.pop("normalized", None)
        e.update(o)
        fields[f] = e
        if BY_ID[f].model is not None:
            norm[f] = n
    return json.dumps({"fields": fields, "normalized": norm}, ensure_ascii=False)


# --- step 2: providers run independently -------------------------------------------------


def test_one_provider_down_does_not_stop_the_other(env):
    pipe = env.make({"gemini": [E503()], LOCAL: [answer(GOOD)]})
    rows = [row(), row(doc_id="d2")]
    out = run.run_docs(rows, 100, pipe=pipe)
    assert out == {"resolved": 0, "compared": 0, "pending": 2, "skipped": 0}
    per_doc = len(pipeline.plan_parts(row(), SENTENCES, pipeline.LOCAL_CFG))
    assert (
        env.fakes[LOCAL].calls == 2 * per_doc
    )  # the local model labeled both documents
    # 3 tries on the first document (D-58), then Gemini is paused for the run: d2 is not tried
    assert env.fakes["gemini"].calls == config.PROVIDERS["gemini"].max_tries == 3
    raw = run.load_raw(pipeline.raw_path("d1", "gemini", "gemini-model"))
    assert pipeline.raw_state(raw) == "unavailable"
    assert not pipeline.raw_path("d2", "gemini", "gemini-model").exists()
    # next run: Gemini is back; the local model is not asked again, both documents resolve
    env.fakes["gemini"].script = [answer(GOOD)]
    before = env.fakes[LOCAL].calls
    out = run.run_docs(rows, 100, pipe=pipe)
    assert out["resolved"] == 2 and env.fakes[LOCAL].calls == before


def test_daily_cap_on_one_provider_lets_the_other_finish(env):
    pipe = env.make(
        {
            "gemini": [ProviderError("daily_quota", "per day", code=429)],
            LOCAL: [answer(GOOD)],
        }
    )
    out = run.run_docs([row(), row(doc_id="d2")], 100, pipe=pipe)
    assert out["pending"] == 2 and env.fakes["gemini"].calls == 1  # stopped for the day
    assert all(
        pipeline.raw_state(
            run.load_raw(pipeline.raw_path(d, "local", "Qwen3.5-9B-Q4_K_M"))
        )
        == "complete"
        for d in ("d1", "d2")
    )
    assert "local   1 complete" in run.status_text("dev")  # label set holds d1
    assert Ledger(env.tmp / "cache" / "usage.jsonl").today("gemini", env.clock.now())[
        "blocked"
    ]


# --- steps 3 and 4: ledger and backoff ---------------------------------------------------


def test_backoff_schedule_then_provider_unavailable(env):
    pipe = env.make({"gemini": [E503()], LOCAL: [answer(GOOD)]})
    slept = []
    pipe.sleep = lambda s: (slept.append(s), env.clock.sleep(s))
    pipe._limiters.clear()
    r = pipe._call("gemini", "s", "u", {}, pipeline.Part(["title"], SENTENCES, 100, 10))
    assert r["status"] == "provider_unavailable" and r["attempts"] == 3  # Gemini, D-58
    assert slept == [30, 60]
    u = Ledger(env.tmp / "cache" / "usage.jsonl").today("gemini", env.clock.now())
    assert u["requests"] == 3 and u["failed"] == 3 and u["outcomes"] == {"http_503": 3}
    # Groq keeps 5 tries and the whole schedule
    pipe = env.make({"groq": [E503()]})
    slept.clear()
    pipe.sleep = lambda s: (slept.append(s), env.clock.sleep(s))
    r = pipe._call("groq", "s", "u", {}, pipeline.Part(["title"], SENTENCES, 100, 10))
    assert r["attempts"] == len(BACKOFF) + 1 == 5 and slept == [30, 60, 120, 240]


def test_backoff_respects_retry_after_and_recovers(env):
    pipe = env.make(
        {
            "gemini": [
                ProviderError("rate_limit", "HTTP 429", retry_after=7, code=429),
                E503(),
                answer(GOOD),
            ]
        }
    )
    slept = []
    pipe.sleep = lambda s: (slept.append(s), env.clock.sleep(s))
    r = pipe._call("gemini", "s", "u", {}, pipeline.Part(["title"], SENTENCES, 100, 10))
    assert r["status"] == "ok" and r["attempts"] == 3
    assert slept == [7, 60]  # the server's Retry-After, then the schedule
    u = Ledger(env.tmp / "cache" / "usage.jsonl").today("gemini", env.clock.now())
    assert u["outcomes"] == {"http_429": 1, "http_503": 1, "ok": 1}


def test_ledger_counts_probes_key_checks_and_failures(env, monkeypatch, capsys):
    from eval.silver import __main__ as cli

    led = Ledger(env.tmp / "cache" / "usage.jsonl")
    fake = Fake("gemini", "gemini-model", [E503(), '{"ok": true}'])
    monkeypatch.setattr(pipeline, "_default_factory", lambda key: fake)
    assert cli.probe("gemini") == 1  # 503
    assert cli.probe("gemini") == 0
    led.append(
        ts=env.clock.now(), provider="gemini", model="m", ok=False
    )  # a pre-sv2 line
    import time

    u = led.today("gemini", time.time())
    assert u["kinds"]["probe"] == 2
    assert u["outcomes"]["http_503"] == 1 and u["outcomes"]["ok"] == 1
    # failures count against the day's request budget: Google does not say otherwise
    assert u["requests"] == u["ok"] + u["failed"]
    assert "AIza" not in (env.tmp / "cache" / "usage.jsonl").read_text()
    assert "gemini: http_503" in capsys.readouterr().out


# --- step 5: parsing and the sv2 schema --------------------------------------------------


def test_normalized_as_a_string_is_parsed_once_more():
    inner = json.dumps({"basis": "bid_excludes_tax"})
    c = from_row(
        {
            "field": "tax_basis",
            "status": "present",
            "normalized": json.dumps(inner),
            "citations": ["p1_s6"],
        },
        "x",
    )
    assert c.normalized == {"basis": "bid_excludes_tax"} and c.parse_error is None
    c = from_row(
        {
            "field": "tax_basis",
            "status": "present",
            "normalized": '"not json"',
            "citations": [],
        },
        "x",
    )
    assert c.parse_error == "normalized is not valid JSON"


def test_text_field_pointer_keeps_its_ref_in_both_shapes():
    ref = {"kind": "bid_instructions", "text_ja": "入札説明書による。"}
    sv1 = from_row({"field": "delivery_location", "status": "see_other_document", "value_ja": "入札説明書による。",
                    "normalized": json.dumps({"ref": ref}), "citations": ["h_s30"]}, "x")  # fmt: skip
    (r,) = [x for x in rows_of(json.loads(sv2_answer({"delivery_location": {"status": "see_other_document", "ref": ref, "citations": ["h_s30"]}}))) or [] if x["field"] == "delivery_location"]  # fmt: skip
    sv2 = from_row(r, "x")
    assert sv1.normalized == sv2.normalized == {"ref": ref}


def test_sv2_schema_is_strict_and_per_field():
    s = response_schema(applicable_fields("notice"))
    fields = s["properties"]["fields"]
    assert fields["required"] == applicable_fields("notice")
    assert set(s["properties"]["normalized"]["properties"]) == {
        f for f in applicable_fields("notice") if BY_ID[f].model is not None
    }

    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "object":
                assert n["additionalProperties"] is False
                assert n["required"] == list(n["properties"])
            assert "default" not in n and "format" not in n
            assert not isinstance(n.get("title"), str)  # a field named title is fine
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(s)
    # values a label never uses are not offered inside normalized
    text = json.dumps(s["properties"]["normalized"])
    assert "not_stated" not in text and "see_other_document" not in text
    officer = s["properties"]["normalized"]["properties"]["contracting_officer"][
        "anyOf"
    ][0]
    assert list(officer["properties"]) == [
        "title",
        "name",
    ]  # a property named title stays
    bond = s["properties"]["normalized"]["properties"]["bid_bond"]["anyOf"][0]
    assert bond["properties"]["status"]["enum"] == [
        "required",
        "waived",
        "waived_with_proviso",
    ]


def test_prompt_carries_the_guide_and_only_the_fields_lines():
    p = system_prompt(["contracting_officer", "contact"])
    assert "支出負担行為担当官 出入国在留管理庁次長" in p  # guide rule
    assert (
        "Never shorten it with an ellipsis" in p
        and "see_other_document: always include ref" in p
    )
    assert "- title: the name of the procurement" not in p  # another field's guide line
    assert "Example: " in p
    assert guide_rules().count("\n- ") >= 12


# --- step 5: chunk merging ---------------------------------------------------------------


def cand(
    field,
    status="present",
    value_ja=None,
    normalized=None,
    citations=(),
    labeler="groq/m",
):
    return Candidate(
        field, status, value_ja, None, normalized, list(citations), labeler=labeler
    )


def test_merge_lists_union_deduplicated():
    a = cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "bid_opening",
                    "datetime": "2026-10-05T14:00:00+09:00",
                    "flags": [],
                    "citations": ["h_s55"],
                }
            ]
        },
        citations=["h_s55"],
    )
    b = cand("deadlines", normalized={"items": [
        {"kind": "bid_opening", "datetime": "2026-10-05T14:00:00+09:00", "flags": [], "citations": ["h_s55", "h_s56"]},
        {"kind": "electronic", "datetime": "2026-10-05T13:30:00+09:00", "flags": [], "citations": ["h_s53"]}]}, citations=["h_s53"])  # fmt: skip
    m = merge("deadlines", [a, b], "groq/m")
    items = m.normalized["items"]
    assert [i["kind"] for i in items] == ["bid_opening", "electronic"]
    assert items[0]["citations"] == ["h_s55", "h_s56"] and m.citations == [
        "h_s55",
        "h_s56",
        "h_s53",
    ]
    assert m.parse_error is None


def test_merge_scalar_keeps_the_part_under_the_heading_cue():
    by_id = {
        s.id: s
        for s in [
            sent("h_s5", "一般競争入札の公告"),
            sent("h_s24", "次のとおり一般競争入札に付します。", path=["1"]),
        ]
    }
    by_id["h_s24"].section_titles.append(
        "一般競争入札"
    )  # section heading carries the cue
    early = cand(
        "procurement_type", normalized={"type": "open_competitive"}, citations=["h_s5"]
    )
    late = cand(
        "procurement_type", normalized={"type": "open_competitive"}, citations=["h_s24"]
    )
    by_id["h_s5"].section_titles.clear()
    m = merge("procurement_type", [early, late], "groq/m", by_id)
    assert m.parse_error is None and not m.alternatives  # same answer: no conflict
    # both cite a cue at a heading here; ties go to the earlier part
    assert m.citations in (["h_s5"], ["h_s24"])


def test_merge_conflicting_scalars_are_alternatives_and_flagged_not_schema_failures(
    env,
):
    a = cand(
        "procurement_type", normalized={"type": "open_competitive"}, citations=["p1_s1"]
    )
    b = cand(
        "procurement_type",
        normalized={"type": "designated_competitive"},
        citations=["p1_s1"],
    )
    m = merge("procurement_type", [a, b], "groq/m")
    assert m.parse_error is None and len(m.alternatives) == 1
    good = {
        **GOOD,
        "procurement_type": dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "open_competitive"},
        ),
    }
    other = {
        **GOOD,
        "procurement_type": dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "designated_competitive"},
        ),
    }
    gemini = pipeline.answers(
        {"chunks": {"0": {"status": "ok", "response": answer(good)}}},
        "gemini/m",
        applicable_fields("notice"),
    )
    groq = pipeline.answers(
        {
            "chunks": {
                "0": {"status": "ok", "response": answer(good)},
                "1": {"status": "ok", "response": answer(other)},
            }
        },
        "groq/m",
        applicable_fields("notice"),
    )
    res = {
        r.field: r
        for r in pipeline.resolve(
            row(), SENTENCES, [gemini, groq], [("g", "m", "d"), ("q", "m", "d")], False
        )
    }
    r = res["procurement_type"]
    assert (
        r.state == "flagged"
        and "B: parts of the document give different answers" in r.reasons
    )
    assert not any("schema_valid" in x for x in r.reasons)
    assert r.sides[1]["candidate"]["alternatives"][0]["normalized"] == {
        "type": "designated_competitive"
    }


def test_merge_absent_in_one_part_present_in_another_is_present():
    m = merge(
        "tax_basis",
        [
            cand("tax_basis", "absent"),
            cand(
                "tax_basis",
                normalized={"basis": "bid_excludes_tax"},
                citations=["p1_s6"],
            ),
        ],
        "x",
    )
    assert m.status == "present"


# --- step 5: ellipsis --------------------------------------------------------------------


# Tax clause from open doc 2f2f5bd3 (Wakayama), parenthetical removed.
NUM6 = "落札者の決定に当たっては、入札書に記載された金額に当該金額の100分の10に相当する額を加算した金額をもって落札価格とする。"


def test_value_in_citation_tolerates_an_ellipsis_in_order_only():
    by_id = {"p1_s6": sent("p1_s6", NUM6)}
    ok = cand(
        "tax_basis",
        value_ja="落札者の決定に当たっては、…落札価格とする。",
        normalized={"basis": "bid_excludes_tax"},
        citations=["p1_s6"],
    )
    dots = cand(
        "tax_basis",
        value_ja="入札書に記載された金額...落札価格とする",
        normalized={"basis": "bid_excludes_tax"},
        citations=["p1_s6"],
    )
    wrong_order = cand(
        "tax_basis",
        value_ja="落札価格とする…落札者の決定に当たっては",
        normalized={"basis": "bid_excludes_tax"},
        citations=["p1_s6"],
    )
    assert checks.value_in_citation(ok, by_id) and checks.value_in_citation(dots, by_id)
    assert not checks.value_in_citation(wrong_order, by_id)


# --- step 6: heading cues ----------------------------------------------------------------


def test_cue_inside_a_longer_word_does_not_count():
    assert not checks.cue_in("担当", "支出負担行為担当官")  # 563042df9941 h_s22
    assert not checks.cue_in("担当", "１．契約担当官等の官職及び氏名")  # h_s21
    assert checks.cue_in("担当", "担当部局")  # starts a word
    assert checks.cue_in("問い合わせ先", "問い合わせ先 総務課")
    assert not checks.cue_in(
        "問い合わせ先",
        "　　　　　　　　　　　　　　　　問い合わせ先",
        checks.HEAD_CHARS,
    )


def test_both_absent_trigger_ignores_short_cues_unless_whole_heading():
    officer = [
        sent("h_s21", "１．契約担当官等の官職及び氏名", path=["1"]),
        sent("h_s22", "支出負担行為担当官", path=["1"]),
    ]
    officer[0].section_titles.append("契約担当官等の官職及び氏名")
    officer[1].section_titles.append("契約担当官等の官職及び氏名")
    assert pipeline.cue_present(officer, "contact") is None
    assert pipeline.cue_present([sent("p1_s1", "(5) 担当")], "contact") == "担当"
    assert (
        pipeline.cue_present([sent("p1_s1", "担当者は総務課")], "contact") is None
    )  # short cue, not the whole heading
    assert (
        pipeline.cue_present([sent("p1_s1", "７．問い合わせ先")], "contact")
        == "問い合わせ先"
    )


def test_heading_cue_check_reads_headings_and_sentence_starts_only():
    s = sent("p1_s9", "この件について不明な点は、下記の問い合わせ先まで連絡すること。")
    c = cand("contact", normalized={"phone": "03-1234-5678"}, citations=["p1_s9"])
    assert checks.heading_cue(c, {"p1_s9": s}) is False  # cue deep inside the sentence


@pytest.mark.corpus
def test_563042df9941_contact_has_no_heading_cue():
    """F-0037: 担当 inside 支出負担行為担当官 made sv1 flag both-absent contact."""
    from collector.manifest import read_rows
    from eval.documents import load_sentences

    rows = [r for r in read_rows() if r.doc_id.startswith("563042df9941")]
    if not rows or not (pipeline.Path(rows[0].path)).exists():
        pytest.skip("document not collected")
    ss = load_sentences(rows[0])
    ids = {s.id: s for s in ss}
    assert ids["h_s22"].text_orig == "支出負担行為担当官"
    assert pipeline.cue_present(ss, "contact") is None


# --- step 7: agreement rules on the pilot replay -----------------------------------------


def test_active_relaxations_never_accept_a_wrong_candidate_on_the_pilot_replay():
    from eval.silver import replay

    if (
        not replay.answers_path().exists()
        or not (replay.batches_dir() / "ids.json").exists()
    ):
        pytest.skip("pilot answers not present")
    items = replay.load_pilot()
    table = {r["rule"]: r for r in replay.relaxation_replay(items)}
    assert all(not table[r]["wrong"] for r in ACTIVE)  # never wrong (D-58 criterion)
    # the D-47 rules also settle at least one item; eligibility_negation settles none
    assert all(table[r]["passes"] for r in ACTIVE - {"eligibility_negation"})
    assert (
        not table["period_relative_optional"]["passes"]
        and "F-0025" in table["period_relative_optional"]["wrong"]
    )
    assert "auto_wrong" not in replay.evaluate(items, ACTIVE).values()


def test_relaxations_never_touch_enums_or_dates():
    x = cand(
        "contracting_officer",
        normalized={
            "title": "支出負担行為担当官 出入国在留管理庁次長",
            "name": "内藤惣一郎",
        },
        citations=["h_s26"],
    )
    y = cand(
        "contracting_officer",
        normalized={
            "title": "支出負担行為担当官",
            "name": "出入国在留管理庁次長 内藤惣一郎",
        },
        citations=["h_s26"],
    )
    assert agree(x, y)[0] and not agree(x, y, frozenset())[0]  # F-0021
    d1 = cand(
        "performance_period",
        normalized={"start": None, "end": "2027-09-30", "relative_text": None},
    )
    d2 = cand(
        "performance_period",
        normalized={"start": None, "end": "2027-09-29", "relative_text": None},
    )
    assert not agree(d1, d2, frozenset(ACTIVE | {"period_relative_optional"}))[0]
    e1 = cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "question",
                    "datetime": "2026-07-01",
                    "flags": [],
                    "citations": ["a"],
                }
            ]
        },
    )
    e2 = cand(
        "deadlines",
        normalized={
            "items": [
                {
                    "kind": "other",
                    "datetime": "2026-07-01",
                    "flags": [],
                    "citations": ["a"],
                }
            ]
        },
    )
    assert not agree(e1, e2, frozenset({"list_items_by_citation"}))[0]


# --- step 8: candidate C, mapping, reviewed_choice, review stats ------------------------


# Mechanics only: the item names are words the fixture sentences contain, not real
# required documents.
DOCS_A = {"required_documents": dict(status="present", normalized={"items": [{"name_ja": "入札保証金", "name_en": "x", "citations": ["p1_s4"]}]})}  # fmt: skip
DOCS_B = {"required_documents": dict(status="present", normalized={"items": [{"name_ja": "契約保証金", "name_en": "y", "citations": ["p1_s5"]}]})}  # fmt: skip


def list_env(env):
    run.run_docs(
        [row()],
        100,
        pipe=env.make(
            {
                "gemini": [answer({**GOOD, **DOCS_A})],
                LOCAL: [answer({**GOOD, **DOCS_B})],
            }
        ),
    )
    return review.export("dev", True, lambda split, open_only: [row()])


def test_export_adds_union_candidate_and_mapping_sidecar(env):
    (p,) = list_env(env)
    text = p.read_text()
    assert "C (union of A and B items)" in text and "accept C" in text
    assert (
        "gemini" not in text.split("## F-0001")[1]
        and "local" not in text.split("## F-0001")[1]
    )
    mapping = json.loads((env.tmp / "cache" / "export" / "mapping.json").read_text())
    assert mapping["F-0001"] == {"A": "gemini", "B": "local", "C": "union"}


def test_import_accept_c_writes_the_union_and_records_the_choice(env):
    list_env(env)
    assert review.import_answers("F-0001 | accept C") == (1, [])
    ln = labels_of(env)["required_documents"]
    assert [i["name_ja"] for i in ln["normalized"]["items"]] == [
        "入札保証金",
        "契約保証金",
    ]
    assert ln["provenance"]["reviewed_choice"] == "union"
    (rec,) = [
        json.loads(x)
        for x in (env.tmp / "cache" / "reviews.jsonl").read_text().splitlines()
    ]
    assert rec["right"] == {"gemini": False, "local": False, "union": True}
    assert "| union | list | 1 | 1 | 100%" in review.review_stats([rec])


def test_import_accept_records_provider_and_custom_may_cite_any_sentence(env):
    a = {
        **GOOD,
        "procurement_type": dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "open_competitive"},
        ),
    }
    b = {
        **GOOD,
        "procurement_type": dict(
            status="present",
            citations=["p1_s1"],
            normalized={"type": "designated_competitive"},
        ),
    }
    run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(a)], LOCAL: [answer(b)]})
    )
    review.export("dev", True, lambda s, o: [row()])
    assert review.import_answers("F-0001 | accept B") == (1, [])
    prov = labels_of(env)["procurement_type"]["provenance"]
    assert prov["reviewed_choice"] == "local" and prov["labeler_overlap"] is True
    # the custom answer cites p1_s6, which no candidate cited
    tax = {**GOOD, "tax_basis": dict(status="absent")}
    run.run_docs(
        [row(doc_id="d2")],
        100,
        pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(tax)]}),
    )
    review.export("dev", True, lambda s, o: [row(doc_id="d2")])
    reply = 'F-0002 | custom | status=present | cites=p1_s6 | normalized={"basis":"bid_excludes_tax"}'
    assert review.import_answers(reply) == (1, [])


def test_c_union_deduplicates_by_citation_and_value():
    items = union_items("required_documents", [
        [{"name_ja": "入札書", "citations": ["h_s49"]}],
        [{"name_ja": "入札書", "citations": ["h_s49", "h_s52"]}, {"name_ja": "提案書", "citations": ["h_s34"]}],
    ])  # fmt: skip
    assert [i["name_ja"] for i in items] == ["入札書", "提案書"] and items[0][
        "citations"
    ] == ["h_s49", "h_s52"]


def test_canonical_ignores_english_and_item_order():
    a = cand(
        "required_documents",
        normalized={
            "items": [
                {"name_ja": "入札書", "name_en": "Bid", "citations": ["x"]},
                {"name_ja": "提案書", "name_en": "P", "citations": ["y"]},
            ]
        },
    )
    b = cand(
        "required_documents",
        normalized={
            "items": [
                {"name_ja": "提案書", "name_en": "Proposal", "citations": ["y"]},
                {"name_ja": "入札書", "name_en": "Bid form", "citations": ["x"]},
            ]
        },
    )
    assert canonical(a) == canonical(b)


# --- step 10: comparison mode never writes labels ----------------------------------------


def test_documents_with_labels_run_in_comparison_mode_only(env, monkeypatch):
    run.run_docs(
        [row()], 100, pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]})
    )
    label = labels_of(env)
    resolved = pipeline.resolved_path("d1").read_text()
    # the same prompt version again: resolved as before, no comparison
    assert (
        run.run_docs(
            [row()],
            100,
            pipe=env.make({"gemini": [answer(GOOD)], LOCAL: [answer(GOOD)]}),
        )["resolved"]
        == 1
    )
    assert not (env.tmp / "silver_pilot.md").exists()
    # a later prompt version: new raw answers, different from the labels
    monkeypatch.setattr(pipeline, "PROMPT_VERSION", "sv9")
    monkeypatch.setattr(pipeline, "LOCAL_PROMPT_VERSION", "sv9")  # both bumped
    other = {
        **GOOD,
        "bid_bond": dict(
            status="present", citations=["p1_s4"], normalized={"status": "required"}
        ),
    }
    pipe: Pipeline = env.make({"gemini": [answer(other)], LOCAL: [answer(other)]})
    out = run.run_docs([row()], 100, pipe=pipe)
    assert out["compared"] == 1 and out["resolved"] == 0
    assert (
        labels_of(env) == label and pipeline.resolved_path("d1").read_text() == resolved
    )
    report = (env.tmp / "silver_pilot.md").read_text()
    assert "optimistic" in report and "| d1 | comparison |" in report
    assert (
        "d1 bid_bond (consensus)" in report
    )  # both labelers now differ from the label


def test_sv2_shaped_answers_resolve_end_to_end(env):
    pipe = env.make({"gemini": [sv2_answer(GOOD)], LOCAL: [sv2_answer(GOOD)]})
    out = run.run_docs([row()], 100, pipe=pipe)
    assert out["resolved"] == 1
    lab = labels_of(env)
    assert lab["performance_bond"]["normalized"] == {
        "status": "required",
        "rate_percent": 10,
    }
    assert lab["title"]["value_ja"] == "庁舎清掃業務"


def test_bad_request_keeps_the_providers_reason():
    from eval.silver.providers import _classify

    body = '{"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "schema has too many states"}}'  # fmt: skip
    e = _classify(400, body, None)
    assert e.kind == "bad_request" and "INVALID_ARGUMENT: schema has too many states" in str(e)  # fmt: skip
