# HTTP Transport Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared HTTP transport foundation in `_core/http/` providing a request engine with retry, auth refresh, streaming, and a typed error hierarchy — then migrate the HTTP storage backend to use it.

**Architecture:** A stateless `HttpRequestEngine` receives an httpx.Client (from any connection type) and a `RequestPolicy`, executes requests through a lifecycle of retry/auth-refresh/error-mapping, and returns typed `HttpResponse` or `HttpStreamResponse` objects. The HTTP error hierarchy is independent of `StorageError` — consumers map between them. The storage backend becomes a thin mapping layer.

**Tech Stack:** Python 3.12, httpx, dataclasses (frozen), typing Protocol

**Spec:** `docs/superpowers/specs/2026-06-10-http-transport-foundation-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/mountainash_transport/_core/http/__init__.py` | Package re-exports |
| Create | `src/mountainash_transport/_core/http/errors.py` | HTTP error hierarchy (18 exception classes) |
| Create | `src/mountainash_transport/_core/http/policy.py` | RequestPolicy, RetryPolicy, TimeoutPolicy, RedirectPolicy, constants |
| Create | `src/mountainash_transport/_core/http/response.py` | HttpResponse, HttpStreamResponse |
| Create | `src/mountainash_transport/_core/http/engine.py` | HttpRequestEngine |
| Delete | `src/mountainash_transport/_core/http.py` | Old stub replaced by package |
| Modify | `src/mountainash_transport/_core/auth/strategies.py` | Add RefreshableAuthStrategy protocol |
| Modify | `src/mountainash_transport/storage/backends/http/__init__.py` | Accept engine, pass to mixins |
| Modify | `src/mountainash_transport/storage/backends/http/_helpers.py` | Remove (replaced by engine) |
| Modify | `src/mountainash_transport/storage/backends/http/http_read.py` | Use engine.request() and engine.stream() |
| Modify | `src/mountainash_transport/storage/backends/http/http_write.py` | Use engine.request() |
| Modify | `src/mountainash_transport/storage/backends/http/http_metadata.py` | Use engine.request() |
| Modify | `src/mountainash_transport/__init__.py` | Add public HTTP exports |
| Create | `tests/_core/http/__init__.py` | Test package |
| Create | `tests/_core/http/test_errors.py` | Error hierarchy tests |
| Create | `tests/_core/http/test_policy.py` | Policy tests |
| Create | `tests/_core/http/test_response.py` | Response tests |
| Create | `tests/_core/http/test_engine.py` | Engine tests |
| Modify | `tests/storage/backends/test_http.py` | Update to engine-based backend |

---

### Task 1: HTTP Error Hierarchy

**Files:**
- Delete: `src/mountainash_transport/_core/http.py`
- Create: `src/mountainash_transport/_core/http/__init__.py`
- Create: `src/mountainash_transport/_core/http/errors.py`
- Test: `tests/_core/http/__init__.py`
- Test: `tests/_core/http/test_errors.py`

- [ ] **Step 1: Delete the old stub and create the package directory**

```bash
rm src/mountainash_transport/_core/http.py
mkdir -p src/mountainash_transport/_core/http
touch src/mountainash_transport/_core/http/__init__.py
mkdir -p tests/_core/http
touch tests/_core/http/__init__.py
```

- [ ] **Step 2: Write failing tests for the error hierarchy**

Create `tests/_core/http/test_errors.py`:

```python
"""Tests for the HTTP transport error hierarchy."""
from __future__ import annotations

import pytest

from mountainash_transport._core.http.errors import (
    HttpTransportError,
    HttpResponseError,
    HttpClientError,
    HttpServerError,
    HttpNotFoundError,
    HttpAuthenticationError,
    HttpForbiddenError,
    HttpRateLimitError,
    HttpConflictError,
    HttpBadGatewayError,
    HttpServiceUnavailableError,
    HttpGatewayTimeoutError,
    HttpConnectionError,
    HttpTimeoutError,
    HttpRedirectError,
    HttpProtocolError,
    HttpRequestError,
    HttpDecodeError,
    map_status_to_error,
)


class TestHierarchy:
    """All HTTP exceptions descend from HttpTransportError."""

    @pytest.mark.parametrize("cls", [
        HttpResponseError,
        HttpClientError,
        HttpServerError,
        HttpNotFoundError,
        HttpAuthenticationError,
        HttpForbiddenError,
        HttpRateLimitError,
        HttpConflictError,
        HttpBadGatewayError,
        HttpServiceUnavailableError,
        HttpGatewayTimeoutError,
        HttpConnectionError,
        HttpTimeoutError,
        HttpRedirectError,
        HttpProtocolError,
        HttpRequestError,
        HttpDecodeError,
    ])
    def test_is_subclass_of_base(self, cls):
        assert issubclass(cls, HttpTransportError)

    def test_client_error_is_response_error(self):
        assert issubclass(HttpClientError, HttpResponseError)

    def test_server_error_is_response_error(self):
        assert issubclass(HttpServerError, HttpResponseError)

    def test_not_found_is_client_error(self):
        assert issubclass(HttpNotFoundError, HttpClientError)

    def test_rate_limit_is_client_error(self):
        assert issubclass(HttpRateLimitError, HttpClientError)

    def test_bad_gateway_is_server_error(self):
        assert issubclass(HttpBadGatewayError, HttpServerError)


class TestHttpResponseErrorContext:
    """HttpResponseError carries request/response context."""

    def test_carries_all_fields(self):
        err = HttpResponseError(
            status_code=418,
            headers={"X-Teapot": "yes"},
            body_preview="I'm a teapot",
            url="https://example.com/brew",
            method="GET",
        )
        assert err.status_code == 418
        assert err.headers == {"X-Teapot": "yes"}
        assert err.body_preview == "I'm a teapot"
        assert err.url == "https://example.com/brew"
        assert err.method == "GET"

    def test_str_includes_status_and_url(self):
        err = HttpResponseError(
            status_code=500,
            headers={},
            body_preview="",
            url="https://example.com/fail",
            method="POST",
        )
        msg = str(err)
        assert "500" in msg
        assert "https://example.com/fail" in msg


class TestHttpRateLimitError:
    """HttpRateLimitError parses Retry-After."""

    def test_retry_after_delta_seconds(self):
        err = HttpRateLimitError(
            headers={"Retry-After": "30"},
            body_preview="",
            url="https://example.com/api",
            method="GET",
            retry_after=30.0,
        )
        assert err.retry_after == 30.0
        assert err.status_code == 429

    def test_retry_after_none_when_absent(self):
        err = HttpRateLimitError(
            headers={},
            body_preview="",
            url="https://example.com/api",
            method="GET",
            retry_after=None,
        )
        assert err.retry_after is None

    def test_negative_retry_after_clamped_to_zero(self):
        err = HttpRateLimitError(
            headers={"Retry-After": "-5"},
            body_preview="",
            url="https://example.com/api",
            method="GET",
            retry_after=0.0,
        )
        assert err.retry_after == 0.0


class TestStatusCodeMapping:
    """map_status_to_error returns the correct exception class."""

    @pytest.mark.parametrize("status,expected_cls", [
        (401, HttpAuthenticationError),
        (403, HttpForbiddenError),
        (404, HttpNotFoundError),
        (409, HttpConflictError),
        (429, HttpRateLimitError),
        (502, HttpBadGatewayError),
        (503, HttpServiceUnavailableError),
        (504, HttpGatewayTimeoutError),
    ])
    def test_mapped_codes(self, status, expected_cls):
        assert map_status_to_error(status) is expected_cls

    def test_unmapped_4xx_returns_client_error(self):
        assert map_status_to_error(422) is HttpClientError

    def test_unmapped_5xx_returns_server_error(self):
        assert map_status_to_error(501) is HttpServerError
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
hatch run test:test tests/_core/http/test_errors.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'mountainash_transport._core.http.errors'`

- [ ] **Step 4: Implement the error hierarchy**

Create `src/mountainash_transport/_core/http/errors.py`:

```python
"""HTTP transport error hierarchy.

Independent of StorageError — consumers map between the two hierarchies.
"""
from __future__ import annotations

import typing as t

_STATUS_MAP: dict[int, type[HttpResponseError]] = {}


class HttpTransportError(Exception):
    """Base exception for all HTTP transport errors."""


class HttpResponseError(HttpTransportError):
    """HTTP response indicated an error (4xx/5xx)."""

    def __init__(
        self,
        *,
        status_code: int,
        headers: dict[str, str],
        body_preview: str,
        url: str,
        method: str,
        **kwargs: t.Any,
    ) -> None:
        self.status_code = status_code
        self.headers = headers
        self.body_preview = body_preview
        self.url = url
        self.method = method
        super().__init__(f"{method} {url} -> {status_code}")


class HttpClientError(HttpResponseError):
    """4xx client error."""


class HttpNotFoundError(HttpClientError):
    """404 Not Found."""


class HttpAuthenticationError(HttpClientError):
    """401 Unauthorized."""


class HttpForbiddenError(HttpClientError):
    """403 Forbidden."""


class HttpRateLimitError(HttpClientError):
    """429 Too Many Requests."""

    def __init__(
        self,
        *,
        retry_after: float | None,
        **kwargs: t.Any,
    ) -> None:
        self.retry_after = retry_after
        kwargs.setdefault("status_code", 429)
        super().__init__(**kwargs)


class HttpConflictError(HttpClientError):
    """409 Conflict."""


class HttpServerError(HttpResponseError):
    """5xx server error."""


class HttpBadGatewayError(HttpServerError):
    """502 Bad Gateway."""


class HttpServiceUnavailableError(HttpServerError):
    """503 Service Unavailable."""


class HttpGatewayTimeoutError(HttpServerError):
    """504 Gateway Timeout."""


class HttpConnectionError(HttpTransportError):
    """Transport-level connection failure (DNS, TCP, TLS, proxy)."""


class HttpTimeoutError(HttpTransportError):
    """Request timed out (connect, read, write, pool)."""


class HttpRedirectError(HttpTransportError):
    """Unhandled redirect or too many redirects."""


class HttpProtocolError(HttpTransportError):
    """HTTP protocol violation (framing, decoding)."""


class HttpRequestError(HttpTransportError):
    """Invalid request (bad URL, unsupported protocol)."""


class HttpDecodeError(HttpTransportError):
    """Response body decode failure (JSON parse, encoding)."""


_STATUS_MAP = {
    401: HttpAuthenticationError,
    403: HttpForbiddenError,
    404: HttpNotFoundError,
    409: HttpConflictError,
    429: HttpRateLimitError,
    502: HttpBadGatewayError,
    503: HttpServiceUnavailableError,
    504: HttpGatewayTimeoutError,
}


def map_status_to_error(status_code: int) -> type[HttpResponseError]:
    """Return the exception class for a given HTTP status code."""
    if status_code in _STATUS_MAP:
        return _STATUS_MAP[status_code]
    if 400 <= status_code < 500:
        return HttpClientError
    if 500 <= status_code < 600:
        return HttpServerError
    return HttpResponseError
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
hatch run test:test tests/_core/http/test_errors.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/_core/http/ tests/_core/http/
git rm src/mountainash_transport/_core/http.py 2>/dev/null || true
git commit -m "feat: add HTTP transport error hierarchy in _core/http/errors.py"
```

---

### Task 2: Request Policy

**Files:**
- Create: `src/mountainash_transport/_core/http/policy.py`
- Test: `tests/_core/http/test_policy.py`

- [ ] **Step 1: Write failing tests for policy dataclasses**

Create `tests/_core/http/test_policy.py`:

```python
"""Tests for HTTP request policy configuration."""
from __future__ import annotations

import dataclasses

import pytest

from mountainash_transport._core.http.policy import (
    RetryPolicy,
    TimeoutPolicy,
    RedirectPolicy,
    RequestPolicy,
    SAFE_METHODS,
    IDEMPOTENT_METHODS,
)


class TestRetryPolicy:
    def test_defaults(self):
        p = RetryPolicy()
        assert p.max_attempts == 3
        assert p.backoff_base == 1.0
        assert p.backoff_max == 60.0
        assert p.backoff_jitter is True
        assert p.retry_on_status == (429, 500, 502, 503, 504)
        assert p.retry_on_transport is True
        assert p.retry_unsafe_methods is False
        assert p.max_retry_after == 120.0

    def test_frozen(self):
        p = RetryPolicy()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.max_attempts = 5  # type: ignore[misc]


class TestTimeoutPolicy:
    def test_defaults(self):
        p = TimeoutPolicy()
        assert p.connect == 10.0
        assert p.read == 30.0
        assert p.write == 30.0
        assert p.pool == 10.0

    def test_frozen(self):
        p = TimeoutPolicy()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.connect = 5.0  # type: ignore[misc]


class TestRedirectPolicy:
    def test_defaults(self):
        p = RedirectPolicy()
        assert p.follow_redirects is True
        assert p.max_redirects == 10

    def test_frozen(self):
        p = RedirectPolicy()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.follow_redirects = False  # type: ignore[misc]


class TestRequestPolicy:
    def test_defaults(self):
        p = RequestPolicy()
        assert isinstance(p.retry, RetryPolicy)
        assert isinstance(p.timeout, TimeoutPolicy)
        assert isinstance(p.redirect, RedirectPolicy)
        assert p.auth_refresh_on_401 is True

    def test_frozen(self):
        p = RequestPolicy()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.auth_refresh_on_401 = False  # type: ignore[misc]

    def test_with_timeout(self):
        original = RequestPolicy()
        new_timeout = TimeoutPolicy(connect=5.0, read=60.0, write=60.0, pool=5.0)
        updated = original.with_timeout(new_timeout)
        assert updated.timeout is new_timeout
        assert updated.retry is original.retry
        assert updated.redirect is original.redirect
        assert updated is not original

    def test_with_retry(self):
        original = RequestPolicy()
        new_retry = RetryPolicy(max_attempts=5)
        updated = original.with_retry(new_retry)
        assert updated.retry is new_retry
        assert updated.timeout is original.timeout
        assert updated is not original

    def test_with_redirect(self):
        original = RequestPolicy()
        new_redirect = RedirectPolicy(follow_redirects=False)
        updated = original.with_redirect(new_redirect)
        assert updated.redirect is new_redirect
        assert updated.timeout is original.timeout
        assert updated is not original


class TestMethodConstants:
    def test_safe_methods(self):
        assert SAFE_METHODS == frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

    def test_idempotent_methods(self):
        assert IDEMPOTENT_METHODS == SAFE_METHODS | frozenset({"PUT", "DELETE"})

    def test_post_not_idempotent(self):
        assert "POST" not in IDEMPOTENT_METHODS

    def test_patch_not_idempotent(self):
        assert "PATCH" not in IDEMPOTENT_METHODS
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
hatch run test:test tests/_core/http/test_policy.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the policy module**

Create `src/mountainash_transport/_core/http/policy.py`:

```python
"""HTTP request policy — immutable configuration for retry, timeout, and redirect behavior."""
from __future__ import annotations

from dataclasses import dataclass, field

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
IDEMPOTENT_METHODS = SAFE_METHODS | frozenset({"PUT", "DELETE"})


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 60.0
    backoff_jitter: bool = True
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_on_transport: bool = True
    retry_unsafe_methods: bool = False
    max_retry_after: float = 120.0


@dataclass(frozen=True)
class TimeoutPolicy:
    connect: float = 10.0
    read: float = 30.0
    write: float = 30.0
    pool: float = 10.0


@dataclass(frozen=True)
class RedirectPolicy:
    follow_redirects: bool = True
    max_redirects: int = 10


@dataclass(frozen=True)
class RequestPolicy:
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    redirect: RedirectPolicy = field(default_factory=RedirectPolicy)
    auth_refresh_on_401: bool = True

    def with_timeout(self, timeout: TimeoutPolicy) -> RequestPolicy:
        return RequestPolicy(
            retry=self.retry,
            timeout=timeout,
            redirect=self.redirect,
            auth_refresh_on_401=self.auth_refresh_on_401,
        )

    def with_retry(self, retry: RetryPolicy) -> RequestPolicy:
        return RequestPolicy(
            retry=retry,
            timeout=self.timeout,
            redirect=self.redirect,
            auth_refresh_on_401=self.auth_refresh_on_401,
        )

    def with_redirect(self, redirect: RedirectPolicy) -> RequestPolicy:
        return RequestPolicy(
            retry=self.retry,
            timeout=self.timeout,
            redirect=redirect,
            auth_refresh_on_401=self.auth_refresh_on_401,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
hatch run test:test tests/_core/http/test_policy.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/_core/http/policy.py tests/_core/http/test_policy.py
git commit -m "feat: add HTTP request policy dataclasses"
```

---

### Task 3: HttpResponse and HttpStreamResponse

**Files:**
- Create: `src/mountainash_transport/_core/http/response.py`
- Test: `tests/_core/http/test_response.py`

- [ ] **Step 1: Write failing tests for response types**

Create `tests/_core/http/test_response.py`:

```python
"""Tests for HTTP response types."""
from __future__ import annotations

import dataclasses
import json
from unittest.mock import MagicMock

import pytest

from mountainash_transport._core.http.errors import HttpDecodeError
from mountainash_transport._core.http.response import HttpResponse, HttpStreamResponse


class TestHttpResponse:
    def test_frozen(self):
        r = HttpResponse(
            status_code=200, headers={}, content=b"ok", url="https://x.com", method="GET",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.status_code = 201  # type: ignore[misc]

    def test_text_decodes_utf8(self):
        r = HttpResponse(
            status_code=200, headers={}, content="héllo".encode(), url="https://x.com", method="GET",
        )
        assert r.text == "héllo"

    def test_json_parses(self):
        payload = {"key": "value"}
        r = HttpResponse(
            status_code=200, headers={}, content=json.dumps(payload).encode(),
            url="https://x.com", method="GET",
        )
        assert r.json() == payload

    def test_json_raises_decode_error_on_invalid(self):
        r = HttpResponse(
            status_code=200, headers={}, content=b"not json",
            url="https://x.com", method="GET",
        )
        with pytest.raises(HttpDecodeError):
            r.json()

    def test_fields_accessible(self):
        r = HttpResponse(
            status_code=201, headers={"X-Id": "abc"}, content=b"body",
            url="https://x.com/res", method="POST",
        )
        assert r.status_code == 201
        assert r.headers == {"X-Id": "abc"}
        assert r.content == b"body"
        assert r.url == "https://x.com/res"
        assert r.method == "POST"


class TestHttpStreamResponse:
    def _make_stream_response(self, chunks: list[bytes]) -> HttpStreamResponse:
        mock_httpx_response = MagicMock()
        mock_httpx_response.status_code = 200
        mock_httpx_response.headers = {}
        mock_httpx_response.url = "https://x.com/big"
        mock_httpx_response.request.method = "GET"
        mock_httpx_response.iter_bytes.return_value = iter(chunks)
        mock_httpx_response.iter_text.return_value = iter([c.decode() for c in chunks])
        mock_httpx_response.read.return_value = b"".join(chunks)
        return HttpStreamResponse(mock_httpx_response)

    def test_iter_bytes(self):
        resp = self._make_stream_response([b"chunk1", b"chunk2"])
        assert list(resp.iter_bytes()) == [b"chunk1", b"chunk2"]

    def test_iter_text(self):
        resp = self._make_stream_response([b"hello", b" world"])
        assert list(resp.iter_text()) == ["hello", " world"]

    def test_read_buffers_all(self):
        resp = self._make_stream_response([b"a", b"b", b"c"])
        assert resp.read() == b"abc"

    def test_close(self):
        resp = self._make_stream_response([b"data"])
        resp.close()
        resp._response.close.assert_called_once()

    def test_headers_accessible(self):
        resp = self._make_stream_response([b"data"])
        assert resp.status_code == 200
        assert resp.url == "https://x.com/big"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
hatch run test:test tests/_core/http/test_response.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement response types**

Create `src/mountainash_transport/_core/http/response.py`:

```python
"""HTTP response types — clean boundary, no httpx dependency for consumers."""
from __future__ import annotations

import json
import typing as t
from dataclasses import dataclass

from mountainash_transport._core.http.errors import HttpDecodeError

if t.TYPE_CHECKING:
    import httpx


@dataclass(frozen=True)
class HttpResponse:
    """Buffered HTTP response."""

    status_code: int
    headers: dict[str, str]
    content: bytes
    url: str
    method: str

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def json(self) -> t.Any:
        """Parse content as JSON. Raises HttpDecodeError on failure."""
        try:
            return json.loads(self.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HttpDecodeError(f"Failed to decode JSON from {self.url}: {exc}") from exc


class HttpStreamResponse:
    """Streaming HTTP response — wraps an httpx streaming response."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._response.headers)

    @property
    def url(self) -> str:
        return str(self._response.url)

    @property
    def method(self) -> str:
        return self._response.request.method

    def iter_bytes(self, chunk_size: int = 65536) -> t.Iterator[bytes]:
        return self._response.iter_bytes(chunk_size=chunk_size)

    def iter_text(self, chunk_size: int = 65536) -> t.Iterator[str]:
        return self._response.iter_text(chunk_size=chunk_size)

    def read(self) -> bytes:
        return self._response.read()

    def close(self) -> None:
        self._response.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
hatch run test:test tests/_core/http/test_response.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/_core/http/response.py tests/_core/http/test_response.py
git commit -m "feat: add HttpResponse and HttpStreamResponse types"
```

---

### Task 4: RefreshableAuthStrategy Protocol

**Files:**
- Modify: `src/mountainash_transport/_core/auth/strategies.py` (add after line 18)
- Test: `tests/_core/auth/test_auth_strategies.py` (extend)

- [ ] **Step 1: Write failing tests for RefreshableAuthStrategy**

Append to `tests/_core/auth/test_auth_strategies.py`:

```python
from mountainash_transport._core.auth.strategies import RefreshableAuthStrategy


class TestRefreshableAuthStrategy:
    def test_is_runtime_checkable(self):
        assert hasattr(RefreshableAuthStrategy, "__protocol_attrs__") or hasattr(
            RefreshableAuthStrategy, "__abstractmethods__"
        )

    def test_regular_strategy_is_not_refreshable(self):
        from mountainash_transport._core.auth.strategies import BearerTokenStrategy
        strategy = BearerTokenStrategy(token="abc")
        assert not isinstance(strategy, RefreshableAuthStrategy)

    def test_concrete_refreshable_detected(self):
        class _MockRefreshable:
            def apply(self, kwargs):
                return kwargs
            def get_headers(self):
                return {"Authorization": "Bearer new"}
            def refresh(self):
                return True

        strategy = _MockRefreshable()
        assert isinstance(strategy, RefreshableAuthStrategy)

    def test_get_headers_contract(self):
        class _MockRefreshable:
            def __init__(self):
                self._token = "old"
            def apply(self, kwargs):
                return kwargs
            def get_headers(self):
                return {"Authorization": f"Bearer {self._token}"}
            def refresh(self):
                self._token = "new"
                return True

        strategy = _MockRefreshable()
        assert strategy.get_headers() == {"Authorization": "Bearer old"}
        strategy.refresh()
        assert strategy.get_headers() == {"Authorization": "Bearer new"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
hatch run test:test tests/_core/auth/test_auth_strategies.py::TestRefreshableAuthStrategy -v
```

Expected: FAIL — `ImportError: cannot import name 'RefreshableAuthStrategy'`

- [ ] **Step 3: Add the RefreshableAuthStrategy protocol**

In `src/mountainash_transport/_core/auth/strategies.py`, add after the `AuthStrategy` protocol (after line 18):

```python
@runtime_checkable
class RefreshableAuthStrategy(AuthStrategy, Protocol):
    """Auth strategy that supports credential refresh.

    After a successful refresh(), subsequent get_headers() calls must
    return headers reflecting the new credentials.

    Implementations must be internally synchronized — concurrent
    refresh() calls must not corrupt state.
    """

    def refresh(self) -> bool: ...

    def get_headers(self) -> dict[str, str]: ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
hatch run test:test tests/_core/auth/test_auth_strategies.py -v
```

Expected: All PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/_core/auth/strategies.py tests/_core/auth/test_auth_strategies.py
git commit -m "feat: add RefreshableAuthStrategy protocol"
```

---

### Task 5: Request Engine — Core Request Lifecycle

**Files:**
- Create: `src/mountainash_transport/_core/http/engine.py`
- Test: `tests/_core/http/test_engine.py`

This is the largest task. The engine implements: httpx exception mapping, status-code error raising, retry with backoff/jitter, body replayability checks, method-safety-aware retry, per-request policy override, redirect error handling, and auth refresh.

- [ ] **Step 1: Write failing tests for the engine**

Create `tests/_core/http/test_engine.py`:

```python
"""Tests for HttpRequestEngine."""
from __future__ import annotations

import io
import typing as t
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError,
    HttpBadGatewayError,
    HttpConnectionError,
    HttpForbiddenError,
    HttpNotFoundError,
    HttpRateLimitError,
    HttpRedirectError,
    HttpRequestError,
    HttpProtocolError,
    HttpServerError,
    HttpServiceUnavailableError,
    HttpTimeoutError,
    HttpTransportError,
)
from mountainash_transport._core.http.policy import (
    IDEMPOTENT_METHODS,
    RequestPolicy,
    RetryPolicy,
    TimeoutPolicy,
)
from mountainash_transport._core.http.response import HttpResponse


def _mock_client(*responses: httpx.Response) -> httpx.Client:
    """Create a mock httpx.Client that returns responses in sequence."""
    call_count = 0
    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return responses[idx]
    return httpx.Client(transport=httpx.MockTransport(_handler))


def _error_client(exc: Exception) -> httpx.Client:
    """Create a mock client that always raises the given exception."""
    def _handler(request: httpx.Request) -> httpx.Response:
        raise exc
    return httpx.Client(transport=httpx.MockTransport(_handler))


def _sequenced_client(sequence: list[httpx.Response | Exception]) -> httpx.Client:
    """Client that returns responses or raises exceptions in order."""
    call_count = 0
    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        idx = min(call_count, len(sequence) - 1)
        call_count += 1
        item = sequence[idx]
        if isinstance(item, Exception):
            raise item
        return item
    return httpx.Client(transport=httpx.MockTransport(_handler))


class TestHappyPath:
    def test_200_returns_http_response(self):
        client = _mock_client(httpx.Response(200, content=b"ok"))
        engine = HttpRequestEngine(client)
        resp = engine.request("GET", "https://example.com/")
        assert isinstance(resp, HttpResponse)
        assert resp.status_code == 200
        assert resp.content == b"ok"

    def test_201_returns_http_response(self):
        client = _mock_client(httpx.Response(201, content=b"created"))
        engine = HttpRequestEngine(client)
        resp = engine.request("POST", "https://example.com/res")
        assert resp.status_code == 201


class TestStatusCodeErrors:
    def test_404_raises_not_found(self):
        client = _mock_client(httpx.Response(404))
        engine = HttpRequestEngine(client, policy=RequestPolicy(retry=RetryPolicy(max_attempts=1)))
        with pytest.raises(HttpNotFoundError) as exc_info:
            engine.request("GET", "https://example.com/missing")
        assert exc_info.value.status_code == 404

    def test_401_raises_auth_error_no_refresh(self):
        client = _mock_client(httpx.Response(401))
        engine = HttpRequestEngine(client, policy=RequestPolicy(retry=RetryPolicy(max_attempts=1)))
        with pytest.raises(HttpAuthenticationError):
            engine.request("GET", "https://example.com/secret")

    def test_403_raises_forbidden(self):
        client = _mock_client(httpx.Response(403))
        engine = HttpRequestEngine(client, policy=RequestPolicy(retry=RetryPolicy(max_attempts=1)))
        with pytest.raises(HttpForbiddenError):
            engine.request("GET", "https://example.com/forbidden")

    def test_unmapped_4xx_raises_client_error(self):
        client = _mock_client(httpx.Response(422))
        engine = HttpRequestEngine(client, policy=RequestPolicy(retry=RetryPolicy(max_attempts=1)))
        from mountainash_transport._core.http.errors import HttpClientError
        with pytest.raises(HttpClientError) as exc_info:
            engine.request("GET", "https://example.com/invalid")
        assert exc_info.value.status_code == 422

    def test_unmapped_5xx_raises_server_error(self):
        client = _mock_client(httpx.Response(501))
        engine = HttpRequestEngine(client, policy=RequestPolicy(retry=RetryPolicy(max_attempts=1)))
        with pytest.raises(HttpServerError) as exc_info:
            engine.request("GET", "https://example.com/error")
        assert exc_info.value.status_code == 501


class TestRetry:
    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_retries_on_5xx_then_succeeds(self, mock_sleep):
        client = _mock_client(
            httpx.Response(503),
            httpx.Response(200, content=b"ok"),
        )
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
        ))
        resp = engine.request("GET", "https://example.com/")
        assert resp.status_code == 200
        assert mock_sleep.call_count == 1

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_retry_exhaustion_raises(self, mock_sleep):
        client = _mock_client(
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(503),
        )
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
        ))
        with pytest.raises(HttpServiceUnavailableError):
            engine.request("GET", "https://example.com/")

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_no_retry_for_post_by_default(self, mock_sleep):
        client = _mock_client(httpx.Response(503))
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3),
        ))
        with pytest.raises(HttpServiceUnavailableError):
            engine.request("POST", "https://example.com/")
        mock_sleep.assert_not_called()

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_retry_unsafe_methods_flag(self, mock_sleep):
        client = _mock_client(
            httpx.Response(503),
            httpx.Response(200, content=b"ok"),
        )
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, retry_unsafe_methods=True, backoff_jitter=False),
        ))
        resp = engine.request("POST", "https://example.com/")
        assert resp.status_code == 200

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_backoff_cap(self, mock_sleep):
        client = _mock_client(
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, content=b"ok"),
        )
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(
                max_attempts=5, backoff_base=10.0, backoff_max=25.0, backoff_jitter=False,
            ),
        ))
        engine.request("GET", "https://example.com/")
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert all(d <= 25.0 for d in delays)

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_transport_error_retried(self, mock_sleep):
        client = _sequenced_client([
            httpx.ConnectError("fail"),
            httpx.Response(200, content=b"ok"),
        ])
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
        ))
        resp = engine.request("GET", "https://example.com/")
        assert resp.status_code == 200


class TestBodyReplayability:
    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_seekable_stream_rewound_on_retry(self, mock_sleep):
        positions: list[int] = []
        def _handler(request: httpx.Request) -> httpx.Response:
            positions.append(0)  # track call count
            if len(positions) == 1:
                return httpx.Response(503)
            return httpx.Response(200, content=b"ok")
        client = httpx.Client(transport=httpx.MockTransport(_handler))
        body = io.BytesIO(b"upload data")
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
        ))
        resp = engine.request("PUT", "https://example.com/upload", stream=body)
        assert resp.status_code == 200

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_non_seekable_stream_not_retried_on_5xx(self, mock_sleep):
        client = _mock_client(httpx.Response(503))
        body = MagicMock(spec=["read"])
        body.read.return_value = b"data"
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3),
        ))
        with pytest.raises(HttpServiceUnavailableError):
            engine.request("PUT", "https://example.com/upload", stream=body)
        mock_sleep.assert_not_called()

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_bytes_body_always_replayable(self, mock_sleep):
        client = _mock_client(
            httpx.Response(503),
            httpx.Response(200, content=b"ok"),
        )
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, retry_unsafe_methods=True, backoff_jitter=False),
        ))
        resp = engine.request("POST", "https://example.com/", content=b"body")
        assert resp.status_code == 200


class TestRateLimitRetry:
    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_429_with_retry_after(self, mock_sleep):
        client = _mock_client(
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, content=b"ok"),
        )
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
        ))
        resp = engine.request("GET", "https://example.com/")
        assert resp.status_code == 200
        mock_sleep.assert_called_once_with(2.0)

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_429_retry_after_capped(self, mock_sleep):
        client = _mock_client(
            httpx.Response(429, headers={"Retry-After": "999"}),
            httpx.Response(200, content=b"ok"),
        )
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, max_retry_after=10.0, backoff_jitter=False),
        ))
        engine.request("GET", "https://example.com/")
        mock_sleep.assert_called_once_with(10.0)

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_429_retries_post_regardless_of_method_safety(self, mock_sleep):
        client = _mock_client(
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, content=b"ok"),
        )
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3, retry_unsafe_methods=False, backoff_jitter=False),
        ))
        resp = engine.request("POST", "https://example.com/")
        assert resp.status_code == 200


class TestAuthRefresh:
    def _make_refreshable(self, success: bool = True):
        from mountainash_transport._core.auth.strategies import RefreshableAuthStrategy
        mock = MagicMock(spec=RefreshableAuthStrategy)
        mock.refresh.return_value = success
        mock.get_headers.return_value = {"Authorization": "Bearer refreshed"}
        mock.apply.return_value = {}
        return mock

    def test_401_triggers_refresh_and_retry(self):
        client = _mock_client(
            httpx.Response(401),
            httpx.Response(200, content=b"ok"),
        )
        auth = self._make_refreshable(success=True)
        engine = HttpRequestEngine(client, auth_strategy=auth)
        resp = engine.request("GET", "https://example.com/")
        assert resp.status_code == 200
        auth.refresh.assert_called_once()

    def test_401_refresh_fails_raises(self):
        client = _mock_client(httpx.Response(401))
        auth = self._make_refreshable(success=False)
        engine = HttpRequestEngine(client, auth_strategy=auth)
        with pytest.raises(HttpAuthenticationError):
            engine.request("GET", "https://example.com/")

    def test_401_after_refresh_still_401_raises(self):
        client = _mock_client(
            httpx.Response(401),
            httpx.Response(401),
        )
        auth = self._make_refreshable(success=True)
        engine = HttpRequestEngine(client, auth_strategy=auth)
        with pytest.raises(HttpAuthenticationError):
            engine.request("GET", "https://example.com/")
        assert auth.refresh.call_count == 1

    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_auth_refresh_not_counted_against_max_attempts(self, mock_sleep):
        client = _mock_client(
            httpx.Response(401),
            httpx.Response(503),
            httpx.Response(200, content=b"ok"),
        )
        auth = self._make_refreshable(success=True)
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=2, backoff_jitter=False),
        ), auth_strategy=auth)
        resp = engine.request("GET", "https://example.com/")
        assert resp.status_code == 200

    def test_401_retries_post_regardless_of_method_safety(self):
        client = _mock_client(
            httpx.Response(401),
            httpx.Response(200, content=b"ok"),
        )
        auth = self._make_refreshable(success=True)
        engine = HttpRequestEngine(client, auth_strategy=auth, policy=RequestPolicy(
            retry=RetryPolicy(retry_unsafe_methods=False),
        ))
        resp = engine.request("POST", "https://example.com/")
        assert resp.status_code == 200


class TestRedirects:
    def test_3xx_with_redirects_disabled_raises(self):
        client = _mock_client(httpx.Response(302, headers={"Location": "/other"}))
        policy = RequestPolicy(retry=RetryPolicy(max_attempts=1))
        engine = HttpRequestEngine(
            httpx.Client(
                transport=httpx.MockTransport(lambda r: httpx.Response(302, headers={"Location": "/other"})),
                follow_redirects=False,
            ),
            policy=policy,
        )
        with pytest.raises(HttpRedirectError):
            engine.request("GET", "https://example.com/old")


class TestHttpxExceptionMapping:
    @pytest.mark.parametrize("httpx_exc,expected_cls", [
        (httpx.ConnectError("fail"), HttpConnectionError),
        (httpx.ConnectTimeout("timeout"), HttpTimeoutError),
        (httpx.ReadTimeout("timeout"), HttpTimeoutError),
        (httpx.WriteTimeout("timeout"), HttpTimeoutError),
        (httpx.PoolTimeout("timeout"), HttpTimeoutError),
        (httpx.ProtocolError("bad frame"), HttpProtocolError),
        (httpx.DecodingError("bad encoding"), HttpProtocolError),
        (httpx.ProxyError("proxy fail"), HttpConnectionError),
        (httpx.UnsupportedProtocol("ftp://"), HttpRequestError),
        (httpx.InvalidURL("not a url"), HttpRequestError),
    ])
    def test_maps_httpx_exception(self, httpx_exc, expected_cls):
        client = _error_client(httpx_exc)
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=1, retry_on_transport=False),
        ))
        with pytest.raises(expected_cls):
            engine.request("GET", "https://example.com/")


class TestPerRequestPolicy:
    @patch("mountainash_transport._core.http.engine.time.sleep")
    def test_override_policy_used(self, mock_sleep):
        client = _mock_client(httpx.Response(503), httpx.Response(503))
        engine = HttpRequestEngine(client, policy=RequestPolicy(
            retry=RetryPolicy(max_attempts=3),
        ))
        override = RequestPolicy(retry=RetryPolicy(max_attempts=1))
        with pytest.raises(HttpServiceUnavailableError):
            engine.request("GET", "https://example.com/", policy=override)

    def test_policy_property(self):
        policy = RequestPolicy(retry=RetryPolicy(max_attempts=5))
        engine = HttpRequestEngine(_mock_client(httpx.Response(200)), policy=policy)
        assert engine.policy is policy


class TestHeaderPrecedence:
    def test_auth_headers_overridden_by_caller(self):
        captured_headers: dict[str, str] = {}
        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200)
        client = httpx.Client(transport=httpx.MockTransport(_handler))
        from mountainash_transport._core.auth.strategies import RefreshableAuthStrategy
        auth = MagicMock(spec=RefreshableAuthStrategy)
        auth.get_headers.return_value = {"Authorization": "Bearer from-auth"}
        auth.apply.return_value = {}
        engine = HttpRequestEngine(client, auth_strategy=auth)
        engine.request("GET", "https://example.com/", headers={"Authorization": "Bearer override"})
        assert captured_headers["authorization"] == "Bearer override"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
hatch run test:test tests/_core/http/test_engine.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'mountainash_transport._core.http.engine'`

- [ ] **Step 3: Implement the request engine**

Create `src/mountainash_transport/_core/http/engine.py`:

```python
"""HttpRequestEngine — single-request lifecycle with retry, auth refresh, and error mapping."""
from __future__ import annotations

import contextlib
import random
import time
import typing as t

import httpx

from mountainash_transport._core.auth.strategies import AuthStrategy, RefreshableAuthStrategy
from mountainash_transport._core.http.errors import (
    HttpConnectionError,
    HttpProtocolError,
    HttpRedirectError,
    HttpRequestError,
    HttpTimeoutError,
    HttpTransportError,
    map_status_to_error,
    HttpRateLimitError,
    HttpResponseError,
)
from mountainash_transport._core.http.policy import (
    IDEMPOTENT_METHODS,
    RequestPolicy,
)
from mountainash_transport._core.http.response import HttpResponse, HttpStreamResponse

_HTTPX_EXCEPTION_MAP: list[tuple[type[httpx.HTTPError], type[HttpTransportError]]] = [
    (httpx.ConnectTimeout, HttpTimeoutError),
    (httpx.ReadTimeout, HttpTimeoutError),
    (httpx.WriteTimeout, HttpTimeoutError),
    (httpx.PoolTimeout, HttpTimeoutError),
    (httpx.TooManyRedirects, HttpRedirectError),
    (httpx.ProxyError, HttpConnectionError),
    (httpx.ConnectError, HttpConnectionError),
    (httpx.ProtocolError, HttpProtocolError),
    (httpx.DecodingError, HttpProtocolError),
    (httpx.UnsupportedProtocol, HttpRequestError),
    (httpx.InvalidURL, HttpRequestError),
    (httpx.StreamError, HttpConnectionError),
]

_BODY_PREVIEW_MAX = 512


def _parse_retry_after(headers: dict[str, str]) -> float | None:
    """Parse Retry-After header into seconds. Returns None if absent."""
    value = headers.get("retry-after") or headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
        return max(seconds, 0.0)
    except ValueError:
        pass
    # Try HTTP-date format
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(value)
        import datetime
        delta = (dt - datetime.datetime.now(tz=datetime.timezone.utc)).total_seconds()
        return max(delta, 0.0)
    except (ValueError, TypeError):
        return None


def _is_body_replayable(content: bytes | None, stream: t.BinaryIO | None) -> bool:
    if stream is None:
        return True
    return hasattr(stream, "seek")


def _rewind_body(stream: t.BinaryIO | None) -> None:
    if stream is not None and hasattr(stream, "seek"):
        stream.seek(0)


def _map_httpx_exception(exc: httpx.HTTPError) -> HttpTransportError:
    for httpx_cls, transport_cls in _HTTPX_EXCEPTION_MAP:
        if isinstance(exc, httpx_cls):
            return transport_cls(str(exc))
    return HttpTransportError(str(exc))


def _is_retryable_transport_error(exc: HttpTransportError) -> bool:
    return isinstance(exc, (HttpConnectionError, HttpTimeoutError))


def _build_response_error(
    response: httpx.Response, method: str,
) -> HttpResponseError:
    status = response.status_code
    headers = dict(response.headers)
    try:
        body_preview = response.text[:_BODY_PREVIEW_MAX]
    except Exception:
        body_preview = ""
    url = str(response.url)

    error_cls = map_status_to_error(status)

    kwargs: dict[str, t.Any] = {
        "status_code": status,
        "headers": headers,
        "body_preview": body_preview,
        "url": url,
        "method": method,
    }

    if error_cls is HttpRateLimitError:
        retry_after = _parse_retry_after(headers)
        kwargs["retry_after"] = retry_after

    return error_cls(**kwargs)


class HttpRequestEngine:
    """Execute HTTP requests with retry, auth refresh, and error mapping."""

    def __init__(
        self,
        client: httpx.Client,
        policy: RequestPolicy | None = None,
        auth_strategy: AuthStrategy | None = None,
    ) -> None:
        self._client = client
        self._policy = policy or RequestPolicy()
        self._auth_strategy = auth_strategy

    @property
    def policy(self) -> RequestPolicy:
        return self._policy

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        stream: t.BinaryIO | None = None,
        params: dict[str, str] | None = None,
        policy: RequestPolicy | None = None,
    ) -> HttpResponse:
        effective_policy = policy or self._policy
        replayable = _is_body_replayable(content, stream)

        body: bytes | None
        if stream is not None:
            body = stream.read()
            if hasattr(stream, "seek"):
                stream.seek(0)
        else:
            body = content

        response = self._execute(
            method=method,
            url=url,
            headers=headers,
            content=body,
            original_stream=stream,
            replayable=replayable,
            params=params,
            policy=effective_policy,
        )
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            url=str(response.url),
            method=method,
        )

    @contextlib.contextmanager
    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        params: dict[str, str] | None = None,
        policy: RequestPolicy | None = None,
    ) -> t.Iterator[HttpStreamResponse]:
        effective_policy = policy or self._policy
        timeout = httpx.Timeout(
            connect=effective_policy.timeout.connect,
            read=effective_policy.timeout.read,
            write=effective_policy.timeout.write,
            pool=effective_policy.timeout.pool,
        )

        merged_headers = self._merge_headers(headers)

        try:
            with self._client.stream(
                method,
                url,
                headers=merged_headers,
                content=content,
                params=params,
                timeout=timeout,
            ) as response:
                status = response.status_code
                if 300 <= status < 400:
                    raise HttpRedirectError(
                        f"{method} {url} -> {status} (redirect not followed in stream)"
                    )
                if status >= 400:
                    raise _build_response_error(response, method)
                yield HttpStreamResponse(response)
        except httpx.HTTPError as exc:
            raise _map_httpx_exception(exc) from exc

    def _merge_headers(self, caller_headers: dict[str, str] | None) -> dict[str, str]:
        merged: dict[str, str] = {}
        if isinstance(self._auth_strategy, RefreshableAuthStrategy):
            merged.update(self._auth_strategy.get_headers())
        if caller_headers:
            merged.update(caller_headers)
        return merged

    def _execute(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None,
        content: bytes | None,
        original_stream: t.BinaryIO | None,
        replayable: bool,
        params: dict[str, str] | None,
        policy: RequestPolicy,
    ) -> httpx.Response:
        retry = policy.retry
        timeout = httpx.Timeout(
            connect=policy.timeout.connect,
            read=policy.timeout.read,
            write=policy.timeout.write,
            pool=policy.timeout.pool,
        )

        method_upper = method.upper()
        method_is_idempotent = method_upper in IDEMPOTENT_METHODS
        can_retry = replayable and (method_is_idempotent or retry.retry_unsafe_methods)
        auth_refreshed = False

        for attempt in range(retry.max_attempts):
            merged_headers = self._merge_headers(headers)

            try:
                response = self._client.request(
                    method,
                    url,
                    headers=merged_headers,
                    content=content,
                    params=params,
                    timeout=timeout,
                )
            except httpx.HTTPError as exc:
                transport_err = _map_httpx_exception(exc)
                if (
                    can_retry
                    and retry.retry_on_transport
                    and _is_retryable_transport_error(transport_err)
                    and attempt < retry.max_attempts - 1
                ):
                    self._backoff(attempt, retry)
                    if original_stream is not None:
                        _rewind_body(original_stream)
                    continue
                raise transport_err from exc

            status = response.status_code

            # Auth refresh on 401
            if (
                status == 401
                and policy.auth_refresh_on_401
                and not auth_refreshed
                and isinstance(self._auth_strategy, RefreshableAuthStrategy)
            ):
                if self._auth_strategy.refresh():
                    auth_refreshed = True
                    continue
                raise _build_response_error(response, method)

            # 3xx not followed
            if 300 <= status < 400:
                raise HttpRedirectError(
                    f"{method} {url} -> {status} (redirect not followed)"
                )

            # Retryable status
            if status in retry.retry_on_status and attempt < retry.max_attempts - 1:
                is_429 = status == 429
                # 429 and auth-refresh retries are exempt from method safety check
                if is_429 or can_retry:
                    if is_429:
                        retry_after = _parse_retry_after(dict(response.headers))
                        if retry_after is not None:
                            delay = min(retry_after, retry.max_retry_after)
                            time.sleep(delay)
                        else:
                            self._backoff(attempt, retry)
                    else:
                        self._backoff(attempt, retry)
                    if original_stream is not None:
                        _rewind_body(original_stream)
                    continue

            # Non-retryable error
            if status >= 400:
                raise _build_response_error(response, method)

            return response

        # Exhausted all attempts — raise last error
        raise _build_response_error(response, method)  # type: ignore[possibly-undefined]

    @staticmethod
    def _backoff(attempt: int, retry_policy: t.Any) -> None:
        delay = min(
            retry_policy.backoff_base * (2 ** attempt),
            retry_policy.backoff_max,
        )
        if retry_policy.backoff_jitter:
            delay = random.uniform(0, delay)
        time.sleep(delay)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
hatch run test:test tests/_core/http/test_engine.py -v
```

Expected: All PASS

- [ ] **Step 5: Run the full test suite to verify no regressions**

```bash
hatch run test:test -v
```

Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/_core/http/engine.py tests/_core/http/test_engine.py
git commit -m "feat: add HttpRequestEngine with retry, auth refresh, and error mapping"
```

---

### Task 6: Package Re-exports and Public API

**Files:**
- Modify: `src/mountainash_transport/_core/http/__init__.py`
- Modify: `src/mountainash_transport/__init__.py`
- Test: `tests/test_public_api.py` (extend)

- [ ] **Step 1: Write failing test for public imports**

Append to `tests/test_public_api.py`:

```python
class TestHttpTransportPublicApi:
    """HTTP transport foundation types importable from package root."""

    def test_engine_importable(self):
        from mountainash_transport import HttpRequestEngine
        assert HttpRequestEngine is not None

    def test_policy_types_importable(self):
        from mountainash_transport import RequestPolicy, RetryPolicy, TimeoutPolicy, RedirectPolicy
        assert all(t is not None for t in [RequestPolicy, RetryPolicy, TimeoutPolicy, RedirectPolicy])

    def test_response_types_importable(self):
        from mountainash_transport import HttpResponse, HttpStreamResponse
        assert HttpResponse is not None
        assert HttpStreamResponse is not None

    def test_error_hierarchy_importable(self):
        from mountainash_transport import (
            HttpTransportError,
            HttpResponseError,
            HttpClientError,
            HttpServerError,
            HttpNotFoundError,
            HttpAuthenticationError,
            HttpForbiddenError,
            HttpRateLimitError,
            HttpConflictError,
            HttpBadGatewayError,
            HttpServiceUnavailableError,
            HttpGatewayTimeoutError,
            HttpConnectionError,
            HttpTimeoutError,
            HttpRedirectError,
            HttpProtocolError,
            HttpRequestError,
            HttpDecodeError,
        )

    def test_method_constants_importable(self):
        from mountainash_transport import SAFE_METHODS, IDEMPOTENT_METHODS
        assert "GET" in SAFE_METHODS
        assert "PUT" in IDEMPOTENT_METHODS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
hatch run test:test tests/test_public_api.py::TestHttpTransportPublicApi -v
```

Expected: FAIL — `ImportError: cannot import name 'HttpRequestEngine' from 'mountainash_transport'`

- [ ] **Step 3: Update _core/http/__init__.py re-exports**

Replace `src/mountainash_transport/_core/http/__init__.py` contents with:

```python
"""HTTP transport foundation — request engine, policies, responses, errors."""
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import (
    HttpBadGatewayError,
    HttpClientError,
    HttpConflictError,
    HttpConnectionError,
    HttpDecodeError,
    HttpForbiddenError,
    HttpGatewayTimeoutError,
    HttpAuthenticationError,
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
    SAFE_METHODS,
    RedirectPolicy,
    RequestPolicy,
    RetryPolicy,
    TimeoutPolicy,
)
from mountainash_transport._core.http.response import HttpResponse, HttpStreamResponse

__all__ = [
    "HttpRequestEngine",
    "RequestPolicy", "RetryPolicy", "TimeoutPolicy", "RedirectPolicy",
    "HttpResponse", "HttpStreamResponse",
    "SAFE_METHODS", "IDEMPOTENT_METHODS",
    "HttpTransportError", "HttpResponseError",
    "HttpClientError", "HttpServerError",
    "HttpNotFoundError", "HttpAuthenticationError", "HttpForbiddenError",
    "HttpRateLimitError", "HttpConflictError",
    "HttpBadGatewayError", "HttpServiceUnavailableError", "HttpGatewayTimeoutError",
    "HttpConnectionError", "HttpTimeoutError",
    "HttpRedirectError", "HttpProtocolError", "HttpRequestError", "HttpDecodeError",
]
```

- [ ] **Step 4: Update package root __init__.py**

In `src/mountainash_transport/__init__.py`, add after the stream transforms block (after line 50):

```python
# HTTP transport foundation
from ._core.http import (
    HttpRequestEngine,
    RequestPolicy, RetryPolicy, TimeoutPolicy, RedirectPolicy,
    HttpResponse, HttpStreamResponse,
    SAFE_METHODS, IDEMPOTENT_METHODS,
    HttpTransportError, HttpResponseError,
    HttpClientError, HttpServerError,
    HttpNotFoundError, HttpAuthenticationError, HttpForbiddenError,
    HttpRateLimitError, HttpConflictError,
    HttpBadGatewayError, HttpServiceUnavailableError, HttpGatewayTimeoutError,
    HttpConnectionError, HttpTimeoutError,
    HttpRedirectError, HttpProtocolError, HttpRequestError, HttpDecodeError,
)
```

Also extend `__all__` to include all new names.

- [ ] **Step 5: Run tests to verify they pass**

```bash
hatch run test:test tests/test_public_api.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/_core/http/__init__.py src/mountainash_transport/__init__.py tests/test_public_api.py
git commit -m "feat: export HTTP transport foundation from package root"
```

---

### Task 7: Migrate HTTP Storage Backend to Engine

**Files:**
- Modify: `src/mountainash_transport/storage/backends/http/__init__.py`
- Modify: `src/mountainash_transport/storage/backends/http/http_read.py`
- Modify: `src/mountainash_transport/storage/backends/http/http_write.py`
- Modify: `src/mountainash_transport/storage/backends/http/http_metadata.py`
- Delete: `src/mountainash_transport/storage/backends/http/_helpers.py`
- Modify: `tests/storage/backends/test_http.py`

- [ ] **Step 1: Update the backend __init__.py to accept and create an engine**

Replace `src/mountainash_transport/storage/backends/http/__init__.py`:

```python
"""HTTPStorageBackend — unified HTTP/HTTPS storage via request engine."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.policy import RequestPolicy
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_transport.storage.registry import register_storage_backend

from .http_metadata import HTTPMetadataMixin
from .http_read import HTTPReadMixin
from .http_write import HTTPWriteMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.HTTP)
class HTTPStorageBackend(HTTPReadMixin, HTTPWriteMixin, HTTPMetadataMixin):
    """HTTP/HTTPS storage backend using HttpRequestEngine."""

    def __init__(
        self,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        connection: t.Any | None = None,
        auth_strategy: t.Any | None = None,
        policy: RequestPolicy | None = None,
        engine: HttpRequestEngine | None = None,
    ) -> None:
        self._storage_profile = storage_profile
        self._connection = connection
        if engine is not None:
            self._engine = engine
        elif connection is not None:
            client = connection.client
            if client is None:
                raise StorageConnectionError("HTTP backend requires a connected connection")
            self._engine = HttpRequestEngine(
                client=client,
                auth_strategy=auth_strategy,
                policy=policy or RequestPolicy(),
            )
        else:
            self._engine = None  # type: ignore[assignment]

    def _get_engine(self) -> HttpRequestEngine:
        if self._engine is None:
            raise StorageConnectionError(
                "HTTP backend requires a connection or engine"
            )
        return self._engine
```

- [ ] **Step 2: Rewrite http_read.py to use the engine**

Replace `src/mountainash_transport/storage/backends/http/http_read.py`:

```python
"""HTTPReadMixin — read operations for HTTP/HTTPS via request engine."""
from __future__ import annotations

import io
import typing as t

from mountainash_transport._core.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageError,
)
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError,
    HttpForbiddenError,
    HttpNotFoundError,
    HttpTransportError,
)
from mountainash_transport.storage.protocols import StorageReadProtocol


class HTTPReadMixin(StorageReadProtocol):
    """Read mixin for HTTP/HTTPS storage."""

    def read_to_bytes(self, path: str) -> bytes:
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            response = engine.request("GET", path)
            return response.content
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

    def read_to_stream(self, path: str) -> t.BinaryIO:
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            with engine.stream("GET", path) as response:
                buffer = io.BytesIO()
                for chunk in response.iter_bytes():
                    buffer.write(chunk)
                buffer.seek(0)
                return buffer
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc
```

- [ ] **Step 3: Rewrite http_write.py to use the engine**

Replace `src/mountainash_transport/storage/backends/http/http_write.py`:

```python
"""HTTPWriteMixin — write operations for HTTP/HTTPS via request engine."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageError,
)
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError,
    HttpForbiddenError,
    HttpNotFoundError,
    HttpTransportError,
)
from mountainash_transport.storage.protocols import StorageWriteProtocol


class HTTPWriteMixin(StorageWriteProtocol):
    """Write mixin for HTTP/HTTPS storage."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            engine.request("PUT", path, content=data)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            engine.request("PUT", path, stream=stream)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc
```

- [ ] **Step 4: Rewrite http_metadata.py to use the engine**

Replace `src/mountainash_transport/storage/backends/http/http_metadata.py`:

```python
"""HTTPMetadataMixin — metadata operations for HTTP/HTTPS via request engine."""
from __future__ import annotations

import typing as t
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport._core.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageError,
)
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError,
    HttpForbiddenError,
    HttpNotFoundError,
    HttpTransportError,
)
from mountainash_transport.storage.protocols import StorageMetadataProtocol


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path.rsplit("/", 1)[-1] if "/" in path else path


class HTTPMetadataMixin(StorageMetadataProtocol):
    """Metadata mixin for HTTP/HTTPS storage."""

    def path_exists(self, path: str) -> bool:
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            engine.request("HEAD", path)
            return True
        except HttpNotFoundError:
            return False
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

    def get_metadata(self, path: str) -> StorageEntry:
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            response = engine.request("HEAD", path)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

        headers = response.headers
        size_str = headers.get("content-length")
        size = int(size_str) if size_str else None
        etag = headers.get("etag", "")
        content_type = headers.get("content-type", "")
        content_md5 = headers.get("content-md5", "")

        last_modified = None
        lm_str = headers.get("last-modified")
        if lm_str:
            try:
                last_modified = parsedate_to_datetime(lm_str)
            except (ValueError, TypeError):
                pass

        checksum = content_md5 if content_md5 else ""
        checksum_algorithm = "MD5" if content_md5 else ""

        return StorageEntry(
            path=path,
            name=_filename_from_url(path),
            size=size,
            last_modified=last_modified,
            etag=etag,
            content_type=content_type,
            source="http",
            checksum=checksum,
            checksum_algorithm=checksum_algorithm,
        )

    def get_size(self, path: str) -> int | None:
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            response = engine.request("HEAD", path)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

        size_str = response.headers.get("content-length")
        return int(size_str) if size_str else None
```

- [ ] **Step 5: Delete the old _helpers.py**

```bash
rm src/mountainash_transport/storage/backends/http/_helpers.py
```

- [ ] **Step 6: Update tests to use engine-based backend**

Replace `tests/storage/backends/test_http.py` test helper to use the engine. The `_FakeConnection` pattern stays similar but the backend now constructs an engine internally:

Update the `_make_backend` helper:

```python
def _make_backend(transport: httpx.MockTransport):
    import mountainash_transport.storage.backends  # noqa: F401
    from mountainash_transport.storage.backends.http import HTTPStorageBackend
    from mountainash_transport._core.http.policy import RequestPolicy, RetryPolicy
    conn = _FakeConnection(transport)
    # Use a no-retry policy for unit tests — tests that need retry test the engine directly
    policy = RequestPolicy(retry=RetryPolicy(max_attempts=1, retry_on_transport=False))
    backend = HTTPStorageBackend(None, connection=conn, policy=policy)
    return backend
```

Update `TestHTTPBackendClientCreation` to test `_get_engine()` instead of `_get_client()`:

```python
class TestHTTPBackendClientCreation:
    def test_engine_created_from_connection(self):
        """Backend creates an engine when a connection is provided."""
        from mountainash_transport._core.http.engine import HttpRequestEngine
        mock_client = MagicMock()
        conn = MagicMock()
        conn.client = mock_client
        backend = HTTPStorageBackend(None, connection=conn)
        assert isinstance(backend._get_engine(), HttpRequestEngine)

    def test_no_connection_raises(self):
        """_get_engine raises StorageConnectionError when no connection is provided."""
        backend = HTTPStorageBackend(None)
        with pytest.raises(StorageConnectionError, match="requires a connection"):
            backend._get_engine()
```

- [ ] **Step 7: Run all tests to verify the migration**

```bash
hatch run test:test -v
```

Expected: All PASS — both new engine tests and migrated backend tests

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_transport/storage/backends/http/ tests/storage/backends/test_http.py
git rm src/mountainash_transport/storage/backends/http/_helpers.py 2>/dev/null || true
git commit -m "refactor: migrate HTTP storage backend to HttpRequestEngine"
```

---

### Task 8: Lint, Type Check, and Final Verification

**Files:** None new — verification only.

- [ ] **Step 1: Run linter**

```bash
hatch run ruff:check
```

Expected: Clean (0 errors). If there are issues, fix them.

- [ ] **Step 2: Run type checker**

```bash
hatch run mypy:check
```

Expected: Clean. Common issues to watch for:
- `httpx.Client` type in engine constructor — ensure httpx is typed
- `RefreshableAuthStrategy` runtime_checkable — ensure `isinstance` usage is correct

- [ ] **Step 3: Run full test suite with coverage**

```bash
hatch run test:cov
```

Expected: All tests PASS, coverage for `_core/http/` at high level.

- [ ] **Step 4: Verify no bare httpx exceptions leak**

```bash
grep -r "except httpx\." src/mountainash_transport/storage/backends/http/ || echo "CLEAN: no httpx exception handling in backend"
```

Expected: "CLEAN" — all httpx exception handling is in the engine, not the backend.

- [ ] **Step 5: Verify _helpers.py is gone**

```bash
test ! -f src/mountainash_transport/storage/backends/http/_helpers.py && echo "CLEAN: _helpers.py removed"
```

Expected: "CLEAN"

- [ ] **Step 6: Commit any lint/type fixes if needed**

```bash
git add -u
git commit -m "chore: lint and type check fixes for HTTP transport foundation"
```

Only if there were fixes needed. Skip if step 1-2 were clean.
