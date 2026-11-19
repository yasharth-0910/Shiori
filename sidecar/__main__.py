"""uv run python -m sidecar [--llama-url http://127.0.0.1:8792]

Starts the server on 127.0.0.1 and a random free port with a random session token, and
prints one JSON line on stdout: {"port": 51234, "token": "..."}. Without --llama-url
only the rules extractor runs. Logs go to stderr.
"""

import argparse
import json
import logging
import secrets
import sys
from urllib.parse import urlparse

import uvicorn
from shiori_core.extract import llm

from sidecar.server import HOST, bind_loopback, create_app


def main() -> None:
    ap = argparse.ArgumentParser(prog="sidecar")
    ap.add_argument(
        "--llama-url", help="llama-server on 127.0.0.1, e.g. http://127.0.0.1:8792"
    )
    a = ap.parse_args()
    lists = None
    if a.llama_url:
        u = urlparse(a.llama_url)
        if u.scheme != "http" or u.hostname != HOST or u.port is None:
            sys.exit(f"--llama-url must be http://{HOST}:<port>")
        client = llm.Client(u.port)
        lists = lambda doc_type, ss: llm.extract_lists(doc_type, ss, client.complete)  # noqa: E731
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(message)s"
    )
    token = secrets.token_urlsafe(32)
    sock = bind_loopback()
    print(json.dumps({"port": sock.getsockname()[1], "token": token}), flush=True)
    server = uvicorn.Server(
        uvicorn.Config(create_app(token, lists), log_level="warning", access_log=False)
    )
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
