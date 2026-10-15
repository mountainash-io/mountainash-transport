"""stream() applies retry and auth refresh before yielding."""
from __future__ import annotations

import typing as t

import httpx
import pytest

from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.auth_protocol import RefreshableAuthStrategy
from mountainash_transport._core.http.errors import HttpAuthenticationError, HttpServiceUnavailableError
from mountainash_transport._core.http.policy import RequestPolicy, RetryPolicy


class _RefreshingAuth:
    """RefreshableAuthStrategy double: token 'old' until refresh() switches to 'new'."""

    def __init__(self, *, fail_refresh: bool = False) -> None:
        self.token = "old"
        self.refreshes = 0
        self.fail_refresh = fail_refresh

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        kwargs.setdefault("headers", {}).update(self.get_headers())
        return kwargs

    def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def refresh(self) -> bool:
        self.refreshes += 1
        if self.fail_refresh:
            raise RuntimeError("refresh failed")
        self.token = "new"
        return True


def _engine(handler, *, auth=None, max_attempts: int = 3) -> HttpRequestEngine:
    policy = RequestPolicy(retry=RetryPolicy(max_attempts=max_attempts, backoff_base=0.0, backoff_jitter=False))
    return HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(handler)), auth_strategy=auth, policy=policy)


def test_stream_refreshes_auth_on_401_before_yield() -> None:
    auth = _RefreshingAuth()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["Authorization"] == "Bearer old":
            return httpx.Response(401)
        return httpx.Response(200, content=b"payload")

    assert isinstance(auth, RefreshableAuthStrategy)  # the double must exercise the real refresh path
    with _engine(handler, auth=auth).stream("GET", "https://h/f") as r:
        assert b"".join(r.iter_bytes()) == b"payload"
    assert auth.refreshes == 1


def test_stream_closes_401_response_when_refresh_raises() -> None:
    closed: list[bool] = []

    class _TrackedStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b""
        def close(self) -> None:
            closed.append(True)

    auth = _RefreshingAuth(fail_refresh=True)
    with pytest.raises(RuntimeError, match="refresh failed"):
        with _engine(lambda r: httpx.Response(401, stream=_TrackedStream()), auth=auth).stream("GET", "https://h/f"):
            pass
    assert closed == [True]


def test_stream_retries_retryable_status_before_yield() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, content=b"ok")

    with _engine(handler).stream("GET", "https://h/f") as r:
        assert b"".join(r.iter_bytes()) == b"ok"
    assert len(calls) == 2


def test_stream_gives_up_after_max_attempts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(HttpServiceUnavailableError):
        with _engine(handler, max_attempts=2).stream("GET", "https://h/f"):
            pass


def test_stream_401_without_refreshable_auth_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    with pytest.raises(HttpAuthenticationError):
        with _engine(handler).stream("GET", "https://h/f"):
            pass


def test_stream_does_not_retry_unsafe_method_with_retryable_status() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(HttpServiceUnavailableError):
        with _engine(handler).stream("POST", "https://h/f", content=b"x"):
            pass
    assert len(calls) == 1