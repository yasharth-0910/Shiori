# ruff: noqa: E501
"""Sidecar tests: a real loopback server on a free port, an invented PDF (pymupdf's
built-in Japanese font) and a fake list extractor. No llama-server, no network beyond
127.0.0.1."""

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pymupdf
import pytest
import uvicorn
from shiori_core.extract.rules import Extracted

from sidecar.server import FIELD_IDS, bind_loopback, create_app

TOKEN = "test-token"
LINES = [
    "入札公告",
    "1 競争入札に参加する者に必要な資格",
    "(1) 指名停止を受けている期間中の者でないこと。",
    "2 入札書の提出期限 令和８年10月15日13時30分",
]
FIXTURE_KEYS = {"doc_id", "pdf", "fields", "sentences"}  # app/public/fixture.json
FIELD_KEYS = {"field", "status", "value_en", "value_ja", "normalized", "items", "citations", "checks"}


def make_pdf(path: Path, lines: list[str] = LINES) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    for n, text in enumerate(lines):
        page.insert_text((72, 100 + 24 * n), text, fontname="japan", fontsize=12)
    doc.save(path)
    return path


def fake_lists(doc_type, sentences):
    s = next(s for s in sentences if "指名停止" in s.text_orig)
    item = {
        "kind": "suspension",
        "polarity": "requirement",
        "text_ja": "指名停止を受けている期間中の者でないこと。",
        "citations": [s.id],
    }
    return {
        "eligibility": Extracted(
            field="eligibility",
            value_ja=item["text_ja"],
            normalized={"items": [item]},
            citations=[s.id],
        )
    }


class Server:
    def __init__(self, app):
        self.sock = bind_loopback()
        self.port = self.sock.getsockname()[1]
        self.server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [self.sock]}
        )

    def __enter__(self):
        self.thread.start()
        while not self.server.started:
            time.sleep(0.01)
        return self

    def __exit__(self, *a):
        self.server.should_exit = True
        self.thread.join(5)

    def call(self, method, path, body=None, token: str | None = TOKEN):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            json.dumps(body).encode() if body is not None else None,
            headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)


def wait_for(srv, doc_id, stage):
    for _ in range(500):
        got = srv.call("GET", f"/documents/{doc_id}/status")[1]
        if got["stage"] == stage:
            return got
        time.sleep(0.01)
    raise AssertionError(f"never reached {stage}, last {got}")


def test_every_request_without_the_token_gets_401(tmp_path):
    with Server(create_app(TOKEN)) as srv:
        for method, path, body in [
            ("POST", "/documents", {"path": "x.pdf"}),
            ("GET", "/documents/abc/status", None),
            ("GET", "/documents/abc/fields", None),
            ("GET", "/nothing-here", None),
            ("GET", "/docs", None),
        ]:
            assert srv.call(method, path, body, token=None)[0] == 401
            assert srv.call(method, path, body, token="wrong")[0] == 401


def test_pdf_through_every_stage_to_fields(tmp_path):
    pdf = make_pdf(tmp_path / "invented.pdf")
    release = {"retrieve": threading.Event(), "extract": threading.Event()}

    def hold(stage, fn):  # block inside a stage so polling can see it
        def run(doc_type, sentences):
            release[stage].wait(5)
            return fn(doc_type, sentences)

        return run

    from shiori_core.extract import rules

    app = create_app(
        TOKEN, hold("extract", fake_lists), hold("retrieve", rules.extract)
    )
    with Server(app) as srv:
        code, got = srv.call("POST", "/documents", {"path": str(pdf)})
        assert code == 200
        doc_id = got["doc_id"]
        seen = [wait_for(srv, doc_id, "retrieve")["stage"]]
        assert srv.call("GET", f"/documents/{doc_id}/fields")[0] == 409  # not ready
        release["retrieve"].set()
        seen.append(wait_for(srv, doc_id, "extract")["stage"])
        release["extract"].set()
        done = wait_for(srv, doc_id, "done")
        assert seen == ["retrieve", "extract"]
        assert done["pages"] == 1 and done["error"] is None
        assert app.state.worker.jobs[doc_id].history == [
            "queued", "ingest", "segment", "retrieve", "extract", "verify", "done",
        ]  # fmt: skip

        code, fields = srv.call("GET", f"/documents/{doc_id}/fields")
        assert code == 200
        assert set(fields) == FIXTURE_KEYS
        assert fields["pdf"] == "invented.pdf"  # base name, never the path
        assert [f["field"] for f in fields["fields"]] == list(FIELD_IDS)
        assert all(set(f) == FIELD_KEYS for f in fields["fields"])
        elig = next(f for f in fields["fields"] if f["field"] == "eligibility")
        assert elig["status"] == "present"
        item = elig["items"][0]
        assert item["polarity"] == "requirement" and item["kind"] == "suspension"
        assert "datetime" not in item  # only when the item has one
        checks = {c["name"]: c["passed"] for c in elig["checks"]}
        assert checks["schema_valid"] and checks["citations_exist"]
        assert checks["value_in_citation"] and checks["values_roundtrip"]
        sid = elig["citations"][0]
        assert fields["sentences"][sid]["page"] == 1
        assert fields["sentences"][sid]["boxes"][0]["page"] == 1
        # a field nobody found is absent, with no checks
        title = next(f for f in fields["fields"] if f["field"] == "title")
        assert title["status"] == "absent" and title["checks"] == []
        assert title["normalized"] is None and isinstance(elig["normalized"], dict)  # the stored value, as written

        # the same bytes again: same id, no second run
        assert srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"] == doc_id
        assert len(app.state.worker.jobs) == 1


def test_a_check_that_fails_is_stored_as_failed(tmp_path):
    pdf = make_pdf(tmp_path / "invented.pdf")

    def bad(doc_type, sentences):  # cites a sentence that says nothing of the value
        s = sentences[0]
        item = {
            "kind": "other",
            "polarity": "requirement",
            "text_ja": "暴力団",
            "citations": [s.id],
        }
        return {"eligibility": Extracted(field="eligibility", value_ja="暴力団", normalized={"items": [item]}, citations=[s.id])}  # fmt: skip

    with Server(create_app(TOKEN, bad)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        elig = next(f for f in srv.call("GET", f"/documents/{doc_id}/fields")[1]["fields"] if f["field"] == "eligibility")  # fmt: skip
        assert {c["name"]: c["passed"] for c in elig["checks"]}[
            "value_in_citation"
        ] is False


def test_bad_input_and_failures(tmp_path):
    notpdf = tmp_path / "a.txt"
    notpdf.write_text("x")
    broken = tmp_path / "broken.pdf"
    broken.write_text("not a pdf")
    with Server(create_app(TOKEN)) as srv:
        assert srv.call("POST", "/documents", {"path": str(notpdf)})[0] == 400
        assert (
            srv.call("POST", "/documents", {"path": str(tmp_path / "none.pdf")})[0]
            == 400
        )
        pdf = make_pdf(tmp_path / "ok.pdf")
        assert (
            srv.call("POST", "/documents", {"path": str(pdf), "doc_type": "zzz"})[0]
            == 400
        )
        assert srv.call("GET", "/documents/nope/status")[0] == 404
        # a file that is not a PDF fails the job; the server keeps going and tells the type only
        doc_id = srv.call("POST", "/documents", {"path": str(broken)})[1]["doc_id"]
        got = wait_for(srv, doc_id, "failed")
        assert got["error"] and str(tmp_path) not in json.dumps(got)
        ok_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, ok_id, "done")


def test_binds_loopback_only():
    sock = bind_loopback()
    try:
        assert sock.getsockname()[0] == "127.0.0.1"
    finally:
        sock.close()


@pytest.mark.parametrize(
    "arg", ["http://0.0.0.0:8792", "http://example.com:8792", "https://127.0.0.1:1"]
)
def test_main_refuses_a_llama_url_that_is_not_loopback_http(arg, monkeypatch):
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["sidecar", "--llama-url", arg])
    with pytest.raises(SystemExit):
        runpy.run_module("sidecar", run_name="__main__")


def _start_sidecar():
    import subprocess
    import sys

    root = Path(__file__).resolve().parent.parent
    p = subprocess.Popen(
        [sys.executable, "-m", "sidecar"], cwd=root, text=True,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )  # fmt: skip
    assert p.stdout and json.loads(p.stdout.readline())["port"]
    return p


def test_exits_cleanly_when_the_parent_closes_stdin():
    p = _start_sidecar()
    assert p.stdin
    p.stdin.close()
    assert p.wait(10) == 0
    assert p.stderr and "Traceback" not in p.stderr.read()


@pytest.mark.parametrize("name", ["SIGINT", "SIGTERM"])
def test_exits_cleanly_on_a_signal(name):
    import signal

    p = _start_sidecar()
    time.sleep(1)  # let uvicorn start serving
    p.send_signal(getattr(signal, name))
    assert p.wait(10) == 0
    assert p.stderr and "Traceback" not in p.stderr.read()


def test_status_carries_a_detail_while_the_model_stage_runs(tmp_path):
    from sidecar import server

    pdf = make_pdf(tmp_path / "invented.pdf")
    go = threading.Event()

    def slow_lists(doc_type, sentences):
        server.report("eligibility (1 of 3)")
        go.wait(5)
        return {}

    with Server(create_app(TOKEN, slow_lists)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        for _ in range(500):
            got = srv.call("GET", f"/documents/{doc_id}/status")[1]
            if got["detail"]:
                break
            time.sleep(0.01)
        assert (got["stage"], got["detail"]) == ("extract", "eligibility (1 of 3)")
        go.set()
        done = wait_for(srv, doc_id, "done")
        assert done["detail"] is None  # a new stage clears it


def test_extract_with_progress_reports_each_field(monkeypatch):
    from shiori_core.models import Sentence
    from shiori_core.normalize import normalize

    from sidecar import __main__ as m

    seen = []
    monkeypatch.setattr(m, "report", seen.append)

    class FakeClient:
        def complete(self, system, user, schema, max_out):
            return '{"items": []}'

    def sent(i, t, titles):
        norm, mp = normalize(t)
        return Sentence(id=i, page=0, section_path=[], section_titles=titles, text_orig=t, text_norm=norm, norm_to_orig=mp, boxes=[])  # fmt: skip

    ss = [
        sent("h_s1", "競争参加資格", ["競争参加資格"]),
        sent("h_s2", "入札書の受領期限　令和８年10月21日", ["入札書の受領期限"]),
    ]
    m.extract_with_progress(FakeClient(), "notice", ss)  # type: ignore[arg-type]
    assert seen[0] == "eligibility (1 of 3)" and all(d.endswith(" of 3)") for d in seen)


def test_translate_endpoint_without_a_model_is_503(tmp_path):
    pdf = make_pdf(tmp_path / "invented.pdf")
    with Server(create_app(TOKEN, fake_lists)) as srv:  # no translator: no llama-server
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        code, body = srv.call(
            "POST", f"/documents/{doc_id}/translate", {"ids": ["p1_s3"]}
        )
        assert code == 503 and "No model" in body["detail"]
        assert (
            srv.call("POST", f"/documents/{doc_id}/translate", {"ids": []}, token=None)[
                0
            ]
            == 401
        )


# --- background translation queue (D-88) -------------------------------------------------------


def cite_all(doc_type, sentences):
    """A fake extractor: one eligibility field citing every sentence, in order."""
    items = [{"kind": "other", "polarity": "requirement", "text_ja": s.text_orig, "citations": [s.id]} for s in sentences]  # fmt: skip
    ids = [s.id for s in sentences]
    return {"eligibility": Extracted(field="eligibility", value_ja="\n".join(s.text_orig for s in sentences), normalized={"items": items}, citations=ids)}  # fmt: skip


class Recorder:
    """A translator that records every call and can be held, one sentence at a time."""

    def __init__(self, hold: bool = False):
        from shiori_core.translate import Translation

        self.Translation = Translation
        self.calls: list[str] = []
        self.gate = threading.Semaphore(0)
        self.hold = hold
        self.started = threading.Event()

    def __call__(self, text, abbreviations, names):
        self.calls.append(text)
        self.started.set()
        if self.hold:
            self.gate.acquire(timeout=10)
        return self.Translation(en="EN " + text, numbers_match=True)


def ask(srv, doc_id, ids=()):
    return srv.call("POST", f"/documents/{doc_id}/translate", {"ids": list(ids)})


def until(fn, what="condition"):
    for _ in range(1000):
        got = fn()
        if got:
            return got
        time.sleep(0.01)
    raise AssertionError(f"never: {what}")


def test_the_queue_translates_every_cited_sentence_after_the_fields_are_ready(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    rec = Recorder()
    with Server(create_app(TOKEN, cite_all, translator=rec)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        got = until(
            lambda: (g := ask(srv, doc_id)[1])["done"] == g["total"] and g,
            "queue empty",
        )
        assert got["total"] == 4 and got["failed"] == []
        assert set(got["items"]) == {"p1_s1", "p1_s2", "p1_s3", "p1_s4"}
        assert got["items"]["p1_s3"] == {"en": "EN (1) 指名停止を受けている期間中の者でないこと。", "numbers_match": True, "protected_lost": False}  # fmt: skip
        assert len(rec.calls) == 4 and len(set(rec.calls)) == 4  # no sentence twice
        ask(
            srv, doc_id, ["p1_s1", "p1_s2"]
        )  # opening a field later asks for nothing again
        assert len(rec.calls) == 4


def test_the_fields_are_ready_before_translation_is_done(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    rec = Recorder(hold=True)
    with Server(create_app(TOKEN, cite_all, translator=rec)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        assert rec.started.wait(5)  # the first translation is running, held
        code, fields = srv.call("GET", f"/documents/{doc_id}/fields")
        assert code == 200 and fields["fields"]  # the Workspace can open
        got = ask(srv, doc_id)[1]
        assert (
            got["done"] == 0 and got["total"] == 4
        )  # nothing ready yet; counts are there
        for _ in range(4):
            rec.gate.release()
        until(lambda: ask(srv, doc_id)[1]["done"] == 4, "all done")


def test_opening_a_field_moves_its_sentences_to_the_front_without_duplicates(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    rec = Recorder(hold=True)
    with Server(create_app(TOKEN, cite_all, translator=rec)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        assert rec.started.wait(5)  # p1_s1 is in flight
        for _ in range(3):  # asking again and again, including for the one in flight
            ask(srv, doc_id, ["p1_s4", "p1_s3", "p1_s1"])
        for _ in range(4):
            rec.gate.release()
        until(lambda: ask(srv, doc_id)[1]["done"] == 4, "all done")
    order = [
        next(i for i, line in enumerate(LINES) if line in c or c in line)
        for c in rec.calls
    ]
    assert order == [
        0,
        3,
        2,
        1,
    ]  # in flight first, then the opened field's ids in the order asked, then the rest
    assert len(rec.calls) == 4  # no duplicate request


def test_without_a_model_nothing_is_queued(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    app = create_app(TOKEN, cite_all)  # no translator
    with Server(app) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        assert ask(srv, doc_id)[0] == 503
    assert app.state.queues is None


def test_a_new_document_cancels_the_running_queue_and_opening_the_old_one_restarts_it(
    tmp_path,
):
    a = make_pdf(tmp_path / "a.pdf")
    b = make_pdf(
        tmp_path / "b.pdf", ["別の入札公告", "(1) 別の資格を有する者であること。"]
    )
    rec = Recorder(hold=True)
    app = create_app(TOKEN, cite_all, translator=rec)
    with Server(app) as srv:
        a_id = srv.call("POST", "/documents", {"path": str(a)})[1]["doc_id"]
        wait_for(srv, a_id, "done")
        assert rec.started.wait(5)  # a's first sentence is in flight
        b_id = srv.call("POST", "/documents", {"path": str(b)})[1][
            "doc_id"
        ]  # another document is added
        assert app.state.worker.jobs[a_id].tq == "cancelled"
        assert app.state.worker.jobs[a_id].pending == []
        for _ in range(10):
            rec.gate.release()
        wait_for(srv, b_id, "done")
        until(lambda: ask(srv, b_id)[1]["done"] == 2, "b translated")
        ask(srv, a_id)  # a is opened again
        assert app.state.worker.jobs[a_id].tq in ("running", "complete")
        until(lambda: ask(srv, a_id)[1]["done"] == 4, "a translated")
    assert (
        len(rec.calls) == 6 and len(set(rec.calls)) == 6
    )  # 4 + 2 sentences, none twice, the in-flight one kept


def test_translation_never_overlaps_extraction(tmp_path):
    a = make_pdf(tmp_path / "a.pdf")
    b = make_pdf(
        tmp_path / "b.pdf", ["別の入札公告", "(1) 別の資格を有する者であること。"]
    )
    rec = Recorder(hold=True)
    extracting, release = threading.Event(), threading.Event()
    overlapped = []

    def slow_cite(doc_type, sentences):
        if any("別の" in s.text_orig for s in sentences):
            extracting.set()
            release.wait(10)
        return cite_all(doc_type, sentences)

    def watching(text, abbreviations, names):
        if extracting.is_set() and not release.is_set():
            overlapped.append(text)
        return rec(text, abbreviations, names)

    with Server(create_app(TOKEN, slow_cite, translator=watching)) as srv:
        a_id = srv.call("POST", "/documents", {"path": str(a)})[1]["doc_id"]
        wait_for(srv, a_id, "done")
        assert rec.started.wait(5)  # a's first sentence is in flight, held
        b_id = srv.call("POST", "/documents", {"path": str(b)})[1]["doc_id"]
        rec.gate.release()  # let the in-flight sentence finish; b's extraction takes the model next
        assert extracting.wait(5)
        time.sleep(
            0.5
        )  # a second translation could have started here, and must not have
        assert len(rec.calls) == 1
        release.set()
        for _ in range(10):
            rec.gate.release()
        wait_for(srv, b_id, "done")
    assert overlapped == []


def test_a_failed_translation_is_counted_and_the_queue_goes_on(tmp_path):
    from shiori_core.translate import Translation

    pdf = make_pdf(tmp_path / "a.pdf")

    def flaky(text, abbreviations, names):
        if "入札公告" == text:
            raise OSError("connection refused for " + text)
        return Translation(en="ok", numbers_match=True)

    with Server(create_app(TOKEN, cite_all, translator=flaky)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        got = until(
            lambda: (g := ask(srv, doc_id)[1])["done"] + len(g["failed"]) == 4 and g,
            "queue empty",
        )
        assert got["failed"] == ["p1_s1"] and got["done"] == 3
        assert "入札公告" not in json.dumps(got["failed"], ensure_ascii=False)


def test_opening_a_field_retries_its_failed_sentence(tmp_path):
    from shiori_core.translate import Translation

    pdf = make_pdf(tmp_path / "a.pdf")
    calls: list[str] = []

    def once_bad(text, abbreviations, names):
        calls.append(text)
        if text == "入札公告" and calls.count(text) == 1:
            raise OSError("down")
        return Translation(en="ok", numbers_match=True)

    with Server(create_app(TOKEN, cite_all, translator=once_bad)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        until(lambda: ask(srv, doc_id)[1]["failed"] == ["p1_s1"] or None, "failed")
        ask(srv, doc_id, ["p1_s1"])  # the field is opened: the failed sentence goes back in
        got = until(lambda: (g := ask(srv, doc_id)[1])["done"] == 4 and g, "retried")
        assert got["failed"] == []


def test_an_uncited_sentence_and_an_unknown_document_are_refused(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    with Server(create_app(TOKEN, fake_lists, translator=Recorder())) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        assert (
            ask(srv, doc_id, ["p1_s1"])[0] == 400
        )  # only p1_s3 is cited by fake_lists
        assert ask(srv, "nope", ["p1_s3"])[0] == 404
        assert (
            srv.call("POST", f"/documents/{doc_id}/translate", {"ids": []}, token=None)[
                0
            ]
            == 401
        )


def test_the_officer_name_is_passed_to_the_translator_for_its_cited_sentences(tmp_path):
    from shiori_core.translate import Translation

    pdf = make_pdf(
        tmp_path / "officer.pdf",
        [
            "入札公告",
            "支出負担行為担当官",
            "気象衛星センター所長 鈴木 花子",
            "無関係な文",
        ],
    )
    seen = []

    def base(doc_type, sentences):
        a, b = (
            next(s for s in sentences if "担当官" in s.text_orig),
            next(s for s in sentences if "鈴木" in s.text_orig),
        )
        return {"contracting_officer": Extracted(field="contracting_officer", value_ja=a.text_orig + "\n" + b.text_orig, normalized={"title": "支出負担行為担当官", "name": "鈴木 花子"}, citations=[a.id, b.id])}  # fmt: skip

    def translator(text, abbreviations, names):
        seen.append((text, names))
        return Translation(en="x", numbers_match=True)

    with Server(create_app(TOKEN, None, base, translator)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        until(lambda: ask(srv, doc_id)[1]["done"] == 2, "translated")
    assert sorted(n for _, n in seen) == [
        ["鈴木 花子"],
        ["鈴木 花子"],
    ]  # both cited sentences carry the structured name
