"""Checks for eval/gold_select.py. Invented manifests; reads no real data."""

import json
from collections import Counter

from collector.manifest import BundleRow, ManifestRow
from eval.gold_select import ORG_MAX, TOTAL, build

SPLITS = {"orgA": "dev", "orgB": "dev", "orgC": "dev", "orgD": "dev", "orgT": "test"}


def row(
    i: str, org: str, doc_type: str = "notice", lic: str = "open", **kw
) -> ManifestRow:
    d = {
        "doc_id": i, "source": "p-portal", "url": "u", "landing_url": "u",
        "issuer_org": org, "title_ja": "t", "doc_type": doc_type, "notice_date": None,
        "wto_covered": None, "jetro_ref": None, "pages": None, "text_layer": None,
        "fetched_at": "2026-10-01T00:00:00Z", "license_note": "n",
        "license_class": lic, "format": "html", "has_english_summary": True,
        "is_it": False, "path": "p",
    }  # fmt: skip
    return ManifestRow.model_validate({**d, **kw})


def invented() -> tuple[list[ManifestRow], dict, list[BundleRow]]:
    rows = []
    for k in range(12):  # notices with a summary, spread over four dev orgs
        rows.append(row(f"n{k:02}", f"org{'ABCD'[k % 4]}"))
    for k in range(12):
        rows.append(row(f"m{k:02}", f"org{'ABCD'[k % 4]}", has_english_summary=False))
    for k in range(6):  # only orgA issues instructions and specs
        for t in ("bid_instructions", "spec"):
            rows.append(row(f"{t[:2]}{k}", "orgA", t, source="x", format="pdf",
                            pages=8, text_layer="full",
                            has_english_summary=None))  # fmt: skip
    rows.append(row("restricted1", "orgB", lic="restricted"))
    rows.append(row("unknown1", "orgB", lic="unknown"))
    rows.append(row("test1", "orgT"))
    rows.append(
        row("ocr1", "orgC", "spec", format="pdf", pages=8, text_layer="partial")
    )
    info = {r.doc_id: {"ok": True, "n_ja": 20, "ocr_pages": 0} for r in rows}
    info["ocr1"]["ocr_pages"] = 3  # 3 of 8 pages: more than a quarter
    bundles = [BundleRow(bundle_id="b0", issuer_org="orgA", title_ja="t",
                         doc_ids=["n00", "bi0", "sp0"])]  # fmt: skip
    return rows, info, bundles


def test_only_open_dev_and_strata() -> None:
    rows, info, bundles = invented()
    g = build(rows, info, SPLITS, bundles)
    docs = [d for w in g["waves"] for d in w["docs"]]
    ids = {d["doc_id"] for d in docs}
    assert len(docs) == len(ids) == TOTAL
    assert not ids & {"restricted1", "unknown1", "test1", "ocr1"}
    assert g["skipped"] == {"mostly OCR": 1}
    c = Counter(d["stratum"] for d in docs)
    assert c["notice_summary"] >= 6
    assert max(Counter(d["org"] for d in docs).values()) <= ORG_MAX
    assert len({d["org"] for d in docs}) >= 4
    # orgA is capped at 6, so 4+4 instructions and specs cannot both fit
    assert "bid_instructions" in g["shortfalls"] or "spec" in g["shortfalls"]


def test_waves_cover_strata_and_pilot_is_wave_zero() -> None:
    rows, info, bundles = invented()
    rows[0] = row("f19cddbd4cba0000", "orgB")  # a pilot id (first 12 chars)
    info["f19cddbd4cba0000"] = {"ok": True, "n_ja": 20, "ocr_pages": 0}
    g = build(rows, info, SPLITS, bundles)
    assert g["pilot_qualified"] == ["f19cddbd4cba"]
    assert g["waves"][0]["wave"] == 0 and g["waves"][0]["already_labeled"]
    assert all(len(w["docs"]) <= 5 for w in g["waves"])
    for w in g["waves"][1:]:
        assert len({d["stratum"] for d in w["docs"]}) >= 2


def test_restricted_pilot_is_left_out() -> None:
    rows, info, bundles = invented()
    rows.append(row("563042df99410000", "orgB", lic="restricted"))
    info["563042df99410000"] = {"ok": True, "n_ja": 20, "ocr_pages": 0}
    g = build(rows, info, SPLITS, bundles)
    assert "563042df9941" in g["pilot_left_out"]


def test_deterministic() -> None:
    rows, info, bundles = invented()
    a = json.dumps(build(rows, info, SPLITS, bundles), sort_keys=True)
    b = json.dumps(build(list(reversed(rows)), info, SPLITS, bundles), sort_keys=True)
    assert a == b
