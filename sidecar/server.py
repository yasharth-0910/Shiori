# ruff: noqa: E501
"""The sidecar: a loopback HTTP server that runs the core pipeline on one PDF at a time.

    POST /documents            {"path": ..., "doc_type": "notice"} -> {"doc_id": ...}
    GET  /documents/{id}/status?since=N -> {"doc_id", "stage", "pages", "detail", "error",
                                            "seconds", "stage_elapsed", "sentences", "fields_total",
                                            "answered", "events", "cursor"} (D-90)
    POST /documents/{id}/cancel -> {"stage"}; the worker stops at the next stage or model call
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
from shiori_core.fields import BY_ID, FIELD_IDS, SPECS, Status
from shiori_core.ingest import read_pages
from shiori_core.models import Sentence
from shiori_core.segment import segment
from shiori_core.translate import Translation, find_abbreviations

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
    "cancelled",
)
MAX_EVENTS = 200  # the live stream keeps this many, newest last (D-90)
SHOWN_CHARS = 200  # a sentence or value in an event is cut to this
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
    normalized: (
        dict | None
    )  # the stored normalized value, as the extractor wrote it (a data shape only)
    items: list[Item]
    citations: list[str]
    checks: list[Check]


class Fields(BaseModel):
    doc_id: str
    pdf: str  # the file's base name; the main process knows where it lives
    fields: list[Field]
    sentences: dict[str, SentenceOut]


class TranslateRequest(BaseModel):
    ids: list[str]


# (sentence, the document's abbreviations, person names to keep) -> English and its checks
Translator = Callable[[str, dict[str, str], list[str]], Translation]


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
            out.append(Field(field=fid, status="absent", value_en=None, value_ja=None, normalized=None,
                             items=[], citations=[], checks=[], ))  # fmt: skip
            continue
        # a text field (title, issuer_org) has no normalized value: rules write {}, the schema wants null
        x = x.model_copy(update={"normalized": x.normalized or None}) if BY_ID[fid].model is None else x  # fmt: skip
        items = [_item(i) for i in ((x.normalized or {}).get("items") or [])] if x.status == "present" else []  # fmt: skip
        ids = list(
            dict.fromkeys([*x.citations, *(c for i in items for c in i.citations)])
        )
        cited.update(i for i in ids if i in ja)
        checks = [Check(name=n, passed=p) for n, p in run_checks(x, doc_type, ja)]
        out.append(Field(
            field=fid, status=cast(Status, x.status), value_en=None, value_ja=x.value_ja,
            normalized=x.normalized if x.status == "present" else None, items=items, citations=x.citations, checks=checks,
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
    detail: str | None = (
        None  # progress inside a stage, e.g. "eligibility (2 of 3)"; no document text
    )
    error: str | None = None  # an exception type name, never a message
    result: Fields | None = None
    abbreviations: dict[str, str] = field(
        default_factory=dict
    )  # 以下「X」という definitions in the document
    names: dict[str, list[str]] = field(
        default_factory=dict
    )  # sentence id -> person names kept in Japanese (D-87)
    translations: dict[str, dict] = field(
        default_factory=dict
    )  # sentence id -> {en, numbers_match, protected_lost}; memory only
    # The background translation queue (D-88). tq: idle, running, cancelled or complete.
    tq: str = "idle"
    pending: list[str] = field(
        default_factory=list
    )  # cited sentence ids still to do, next first
    inflight: str | None = None  # the sentence being translated right now
    failed: set[str] = field(default_factory=set)
    total: int = 0  # cited sentences
    # The live view (D-90). Memory only; event text is Japanese from the document, sent to the UI
    # through the status call and never logged.
    cancel: bool = (
        False  # asked to stop; checked between stages and before each model call
    )
    events: list[dict] = field(
        default_factory=list
    )  # capped at MAX_EVENTS, each with a number n
    n_events: int = 0
    seconds: dict[str, float] = field(
        default_factory=dict
    )  # measured, per finished stage
    t0: float = field(default_factory=time.monotonic)  # when the current stage began
    sentences: int | None = None  # Japanese sentences after segmentation
    answered: int = 0  # fields with an answer so far

    def go(self, stage: str) -> None:
        now = time.monotonic()
        if self.stage not in ("queued", "done", "failed", "cancelled"):
            self.seconds[self.stage] = round(now - self.t0, 1)
        self.t0 = now
        self.stage = stage
        self.detail = None
        self.history.append(stage)

    def emit(self, kind: str, **data: object) -> None:
        self.n_events += 1
        self.events.append({"n": self.n_events, "kind": kind, **data})
        if len(self.events) > MAX_EVENTS:
            del self.events[0]

    def check_cancel(self) -> None:
        if self.cancel:
            raise Cancelled


class Cancelled(Exception):
    """Raised between stages and before a model call when the user cancelled. Not a ValueError
    or OSError, so the extractor's own error handling does not swallow it."""


_running: Job | None = None  # the job the worker is on (one at a time), for `report`


def report(detail: str) -> None:
    """Say what the running job is doing inside its stage. Called by an extractor."""
    if _running is not None:
        _running.detail = detail


def emit_event(kind: str, **data: object) -> None:
    """Add an event to the running job's live stream. Called by an extractor wrapper."""
    if _running is not None:
        _running.emit(kind, **data)


def check_cancel() -> None:
    """Raise Cancelled when the running job was cancelled. Called before each model call."""
    if _running is not None:
        _running.check_cancel()


def _cut(text: str) -> str:
    return text if len(text) <= SHOWN_CHARS else text[:SHOWN_CHARS] + "…"


class Worker:
    """One document at a time: a queue and one background thread."""

    def __init__(self, extractors: list[Extractor]) -> None:
        self.extractors = extractors
        self.jobs: dict[str, Job] = {}
        self.model_lock = (
            threading.Lock()
        )  # one llama-server request at a time: extraction or translation
        self.outstanding = (
            0  # documents submitted and not finished; translation waits while > 0
        )
        self.on_new: Callable[[Job], None] | None = None  # a new document was added
        self.on_done: Callable[[Job], None] | None = (
            None  # a document's fields are ready
        )
        self._queue: queue.Queue[Job] = queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    def submit(self, path: Path, doc_type: str) -> Job:
        h = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        old = self.jobs.get(h)
        if old is not None and old.stage != "failed" and not old.cancel:
            return old  # same bytes: already done or on its way
        job = self.jobs[h] = Job(h, path, doc_type)
        self.outstanding += 1
        if self.on_new:
            self.on_new(job)
        self._queue.put(job)
        return job

    def _loop(self) -> None:
        while True:
            job = self._queue.get()
            t0 = time.monotonic()
            try:
                with self.model_lock:
                    self._run(job)
            except Cancelled:
                job.go("cancelled")
                log.info("job_cancelled doc=%s", job.doc_id[:8])
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
            finally:
                self.outstanding -= 1
            if job.stage == "done" and self.on_done:
                self.on_done(job)

    def _run(self, job: Job) -> None:
        global _running
        _running = job
        job.check_cancel()
        job.go("ingest")
        doc = read_pages(job.path)
        job.pages = len(doc.pages)
        log.info("ingested doc=%s pages=%d", job.doc_id[:8], job.pages)
        job.check_cancel()
        job.go("segment")
        doc.sentences = segment(doc.pages)
        sents = doc.sentences
        ja = {s.id: s for s in sents if s.language == "ja"}
        job.sentences = len(ja)
        job.abbreviations = find_abbreviations(s.text_norm for s in ja.values())
        log.info("segmented doc=%s sentences=%d", job.doc_id[:8], len(sents))
        found: dict[str, Extracted] = {}
        for stage, extract in zip(
            ("retrieve", "extract"), self.extractors, strict=False
        ):
            job.check_cancel()
            job.go(stage)
            got = extract(job.doc_type, sents)
            found |= got
            job.answered = len(found)
            for fid, x in got.items():
                first = ja.get(x.citations[0]) if x.citations else None
                job.emit("answer", field=fid, value_ja=_cut(x.value_ja), page=first.page if first else None)  # fmt: skip
        job.check_cancel()
        job.go("verify")
        job.result = build_fields(job.doc_id, doc.filename, job.doc_type, sents, found)
        for f in job.result.fields:
            if f.status == "absent":
                continue
            exact = next((c.passed for c in f.checks if c.name == "value_in_citation"), None)  # fmt: skip
            job.emit("check", field=f.field, exact=exact)
        log.info("verified doc=%s fields=%d", job.doc_id[:8], len(found))
        off = found.get(
            "contracting_officer"
        )  # the structured name, never guessed from text
        if off and off.normalized.get("name"):
            job.names = {sid: [off.normalized["name"]] for sid in off.citations}
        job.go("done")


# --- background translation (D-88) -----------------------------------------------------------


def cited_order(job: Job) -> list[str]:
    """The cited sentence ids in field order, each once."""
    assert job.result is not None
    ids = [
        i
        for f in job.result.fields
        for i in [*f.citations, *(c for it in f.items for c in it.citations)]
    ]
    return [i for i in dict.fromkeys(ids) if i in job.result.sentences]


class Translations:
    """One translation queue per document, run one sentence at a time by one thread, only
    while no extraction runs or waits (the Worker holds `model_lock` for a whole document, and
    `outstanding` stops this thread from taking the lock ahead of a document that is waiting).
    The queue starts when a document's fields are ready. Adding another document cancels the
    running queue; opening the cancelled document again restarts it from the front. Opening a
    field moves its untranslated sentences to the front. A sentence is never queued twice, and
    one already translated or in flight is never asked again. Memory only; events and counts
    are logged, never text."""

    def __init__(self, worker: Worker, translator: Translator) -> None:
        self.worker = worker
        self.translator = translator
        self.cond = threading.Condition()
        self.active: Job | None = None
        worker.on_new = self.cancel_for
        worker.on_done = self.start
        threading.Thread(target=self._loop, daemon=True).start()

    def _fill(self, job: Job) -> None:
        """Queue every cited sentence that has no English and is not in flight."""
        order = cited_order(job)
        job.total = len(order)
        job.failed.clear()
        job.pending = [
            i for i in order if i not in job.translations and i != job.inflight
        ]
        job.tq = "running" if job.pending or job.inflight else "complete"

    def start(self, job: Job) -> None:
        with self.cond:
            self._cancel_other(job)
            self._fill(job)
            self.active = job
            log.info("queue_started doc=%s queued=%d", job.doc_id[:8], len(job.pending))
            self.cond.notify()

    def _cancel_other(self, keep: Job | None) -> None:
        a = self.active
        if a is not None and a is not keep and a.tq == "running":
            a.tq = "cancelled"
            log.info(
                "queue_cancelled doc=%s remaining=%d", a.doc_id[:8], len(a.pending)
            )
            a.pending = []
        if a is not keep:
            self.active = None

    def cancel_for(self, new: Job) -> None:
        """A document was added: the running queue stops, and restarts when its document is opened."""
        with self.cond:
            self._cancel_other(new)

    def prioritize(self, job: Job, ids: list[str]) -> None:
        """The document or a field was opened: restart a cancelled queue, and move `ids` to the front."""
        with self.cond:
            if job.tq == "cancelled":
                self._cancel_other(job)
                self._fill(job)
                self.active = job
                log.info(
                    "queue_resumed doc=%s queued=%d", job.doc_id[:8], len(job.pending)
                )
            # A sentence that failed is asked again when its field is opened.
            again = [i for i in dict.fromkeys(ids) if i in job.failed]
            if again:
                job.failed.difference_update(again)
                job.pending = again + job.pending
                job.tq = "running"
                self._cancel_other(job)
                self.active = job
                log.info("queue_retry doc=%s retried=%d", job.doc_id[:8], len(again))
            front = [i for i in dict.fromkeys(ids) if i in job.pending]
            if front:
                job.pending = front + [i for i in job.pending if i not in front]
                log.info(
                    "queue_prioritized doc=%s moved=%d", job.doc_id[:8], len(front)
                )
            self.cond.notify()

    def counts(self, job: Job) -> dict:
        with self.cond:
            return {
                "items": dict(job.translations),
                "done": len(job.translations),
                "total": job.total or len(cited_order(job)),
                "failed": sorted(job.failed),
            }

    def _loop(self) -> None:
        w = self.worker
        while True:
            with self.cond:
                self.cond.wait_for(lambda: self.active is not None and bool(self.active.pending) and w.outstanding == 0, timeout=0.2)  # fmt: skip
            with w.model_lock:
                with self.cond:
                    job = self.active
                    if job is None or not job.pending or w.outstanding:
                        continue
                    sid = job.pending.pop(0)
                    job.inflight = sid
                    assert job.result is not None
                    text = job.result.sentences[sid].text_orig
                try:
                    res = self.translator(text, job.abbreviations, job.names.get(sid, [])).model_dump()  # fmt: skip
                except Exception as e:  # noqa: BLE001  the type is logged, never the text
                    res = None
                    log.warning("translate_failed doc=%s error=%s", job.doc_id[:8], type(e).__name__)  # fmt: skip
                with self.cond:
                    job.inflight = None
                    if res is None:
                        job.failed.add(sid)
                    else:
                        job.translations[sid] = res
                    if not job.pending and job.tq == "running":
                        job.tq = "complete"
                        log.info("queue_empty doc=%s done=%d failed=%d", job.doc_id[:8], len(job.translations), len(job.failed))  # fmt: skip
                    elif res is not None:
                        log.info("translated doc=%s done=%d total=%d", job.doc_id[:8], len(job.translations), job.total)  # fmt: skip


# --- the app ---------------------------------------------------------------------------------


def create_app(
    token: str,
    lists: Extractor | None = None,
    base: Extractor = rules.extract,
    translator: Translator | None = None,
) -> FastAPI:
    """`base` answers what rules can (stage retrieve); `lists`, when given, is the model
    extractor for the list fields (stage extract); `translator` is the sentence translator
    (only with a llama-server). All injected so tests need no model."""
    worker = Worker([base, *([lists] if lists else [])])
    # no /docs, /redoc or /openapi.json: nothing to browse, and they would sit behind the token anyway
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.worker = worker
    queues = Translations(worker, translator) if translator else None
    app.state.queues = queues
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
    def status(doc_id: str, since: int = 0) -> dict:
        """`since` is the cursor from the last call: only newer events come back."""
        j = job_of(doc_id)
        running = j.stage not in ("done", "failed", "cancelled")
        return {
            "doc_id": j.doc_id,
            "stage": j.stage,
            "pages": j.pages,
            "detail": j.detail,
            "error": j.error,
            "seconds": dict(j.seconds),
            "stage_elapsed": round(time.monotonic() - j.t0, 1) if running else None,
            "sentences": j.sentences,
            "fields_total": sum(j.doc_type in BY_ID[f].applies_to for f in FIELD_IDS),
            "answered": j.answered,
            "events": [e for e in list(j.events) if e["n"] > since],
            "cursor": j.n_events,
        }

    @app.post("/documents/{doc_id}/cancel")
    def cancel(doc_id: str) -> dict:
        """Ask the job to stop. It stops at the next stage or before the next model call; a
        page read or a model call already running finishes first. No effect once it is over."""
        j = job_of(doc_id)
        if j.stage not in ("done", "failed", "cancelled"):
            j.cancel = True
            log.info("cancel_asked doc=%s stage=%s", j.doc_id[:8], j.stage)
        return {"stage": j.stage}

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

    @app.post("/documents/{doc_id}/translate")
    def translate(doc_id: str, body: TranslateRequest) -> dict:
        """Opening a document or a field: `ids` go to the front of the queue (none asks for no
        change). Returns what is translated so far and the counts. Never waits for the model."""
        if queues is None:
            raise HTTPException(
                503, "No model is set up, so sentences cannot be translated."
            )
        j = job_of(doc_id)
        if j.result is None:
            raise HTTPException(409, f"not ready: {j.stage}")
        if any(i not in j.result.sentences for i in body.ids):
            raise HTTPException(400, "only cited sentences can be translated")
        queues.prioritize(j, body.ids)
        return queues.counts(j)

    return app


def bind_loopback() -> socket.socket:
    """A listening socket on 127.0.0.1 and a free port the OS picks. uvicorn is handed
    this socket, so the port is known before the server starts."""
    s = socket.socket()
    s.bind((HOST, 0))
    s.listen()
    return s
