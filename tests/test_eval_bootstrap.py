"""eval/bootstrap.py on invented run reports only (no corpus, no model, no network)."""

import json
from pathlib import Path

import pytest

from eval import bootstrap as bs


def rec(doc: str, field: str, ok: bool = False, wrong: bool = False,
        pred: str = "absent", gold: str = "present") -> dict:  # fmt: skip
    return {"doc": doc, "field": field, "gold": gold, "pred": pred,
            "value_ok": ok, "verified_ok": ok, "wrong_shown": wrong}  # fmt: skip


def report(records: list[dict], **kw) -> dict:
    return {"name": "invented", "split": "dev", "extractor_version": "9.9.9",
            "schema_version": "9.9.9", "records": records} | kw  # fmt: skip


def grid(ok, docs: int = 6, fields: int = 4) -> list[dict]:
    """docs x fields rows; ok(doc number, field number) says if the row is correct."""
    return [
        rec(f"doc{d}", f"f{f}", ok(d, f)) for d in range(docs) for f in range(fields)
    ]


def parse(data: dict) -> bs.Report:
    return bs.Report.model_validate(data)


def run_two(a: list[dict], b: list[dict]) -> dict:
    ra, rb = bs.paired(parse(report(a)), parse(report(b)))
    return bs.bootstrap(ra, rb, "verified_ok")


def test_same_gain_in_every_document_gives_a_zero_width_interval_and_a_gain():
    r = run_two(grid(lambda d, f: False), grid(lambda d, f: f == 0))
    assert (r["delta"], r["low"], r["high"]) == (0.25, 0.25, 0.25)
    assert (r["false_to_true"], r["true_to_false"]) == (6, 0)
    assert (r["a"], r["b"], r["rows"]) == (0, 6, 24)
    assert bs.verdict(r, 6).startswith("Verdict: gain")


def test_gain_in_one_document_only_is_not_claimed():
    r = run_two(grid(lambda d, f: False), grid(lambda d, f: d == 0))
    assert r["delta"] > 0 and r["low"] == 0 < r["high"]
    assert "no measurable difference" in bs.verdict(r, 6)


def test_flips_both_ways_and_loss():
    r = run_two(grid(lambda d, f: f == 0), grid(lambda d, f: f == 1))
    assert (r["delta"], r["false_to_true"], r["true_to_false"]) == (0, 6, 6)
    assert "no measurable difference" in bs.verdict(r, 6)
    loss = run_two(grid(lambda d, f: f == 0), grid(lambda d, f: False))
    assert bs.verdict(loss, 6).startswith("Verdict: loss")


def test_rows_are_summed_not_averaged_per_document():
    # 1 row gained in a 1-row document, none in a 9-row one: 1 of 10 rows, not 50%
    a = [rec("small", "f0")] + [rec("big", f"f{i}") for i in range(9)]
    b = [rec("small", "f0", True)] + a[1:]
    r = run_two(a, b)
    assert (r["delta"], r["low"], r["high"]) == (0.1, 0.0, 1.0)


def test_seeded_and_independent_of_row_order():
    a = grid(lambda d, f: False)
    b = grid(lambda d, f: (d * f) % 3 == 1)
    assert run_two(a, b) == run_two(a[::-1], b)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r.update(split="test"), "only dev"),
        (lambda r: r.update(extractor_version="1"), "extractor_version differs"),
        (lambda r: r.update(schema_version="1"), "schema_version differs"),
        (lambda r: r["records"].append(rec("extra", "f0")), "documents differ"),
        (lambda r: r["records"].pop(), "rows differ"),
        (lambda r: r["records"].append(r["records"][0]), "appears twice"),
        (lambda r: r["records"][0].update(gold="absent"), "label status differs"),
    ],
)
def test_refuses_reports_that_cannot_be_compared(change, message):
    a = report(grid(lambda d, f: False))
    b = report(grid(lambda d, f: False))
    change(b)
    with pytest.raises(ValueError, match=message):
        bs.paired(parse(a), parse(b))


def test_refuses_one_document():
    one = parse(report(grid(lambda d, f: True, docs=1)))
    with pytest.raises(ValueError, match="at least 2 documents"):
        bs.paired(one, one)


def hashes(docs: int = 6) -> dict[str, str]:
    return {f"doc{d}": f"{d:064x}" for d in range(docs)}


def test_matching_label_hashes_pass():
    r = parse(report(grid(lambda d, f: False), label_sha256=hashes()))
    out = bs.render(r, r)
    assert "SHA-256 equal for all 6 documents" in out and "WARNING" not in out


@pytest.mark.parametrize("change", [{"doc3": "f" * 64}, {"doc3": None}])
def test_refuses_a_differing_or_missing_label_hash(change):
    other = {k: v for k, v in (hashes() | change).items() if v is not None}
    rows = grid(lambda d, f: False)
    a = parse(report(rows, label_sha256=hashes()))
    b = parse(report(rows, label_sha256=other))
    with pytest.raises(ValueError, match=r"label files differ.*\['doc3'\]"):
        bs.paired(a, b)


@pytest.mark.parametrize(
    ("a_has", "b_has", "named"),
    [(False, False, "A and B"), (False, True, "A"), (True, False, "B")],
)
def test_report_without_label_hashes_is_read_with_a_warning(a_has, b_has, named):
    rows = grid(lambda d, f: False)
    plain, hashed = report(rows), report(rows, label_sha256=hashes())
    a, b = (parse(hashed if has else plain) for has in (a_has, b_has))
    out = bs.render(a, b)
    assert f"WARNING: no label file hashes in report {named}," in out
    assert "label identity is unproven" in out and "Verdict:" in out


def test_load_refuses_test_split_before_reading_rows(tmp_path: Path):
    p = tmp_path / "run_x.json"
    p.write_text(json.dumps({"split": "test", "records": "never looked at"}))
    with pytest.raises(ValueError, match="only dev"):
        bs.load(p)


def test_readable_gain_matches_the_plan_table():
    assert round(100 * bs.readable_gain(324, 15), 1) == 6.8
    assert round(100 * bs.readable_gain(190, 10), 1) == 8.5


def test_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    a = grid(lambda d, f: False)
    b = grid(lambda d, f: f == 0)
    a[1] = rec("doc0", "f1", wrong=True, pred="present")
    b[2] = rec("doc0", "f2", pred="see_other_document")  # a wrong pointer
    b[3] = rec("doc0", "f3", True, pred="see_other_document")  # a right one
    paths = []
    for name, rows in (("a", a), ("b", b)):
        p = tmp_path / f"run_{name}.json"
        p.write_text(json.dumps(report(rows, name=name)))
        paths.append(str(p))
    assert bs.main(paths) == 0
    out = capsys.readouterr().out
    assert "Wrong-answer rate: A 1 of 24 (4.2%), B 0 of 24 (0.0%)" in out
    assert "rows flipped: 0 false to true, 1 true to false" in out
    assert "wrong see_other_document (not in the rate above): A 0, B 1" in out
    assert "Verdict: gain" in out
    assert bs.main([paths[0], str(tmp_path / "missing.json")]) == 1
    assert "refused:" in capsys.readouterr().err
