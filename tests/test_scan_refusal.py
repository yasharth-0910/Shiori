# ruff: noqa: E501
"""v0.1 does not ship OCR (D-112). A document with a page that needs OCR is refused whole
with the typed error `scan_not_supported`, never read in part (a partial read would turn
text on the skipped pages into wrong "Not found" answers). Tests run with no OCR engine
(SHIORI_NDLOCR_DIR points at an empty folder), the state of a packaged build."""

import sys
from pathlib import Path

import pytest
from shiori_core import ocr
from shiori_core.ocr.ndlocr import ENV_VAR, NdlocrEngine, ndlocr_dir
from test_sidecar import TOKEN, Server, wait_for

from sidecar.server import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pdf"


@pytest.fixture
def no_ocr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "absent"))
    monkeypatch.setattr(
        ocr, "_default", None
    )  # an engine loaded by an earlier test would hide the refusal


def run(path: Path) -> dict:
    with Server(create_app(TOKEN)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(path)})[1]["doc_id"]
        return wait_for(srv, doc_id, "failed")


def test_committed_scanned_fixture_is_refused_with_the_typed_code(no_ocr) -> None:
    # okayama_scanned.pdf is doc 7fb45ac7dec4..., one image-only page (D-23)
    got = run(FIXTURES / "okayama_scanned.pdf")
    assert got["error"] == "scan_not_supported"


@pytest.mark.corpus
@pytest.mark.parametrize(
    "prefix", ["7fb45ac7dec4", "7c76af66d35d"]
)  # scanned, outlined
def test_corpus_scan_and_outlined_documents_are_refused(
    no_ocr, corpus_pdf, prefix
) -> None:
    assert run(corpus_pdf(prefix))["error"] == "scan_not_supported"


def test_a_frozen_build_does_not_look_in_the_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert ndlocr_dir() is None
    with pytest.raises(Exception, match="NDLOCR-Lite not found"):
        NdlocrEngine()


def test_the_env_var_still_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert ndlocr_dir() == tmp_path
