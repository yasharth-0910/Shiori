"""PoliteClient rules, offline: httpx.MockTransport and a fake clock, no live sites."""

import pytest

pytest.importorskip("httpx")  # "collector" dependency group

import httpx  # noqa: E402

from collector.http import (  # noqa: E402
    MIN_INTERVAL_S,
    BlockedError,
    DisallowedError,
    PoliteClient,
    user_agent,
)

DROP = -1  # a route status that makes the fake server drop the connection
CONTACT = "collector-test@example.invalid"  # invented


@pytest.fixture(autouse=True)
def contact_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHIORI_CONTACT_EMAIL", CONTACT)


def test_user_agent_carries_the_contact_from_the_environment() -> None:
    assert user_agent() == f"ShioriResearchBot/0.1 (contact: {CONTACT})"


def test_missing_contact_raises_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("SHIORI_CONTACT_EMAIL")
    monkeypatch.chdir(tmp_path)  # no .env here
    with pytest.raises(RuntimeError, match="SHIORI_CONTACT_EMAIL is not set"):
        PoliteClient(cache_dir=None)


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Server:
    """Answers from a dict of url -> list of (status, body); the last entry repeats."""

    def __init__(
        self, time: FakeTime, routes: dict[str, list[tuple[int, str]]]
    ) -> None:
        self.time = time
        self.routes = routes
        self.log: list[tuple[float, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == user_agent()
        url = str(request.url)
        self.log.append((self.time.now, url))
        answers = self.routes.get(url, [(404, "")])
        status, body = answers.pop(0) if len(answers) > 1 else answers[0]
        if status == DROP:
            raise httpx.RemoteProtocolError("Server disconnected", request=request)
        return httpx.Response(status, text=body)

    def calls(self, url: str) -> int:
        return sum(u == url for _, u in self.log)


def make(
    routes: dict[str, list[tuple[int, str]]], cache_dir=None
) -> tuple[PoliteClient, Server]:
    """A client wired to a fake server and clock. server.time.sleeps logs every wait."""
    time = FakeTime()
    server = Server(time, routes)
    client = PoliteClient(
        cache_dir=cache_dir,
        transport=httpx.MockTransport(server),
        sleep=time.sleep,
        clock=time.clock,
    )
    return client, server


def test_same_host_requests_are_at_least_3s_apart() -> None:
    routes = {
        f"https://{h}/{n}": [(200, "x")] for h in ("a.test", "b.test") for n in (1, 2)
    }
    client, server = make(routes)
    client.get("https://a.test/1")
    client.get("https://a.test/2")
    client.get("https://b.test/1")  # other host: no wait needed
    times = [t for t, url in server.log if url.startswith("https://a.test")]
    assert len(times) == 3  # robots.txt, /1, /2
    assert all(b - a >= MIN_INTERVAL_S for a, b in zip(times, times[1:], strict=False))
    b_time = next(t for t, url in server.log if url.startswith("https://b.test"))
    assert b_time == times[-1]  # no sleep before the first request to b.test


def test_robots_disallow_is_respected() -> None:
    robots = "User-agent: *\nDisallow: /private/\n"
    client, server = make({"https://a.test/robots.txt": [(200, robots)]})
    with pytest.raises(DisallowedError):
        client.get("https://a.test/private/x.pdf")
    assert server.calls("https://a.test/private/x.pdf") == 0


def test_robots_fetched_once_per_host() -> None:
    client, server = make(
        {"https://a.test/1": [(200, "x")], "https://a.test/2": [(200, "y")]}
    )
    client.get("https://a.test/1")
    client.get("https://a.test/2")
    assert server.calls("https://a.test/robots.txt") == 1


def test_403_is_never_retried() -> None:
    client, server = make({"https://a.test/1": [(403, "")]})
    with pytest.raises(BlockedError):
        client.get("https://a.test/1")
    assert server.calls("https://a.test/1") == 1


def test_403_on_robots_blocks_the_site() -> None:
    client, server = make({"https://a.test/robots.txt": [(403, "")]})
    with pytest.raises(BlockedError):
        client.get("https://a.test/1")
    assert server.calls("https://a.test/1") == 0


def test_5xx_is_retried_with_waits() -> None:
    client, server = make({"https://a.test/1": [(503, ""), (200, "ok")]})
    assert client.get("https://a.test/1").text == "ok"
    assert server.calls("https://a.test/1") == 2
    assert 10.0 in server.time.sleeps


def test_5xx_gives_up_after_three_attempts() -> None:
    client, server = make({"https://a.test/1": [(500, "")]})
    with pytest.raises(httpx.HTTPStatusError):
        client.get("https://a.test/1")
    assert server.calls("https://a.test/1") == 3


def test_pages_are_cached_on_disk(tmp_path) -> None:
    client, server = make(
        {"https://a.test/p.html": [(200, "<p>hi</p>")]}, cache_dir=tmp_path
    )
    assert client.get_page("https://a.test/p.html") == b"<p>hi</p>"
    assert client.get_page("https://a.test/p.html") == b"<p>hi</p>"
    assert server.calls("https://a.test/p.html") == 1


def test_dropped_connection_is_retried() -> None:
    client, server = make({"https://a.test/1": [(DROP, ""), (200, "ok")]})
    assert client.get("https://a.test/1").text == "ok"
    assert server.calls("https://a.test/1") == 2
    assert 10.0 in server.time.sleeps


def test_dropped_connection_gives_up_after_three_attempts() -> None:
    client, server = make({"https://a.test/1": [(DROP, "")]})
    with pytest.raises(httpx.TransportError):
        client.get("https://a.test/1")
    assert server.calls("https://a.test/1") == 3


def test_post_sends_the_form_under_the_same_rules() -> None:
    client, server = make(
        {
            "https://a.test/search": [(200, "results")],
            "https://a.test/robots.txt": [(200, "User-agent: *\nDisallow: /private")],
        }
    )
    assert client.post("https://a.test/search", {"q": "システム"}) == b"results"
    with pytest.raises(DisallowedError):
        client.post("https://a.test/private", {"q": "x"})
    assert server.calls("https://a.test/private") == 0
    client.post("https://a.test/search", {"q": "x"})
    times = [t for t, u in server.log if u == "https://a.test/search"]
    assert times[1] - times[0] >= MIN_INTERVAL_S
