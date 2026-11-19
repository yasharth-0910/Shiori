# ruff: noqa: E501
"""uv run python -m sidecar [--llama-url http://127.0.0.1:8792]

Starts the server on 127.0.0.1 and a random free port with a random session token, and
prints one JSON line on stdout: {"port": 51234, "token": "..."}. Without --llama-url
only the rules extractor runs. Logs go to stderr.
"""

import argparse
import json
import logging
import os
import secrets
import signal
import sys
import threading
from urllib.parse import urlparse

import uvicorn
from shiori_core import translate as tr
from shiori_core.extract import llm
from shiori_core.fields import BY_ID

from sidecar.server import (
    HOST,
    SHOWN_CHARS,
    bind_loopback,
    check_cancel,
    create_app,
    emit_event,
    report,
)


def watch_stdin(stop) -> None:
    # raw fd read: a thread blocked in sys.stdin.buffer.read aborts the interpreter at exit
    while os.read(0, 4096):
        pass
    stop()


def extract_with_progress(client: llm.Client, doc_type: str, ss) -> dict:
    """llm.extract_lists, reporting "<field> (n of m)" before each model call, adding a
    "candidates" event the first time a field is asked (D-90), and stopping before a model call
    when the user cancelled."""
    fields = [f for f in llm.LIST_FIELDS if doc_type in BY_ID[f].applies_to]
    ja = [s for s in ss if s.language == "ja"]
    announced: set[str] = set()

    def complete(system: str, user: str, schema: dict, max_out: int) -> str:
        check_cancel()
        f = user.split("Field: ", 1)[1].split("\n", 1)[0]
        if f in fields:
            report(f"{f} ({fields.index(f) + 1} of {len(fields)})")
            if (
                f not in announced
            ):  # the retry asks again; the same candidates are not news
                announced.add(f)
                cand = llm.retrieve(
                    f, ja
                )  # the same call extract_lists made for this prompt
                if cand:
                    s = cand[0]
                    emit_event(
                        "candidates", field=f, count=len(cand), page=s.page,
                        section=" > ".join(s.section_titles[:2]), text=s.text_orig[:SHOWN_CHARS],
                    )  # fmt: skip
        return client.complete(system, user, schema, max_out)

    return llm.extract_lists(doc_type, ss, complete)


def main() -> None:
    ap = argparse.ArgumentParser(prog="sidecar")
    ap.add_argument(
        "--llama-url", help="llama-server on 127.0.0.1, e.g. http://127.0.0.1:8792"
    )
    a = ap.parse_args()
    lists = translator = None
    if a.llama_url:
        u = urlparse(a.llama_url)
        if u.scheme != "http" or u.hostname != HOST or u.port is None:
            sys.exit(f"--llama-url must be http://{HOST}:<port>")
        # The key comes from the environment, not argv (argv shows in `ps`).
        client = llm.Client(u.port, api_key=os.environ.get("SHIORI_LLAMA_KEY") or None)
        lists = lambda doc_type, ss: extract_with_progress(client, doc_type, ss)  # noqa: E731
        translator = lambda text, abbrs, names: tr.translate(client, text, abbrs, names)  # noqa: E731
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(message)s"
    )
    token = secrets.token_urlsafe(32)
    sock = bind_loopback()
    print(json.dumps({"port": sock.getsockname()[1], "token": token}), flush=True)
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(token, lists, translator=translator),
            log_level="warning",
            access_log=False,
        )
    )

    def stop(
        *_: object,
    ) -> None:  # Ctrl+C or terminate: leave the serve loop, no traceback
        server.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    if (
        not sys.stdin.isatty()
    ):  # the app holds our stdin open; when it quits or dies, so do we
        threading.Thread(target=watch_stdin, args=(stop,), daemon=True).start()
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
