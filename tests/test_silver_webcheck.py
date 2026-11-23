"""webcheck (D-111): only open-license documents pass; temporary manifest."""

import json

from eval.silver.webcheck import webcheck


def manifest(tmp_path):
    p = tmp_path / "documents.jsonl"
    rows = [("aaaa1111", "open"), ("bbbb2222", "restricted"), ("cccc3333", "unknown")]
    p.write_text(
        "\n".join(
            json.dumps({"doc_id": d + "0" * 8, "license_class": c}) for d, c in rows
        )
    )
    return p


def test_open_passes(tmp_path):
    lines, bad = webcheck(["aaaa1111"], manifest(tmp_path))
    assert lines == ["aaaa1111 open"] and bad == []


def test_restricted_unknown_and_missing_fail(tmp_path):
    lines, bad = webcheck(
        ["aaaa1111", "bbbb2222", "cccc3333", "dddd4444"], manifest(tmp_path)
    )
    assert bad == ["bbbb2222", "cccc3333", "dddd4444"]
    assert lines[3] == "dddd4444 missing"
