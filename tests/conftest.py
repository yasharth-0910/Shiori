from collections.abc import Callable
from pathlib import Path

import pytest

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def _find_corpus_pdf(doc_id_prefix: str) -> Path:
    matches = sorted(RAW_DIR.rglob(f"{doc_id_prefix}*.pdf"))
    if not matches:
        pytest.skip(f"corpus file {doc_id_prefix} not in data/raw/")
    return matches[0]


@pytest.fixture
def corpus_pdf() -> Callable[[str], Path]:
    """Look up a collected PDF in data/raw/ (gitignored) by doc_id prefix. Skips the
    test when the file isn't on this machine, so `corpus` tests pass on a fresh
    clone."""
    return _find_corpus_pdf
