# ruff: noqa: E501
"""The sidecar: a loopback HTTP server that runs the core pipeline on one PDF at a time.

    POST /documents            {"path": ..., "doc_type": "notice"} -> {"doc_id": ...}
    GET  /documents/{id}/status -> {"doc_id", "stage", "pages", "error"}
    GET  /documents/{id}/fields -> the shape of app/public/fixture.json (app/src/types.ts)

Every request needs `Authorization: Bearer <token>`. The server binds 127.0.0.1 only
and makes no network request of its own. Nothing here logs document text or a file
path: logs carry event names, seconds, page counts and field counts (privacy.md).
"""

import hashlib
import hmac
import logging
import queue
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from shiori_core.checks import run_checks
from shiori_core.extract import rules
from shiori_core.extract.rules import Extracted
from shiori_core.fields import FIELD_IDS, SPECS, Status
from shiori_core.ingest import read_pages
from shiori_core.models import Sentence
from shiori_core.segment import segment

log = logging.getLogger("shiori.sidecar")

HOST = "127.0.0.1"
STAGES = (
    "queued",
    "ingest",
    "segment",
    "retrieve",
    "extract",
    "verify",
    "done",
    "failed",
)
DOC_TYPES = {t for s in SPECS for t in s.applies_to}

# (doc_type, Japanese sentences) -> {field: Extracted}. `rules.extract` and, when a
# llama-server is given, `llm.extract_lists` bound to its client.
Extractor = Callable[[str, list[Sentence]], dict[str, Extracted]]


# --- the response, matching app/src/types.ts ------------------------------------------------


class Box(BaseModel):
    page: int
    bbox: tuple[float, float, float, float]


class SentenceOut(BaseModel):
    page: int
    text_orig: str
    section_path: list[str]
    section_titles: list[str]
    boxes: list[Box]


class Check(BaseModel):
    name: str
    passed: bool


class Item(BaseModel):
    text_ja: str | None
    text_en: str | None
    citations: list[str]
    datetime: str | None = None  # only when the item has one (D-80)
    kind: str | None = None
    polarity: Literal["requirement", "disqualification"] | None = None


class Field(BaseModel):
    field: str
    status: Status
    value_en: str | None
    value_ja: str | None
    items: list[Item]
    citations: list[str]
    checks: list[Check]


class Fields(BaseModel):
    doc_id: str
    pdf: str  # the file's base name; the main process knows where it lives
    fields: list[Field]
    sentences: dict[str, SentenceOut]


class NewDocument(BaseModel):
    path: str
    doc_type: str = "notice"


def _item(raw: dict) -> Item:
    # text_ja is the sentence text of an eligibility item or the name of a required
    # document; deadlines have neither. Translation is a later stage: text_en stays null.
    extra = {
        k: raw[k] for k in ("datetime", "kind", "polarity") if raw.get(k) is not None
    }
    return Item(
        text_ja=raw.get("text_ja") or raw.get("name_ja"),
        text_en=None,
        citations=raw.get("citations", []),
        **extra,
    )


def build_fields(
    doc_id: str,
    filename: str,
    doc_type: str,
    sentences: list[Sentence],
    found: dict[str, Extracted],
) -> Fields:
    """One entry per v1 field: found and checked, or absent ("not found"). Checks are
    computed here, once, and stored; the app never recomputes them."""
    ja = {s.id: s for s in sentences if s.language == "ja"}
    out: list[Field] = []
    cited: set[str] = set()
    for fid in FIELD_IDS:
        x = found.get(fid)
        if x is None:
            out.append(Field(field=fid, status="absent", value_en=None, value_ja=None,
                             items=[], citations=[], checks=[], ))  # fmt: skip
            continue
        items = [_item(i) for i in (x.normalized.get("items") or [])] if x.status == "present" else []  # fmt: skip
        ids = list(
            dict.fromkeys([*x.citations, *(c for i in items for c in i.citations)])
        )
        cited.update(i for i in ids if i in ja)
        checks = [Check(name=n, passed=p) for n, p in run_checks(x, doc_type, ja)]
        out.append(Field(
            field=fid, status=cast(Status, x.status), value_en=None, value_ja=x.value_ja,
            items=items, citations=x.citations, checks=checks,
        ))  # fmt: skip
    sents = {
        i: SentenceOut(
            page=ja[i].page,
            text_orig=ja[i].text_orig,
            section_path=ja[i].section_path,
            section_titles=ja[i].section_titles,
            boxes=[Box(page=b.page, bbox=b.bbox) for b in ja[i].boxes],
        )
        for i in sorted(cited)
    }
    return Fields(doc_id=doc_id, pdf=filename, fields=out, sentences=sents)


# --- jobs ------------------------------------------------------------------------------------


@dataclass
class Job:
    doc_id: str
    path: Path
    doc_type: str
    stage: str = "queued"
    history: list[str] = field(
        default_factory=lambda: ["queued"]
    )  # every stage, in order
    pages: int | None = None
    error: str | None = None  # an exception type name, never a message
    result: Fields | None = None

    def go(self, stage: str) -> None:
        self.stage = stage
        self.history.append(stage)


class Worker:
    """One document at a time: a queue and one background thread."""

    def __init__(self, extractors: list[Extractor]) -> None:
        self.extractors = extractors
        self.jobs: dict[str, Job] = {}
        self._queue: queue.Queue[Job] = queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    def submit(self, path: Path, doc_type: str) -> Job:
        h = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        old = self.jobs.get(h)
        if old is not None and old.stage != "failed":
            return old  # same bytes: already done or on its way
        job = self.jobs[h] = Job(h, path, doc_type)
        self._queue.put(job)
        return job

    def _loop(self) -> None:
        while True:
            job = self._queue.get()
            t0 = time.monotonic()
            try:
                self._run(job)
            except Exception as e:  # noqa: BLE001  any failure ends this job, not the server
                job.error = type(e).__name__
                job.go("failed")
                log.warning("job_failed doc=%s error=%s", job.doc_id[:8], job.error)
            else:
                log.info(
                    "job_done doc=%s seconds=%.1f",
                    job.doc_id[:8],
                    time.monotonic() - t0,
                )

    def _run(self, job: Job) -> None:
        job.go("ingest")
        doc = read_pages(job.path)
        job.pages = len(doc.pages)
        log.info("ingested doc=%s pages=%d", job.doc_id[:8], job.pages)
        job.go("segment")
        doc.sentences = segment(doc.pages)
        sents = doc.sentences
        log.info("segmented doc=%s sentences=%d", job.doc_id[:8], len(sents))
        found: dict[str, Extracted] = {}
        for stage, extract in zip(
            ("retrieve", "extract"), self.extractors, strict=False
        ):
            job.go(stage)
            found |= extract(job.doc_type, sents)
        job.go("verify")
        job.result = build_fields(job.doc_id, doc.filename, job.doc_type, sents, found)
        log.info("verified doc=%s fields=%d", job.doc_id[:8], len(found))
        job.go("done")


# --- the app ---------------------------------------------------------------------------------


def create_app(
    token: str, lists: Extractor | None = None, base: Extractor = rules.extract
) -> FastAPI:
    """`base` answers what rules can (stage retrieve); `lists`, when given, is the model
    extractor for the list fields (stage extract). Both are injected so tests need no model."""
    worker = Worker([base, *([lists] if lists else [])])
    # no /docs, /redoc or /openapi.json: nothing to browse, and they would sit behind the token anyway
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.worker = worker
    want = f"Bearer {token}".encode()

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        got = request.headers.get("authorization", "").encode()
        if not hmac.compare_digest(got, want):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    def job_of(doc_id: str) -> Job:
        if doc_id not in worker.jobs:
            raise HTTPException(404, "unknown document")
        return worker.jobs[doc_id]

    @app.post("/documents")
    def post_document(body: NewDocument) -> dict:
        path = Path(body.path)
        if path.suffix.lower() != ".pdf" or not path.is_file():
            raise HTTPException(
                400, "not a readable pdf path"
            )  # the path is not echoed
        if body.doc_type not in DOC_TYPES:
            raise HTTPException(400, "unknown doc_type")
        return {"doc_id": worker.submit(path, body.doc_type).doc_id}

    @app.get("/documents/{doc_id}/status")
    def status(doc_id: str) -> dict:
        j = job_of(doc_id)
        return {
            "doc_id": j.doc_id,
            "stage": j.stage,
            "pages": j.pages,
            "error": j.error,
        }

    @app.get(
        "/documents/{doc_id}/fields",
        response_model=Fields,
        response_model_exclude_unset=True,
    )
    def fields(doc_id: str) -> Fields:
        j = job_of(doc_id)
        if j.result is None:
            raise HTTPException(409, f"not ready: {j.stage}")
        return j.result

    return app


def bind_loopback() -> socket.socket:
    """A listening socket on 127.0.0.1 and a free port the OS picks. uvicorn is handed
    this socket, so the port is known before the server starts."""
    s = socket.socket()
    s.bind((HOST, 0))
    s.listen()
    return s
