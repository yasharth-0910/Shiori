"""Load a manifest document's sentences for dev-time tools (label validator, label set).

Sentences are cached in data/processed/<doc_id>/sentences.json, keyed by extractor
version, so OCR runs once per document. Dev-time only: never imported by the app.
"""

import json
from pathlib import Path

from pydantic import TypeAdapter
from shiori_core.html_ingest import load_html_document
from shiori_core.ingest import load_document
from shiori_core.models import EXTRACTOR_VERSION, Document, Sentence

from collector.manifest import ManifestRow

PROCESSED_DIR = Path("data/processed")
_SENTENCES = TypeAdapter(list[Sentence])


def extract(row: ManifestRow, ocr: bool = True) -> Document:
    path = Path(row.path)
    if row.format == "html":
        return load_html_document(path)
    return load_document(path, ocr=ocr)


def load_sentences(row: ManifestRow) -> list[Sentence]:
    cache = PROCESSED_DIR / row.doc_id / "sentences.json"
    if cache.exists():
        data = json.loads(cache.read_text())
        if data["extractor_version"] == EXTRACTOR_VERSION:
            return _SENTENCES.validate_python(data["sentences"])
    sentences = extract(row).sentences
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(
            {
                "extractor_version": EXTRACTOR_VERSION,
                "sentences": _SENTENCES.dump_python(sentences, mode="json"),
            },
            ensure_ascii=False,
        )
    )
    return sentences
