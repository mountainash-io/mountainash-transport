"""Tests for HttpRequestEngine — retry, auth refresh, error mapping, streaming."""
from __future__ import annotations

import io
import typing as t
from unittest.mock import patch

import httpx
import pytest

from mountainash_transport._core.http.auth_protocol import (
    AuthStrategy,
    RefreshableAuthStrategy,
)
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError,
    HttpClientError,
    HttpConnectionError,
    HttpForbiddenError,
    HttpNotFoundError,
    HttpProtocolError,
    HttpRateLimitError,
    HttpRedirectError,
    HttpRequestError,
    HttpResponseError,
    HttpServerError,
    HttpServiceUnavailableError,
    HttpTimeoutError,
    HttpTransportError,
)
from mountainash_transport._core.http.policy import (
    IDEMPOTENT_METHODS,
    RedirectPolicy,
    RequestPolicy,
    RetryPolicy,
    TimeoutPolicy,
)
from mountainash_transport._core.http.response import HttpResponse, HttpStreamResponse
from mountainash_transport.connections.auth_strategy import OAuth2RefreshableAuthStrategy


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _mock_client(*responses: httpx.Response) -> httpx.Client:
    """Client that returns responses in sequence."""
    it = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return next(it)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def _error_client(exc: Exception) -> httpx.Client:
    """Client that always raises the given httpx exception."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


_Outcome = t.Union[httpx.Response, Exception]


def _sequenced_client(sequence: list[_Outcome]) -> httpx.Client:
    """Client that returns responses OR raises exceptions in order."""
    it = iter(sequence)

    def handler(request: httpx.Request) -> httpx.Response:
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return item

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def _resp(status: int = 200, headers: dict[str, str] | None = None, content: bytes = b"") -> httpx.Response:
    """Build an httpx.Response for mock transport."""
    return httpx.Response(status_code=status, headers=headers or {}, content=content)


# No-retry policy for tests that should not retry
_NO_RETRY = RequestPolicy(
    retry=RetryPolicy(max_attempts=1),
    auth_refresh_on_401=False,
    redirect=RedirectPolicy(follow_redirects=False),
)

_NO_RETRY_WITH_AUTH = RequestPolicy(
    retry=RetryPolicy(max_attempts=1),
    auth_refresh_on_401=True,
    redirect=RedirectPolicy(follow_redirects=False),
)


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_200_returns_http_response(self) -> None:
        client = _mock_client(_resp(200, content=b"ok"))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        resp = engine.request("GET", "https://example.com")
        assert isinstance(resp, HttpResponse)
        assert resp.status_code == 200
        assert resp.content == b"ok"

    def test_201_returns_http_response(self) -> None:
        client = _mock_client(_resp(201, content=b"created"))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        resp = engine.request("POST", "https://example.com/resource")
        assert resp.status_code == 201
        assert resp.content == b"created"

    def test_response_captures_method_and_url(self) -> None:
        client = _mock_client(_resp(200))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        resp = engine.request("PUT", "https://example.com/thing")
        assert resp.method == "PUT"
        assert "example.com" in resp.url


# ---------------------------------------------------------------------------
# 2. Status code errors
# ---------------------------------------------------------------------------


class TestStatusCodeErrors:
    def test_404_raises_not_found(self) -> None:
        client = _mock_client(_resp(404, content=b"nope"))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpNotFoundError) as exc_info:
            engine.request("GET", "https://example.com/missing")
        assert exc_info.value.status_code == 404

    def test_401_without_refresh_raises_auth_error(self) -> None:
        client = _mock_client(_resp(401))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpAuthenticationError):
            engine.request("GET", "https://example.com/secret")

    def test_403_raises_forbidden(self) -> None:
        client = _mock_client(_resp(403))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpForbiddenError):
            engine.request("GET", "https://example.com/nope")

    def test_unmapped_4xx_raises_client_error(self) -> None:
        client = _mock_client(_resp(418))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpClientError) as exc_info:
            engine.request("GET", "https://example.com/teapot")
        assert exc_info.value.status_code == 418

    def test_unmapped_5xx_raises_server_error(self) -> None:
        client = _mock_client(_resp(599))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpServerError) as exc_info:
            engine.request("GET", "https://example.com/error")
        assert exc_info.value.status_code == 599


# ---------------------------------------------------------------------------
# 3. Retry
# ---------------------------------------------------------------------------


class TestRetry:
    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_503_then_200_retries(self, mock_sleep: t.Any) -> None:
        client = _mock_client(_resp(503), _resp(200, content=b"ok"))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        resp = engine.request("GET", "https://example.com")
        assert resp.status_code == 200
        mock_sleep.assert_called_once()

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_retry_exhaustion_raises(self, mock_sleep: t.Any) -> None:
        client = _mock_client(_resp(503), _resp(503), _resp(503))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        with pytest.raises(HttpServiceUnavailableError):
            engine.request("GET", "https://example.com")

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_post_not_retried_by_default(self, mock_sleep: t.Any) -> None:
        client = _mock_client(_resp(503))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        with pytest.raises(HttpServiceUnavailableError):
            engine.request("POST", "https://example.com")
        mock_sleep.assert_not_called()

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_retry_unsafe_methods_flag(self, mock_sleep: t.Any) -> None:
        client = _mock_client(_resp(503), _resp(200, content=b"ok"))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, retry_unsafe_methods=True, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        resp = engine.request("POST", "https://example.com")
        assert resp.status_code == 200

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_backoff_max_respected(self, mock_sleep: t.Any) -> None:
        # 3 retries with backoff_base=10, backoff_max=5 → sleep should never exceed 5
        client = _mock_client(_resp(503), _resp(503), _resp(200, content=b"ok"))
        policy = RequestPolicy(
            retry=RetryPolicy(
                max_attempts=3, backoff_base=10.0, backoff_max=5.0, backoff_jitter=False,
            ),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        engine.request("GET", "https://example.com")
        for call in mock_sleep.call_args_list:
            assert call.args[0] <= 5.0

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_transport_error_retried(self, mock_sleep: t.Any) -> None:
        client = _sequenced_client([
            httpx.ConnectError("fail"),
            _resp(200, content=b"ok"),
        ])
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        resp = engine.request("GET", "https://example.com")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Body replayability
# ---------------------------------------------------------------------------


class TestBodyReplayability:
    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_bytes_always_replayable(self, mock_sleep: t.Any) -> None:
        client = _mock_client(_resp(503), _resp(200, content=b"ok"))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, retry_unsafe_methods=True, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        resp = engine.request("POST", "https://example.com", content=b"body")
        assert resp.status_code == 200

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_seekable_stream_replayable(self, mock_sleep: t.Any) -> None:
        stream = io.BytesIO(b"stream-body")
        client = _mock_client(_resp(503), _resp(200, content=b"ok"))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, retry_unsafe_methods=True, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        resp = engine.request("POST", "https://example.com", stream=stream)
        assert resp.status_code == 200

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_non_seekable_stream_not_retried_on_5xx(self, mock_sleep: t.Any) -> None:
        """Non-seekable stream body prevents retry on 5xx."""

        class NonSeekableIO(io.RawIOBase):
            def __init__(self, data: bytes) -> None:
                self._data = data
                self._pos = 0

            def read(self, size: int = -1) -> bytes:
                if size == -1:
                    result = self._data[self._pos:]
                    self._pos = len(self._data)
                else:
                    result = self._data[self._pos:self._pos + size]
                    self._pos += size
                return result

            def readable(self) -> bool:
                return True

            def seekable(self) -> bool:
                return False

        stream = NonSeekableIO(b"data")
        client = _mock_client(_resp(503))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, retry_unsafe_methods=True, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        with pytest.raises(HttpServiceUnavailableError):
            engine.request("POST", "https://example.com", stream=stream)
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Rate limit retry (429)
# ---------------------------------------------------------------------------


class TestRateLimitRetry:
    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_429_with_retry_after(self, mock_sleep: t.Any) -> None:
        client = _mock_client(
            _resp(429, headers={"retry-after": "2"}),
            _resp(200, content=b"ok"),
        )
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        resp = engine.request("GET", "https://example.com")
        assert resp.status_code == 200
        mock_sleep.assert_called_once_with(2.0)

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_429_retry_after_capped(self, mock_sleep: t.Any) -> None:
        client = _mock_client(
            _resp(429, headers={"retry-after": "999"}),
            _resp(200, content=b"ok"),
        )
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, max_retry_after=5.0, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        resp = engine.request("GET", "https://example.com")
        assert resp.status_code == 200
        mock_sleep.assert_called_once_with(5.0)

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_429_retries_post(self, mock_sleep: t.Any) -> None:
        """429 retries are exempt from method safety check."""
        client = _mock_client(
            _resp(429, headers={"retry-after": "1"}),
            _resp(200, content=b"ok"),
        )
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3, retry_unsafe_methods=False, backoff_jitter=False),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        resp = engine.request("POST", "https://example.com")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 6. Auth refresh
# ---------------------------------------------------------------------------


class _FakeRefreshableAuth:
    """Fake that satisfies RefreshableAuthStrategy protocol."""

    def __init__(self, refresh_succeeds: bool = True, second_401: bool = False) -> None:
        self._refresh_succeeds = refresh_succeeds
        self._second_401 = second_401
        self._token = "old-token"
        self.refresh_called = False

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        return {**kwargs}

    def refresh(self) -> bool:
        self.refresh_called = True
        if self._refresh_succeeds:
            self._token = "new-token"
        return self._refresh_succeeds

    def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


class _Cred:
    """Fake credential object for OAuth2RefreshableAuthStrategy."""
    def __init__(self, tok: str) -> None:
        self.access_token = tok
        self.token_type = "Bearer"


class _Mgr:
    """Fake OAuth2 manager for testing OAuth2RefreshableAuthStrategy integration."""
    def __init__(self) -> None:
        self.refreshed = 0

    def acquire(self) -> _Cred:
        return _Cred("A")

    def refresh(self) -> _Cred:
        self.refreshed += 1
        return _Cred("B")


class TestAuthRefresh:
    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_401_refresh_retry_succeeds(self, mock_sleep: t.Any) -> None:
        client = _mock_client(_resp(401), _resp(200, content=b"ok"))
        auth = _FakeRefreshableAuth(refresh_succeeds=True)
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=1),  # only 1 attempt allowed
            auth_refresh_on_401=True,
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy, auth_strategy=auth)
        resp = engine.request("GET", "https://example.com")
        assert resp.status_code == 200
        assert auth.refresh_called

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_refresh_fails_raises(self, mock_sleep: t.Any) -> None:
        client = _mock_client(_resp(401))
        auth = _FakeRefreshableAuth(refresh_succeeds=False)
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=1),
            auth_refresh_on_401=True,
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy, auth_strategy=auth)
        with pytest.raises(HttpAuthenticationError):
            engine.request("GET", "https://example.com")

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_still_401_after_refresh_raises(self, mock_sleep: t.Any) -> None:
        client = _mock_client(_resp(401), _resp(401))
        auth = _FakeRefreshableAuth(refresh_succeeds=True)
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=1),
            auth_refresh_on_401=True,
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy, auth_strategy=auth)
        with pytest.raises(HttpAuthenticationError):
            engine.request("GET", "https://example.com")

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_auth_refresh_not_counted_against_max_attempts(self, mock_sleep: t.Any) -> None:
        """Auth refresh retry doesn't consume from max_attempts budget."""
        # max_attempts=1 means only 1 normal attempt. 401→refresh→200 should still work.
        client = _mock_client(_resp(401), _resp(200, content=b"ok"))
        auth = _FakeRefreshableAuth(refresh_succeeds=True)
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=1),
            auth_refresh_on_401=True,
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy, auth_strategy=auth)
        resp = engine.request("GET", "https://example.com")
        assert resp.status_code == 200

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_auth_refresh_retries_post(self, mock_sleep: t.Any) -> None:
        """Auth refresh always retries regardless of method safety."""
        client = _mock_client(_resp(401), _resp(200, content=b"ok"))
        auth = _FakeRefreshableAuth(refresh_succeeds=True)
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=1, retry_unsafe_methods=False),
            auth_refresh_on_401=True,
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy, auth_strategy=auth)
        resp = engine.request("POST", "https://example.com")
        assert resp.status_code == 200

    def test_engine_refreshes_on_401_and_resends(self) -> None:
        """A 401 triggers strategy.refresh() (auth_refresh_on_401 True) and a re-send
        carrying the refreshed bearer. Integration test with OAuth2RefreshableAuthStrategy."""
        seen: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers.get("authorization"))
            return httpx.Response(401 if len(seen) == 1 else 200)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        mgr = _Mgr()
        engine = HttpRequestEngine(
            client=client,
            auth_strategy=OAuth2RefreshableAuthStrategy(mgr),
            policy=_NO_RETRY_WITH_AUTH,
        )
        resp = engine.request("GET", "https://example.com/obj")
        assert resp.status_code == 200
        assert mgr.refreshed == 1
        assert seen == ["Bearer A", "Bearer B"]


# ---------------------------------------------------------------------------
# 7. Redirects
# ---------------------------------------------------------------------------


class TestRedirects:
    def test_3xx_with_redirects_disabled_raises(self) -> None:
        client = _mock_client(_resp(302, headers={"location": "https://other.com"}))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=1),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        with pytest.raises(HttpRedirectError):
            engine.request("GET", "https://example.com")


# ---------------------------------------------------------------------------
# 8. httpx exception mapping
# ---------------------------------------------------------------------------


class TestHttpxExceptionMapping:
    @pytest.mark.parametrize(
        "httpx_exc,expected_cls",
        [
            (httpx.ConnectTimeout("t"), HttpTimeoutError),
            (httpx.ReadTimeout("t"), HttpTimeoutError),
            (httpx.WriteTimeout("t"), HttpTimeoutError),
            (httpx.PoolTimeout("t"), HttpTimeoutError),
            (httpx.TooManyRedirects("t"), HttpRedirectError),
            (httpx.ConnectError("c"), HttpConnectionError),
            (httpx.ProtocolError("p"), HttpProtocolError),
            (httpx.DecodingError("d"), HttpProtocolError),
            (httpx.InvalidURL("u"), HttpRequestError),
        ],
    )
    def test_exception_mapping(self, httpx_exc: Exception, expected_cls: type) -> None:
        client = _error_client(httpx_exc)
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(expected_cls):
            engine.request("GET", "https://example.com")


# ---------------------------------------------------------------------------
# 9. Per-request policy
# ---------------------------------------------------------------------------


class TestPerRequestPolicy:
    def test_per_request_policy_overrides_default(self) -> None:
        client = _mock_client(_resp(503))
        # Engine default allows retries
        engine_policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=3),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        # Per-request: no retries
        req_policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=1),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=engine_policy)
        with pytest.raises(HttpServiceUnavailableError):
            engine.request("GET", "https://example.com", policy=req_policy)

    def test_policy_property(self) -> None:
        client = _mock_client()
        policy = RequestPolicy()
        engine = HttpRequestEngine(client, policy=policy)
        assert engine.policy is policy

    def test_default_policy_when_none(self) -> None:
        client = _mock_client()
        engine = HttpRequestEngine(client)
        assert isinstance(engine.policy, RequestPolicy)


# ---------------------------------------------------------------------------
# 10. Header precedence
# ---------------------------------------------------------------------------


class TestHeaderPrecedence:
    def test_caller_headers_override_auth_headers(self) -> None:
        """Caller-provided headers win over auth strategy headers."""
        captured_headers: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(200, content=b"ok")

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)

        auth = _FakeRefreshableAuth()
        engine = HttpRequestEngine(client, policy=_NO_RETRY, auth_strategy=auth)
        engine.request(
            "GET", "https://example.com",
            headers={"Authorization": "Bearer caller-wins"},
        )
        assert captured_headers[0]["authorization"] == "Bearer caller-wins"


# ---------------------------------------------------------------------------
# 11. Streaming
# ---------------------------------------------------------------------------


class TestStreaming:
    def test_stream_yields_stream_response(self) -> None:
        client = _mock_client(_resp(200, content=b"streamed-data"))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with engine.stream("GET", "https://example.com") as resp:
            assert isinstance(resp, HttpStreamResponse)
            assert resp.status_code == 200

    def test_stream_4xx_raises(self) -> None:
        client = _mock_client(_resp(404, content=b"nope"))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpNotFoundError):
            with engine.stream("GET", "https://example.com/missing") as resp:
                pass  # pragma: no cover

    def test_stream_3xx_raises_redirect(self) -> None:
        client = _mock_client(_resp(302, headers={"location": "https://other.com"}))
        policy = RequestPolicy(
            retry=RetryPolicy(max_attempts=1),
            redirect=RedirectPolicy(follow_redirects=False),
        )
        engine = HttpRequestEngine(client, policy=policy)
        with pytest.raises(HttpRedirectError):
            with engine.stream("GET", "https://example.com") as resp:
                pass  # pragma: no cover

    def test_stream_wraps_httpx_errors(self) -> None:
        client = _error_client(httpx.ConnectError("fail"))
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpConnectionError):
            with engine.stream("GET", "https://example.com") as resp:
                pass  # pragma: no cover
