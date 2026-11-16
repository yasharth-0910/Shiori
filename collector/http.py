"""One polite HTTP client for every collector adapter.

Rules (CLAUDE.md, D-14, D-17): robots.txt is checked and cached per host, at most
one request every 3 seconds per host, a fixed honest User-Agent, polite retries on
5xx and dropped connections, and no retry at all on 403. HTML pages are cached on
disk so re-running an adapter costs no requests.
"""

import hashlib
import os
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from eval.silver.keys import _dotenv

CONTACT_ENV = "SHIORI_CONTACT_EMAIL"
MIN_INTERVAL_S = 3.0
RETRY_WAITS_S = (10.0, 30.0)  # waits before the 2nd and 3rd attempt on a 5xx
DEFAULT_CACHE_DIR = Path("data/raw/_http_cache")


def user_agent() -> str:
    """Honest User-Agent with a contact email (CLAUDE.md). The address comes from the
    environment or .env, never from the repo."""
    contact = os.environ.get(CONTACT_ENV) or _dotenv().get(CONTACT_ENV)
    if not contact:
        raise RuntimeError(
            f"{CONTACT_ENV} is not set. The collector sends a contact email in its "
            f"User-Agent: set {CONTACT_ENV}=<your address> in the environment or .env."
        )
    return f"ShioriResearchBot/0.1 (contact: {contact})"


class BlockedError(Exception):
    """The site refused us (403). D-17: skip the site, never work around it."""


class DisallowedError(Exception):
    """robots.txt disallows this URL for our User-Agent."""


class PoliteClient:
    def __init__(
        self,
        cache_dir: Path | None = DEFAULT_CACHE_DIR,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ua = user_agent()
        self._http = httpx.Client(
            headers={"User-Agent": self._ua},
            follow_redirects=True,
            timeout=60.0,
            transport=transport,
        )
        self._cache_dir = cache_dir
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self.request_count = 0

    def get_page(self, url: str) -> bytes:
        """GET an HTML page as raw bytes, from the disk cache when possible.

        Bytes, not text, so a page saved as a document keeps its original encoding
        and its SHA-256 matches what the server sent. Delete the cache to refresh.
        """
        cache_path = self._cache_path(url)
        if cache_path is not None and cache_path.exists():
            return cache_path.read_bytes()
        content = self.get(url).content
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(content)
        return content

    def get_bytes(self, url: str) -> bytes:
        """Download a file. Not cached here: the manifest dedupes files."""
        return self.get(url).content

    def post(self, url: str, data: dict[str, str | list[str]]) -> bytes:
        """POST a public search form (p-portal). Same rules as get, never cached:
        the result depends on the form and on the session cookie."""
        return self.get(url, data).content

    def get(
        self, url: str, data: dict[str, str | list[str]] | None = None
    ) -> httpx.Response:
        """GET (or POST when `data` is given) with robots.txt check, rate limit and
        retries. Raises on failure."""
        if not self._robots_for(url).can_fetch(self._ua, url):
            raise DisallowedError(url)
        return self._request(url, data)

    def _request(
        self, url: str, data: dict[str, str | list[str]] | None = None
    ) -> httpx.Response:
        """Retry 5xx and transport errors (dropped connection, timeout) politely."""
        waits = (0.0, *RETRY_WAITS_S)
        response: httpx.Response | None = None
        for attempt, wait in enumerate(waits):
            if wait:
                self._sleep(wait)
            try:
                response = self._rate_limited(url, data)
            except httpx.TransportError:
                if attempt == len(waits) - 1:
                    raise
                continue
            if response.status_code == 403:
                raise BlockedError(f"403 from {urlsplit(url).netloc}")
            if response.status_code < 500:
                break
        assert response is not None
        response.raise_for_status()
        return response

    def _rate_limited(
        self, url: str, data: dict[str, str | list[str]] | None = None
    ) -> httpx.Response:
        host = urlsplit(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            remaining = MIN_INTERVAL_S - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        try:
            if data is not None:
                return self._http.post(url, data=data)
            return self._http.get(url)
        finally:
            self._last_request[host] = self._clock()
            self.request_count += 1

    def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        host = parts.netloc
        if host not in self._robots:
            robots_url = f"{parts.scheme}://{host}/robots.txt"
            parser = RobotFileParser(robots_url)
            response = self._rate_limited(robots_url)
            if response.status_code in (401, 403):
                raise BlockedError(f"{response.status_code} on robots.txt of {host}")
            if response.status_code >= 500:
                lines = ["User-agent: *", "Disallow: /"]  # server trouble: assume no
            elif response.status_code >= 400:
                lines = []  # no robots.txt means no rules
            else:
                lines = response.text.splitlines()
            parser.parse(lines)
            self._robots[host] = parser
        return self._robots[host]

    def _cache_path(self, url: str) -> Path | None:
        if self._cache_dir is None:
            return None
        return self._cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".html")
