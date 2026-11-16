"""Shared collection steps: adapters find candidates, this module does the rest.

An adapter (collector/sources/<name>.py) exposes SOURCE and discover(client) and only
finds links and metadata. This module downloads, dedupes by URL and SHA-256, checks
pages and text layer with PyMuPDF, writes manifest rows and bundle rows.
"""

import hashlib
import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol

from pydantic import BaseModel

from collector.manifest import (
    BUNDLES_PATH,
    DOCUMENTS_PATH,
    BundleRow,
    DocType,
    LicenseClass,
    ManifestRow,
    TextLayer,
    append_row,
    read_bundles,
    read_rows,
    write_bundles,
)

RAW_DIR = Path("data/raw")
SAVED_FORMATS = ("pdf", "html", "zip")  # docx, xlsx are listed but not downloaded
MIN_TEXT_CHARS_PER_PAGE = 20  # same threshold as the source survey
MAX_ZIP_UNCOMPRESSED = (
    200 * 1024 * 1024
)  # D-21: skip any ZIP that would expand past this


class Client(Protocol):
    def get_page(self, url: str) -> bytes: ...  # cached HTML
    def get_bytes(self, url: str) -> bytes: ...  # uncached file download


class Candidate(BaseModel):
    """One file an adapter found. `format` is the URL's extension, or "html"."""

    url: str
    landing_url: str
    issuer_org: str
    title_ja: str
    doc_type: DocType
    notice_date: date | None
    format: str
    bundle_id: str
    bundle_title: str
    license_note: str
    license_class: LicenseClass
    wto_covered: bool | None = None
    has_english_summary: bool | None = None


# Checked in order, first match wins. Answers and results first, since their titles
# often repeat the name of the document they answer (e.g. 仕様書 ... に対する回答).
DOC_TYPE_CUES: list[tuple[str, DocType]] = [
    ("回答", "qa"),  # answers to questions or to an opinion call
    ("質疑応答書", "forms"),  # the blank form for asking questions
    ("質疑応答", "qa"),
    ("結果", "result"),  # evaluation or award results
    ("開札録", "result"),  # record of the bid opening, with the bid amounts
    ("評価基準", "evaluation_criteria"),
    ("審査基準", "evaluation_criteria"),
    ("選定基準", "evaluation_criteria"),
    ("評価項目", "evaluation_criteria"),  # 評価項目及び配点 = items and points
    ("契約書", "draft_contract"),
    ("仕様書", "spec"),
    # Hokkaido calls its consignment spec 業務処理要領 [verify], see decisions.md
    ("業務処理要領", "spec"),
    ("落札者決定基準", "evaluation_criteria"),  # Hokkaido: how the winner is chosen
    ("申告調書", "forms"),  # Koriyama: a declaration the bidder fills in
    ("施行実績調書", "forms"),  # Koriyama: past-performance record the bidder fills in
    ("企画提案指示書", "bid_instructions"),  # Hokkaido: instructions for the proposal
    # Forms before instructions: "実施要領（第1号様式-質問票）" is a form
    # attached to the 要領, not the 要領 itself.
    ("記載要領", "bid_instructions"),  # how to fill in a form, e.g. 申請書記載要領
    ("設置要領", "other"),  # rules for setting up the evaluation committee
    ("様式", "forms"),
    ("申込書", "forms"),
    ("申請書", "forms"),
    ("誓約書", "forms"),
    ("質問書", "forms"),
    ("質問票", "forms"),
    ("要領", "bid_instructions"),
    ("説明書", "bid_instructions"),
    ("要項", "bid_instructions"),
    ("公告", "notice"),
    ("公募文", "notice"),  # Asahikawa: the text of the public call
    ("公示", "notice"),
]


# Title words that mark an IT or system tender, for the manifest's is_it (D-27).
# Stricter than the adapters' ordering cues: 運用, 保守 and 構築 also match building
# and equipment maintenance.
STRICT_IT_CUES = ("システム", "クラウド", "ソフトウェア", "データ", "開発")


def is_it_title(*titles: str) -> bool:
    return any(cue in t for t in titles for cue in STRICT_IT_CUES)


def classify_doc_type(title: str) -> DocType:
    for cue, doc_type in DOC_TYPE_CUES:
        if cue in title:
            return doc_type
    return "other"


# A status tag in front of a page title: "【審査結果を掲載しました】", "(終了)".
_STATUS_PREFIX = re.compile(r"^\s*[【［\[(（][^】］\])）]*[】］\])）]\s*")
# Titles of pages that only announce a result: "...の結果について", "...結果の公表".
_RESULT_PAGE = re.compile(r"結果(の公表)?(について)?$")


def classify_page(title: str, has_pdf_notice: bool) -> DocType:
    """doc_type of a saved tender page (D-20), from its title.

    A status tag like 【審査結果掲載】 only says the page was updated; the page is
    still the tender page, so the tag is ignored.
    """
    title = _STATUS_PREFIX.sub("", title).strip()
    if _RESULT_PAGE.search(title):
        return "result"
    if "回答" in title:
        return "qa"
    return "tender_page" if has_pdf_notice else "notice"


# "（PDF形式486キロバイト）", "(PDF 182KB)" or "[PDFファイル／193KB]" at the end.
_FILE_INFO_SUFFIX = re.compile(
    r"\s*[（(\[［][^（()）\[\]［］]*(?:PDF|Excel|Word|ZIP|形式|ファイル)"
    r"[^（()）\[\]［］]*[）)\]］]\s*$"
)
# "1." or a bare "1" before the title, but not the start of "2026年度" or "20年".
_LIST_NUMBER_PREFIX = re.compile(r"^\d{1,2}[.．]?\s*(?![\d年月日度])")


def clean_link_text(text: str) -> str:
    """Drop a list number and the file-size note.

    "1.仕様書（PDF形式486キロバイト）" -> "仕様書"
    """
    text = _FILE_INFO_SUFFIX.sub("", text.strip())
    return _LIST_NUMBER_PREFIX.sub("", text).strip()


_GREGORIAN_IN_PARENS = re.compile(r"（(\d{4})年）(\d{1,2})月(\d{1,2})日")


def parse_notice_date(text: str) -> date | None:
    """First date like "令和8年（2026年）2月13日", read from the Gregorian part."""
    m = _GREGORIAN_IN_PARENS.search(text)
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def is_locked(content: bytes) -> bool:
    """True for a PDF that needs an open password (the empty one doesn't work).
    Its text can't be read, so it is useless to the pipeline and is skipped."""
    import pymupdf  # D-13; a runtime dependency since D-28

    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except RuntimeError:  # FileDataError: broken, not locked; page_info will say
        return False
    with doc:
        return bool(doc.needs_pass) and not doc.authenticate("")


def page_info(path: Path) -> tuple[int, TextLayer]:
    """Page count and text layer ("full" | "partial" | "none"), via PyMuPDF."""
    import pymupdf  # D-13; a runtime dependency since D-28

    with pymupdf.open(path) as doc:
        with_text = sum(
            1
            for page in doc
            if len("".join(str(page.get_text()).split())) >= MIN_TEXT_CHARS_PER_PAGE
        )
        pages = doc.page_count
    if with_text == pages:
        return pages, "full"
    return pages, ("none" if with_text == 0 else "partial")


def it_and_spec_first(
    candidates: list[Candidate], it_cues: tuple[str, ...]
) -> list[Candidate]:
    """Stable sort: IT bundles first (a cue in the bundle title), then bundles with a
    spec PDF, otherwise the adapter's page order."""
    with_spec = {
        c.bundle_id for c in candidates if c.doc_type == "spec" and c.format == "pdf"
    }

    def key(c: Candidate) -> tuple[bool, bool]:
        is_it = any(cue in c.bundle_title for cue in it_cues)
        return (not is_it, c.bundle_id not in with_spec)

    return sorted(candidates, key=key)


@dataclass
class Plan:
    """What a run will do, bundle by bundle. Built the same way for --dry-run."""

    take: list[list[Candidate]] = field(default_factory=list)
    later: list[list[Candidate]] = field(default_factory=list)  # over --limit
    known_urls: dict[str, str] = field(default_factory=dict)  # url -> doc_id

    def is_new(self, c: Candidate) -> bool:
        return c.format in SAVED_FORMATS and c.url not in self.known_urls


def group_bundles(candidates: list[Candidate]) -> list[list[Candidate]]:
    """Group by bundle_id, keeping the adapter's order (its priority)."""
    bundles: dict[str, list[Candidate]] = {}
    for c in candidates:
        bundles.setdefault(c.bundle_id, []).append(c)
    return list(bundles.values())


def make_plan(
    candidates: list[Candidate],
    rows: list[ManifestRow],
    limit: int,
    max_bundles: int | None = None,
) -> Plan:
    """Take whole bundles in order until one would go over `limit` new files, or
    `max_bundles` bundles with something new are taken."""
    plan = Plan(known_urls={r.url: r.doc_id for r in rows})
    budget = limit
    taken_new = 0
    for bundle in group_bundles(candidates):
        new = sum(plan.is_new(c) for c in bundle)
        full = max_bundles is not None and new and taken_new >= max_bundles
        if plan.later or new > budget or full:
            plan.later.append(bundle)
        else:
            plan.take.append(bundle)
            budget -= new
            taken_new += bool(new)
    return plan


def run(
    source: str,
    candidates: list[Candidate],
    client: Client,
    limit: int,
    dry_run: bool,
    log: Callable[[str], None] = print,
    documents_path: Path = DOCUMENTS_PATH,
    bundles_path: Path = BUNDLES_PATH,
    raw_dir: Path = RAW_DIR,
    max_bundles: int | None = None,
) -> Plan:
    rows = read_rows(documents_path)
    plan = make_plan(candidates, rows, limit, max_bundles)
    _log_plan(plan, log)
    if dry_run:
        return plan

    store = _Store(source, raw_dir, documents_path, {r.doc_id for r in rows}, log)
    bundles = read_bundles(bundles_path)
    for bundle in plan.take:
        for c in bundle:
            if c.format not in SAVED_FORMATS:
                continue
            if c.url in plan.known_urls:
                # A known ZIP's PDFs joined their bundle when it was first fetched.
                bundle_ids = [] if c.format == "zip" else [plan.known_urls[c.url]]
            else:
                bundle_ids = _download(c, client, store, plan)
            for doc_id in bundle_ids:
                _add_to_bundle(bundles, c, doc_id)
        write_bundles(bundles, bundles_path)  # after each bundle: a crash loses little
    return plan


@dataclass
class _Store:
    """Where and how files and rows are written during one run."""

    source: str
    raw_dir: Path
    documents_path: Path
    doc_ids: set[str]
    log: Callable[[str], None]

    def save(self, content: bytes, c: Candidate, **row_fields: object) -> str:
        """Write the file and its manifest row unless the bytes are already known."""
        doc_id = hashlib.sha256(content).hexdigest()
        if doc_id in self.doc_ids:
            self.log(
                f"  same bytes already in manifest: {row_fields.get('url', c.url)}"
            )
            return doc_id
        fmt = str(row_fields.get("format", c.format))
        path = self.raw_dir / self.source / f"{doc_id}.{fmt}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        pages, text_layer = page_info(path) if fmt == "pdf" else (None, None)
        row = ManifestRow.model_validate(
            {
                **c.model_dump(include=set(ManifestRow.model_fields)),
                "doc_id": doc_id,
                "source": self.source,
                "jetro_ref": None,
                "is_it": is_it_title(c.title_ja, c.bundle_title),
                "pages": pages,
                "text_layer": text_layer,
                "fetched_at": datetime.now(UTC).replace(microsecond=0),
                "path": path.as_posix(),
                **row_fields,
            }
        )
        append_row(row, self.documents_path)
        self.doc_ids.add(doc_id)
        self.log(f"  saved {row.doc_type:<19} {row.title_ja[:50]}")
        return doc_id


def _download(c: Candidate, client: Client, store: _Store, plan: Plan) -> list[str]:
    """Fetch one candidate. Returns the doc_ids that belong in its bundle."""
    content = client.get_page(c.url) if c.format == "html" else client.get_bytes(c.url)
    if c.format == "pdf" and not content.startswith(b"%PDF"):
        store.log(f"  skip, not a PDF: {c.url}")
        return []
    if c.format == "pdf" and is_locked(content):
        store.log(f"  skip, PDF needs a password: {c.url}")
        return []
    doc_id = store.save(content, c)
    plan.known_urls[c.url] = doc_id
    if c.format != "zip":
        return [doc_id]
    # The ZIP keeps its own row for provenance but stays out of the bundle; the
    # PDFs inside it go in instead.
    pdfs = extract_pdfs(content, store.log)
    return [
        store.save(
            data,
            c,
            url=f"{c.url}#{name}",
            title_ja=PurePosixPath(name).stem,
            doc_type=classify_doc_type(PurePosixPath(name).stem),
            format="pdf",
            extracted_from=doc_id,
        )
        for name, data in pdfs
    ]


def extract_pdfs(content: bytes, log: Callable[[str], None]) -> list[tuple[str, bytes]]:
    """(member name, bytes) for every PDF in a ZIP, read in memory (D-21).

    Nothing is extracted to disk under its member name, so a zip-slip path can't
    write outside data/raw/. Such paths are still skipped as suspicious. A ZIP whose
    members would expand past MAX_ZIP_UNCOMPRESSED is skipped whole.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        log("  skip, not a valid ZIP")
        return []
    with archive:
        members = [i for i in archive.infolist() if not i.is_dir()]
        if sum(i.file_size for i in members) > MAX_ZIP_UNCOMPRESSED:
            log("  skip ZIP: over the uncompressed size limit")
            return []
        pdfs: list[tuple[str, bytes]] = []
        for info in members:
            name = zip_member_name(info)
            path = PurePosixPath(name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                log(f"  skip ZIP member with unsafe path: {name}")
            elif info.flag_bits & 0x1:
                log(f"  skip encrypted ZIP member: {name}")
            elif path.suffix.lower() == ".pdf":
                data = archive.read(info)  # zipfile stops at the declared size
                if not data.startswith(b"%PDF"):
                    continue
                if is_locked(data):
                    log(f"  skip ZIP member that needs a password: {name}")
                else:
                    pdfs.append((name, data))
        return pdfs


def zip_member_name(info: zipfile.ZipInfo) -> str:
    """Member name, fixing Japanese names stored in CP932 without the UTF-8 flag.

    zipfile decodes such names as CP437, which turns Japanese into mojibake.
    Re-encode to the raw bytes, then try UTF-8 (some tools omit the flag) and CP932.
    """
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437")
    for encoding in ("utf-8", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return info.filename


def _add_to_bundle(bundles: dict[str, BundleRow], c: Candidate, doc_id: str) -> None:
    bundle = bundles.setdefault(
        c.bundle_id,
        BundleRow(
            bundle_id=c.bundle_id,
            issuer_org=c.issuer_org,
            title_ja=c.bundle_title,
            doc_ids=[],
        ),
    )
    if doc_id not in bundle.doc_ids:
        bundle.doc_ids.append(doc_id)


def _log_plan(plan: Plan, log: Callable[[str], None]) -> None:
    def describe(c: Candidate) -> str:
        if c.format not in SAVED_FORMATS:
            status = f"skip .{c.format}"
        elif c.url in plan.known_urls:
            status = "in manifest"
        else:
            status = "new"
        return f"    [{status:<11}] {c.doc_type:<19} {c.title_ja[:60]}"

    for label, bundles in (("take", plan.take), ("over limit", plan.later)):
        for bundle in bundles:
            log(f"{label}: {bundle[0].bundle_id}  {bundle[0].bundle_title[:60]}")
            for c in bundle:
                log(describe(c))
    everything = [c for bundle in plan.take + plan.later for c in bundle]
    taken = [c for bundle in plan.take for c in bundle]
    skipped = sum(c.format not in SAVED_FORMATS for c in everything)
    new_taken = sum(plan.is_new(c) for c in taken)
    log(
        f"\nfound {len(plan.take) + len(plan.later)} bundles, {len(everything)} files "
        f"({skipped} not pdf/html/zip, skipped); "
        f"new files: {sum(plan.is_new(c) for c in everything)}. "
        f"This run takes {len(plan.take)} bundles, {new_taken} new files."
    )
