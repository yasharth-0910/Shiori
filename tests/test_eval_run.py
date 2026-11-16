# ruff: noqa: E501
"""eval/run.py on two tiny invented documents (no corpus, no model, no network)."""

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from shiori_core.models import EXTRACTOR_VERSION, Sentence

from collector.manifest import ManifestRow
from eval import run
from eval.silver.compare import gold_of
from eval.silver.model import Candidate

TITLE = "テスト調達業務"


def row(doc_id: str) -> ManifestRow:
    return ManifestRow(
        doc_id=doc_id, source="s", url="u", landing_url="l", issuer_org="org",
        title_ja="t", doc_type="notice", notice_date=date(2026, 1, 1), wto_covered=None,
        jetro_ref=None, pages=1, text_layer="full", fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        license_note="", license_class="open", format="pdf", path="x.pdf", is_it=False,
    )  # fmt: skip


def sentence(i: str, text: str) -> Sentence:
    return Sentence(id=i, page=1, section_path=[], section_titles=[], text_orig=text,
                    text_norm=text, norm_to_orig=list(range(len(text))), boxes=[])  # fmt: skip


def line(doc_id: str, field: str, status: str, **kw) -> dict:
    return {"doc_id": doc_id, "extractor_version": EXTRACTOR_VERSION, "schema_version": "1.0.0",
            "field": field, "status": status, "value_ja": kw.get("value_ja"), "normalized": None,
            "citations": kw.get("citations", []),
            "provenance": {"reviewed_by": kw.get("reviewed_by")}}  # fmt: skip


def labels(doc_id: str) -> list[dict]:
    return [line(doc_id, "title", "present", value_ja=TITLE, citations=["p1_s1"], reviewed_by="claude_code"),
            line(doc_id, "bid_bond", "absent")]  # fmt: skip


@pytest.fixture
def world(tmp_path: Path):
    rows = [row("a" * 64), row("b" * 64)]
    d = tmp_path / "labels"
    d.mkdir()
    for r in rows:
        (d / f"{r.doc_id}.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in labels(r.doc_id))
        )
    return rows, [d], lambda r: [sentence("p1_s1", TITLE)]


def echo(r, sents):
    """A perfect extractor for these labels."""
    return {f: gold_of(ln) for ln in labels(r.doc_id) if (f := ln["field"])}


def test_stub_is_the_floor(world) -> None:
    rows, dirs, sents = world
    recs, skipped = run.evaluate(rows, dirs, run.stub_extractor, sents)
    t = run.tally(recs)
    assert skipped == []
    assert t["not_found"] == (2 * 2, 2 * 2)  # 2 documents x (title, bid_bond)
    assert t["verified_accuracy"] == (2, 4)  # only the two absent bid_bonds are right
    assert t["over_abstention"] == (2, 2)
    assert t["hallucination"] == (0, 0) and t["citation_exists"] == (0, 0)


def test_perfect_extractor_scores_everything(world) -> None:
    rows, dirs, sents = world
    t = run.tally(run.evaluate(rows, dirs, echo, sents)[0])
    assert t["verified_accuracy"] == (4, 4)
    assert t["citation_exists"] == (2, 2) and t["value_in_citation"] == (2, 2)
    assert t["hallucination"] == (0, 2) and t["not_found"] == (2, 4)


def test_value_not_in_citation_is_hallucination(world) -> None:
    rows, dirs, sents = world

    def liar(r, s):
        return {
            "title": Candidate(
                "title", "present", "存在しない文", None, None, ["p1_s1"]
            )
        }

    t = run.tally(run.evaluate(rows, dirs, liar, sents)[0])
    assert t["hallucination"] == (2, 2)
    assert t["value_in_citation"] == (0, 2)
    assert t["wrong_shown"] == (2, 4)


def test_right_value_with_wrong_citation_is_not_verified(world) -> None:
    rows, dirs, sents = world

    def off(r, s):
        return {"title": Candidate("title", "present", TITLE, None, None, ["p1_s9"])}

    t = run.tally(run.evaluate(rows, dirs, off, sents)[0])
    assert t["value_accuracy"] == (
        2 + 0,
        4,
    )  # titles agree only with overlapping citations
    assert t["verified_accuracy"][0] <= t["value_accuracy"][0]


def test_document_without_labels_is_listed_and_skipped(world) -> None:
    rows, dirs, sents = world
    (dirs[0] / f"{rows[1].doc_id}.jsonl").unlink()
    recs, skipped = run.evaluate(rows, dirs, run.stub_extractor, sents)
    assert skipped == [rows[1].doc_id] and {r["doc"] for r in recs} == {
        rows[0].doc_id[:12]
    }
    rep = run.build(recs, skipped, rows, "x", "dev", "stub", (0, 0))
    assert rep["skipped"] == [rows[1].doc_id[:12]] and rows[1].doc_id[
        :12
    ] in run.markdown(rep)


def test_labels_for_another_extractor_version_are_refused(world) -> None:
    rows, dirs, sents = world
    bad = labels(rows[0].doc_id)
    bad[0]["extractor_version"] = "9.9.9"
    (dirs[0] / f"{rows[0].doc_id}.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in bad)
    )
    with pytest.raises(ValueError, match="extractor"):
        run.evaluate(rows, dirs, run.stub_extractor, sents)


def test_reports_are_never_overwritten(world, tmp_path: Path, monkeypatch) -> None:
    rows, dirs, sents = world
    monkeypatch.setattr(run, "REPORTS", tmp_path / "reports")
    recs, skipped = run.evaluate(rows, dirs, run.stub_extractor, sents)
    names = [run.write(run.build(recs, skipped, rows, "dev_stub", "dev", "stub", (2, 4)))[0].name for _ in range(2)]  # fmt: skip
    assert names == ["run_dev_stub.json", "run_dev_stub_2.json"]
    assert "Hallucination" in (tmp_path / "reports" / "run_dev_stub.md").read_text()


# --- the test split stays closed -------------------------------------------------------


def test_only_dev_is_allowed() -> None:
    for split in ("test", "train", "../test", ""):
        with pytest.raises(ValueError):
            run.require_dev(split)
        with pytest.raises(ValueError):
            run.label_dirs(split)
    assert all("test" not in str(p) for p in run.label_dirs("dev"))
    with pytest.raises(SystemExit):
        run.main(["--split", "test"])


def test_harness_never_touches_a_test_path(world, tmp_path: Path, monkeypatch) -> None:
    """Every path the harness stats or reads while scoring the real dev label
    directories (by invented doc ids) stays out of the test split."""
    rows, _, sents = world
    monkeypatch.chdir(tmp_path)
    seen: list[str] = []
    for name in ("exists", "read_text", "glob", "is_file", "stat"):
        orig = getattr(Path, name)

        def spy(self, *a, _o=orig, **k):
            seen.append(str(self))
            return _o(self, *a, **k)

        monkeypatch.setattr(Path, name, spy)
    run.evaluate(rows, run.label_dirs("dev"), run.stub_extractor, sents)
    assert seen and not [p for p in seen if re.search(r"(^|/)test(/|$)", p)]


def test_source_has_no_test_split_path() -> None:
    src = Path(run.__file__).read_text()
    assert not re.search(r"eval(_private)?/test|/test/", src)
