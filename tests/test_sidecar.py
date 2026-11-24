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
FIELD_KEYS = {
    "field",
    "status",
    "value_en",
    "value_ja",
    "normalized",
    "items",
    "citations",
    "checks",
}


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
        assert title["normalized"] is None and isinstance(
            elig["normalized"], dict
        )  # the stored value, as written

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
    assert seen[0] == "eligibility (1 of 3)" and all(d.endswith(" of 3)") or d == "Other fields" for d in seen)  # fmt: skip


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
        ask(
            srv, doc_id, ["p1_s1"]
        )  # the field is opened: the failed sentence goes back in
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


def test_text_field_comes_back_with_null_normalized_and_a_passing_schema_check(
    tmp_path,
):
    # rules write {} for title and issuer_org; the schema wants null, so schema_valid used to fail
    pdf = make_pdf(tmp_path / "invented.pdf")

    def title_only(doc_type, sentences):
        s = next(s for s in sentences if "指名停止" in s.text_orig)
        return {
            "title": Extracted(
                field="title", value_ja="指名停止", normalized={}, citations=[s.id]
            )
        }

    with Server(create_app(TOKEN, None, title_only)) as srv:
        doc_id = srv.call(
            "POST", "/documents", {"path": str(pdf), "doc_type": "notice"}
        )[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        f = next(
            x
            for x in srv.call("GET", f"/documents/{doc_id}/fields")[1]["fields"]
            if x["field"] == "title"
        )
    assert f["status"] == "present" and f["normalized"] is None
    assert {"name": "schema_valid", "passed": True} in f["checks"]


# --- the live view: events, cursor, cancel (D-90) ---------------------------------------------


def events_of(srv, doc_id, since=0):
    got = srv.call("GET", f"/documents/{doc_id}/status?since={since}")[1]
    return got["events"], got["cursor"], got


def test_status_events_and_cursor(tmp_path):
    pdf = make_pdf(tmp_path / "invented.pdf")
    with Server(create_app(TOKEN, fake_lists)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        evs, cursor, got = events_of(srv, doc_id)
        assert [e["n"] for e in evs] == list(range(1, cursor + 1))
        ans = next(
            e for e in evs if e["kind"] == "answer" and e["field"] == "eligibility"
        )
        assert ans["value_ja"].startswith("指名停止") and ans["page"] == 1
        assert (
            ans["exact"] is True
        )  # the stored value_in_citation check, on the answer card itself
        assert {e["kind"] for e in evs} <= {
            "answer",
            "reading",
            "none",
        }  # no separate check events
        assert (
            len(
                [
                    e
                    for e in evs
                    if e["kind"] == "answer" and e["field"] == "eligibility"
                ]
            )
            == 1
        )  # one card per field
        assert not any(
            e["field"] == "title" for e in evs
        )  # an absent field has no card
        fields = srv.call("GET", f"/documents/{doc_id}/fields")[1]["fields"]
        for e in (
            e for e in evs if e["kind"] == "answer"
        ):  # the card says what the stored check says
            f = next(f for f in fields if f["field"] == e["field"])
            assert e["exact"] == next(
                (c["passed"] for c in f["checks"] if c["name"] == "value_in_citation"),
                None,
            )
        # measured per-step seconds and counts
        assert {"ingest", "segment", "retrieve", "extract"} <= set(got["seconds"])
        assert got["sentences"] and got["fields_total"] > 0
        assert got["answered"] >= 1 and got["stage_elapsed"] is None
        # the cursor: only newer events, none when nothing is new
        assert events_of(srv, doc_id, cursor)[0] == []
        assert [e["n"] for e in events_of(srv, doc_id, cursor - 1)[0]] == [cursor]


def test_events_are_capped_and_numbers_keep_counting():
    from sidecar.server import MAX_EVENTS, Job

    job = Job("x", Path("x.pdf"), "notice")
    for _ in range(MAX_EVENTS + 50):
        job.emit("check", field="title", exact=None)
    assert len(job.events) == MAX_EVENTS
    assert job.events[0]["n"] == 51 and job.events[-1]["n"] == MAX_EVENTS + 50


def test_cancel_stops_the_run_before_the_next_model_call(tmp_path):
    from sidecar import server

    pdf = make_pdf(tmp_path / "invented.pdf")
    in_call, go = threading.Event(), threading.Event()
    calls = []

    def lists(doc_type, sentences):
        calls.append(1)
        in_call.set()
        go.wait(5)
        server.check_cancel()  # what the model wrapper does before each call
        calls.append(2)  # must not be reached
        return {}

    app = create_app(TOKEN, lists)
    with Server(app) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        assert in_call.wait(5)
        assert srv.call("POST", f"/documents/{doc_id}/cancel")[1]["stage"] == "extract"
        go.set()
        done = wait_for(srv, doc_id, "cancelled")
        assert calls == [1] and done["error"] is None
        assert srv.call("GET", f"/documents/{doc_id}/fields")[0] == 409
        # the same file can be added again after a cancel, and runs to the end
        again = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        assert again == doc_id
        # a new job object: its flag is clear, so it runs to the end
        wait_for(srv, doc_id, "done")
        assert app.state.worker.jobs[doc_id].history[-1] == "done"


def test_cancel_before_the_run_starts_and_after_it_ends(tmp_path):
    from sidecar import server

    pdf = make_pdf(tmp_path / "invented.pdf")
    block = threading.Event()
    other = make_pdf(tmp_path / "other.pdf", LINES[:2])

    def slow(doc_type, sentences):
        block.wait(5)
        return {}

    with Server(create_app(TOKEN, slow)) as srv:
        first = srv.call("POST", "/documents", {"path": str(other)})[1]["doc_id"]
        wait_for(srv, first, "extract")
        queued = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        assert srv.call("POST", f"/documents/{queued}/cancel")[1]["stage"] == "queued"
        block.set()
        wait_for(srv, first, "done")
        assert wait_for(srv, queued, "cancelled")["pages"] is None  # never read
        assert (
            srv.call("POST", f"/documents/{first}/cancel")[1]["stage"] == "done"
        )  # no effect once over
        assert srv.call("GET", f"/documents/{first}/status")[1]["stage"] == "done"
        assert srv.call("POST", "/documents/nope/cancel")[0] == 404
    assert server.STAGES[-1] == "cancelled"


def test_cancel_check_comes_before_each_model_call(monkeypatch):
    from shiori_core.models import Sentence
    from shiori_core.normalize import normalize

    from sidecar import __main__ as m
    from sidecar import server

    class FakeClient:
        calls = 0

        def complete(self, system, user, schema, max_out):
            FakeClient.calls += 1
            return '{"items": []}'

    norm, mp = normalize("競争参加資格")
    ss = [Sentence(id="h_s1", page=0, section_path=[], section_titles=["競争参加資格"], text_orig="競争参加資格", text_norm=norm, norm_to_orig=mp, boxes=[])]  # fmt: skip
    job = server.Job("x", Path("x.pdf"), "notice")
    monkeypatch.setattr(server, "_running", job)
    m.extract_with_progress(FakeClient(), "notice", ss)  # type: ignore[arg-type]
    first = FakeClient.calls
    assert first >= 1
    cands = [e for e in job.events if e["kind"] == "reading"]
    assert [e["field"] for e in cands] == [
        "eligibility"
    ]  # one reading event per field, however many calls
    assert cands[0]["count"] == 1 and cands[0]["sentences"] == [{"page": 0, "section": "競争参加資格", "text": "競争参加資格"}]  # fmt: skip
    assert [e["field"] for e in job.events if e["kind"] == "none"] == [
        "eligibility"
    ]  # read, nothing answered
    job.cancel = True
    with pytest.raises(server.Cancelled):
        m.extract_with_progress(FakeClient(), "notice", ss)  # type: ignore[arg-type]
    assert FakeClient.calls == first  # no model call after the flag


def test_no_event_text_reaches_the_logs(tmp_path, caplog):
    import logging

    pdf = make_pdf(tmp_path / "invented.pdf")
    with caplog.at_level(logging.DEBUG):
        with Server(create_app(TOKEN, fake_lists)) as srv:
            doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
            wait_for(srv, doc_id, "done")
            evs = events_of(srv, doc_id)[0]
            srv.call("POST", f"/documents/{doc_id}/cancel")
    assert any(e["kind"] == "answer" for e in evs)
    text = "\n".join(r.getMessage() for r in caplog.records)
    for e in evs:
        for v in (e.get("value_ja"), *(x["text"] for x in e.get("sentences", []))):
            assert not v or v not in text
    assert "指名停止" not in text and "invented.pdf" not in text


def test_each_group_answer_arrives_as_the_group_finishes(monkeypatch):
    """The answer card of eligibility is in the stream before the model is asked about deadlines."""
    from shiori_core.models import Sentence
    from shiori_core.normalize import normalize

    from sidecar import __main__ as m
    from sidecar import server

    ok = "予算決算及び会計令第71条の規定に該当しない者であること。"
    texts = [("h_s1", "競争参加資格", ["競争参加資格"]), ("h_s2", ok, ["競争参加資格"]), ("h_s3", "入札書の受領期限　令和８年10月21日17時00分", ["入札書の受領期限"])]  # fmt: skip
    ss = []
    for i, t, titles in texts:
        norm, mp = normalize(t)
        ss.append(Sentence(id=i, page=1, section_path=[], section_titles=titles, text_orig=t, text_norm=norm, norm_to_orig=mp, boxes=[]))  # fmt: skip
    job = server.Job("x", Path("x.pdf"), "notice")
    job.ja = {s.id: s for s in ss}
    monkeypatch.setattr(server, "_running", job)
    seen: dict[str, list[str]] = {}

    class FakeClient:
        def complete(self, system, user, schema, max_out):
            f = user.split("Field: ", 1)[1].split("\n", 1)[0]
            seen[f] = [
                e["kind"] + ":" + e["field"] for e in job.events
            ]  # the stream when this call began
            if f == "eligibility":
                it = {
                    "kind": "legal",
                    "polarity": "requirement",
                    "text_ja": ok,
                    "citations": ["h_s2"],
                }
                return json.dumps({"items": [it]}, ensure_ascii=False)
            return '{"items": []}'

    out = m.extract_with_progress(FakeClient(), "notice", ss)  # type: ignore[arg-type]
    assert "eligibility" in out
    assert (
        "answer:eligibility" in seen["deadlines"]
    )  # shown before the next group is asked
    assert (
        "reading:eligibility" in seen["eligibility"]
        and "reading:deadlines" not in seen["eligibility"]
    )
    ans = next(e for e in job.events if e["kind"] == "answer")
    assert ans["value_ja"] == ok and ans["page"] == 1 and ans["exact"] is True
    assert [e["field"] for e in job.events if e["kind"] == "none"] == [
        "deadlines",
        "required_documents",
    ]  # read, nothing: one card each


def test_cancel_in_the_middle_of_a_model_call_aborts_the_request(tmp_path, caplog):
    """Real llm.Client against a slow fake llama-server: Cancel closes the connection, the job ends as
    cancelled within seconds, no second request is sent, and the logs have cancel_asked then job_cancelled."""
    import http.server
    import logging
    import socketserver

    from shiori_core.extract import llm

    from sidecar import __main__ as m

    pdf = make_pdf(tmp_path / "invented.pdf")
    got, release = threading.Event(), threading.Event()
    n: list[int] = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            n.append(1)
            got.set()
            release.wait(20)  # a long eligibility call

        def log_message(self, *a: object) -> None:
            pass

    class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    fake = S(("127.0.0.1", 0), H)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    client = llm.Client(fake.server_port)
    lists = lambda doc_type, ss: m.extract_with_progress(client, doc_type, ss)  # noqa: E731
    try:
        with caplog.at_level(logging.INFO, logger="shiori.sidecar"):
            with Server(create_app(TOKEN, lists, abort=client.abort)) as srv:
                doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
                assert got.wait(10)  # inside the model call
                t0 = time.monotonic()
                srv.call("POST", f"/documents/{doc_id}/cancel")
                wait_for(srv, doc_id, "cancelled")
                assert time.monotonic() - t0 < 3
                time.sleep(0.5)  # anything that would still follow
    finally:
        release.set()
        fake.shutdown()
        fake.server_close()
    names = [
        r.getMessage().split(" ")[0]
        for r in caplog.records
        if r.name == "shiori.sidecar"
    ]
    assert names[names.index("cancel_asked") :] == [
        "cancel_asked",
        "job_cancelled",
    ]  # and nothing after
    assert len(n) == 1  # the retry never reached the server


def cite_all_with_title(doc_type, sentences):
    """cite_all plus a title field whose value is the first sentence's text (a value, not an id)."""
    got = cite_all(doc_type, sentences)
    got["title"] = Extracted(field="title", value_ja="件名の値", normalized={}, citations=[sentences[0].id])  # fmt: skip
    return got


def test_a_field_value_is_translated_first_and_is_not_counted_as_a_sentence(tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    rec = Recorder()
    with Server(create_app(TOKEN, cite_all_with_title, translator=rec)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        got = until(lambda: (g := ask(srv, doc_id)[1])["done"] == g["total"] and "value:title" in g["items"] and g, "queue empty")  # fmt: skip
        assert (
            got["total"] == 4 and got["done"] == 4 and got["failed"] == []
        )  # sentences only
        assert got["items"]["value:title"] == {"en": "EN 件名の値", "numbers_match": True, "protected_lost": False}  # fmt: skip
        assert (
            rec.calls[0] == "件名の値"
        )  # first in the queue, through the same translator
        assert len(rec.calls) == 5 and len(set(rec.calls)) == 5  # once each


def test_the_value_key_is_accepted_to_move_to_the_front_and_others_are_refused(
    tmp_path,
):
    pdf = make_pdf(tmp_path / "a.pdf")
    with Server(create_app(TOKEN, cite_all_with_title, translator=Recorder())) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        assert ask(srv, doc_id, ["value:title"])[0] == 200
        assert (
            ask(srv, doc_id, ["value:issuer_org"])[0] == 400
        )  # only listed value fields
        assert ask(srv, doc_id, ["p9_s9"])[0] == 400


def test_a_failed_value_translation_is_retried_when_asked_and_never_counted_as_failed(
    tmp_path,
):
    from shiori_core.translate import Translation

    pdf = make_pdf(tmp_path / "a.pdf")
    state = {"fail": True}

    def flaky(text, abbreviations, names):
        if text == "件名の値" and state["fail"]:
            raise OSError("down")
        return Translation(en="ok", numbers_match=True)

    with Server(create_app(TOKEN, cite_all_with_title, translator=flaky)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        got = until(
            lambda: (g := ask(srv, doc_id)[1])["done"] == 4 and g, "sentences done"
        )
        assert (
            "value:title" not in got["items"] and got["failed"] == []
        )  # not in the sentence counts
        state["fail"] = False
        ask(srv, doc_id, ["value:title"])
        until(lambda: "value:title" in ask(srv, doc_id)[1]["items"], "retried")


def test_doc_type_is_read_from_the_first_page_unless_given(tmp_path):
    """D-92: no doc_type in the post means the rule on page 1 decides; a given type wins; no cue is notice."""
    spec = make_pdf(
        tmp_path / "spec.pdf",
        ["委託業務仕様書（案）", "１．業務の名称", "invented system"],
    )
    plain = make_pdf(tmp_path / "plain.pdf")
    given = make_pdf(
        tmp_path / "given.pdf",
        ["委託業務仕様書（案）", "１．業務の名称", "invented system two"],
    )  # other bytes, so a new job
    from shiori_core.extract import rules

    app = create_app(TOKEN, lambda d, s: {}, rules.extract)
    with Server(app) as srv:
        got = {}
        for name, pdf, body in (
            ("spec", spec, {}),
            ("plain", plain, {}),
            ("given", given, {"doc_type": "bid_instructions"}),
        ):
            code, r = srv.call("POST", "/documents", {"path": str(pdf), **body})
            assert code == 200
            got[name] = wait_for(srv, r["doc_id"], "done")
        assert got["spec"]["doc_type"] == "spec"
        assert (
            got["spec"]["fields_total"] == 6
        )  # title, issuer, scope, period, delivery deadline and place
        assert (
            got["plain"]["doc_type"] == "notice" and got["plain"]["fields_total"] == 23
        )
        assert got["given"]["doc_type"] == "bid_instructions"


HTML_NOTICE = """<html><body><div id="main_body"><h1>入札公告</h1>
<p>1 競争入札に参加する者に必要な資格</p>
<p>(1) 指名停止を受けている期間中の者でないこと。</p>
<p>2 入札書の提出期限 令和８年10月15日13時30分<br>までに提出すること。</p>
<h2>５ Summary</h2>
<p>(1) Contracting entity: Ministry of Invented Affairs</p>
<script>fetch("http://example.invalid/x")</script>
</div></body></html>"""


def test_html_notice_through_to_fields_with_anchors(tmp_path):
    f = tmp_path / "invented.html"
    f.write_text(HTML_NOTICE, encoding="utf-8")
    with Server(create_app(TOKEN, lists=fake_lists)) as srv:
        assert (
            srv.call("POST", "/documents", {"path": str(tmp_path / "x.htm")})[0] == 400
        )  # missing file
        doc_id = srv.call("POST", "/documents", {"path": str(f)})[1]["doc_id"]
        got = wait_for(srv, doc_id, "done")
        assert got["pages"] is None and got["doc_type"] == "notice"
        out = srv.call("GET", f"/documents/{doc_id}/fields")[1]
    assert (
        out["format"] == "html" and "fetch(" not in out["text"]
    )  # scripts never reach the text
    assert out["en_summary"]["start"] < out["en_summary"]["end"] <= len(out["text"])
    assert out["text"][out["en_summary"]["start"] :].lstrip().startswith("５ Summary")
    cited = [s for s in out["sentences"].values() if "指名停止" in s["text_orig"]]
    assert cited
    for s in out["sentences"].values():
        a = s["anchor"]
        assert out["text"][a["start"] : a["end"]].replace("\n", "") == s[
            "text_orig"
        ].replace("\n", "")
        assert s["boxes"] == [] and s["page"] == 0


def test_pdf_fields_have_no_html_keys(tmp_path):
    pdf = make_pdf(tmp_path / "invented.pdf")
    with Server(create_app(TOKEN)) as srv:
        doc_id = srv.call("POST", "/documents", {"path": str(pdf)})[1]["doc_id"]
        wait_for(srv, doc_id, "done")
        out = srv.call("GET", f"/documents/{doc_id}/fields")[1]
    assert {"text", "en_summary"}.isdisjoint(out) and all(
        "anchor" not in s for s in out["sentences"].values()
    )


def test_health_answers_with_the_token_only():
    with Server(create_app(TOKEN)) as srv:
        assert srv.call("GET", "/health") == (200, {"ok": True})
        assert srv.call("GET", "/health", token=None)[0] == 401
