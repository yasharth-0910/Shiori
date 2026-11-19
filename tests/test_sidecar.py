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
FIELD_KEYS = {"field", "status", "value_en", "value_ja", "items", "citations", "checks"}


def make_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    for n, text in enumerate(LINES):
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
