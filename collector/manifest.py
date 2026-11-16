"""Manifest rows (data/README.md) and bundle rows, validated on every read and write."""

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

DocType = Literal[
    "notice",
    "bid_instructions",
    "spec",
    "evaluation_criteria",
    "draft_contract",
    "forms",
    "rfi_material",  # anything posted for a request for information (情報提供依頼)
    "tender_page",  # HTML page around a tender whose notice is a separate PDF
    "qa",  # answers to bidders' questions (質問回答, 質疑応答)
    "result",  # award or evaluation results (入札結果, 審査結果, 開札録)
    "other",
]
LicenseClass = Literal["open", "restricted", "unknown"]  # D-16
TextLayer = Literal["full", "partial", "none"]

DOCUMENTS_PATH = Path("data/manifests/documents.jsonl")
BUNDLES_PATH = Path("data/manifests/bundles.jsonl")


class ManifestRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    source: str
    url: str
    landing_url: str
    issuer_org: str
    title_ja: str
    doc_type: DocType
    notice_date: date | None
    wto_covered: bool | None
    jetro_ref: str | None
    pages: int | None  # None unless pdf
    text_layer: TextLayer | None  # None unless pdf
    fetched_at: datetime
    license_note: str
    license_class: LicenseClass
    format: Literal["pdf", "html", "zip"]
    extracted_from: str | None = None  # doc_id of the ZIP this PDF came out of (D-21)
    # English Summary section found on the page (WTO notices); None unless p-portal
    has_english_summary: bool | None = None
    is_it: bool  # a STRICT_IT_CUES word in the title or the bundle title (D-27)
    path: str


class BundleRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    issuer_org: str
    title_ja: str
    doc_ids: list[str]


def read_rows(path: Path = DOCUMENTS_PATH) -> list[ManifestRow]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ManifestRow.model_validate_json(line) for line in lines if line.strip()]


def append_row(row: ManifestRow, path: Path = DOCUMENTS_PATH) -> None:
    """Append one row, re-validated so an unchecked model_construct can't slip in."""
    line = ManifestRow.model_validate(row.model_dump()).model_dump_json()
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_bundles(path: Path = BUNDLES_PATH) -> dict[str, BundleRow]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [BundleRow.model_validate_json(line) for line in lines if line.strip()]
    return {row.bundle_id: row for row in rows}


def write_bundles(bundles: dict[str, BundleRow], path: Path = BUNDLES_PATH) -> None:
    """Rewrite the whole file. It is small, and bundles gain members across runs."""
    lines = [bundles[key].model_dump_json() for key in sorted(bundles)]
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
