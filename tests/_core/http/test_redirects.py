"""Redirect policy enforcement through real httpx request/response handling."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Barrier

import httpx
import pytest

from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import HttpRedirectError, HttpTimeoutError
from mountainash_transport._core.http.policy import (
    RedirectPolicy,
    RequestPolicy,
    RetryPolicy,
    TimeoutPolicy,
)


@pytest.fixture(params=["request", "stream"])
def fetch(request):
    """Exercise both engine entry points, consuming and closing their responses."""

    def send(engine, url, method="GET", **kwargs):
        if request.param == "request":
            return engine.request(method, url, **kwargs).content
        with engine.stream(method, url, **kwargs) as response:
            return response.read()

    return send


class Body(httpx.SyncByteStream):
    """A real streaming body whose consumption and closure are observable."""

    def __init__(self, content=b"done"):
        self.content = content
        self.consumed = False
        self.closed = False

    def __iter__(self):
        self.consumed = True
        yield self.content

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "limit,redirects,expected_paths,exceeds_limit",
    [
        (0, 0, ["/0"], False),
        (0, 1, ["/0"], True),
        (1, 1, ["/0", "/1"], False),
        (1, 2, ["/0", "/1"], True),
        (2, 2, ["/0", "/1", "/2"], False),
        (2, 3, ["/0", "/1", "/2"], True),
    ],
)
def test_redirect_limit_stops_before_excess_request(
    fetch, limit, redirects, expected_paths, exceeds_limit
):
    paths = []
    bodies = []

    def handler(request):
        paths.append(request.url.path)
        index = int(request.url.path[1:])
        body = Body()
        bodies.append(body)
        if index < redirects:
            return httpx.Response(
                302, headers={"Location": f"/{index + 1}"}, stream=body
            )
        return httpx.Response(200, stream=body)

    policy = RequestPolicy(
        retry=RetryPolicy(max_attempts=1),
        redirect=RedirectPolicy(max_redirects=limit),
    )
    with httpx.Client(
        transport=httpx.MockTransport(handler), max_redirects=20
    ) as client:
        engine = HttpRequestEngine(client, policy=policy)
        if exceeds_limit:
            with pytest.raises(HttpRedirectError):
                fetch(engine, "https://example.test/0")
        else:
            assert fetch(engine, "https://example.test/0") == b"done"

    assert paths == expected_paths
    assert all(body.closed for body in bodies)


def test_per_call_limit_overrides_engine_and_client_without_mutating_client(fetch):
    def handler(request):
        assert client.max_redirects == 0
        assert client.follow_redirects is False
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/end"})
        return httpx.Response(200, content=b"done")

    with httpx.Client(
        transport=httpx.MockTransport(handler), max_redirects=0
    ) as client:
        engine = HttpRequestEngine(
            client, policy=RequestPolicy(redirect=RedirectPolicy(max_redirects=0))
        )
        with pytest.raises(HttpRedirectError):
            fetch(engine, "https://example.test/start")
        assert (
            fetch(
                engine,
                "https://example.test/start",
                policy=RequestPolicy(redirect=RedirectPolicy(max_redirects=1)),
            )
            == b"done"
        )
        with pytest.raises(HttpRedirectError):
            fetch(engine, "https://example.test/start")
        assert client.max_redirects == 0
        assert client.follow_redirects is False


def test_concurrent_calls_keep_independent_redirect_budgets(fetch):
    started = Barrier(2)

    def handler(request):
        assert client.max_redirects == 20
        index = int(request.url.path[1:])
        if index == 0:
            started.wait(timeout=5)
        if index < 2:
            return httpx.Response(302, headers={"Location": f"/{index + 1}"})
        return httpx.Response(200, content=b"done")

    with httpx.Client(
        transport=httpx.MockTransport(handler), max_redirects=20
    ) as client:
        engine = HttpRequestEngine(client)

        def call(limit):
            try:
                return fetch(
                    engine,
                    "https://example.test/0",
                    policy=RequestPolicy(redirect=RedirectPolicy(max_redirects=limit)),
                )
            except HttpRedirectError:
                return "limit exceeded"

        with ThreadPoolExecutor(max_workers=2) as pool:
            short = pool.submit(call, 1)
            long = pool.submit(call, 2)
            assert short.result(timeout=10) == "limit exceeded"
            assert long.result(timeout=10) == b"done"


@pytest.mark.parametrize(
    "status,method,body", [(303, "GET", b""), (307, "POST", b"payload")]
)
@pytest.mark.parametrize("auth_source", ["client", "url"])
def test_redirects_preserve_httpx_request_semantics(
    fetch, status, method, body, auth_source
):
    seen = []

    def handler(request):
        seen.append(
            (
                request.url.host,
                request.method,
                request.content,
                request.headers.get("Authorization"),
                request.headers.get("Cookie"),
            )
        )
        assert request.extensions["timeout"]["connect"] == 1.5
        if request.url.path == "/start":
            return httpx.Response(
                status,
                headers={"Location": "next", "Set-Cookie": "session=abc; Path=/"},
            )
        if request.url.path == "/next":
            return httpx.Response(307, headers={"Location": "https://other.test/end"})
        return httpx.Response(200, content=b"done")

    auth = ("user", "pass") if auth_source == "client" else None
    url = (
        "https://example.test/start" if auth else "https://user:pass@example.test/start"
    )
    with httpx.Client(transport=httpx.MockTransport(handler), auth=auth) as client:
        engine = HttpRequestEngine(
            client,
            policy=RequestPolicy(timeout=TimeoutPolicy(connect=1.5)),
        )
        assert fetch(engine, url, method="POST", content=b"payload") == b"done"

    assert seen == [
        ("example.test", "POST", b"payload", "Basic dXNlcjpwYXNz", None),
        ("example.test", method, body, "Basic dXNlcjpwYXNz", "session=abc"),
        ("other.test", method, body, None, None),
    ]


def test_client_auth_can_handle_challenge_after_redirect(fetch):
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/protected"})
        if request.headers.get("Authorization", "").startswith("Digest "):
            return httpx.Response(200, content=b"authenticated")
        return httpx.Response(
            401,
            headers={
                "WWW-Authenticate": 'Digest realm="test", nonce="abc", qop="auth"'
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), auth=httpx.DigestAuth("user", "pass")
    ) as client:
        assert (
            fetch(HttpRequestEngine(client), "https://example.test/start")
            == b"authenticated"
        )


@pytest.mark.parametrize("consumer_raises", [False, True])
def test_redirected_stream_stays_lazy_and_closes_on_exit(consumer_raises):
    intermediate = Body(b"redirect")
    final = Body(b"payload")

    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(
                302, headers={"Location": "/end"}, stream=intermediate
            )
        return httpx.Response(200, stream=final)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        engine = HttpRequestEngine(client)
        outcome = (
            pytest.raises(ValueError, match="consumer failed")
            if consumer_raises
            else nullcontext()
        )
        with outcome:
            with engine.stream("GET", "https://example.test/start") as response:
                assert intermediate.closed
                assert not final.consumed
                assert not final.closed
                if consumer_raises:
                    raise ValueError("consumer failed")
                assert response.read() == b"payload"

        assert final.closed


def test_redirected_response_closes_when_body_read_fails(fetch):
    class FailingBody(Body):
        def __iter__(self):
            yield b"partial"
            raise httpx.ReadTimeout("body timed out")

    intermediate = Body(b"redirect")
    final = FailingBody()

    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(
                302, headers={"Location": "/end"}, stream=intermediate
            )
        return httpx.Response(200, stream=final)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        engine = HttpRequestEngine(
            client, policy=RequestPolicy(retry=RetryPolicy(max_attempts=1))
        )
        with pytest.raises(HttpTimeoutError):
            fetch(engine, "https://example.test/start")
        assert intermediate.closed
        assert final.closed
