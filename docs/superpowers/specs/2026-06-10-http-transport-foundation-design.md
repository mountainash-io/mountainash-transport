# HTTP Transport Foundation

## Context

mountainash-transport provides unified file operations across storage backends.
Its HTTP path (HTTPConnection + HTTPStorageBackend) is paper-thin — it creates
an httpx.Client, makes requests, and maps three status codes to storage
exceptions. No retries, no auth refresh, no structured error model.

Meanwhile, mountainash-http-client built robust HTTP transport primitives —
exponential-backoff retries, multi-window rate limiting, auth refresh on 401, a
typed error hierarchy — but locked them inside application-level orchestration
(pagination, date-range iteration, archive extraction). Neither this project
nor any other consumer can reuse the transport semantics without importing the
orchestration.

mountainash-transport is already planned to include messaging systems alongside
storage, making it the natural home for shared endpoint infrastructure. If the
storage HTTP backend can consume a generic HTTP transport layer from `_core/`,
the fit is validated — the same foundation serves API clients, messaging
backends, and storage backends alike.

### Scope

All changes are within mountainash-transport only. Breaking changes to
mountainash-http-client are expected and understood — that project will adapt
to consume this foundation on its own timeline.

### Relationship to prior specs

- **2026-06-09-connection-architecture-design.md**: Defines HTTPConnection,
  OAuth2Connection, TunnelledConnection. This spec builds on top — the engine
  receives clients produced by those connections.
- **2026-06-10-storage-protocol-redesign.md**: Defines StorageEntry and the
  protocol set. The HTTP backend's integration with the engine follows that
  spec's error contract.
- **2026-06-09-oauth-extraction-design.md**: Notes that `OAuth2Connection`
  resolves a token once and has no automatic refresh for long-lived sessions,
  suggesting a future `ensure_connected()` method. This spec defines the
  complementary request-side recovery (engine-driven 401 → refresh → retry)
  and Section "Auth Refresh Integration" details how the two converge.

## Design

### Guiding Principle

HTTP is a full protocol with its own error semantics, retry semantics, and auth
lifecycle. The transport foundation models these as first-class concerns.
Callers *configure* transport behavior via policy objects — they do not
*implement* it. Rate limiting is an orchestration concern (managing a budget
across many requests) and stays with the caller; the transport layer surfaces
the information (429 status, Retry-After header) so the orchestrator can act.

### HTTP Error Hierarchy

Lives in `_core/http/errors.py`. These are HTTP-native exceptions — they model
HTTP semantics, not storage or API semantics. Consumers map from these to their
domain errors.

```
HttpTransportError (base)
├── HttpResponseError
│   │   attrs: status_code, headers, body_preview, url, method
│   ├── HttpClientError (4xx)
│   │   ├── HttpNotFoundError (404)
│   │   ├── HttpAuthenticationError (401)
│   │   ├── HttpForbiddenError (403)
│   │   ├── HttpRateLimitError (429)
│   │   │       attrs: retry_after: float | None
│   │   └── HttpConflictError (409)
│   └── HttpServerError (5xx)
│       ├── HttpBadGatewayError (502)
│       ├── HttpServiceUnavailableError (503)
│       └── HttpGatewayTimeoutError (504)
├── HttpConnectionError (DNS, TCP, TLS, proxy failures)
├── HttpTimeoutError (connect, read, write, pool timeouts)
├── HttpRedirectError (unhandled 3xx, too many redirects)
├── HttpProtocolError (HTTP/2 framing, invalid responses)
├── HttpRequestError (invalid URL, unsupported protocol)
└── HttpDecodeError (JSON parse failure, encoding errors)
```

**`HttpResponseError` context fields:**
- `status_code: int`
- `headers: dict[str, str]` — response headers
- `body_preview: str` — first 512 bytes of response body, captured only from
  already-buffered responses. For streaming responses, `body_preview` is empty
  — the engine does not consume stream bytes to populate it.
- `url: str` — the request URL
- `method: str` — the HTTP method

**`HttpRateLimitError`** parses the `Retry-After` header into
`retry_after: float | None` (seconds). Supports both delta-seconds and
HTTP-date formats per RFC 9110. `None` when the header is absent. Negative
values and past HTTP-dates are clamped to `0.0` (retry immediately). Values
exceeding `max_retry_after` (see RetryPolicy) are clamped to that cap.

**Unmapped status codes:** 4xx codes without a specific subclass (e.g., 408,
410, 422) raise `HttpClientError` with the actual `status_code` on the
exception. 5xx codes without a specific subclass raise `HttpServerError`.
Callers that need to handle a specific unmapped code check the `status_code`
attribute. New subclasses are added when a code has distinct semantic meaning
that multiple consumers would branch on — not speculatively.

**Complete httpx exception mapping:** The engine wraps every `httpx` exception
into the transport hierarchy. No bare httpx exceptions leak to callers.

| httpx exception | Transport exception |
|----------------|-------------------|
| `httpx.ConnectError` | `HttpConnectionError` |
| `httpx.ConnectTimeout` | `HttpTimeoutError` |
| `httpx.ReadTimeout` | `HttpTimeoutError` |
| `httpx.WriteTimeout` | `HttpTimeoutError` |
| `httpx.PoolTimeout` | `HttpTimeoutError` |
| `httpx.TooManyRedirects` | `HttpRedirectError` |
| `httpx.ProtocolError` | `HttpProtocolError` |
| `httpx.DecodingError` | `HttpProtocolError` |
| `httpx.ProxyError` | `HttpConnectionError` |
| `httpx.UnsupportedProtocol` | `HttpRequestError` |
| `httpx.InvalidURL` | `HttpRequestError` |
| `httpx.StreamError` | `HttpConnectionError` |
| `httpx.HTTPError` (catch-all) | `HttpTransportError` |

The mapping is ordered — specific exceptions are caught before their base
classes. The catch-all ensures forward compatibility with new httpx exception
types.

**Parallel hierarchy:** `HttpTransportError` is independent of `StorageError`.
These are sibling hierarchies. Storage backends catch HTTP exceptions and map
to storage exceptions. API clients catch and map to API exceptions. The HTTP
layer does not import from or subclass the storage error tree.

### Request Policy

Lives in `_core/http/policy.py`. Immutable configuration objects.

```python
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

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
IDEMPOTENT_METHODS = SAFE_METHODS | frozenset({"PUT", "DELETE"})

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
```

**Backoff calculation:** `min(backoff_base * (2 ** attempt), backoff_max)`
seconds. When `backoff_jitter=True` (default), the actual delay is
`random.uniform(0, calculated_backoff)` — full jitter per the AWS
architecture blog recommendation. This prevents synchronized retry storms
when multiple clients hit the same endpoint.

**429 with Retry-After:** When the status is 429 and `Retry-After` is present,
the engine sleeps for `min(retry_after, max_retry_after)` instead of the
calculated backoff. When absent, falls back to exponential backoff.
`max_retry_after` (default 120s) caps the sleep to prevent unbounded waits
from misbehaving servers.

**Method-safety-aware retries:** By default, only idempotent methods (GET,
HEAD, OPTIONS, TRACE, PUT, DELETE) are retried on transport errors and 5xx.
POST, PATCH, and other non-idempotent methods are not retried unless
`retry_unsafe_methods=True`. This prevents silent replay of requests that may
have already been processed server-side. 429 retries are exempt from this
check — a 429 means the server did not process the request. Auth refresh
retries (401 → refresh → retry) are also exempt — the original request was
rejected, not processed.

**Redirect handling:** `follow_redirects=True` by default, configured on the
httpx.Client. `max_redirects` caps the chain. If redirects are disabled or
the chain exceeds the cap, the engine raises `HttpRedirectError`. Unhandled
3xx responses (when `follow_redirects=False`) are raised as
`HttpRedirectError` with the status code and `Location` header accessible on
the exception — they are never silently returned as successful responses.

**Timeout mapping:** `TimeoutPolicy` maps directly to `httpx.Timeout(connect=,
read=, write=, pool=)`. Write timeouts matter for uploads; pool timeouts
matter when sharing clients across concurrent callers.

**Per-request override:** `request()` and `stream()` accept an optional
`policy` parameter that replaces the engine's default for that call.

**Partial override helpers:** `RequestPolicy` provides `with_timeout()`,
`with_retry()`, and `with_redirect()` methods that return a new
`RequestPolicy` with the specified sub-policy replaced and all other fields
preserved:

```python
# Loosen read timeout for a large download, keep everything else
response = engine.request("GET", url, policy=engine.policy.with_timeout(
    TimeoutPolicy(connect=10.0, read=120.0, write=30.0, pool=10.0)
))
```

### Request Engine

Lives in `_core/http/engine.py`. The core component.

```python
class HttpRequestEngine:
    def __init__(
        self,
        client: httpx.Client,
        policy: RequestPolicy = RequestPolicy(),
        auth_strategy: AuthStrategy | None = None,
    ): ...

    @property
    def policy(self) -> RequestPolicy: ...

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        stream: BinaryIO | None = None,
        params: dict[str, str] | None = None,
        policy: RequestPolicy | None = None,
    ) -> HttpResponse: ...

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        params: dict[str, str] | None = None,
        policy: RequestPolicy | None = None,
    ) -> contextlib.AbstractContextManager[HttpStreamResponse]: ...
```

**Request lifecycle** (applies to both `request()` and `stream()`):

```
1. Resolve policy (per-request override or engine default)
2. Resolve headers: auth strategy headers < engine default headers < per-request headers
   (later entries win on conflict — per-request headers have highest precedence)
3. Check body replayability (see "Body replayability and retry safety")
4. Configure httpx timeout from policy
5. Configure httpx redirect policy from policy
6. Execute request via client
7. On httpx exception:
   → Map to transport exception (see httpx exception mapping table)
   → If retryable per policy, method is retryable, body is replayable,
     and attempts remain: backoff (with jitter), rewind body, goto 6
   → Else: raise
8. On response:
   a. 401 + auth_refresh_on_401 + auth_strategy is RefreshableAuthStrategy:
      → Call auth_strategy.refresh()
      → If refresh succeeds: apply refreshed headers, retry once
        (not counted against max_attempts)
      → If refresh fails: raise HttpAuthenticationError
   b. 429: parse Retry-After header
      → If 429 in retry_on_status and attempts remain:
        sleep(min(retry_after, max_retry_after) or backoff), goto 6
      → Else: raise HttpRateLimitError(retry_after=...)
   c. Other status in retry_on_status and method is retryable and
      body is replayable and attempts remain:
      → Backoff (with jitter), rewind body, goto 6
   d. 3xx (when follow_redirects=False or max_redirects exceeded):
      → Raise HttpRedirectError
   e. Other 4xx: raise mapped HttpClientError subclass
   f. Other 5xx: raise mapped HttpServerError subclass
   g. 2xx: return HttpResponse (for request()) or HttpStreamResponse
      (for stream())
```

**Body replayability and retry safety:**

Before entering the retry loop, the engine classifies the request body:

| Body type | Replayable? | Retry behavior |
|-----------|-------------|----------------|
| `None` (no body) | Yes | Normal retry |
| `bytes` | Yes | Normal retry |
| `BinaryIO` with `seek` | Yes | `seek(0)` before each retry |
| `BinaryIO` without `seek` | No | No retry on transport/5xx errors |

When the body is not replayable, the engine sets effective `max_attempts=1`
for transport errors and 5xx status codes. Auth refresh (401) and rate limit
(429) retries are still attempted for non-replayable bodies because neither
means the server processed the request — 401 means rejected, 429 means not
attempted.

The engine does not buffer non-seekable streams into memory to make them
replayable. If the caller needs retries on a non-seekable stream, they must
buffer it themselves and pass `content=` (bytes) instead.

**Stateless engine, stateful client.** The engine does not own the
httpx.Client — it receives one. This composes with HTTPConnection,
OAuth2Connection, TunnelledConnection, all of which produce httpx.Clients
through different paths.

**Auth refresh is a single retry.** Not counted against `max_attempts`. If the
refresh succeeds and the retried request still returns 401, that raises
`HttpAuthenticationError` — no infinite refresh loops.

**Header ownership rule:** Auth material is applied at the per-request level
via the auth strategy, not mutated on the shared client. The engine calls
`auth_strategy.get_headers()` before each request attempt (including after
refresh) and merges the result into the request headers. This prevents
concurrent requests sharing the same client from seeing each other's stale
or refreshed credentials. Client-level headers (set by HTTPConnection during
creation) are treated as defaults — per-request headers from the auth
strategy and the caller override them.

### HttpResponse

Lives in `_core/http/response.py`. A clean boundary — consumers do not depend
on httpx's API surface.

```python
@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes
    url: str
    method: str

    @property
    def text(self) -> str: ...

    def json(self) -> Any:
        """Parse content as JSON. Raises HttpDecodeError on failure."""
        ...
```

`json()` is a method, not a property — it performs parsing and can raise
`HttpDecodeError` (a subclass of `HttpTransportError`). Making it a method
signals that it does work and may fail.

### HttpStreamResponse

Lives in `_core/http/response.py`. Context-managed streaming response for
large downloads.

```python
class HttpStreamResponse:
    status_code: int
    headers: dict[str, str]
    url: str
    method: str

    def iter_bytes(self, chunk_size: int = 65536) -> Iterator[bytes]: ...
    def iter_text(self, chunk_size: int = 65536) -> Iterator[str]: ...
    def read(self) -> bytes: ...
    def close(self) -> None: ...
```

Returned by `engine.stream()` as a context manager:

```python
with engine.stream("GET", url) as response:
    for chunk in response.iter_bytes():
        output_file.write(chunk)
```

The context manager ensures the underlying httpx stream is closed even if
the caller abandons iteration early. `read()` buffers the entire response
for callers that want to inspect headers before deciding whether to stream.

**Error handling during streaming:** If the connection drops mid-stream,
`iter_bytes()` / `iter_text()` raise `HttpConnectionError`. Mid-stream
errors are not retried — the engine cannot replay a partially-consumed
response. The caller is responsible for retry-from-scratch if needed (e.g.,
re-calling `engine.stream()`). This is a deliberate design choice: streaming
retries require range-request support and resumable download logic, which is
an orchestration concern.

**Streaming and body_preview:** `HttpResponseError` exceptions raised from
streaming responses have an empty `body_preview`. The engine does not consume
stream bytes to populate the preview.

### Auth Strategy Extension

The existing `AuthStrategy` protocol in `_core/auth/strategies.py` gains a
companion protocol:

```python
@runtime_checkable
class RefreshableAuthStrategy(AuthStrategy, Protocol):
    def refresh(self) -> bool:
        """Attempt to refresh credentials.

        Returns True if new credentials were obtained. After a successful
        refresh, subsequent calls to get_headers() must return headers
        reflecting the new credentials.

        Implementations must be internally synchronized — concurrent calls
        to refresh() must not corrupt state. A simple approach is to use
        a threading.Lock and short-circuit if another thread already
        refreshed since the 401 was observed.

        Returns False if refresh is not possible (e.g., refresh token
        expired, no refresh mechanism available). The engine will raise
        HttpAuthenticationError.
        """
        ...

    def get_headers(self) -> dict[str, str]:
        """Return current auth headers.

        Called before each request attempt, including after refresh.
        Must reflect the latest credentials without the caller needing
        to know whether a refresh occurred.
        """
        ...
```

New protocol — not a change to `AuthStrategy`. Existing strategies are
unaffected. The engine checks `isinstance(auth_strategy,
RefreshableAuthStrategy)` before attempting refresh.

**Contract details:**

1. `refresh()` returns `bool`, not new credentials directly. The engine
   obtains updated credentials via `get_headers()` after a successful
   refresh. This keeps the refresh and header-generation concerns separate
   and avoids a complex return type.

2. `refresh()` must be thread-safe. The engine may call it from multiple
   threads if the same engine instance is used concurrently (e.g., in an
   async orchestrator). Implementations should use internal locking and
   single-flight behavior — if multiple threads detect a 401 simultaneously,
   only one performs the actual refresh; others wait for its result.

3. The engine calls `get_headers()` before every request attempt, not just
   after refresh. This means the strategy can implement proactive expiry
   checks (return fresh headers if the current token is about to expire)
   without engine involvement. This complements the connection-side
   `ensure_connected()` approach described in the deferred section.

### Auth Refresh Integration — Deferred Implementation Detail

*The `RefreshableAuthStrategy` protocol and the engine's 401→refresh→retry
logic ship now. No concrete strategy implements `RefreshableAuthStrategy` in
this release — the engine path is exercisable only via test doubles until the
bridges described below are built. This is intentional: we are laying
foundations for others to build on. The protocol, the engine logic, and the
test coverage establish the contract; concrete implementations follow.*

#### The Two Auth Paths

The engine receives both an `httpx.Client` (from a connection) and optionally
an `AuthStrategy`. These interact in three ways:

**Path 1 — Strategy-injected auth.** HTTPConnection creates a bare
httpx.Client. The auth strategy injects headers (Bearer, Basic, IAM). The
engine owns the full auth lifecycle: it calls `get_headers()` before each
request and can refresh+retry on 401.

```
HTTPConnection → httpx.Client (no auth baked in)
AuthStrategy   → get_headers() → headers dict
Engine         → merges headers per-request, refreshes on 401
```

**Path 2 — Connection-managed auth.** OAuth2Connection and OAuth1Connection
decorate the httpx.Client with auth handling — the client itself manages token
lifecycle and signing. The engine receives a "pre-authenticated" client and no
separate auth strategy.

```
OAuth2Connection → httpx.Client (auth baked into client via httpx.Auth)
AuthStrategy     → None
Engine           → executes, has no refresh capability
```

**Path 3 — Hybrid (the current gap).** OAuth2Connection handles its own token
refresh internally, but this is invisible to the engine. If the connection's
internal refresh fails or the token expires during a long-lived session, the
engine sees a 401 and cannot help — it has no `RefreshableAuthStrategy` to
call.

This gap was identified in the connection architecture spec (2026-06-09) which
noted: *"Token refresh for long-lived sessions: `OAuth2Connection.connect()`
resolves a token once. If the token expires during a long-lived session, there
is no automatic re-connection. A future `ensure_connected()` method on
`ConnectionProtocol` could check token validity before returning the client."*

#### Design Intent for Resolution

The engine-side `RefreshableAuthStrategy` and the connection-side
`ensure_connected()` are complementary:

- **`ensure_connected()`** — proactive, pre-request. The connection checks
  token validity before the engine sends a request. Prevents unnecessary 401
  round-trips when the connection *knows* the token has expired (e.g., by
  checking expiry timestamps).
- **`RefreshableAuthStrategy.refresh()`** — reactive, post-401. The engine
  recovers from a 401 that the connection didn't prevent (token revoked
  server-side, clock skew, race conditions).

Both are needed for robust long-lived sessions. Neither alone is sufficient.

**Bridge pattern for connection-managed auth:**

OAuth2Connection and OAuth1Connection should expose their refresh capability
through `RefreshableAuthStrategy` so the engine can participate in recovery:

```python
class OAuth2RefreshBridge(RefreshableAuthStrategy):
    """Bridges OAuth2Connection's token lifecycle to the engine's
    refresh protocol."""

    def __init__(self, oauth2_connection: OAuth2Connection): ...

    def inject(self, kwargs: dict) -> dict:
        return kwargs  # no-op — connection's client handles auth

    def get_headers(self) -> dict[str, str]:
        return {}  # no-op — connection's client handles auth

    def refresh(self) -> bool:
        # Delegates to the connection's OAuthFlow.
        # Internally synchronized — uses the connection's lock.
        return self._connection.refresh_token()
```

**Factory change:** `create_connection()` would return both a connection and an
optional auth strategy. The engine constructor receives both:

```python
conn = create_connection(profile, auth_profile)
engine = HttpRequestEngine(
    client=conn.client,
    auth_strategy=conn.auth_strategy,  # RefreshableAuthStrategy or None
    policy=policy,
)
```

**Why not let connections handle 401 internally:**

Connections manage client lifecycle (connect, disconnect, configuration).
Request-level retry logic — including auth retry — belongs in the engine
because:

1. **Retry budget.** The engine tracks attempt counts. Silent connection
   refreshes don't count against the budget, risking invisible retry storms.
2. **Observability.** The engine can log that an auth refresh occurred. Silent
   connection-internal refreshes are invisible to callers.
3. **Policy control.** `auth_refresh_on_401` on `RequestPolicy` lets callers
   opt out. Connection-internal refresh gives no such control.
4. **Consistency.** All retry-like behavior (transient errors, 429, 401) goes
   through one code path in the engine.

**What ships now vs later:**

| Component | Ships now | Deferred |
|-----------|-----------|----------|
| `RefreshableAuthStrategy` protocol | Yes | — |
| `HttpRequestEngine` 401→refresh→retry logic | Yes (tested via mocks) | — |
| `OAuth2RefreshBridge` | — | Yes |
| `OAuth1RefreshBridge` | — | Yes |
| `create_connection` returning auth strategy | — | Yes |
| `ConnectionProtocol.ensure_connected()` | — | Yes |

### Client Lifecycle and Staleness

The engine does not own the httpx.Client — it receives one at construction.
This creates a staleness risk: if a connection reconnects, rotates, or a
tunnelled connection rebuilds its client, the engine holds the old reference.

**Current scope (ships now):** The engine captures `client` at construction
and uses it for all requests. This is correct for the initial consumers —
HTTPStorageBackend creates a connection, connects once, and passes the client
to the engine. The client reference is stable for the backend's lifetime.

**Design intent for long-lived sessions:** When `ensure_connected()` lands on
`ConnectionProtocol`, the engine should accept a client *provider* (a callable
or the connection itself) rather than a bare client, calling it before each
request to get the current client:

```python
# Future — not shipped now
class HttpRequestEngine:
    def __init__(
        self,
        client: httpx.Client | ConnectionProtocol,
        ...
    ):
        if isinstance(client, ConnectionProtocol):
            self._get_client = lambda: (client.ensure_connected(), client.client)[1]
        else:
            self._get_client = lambda: client
```

This is deferred because it depends on `ensure_connected()` existing. The
current constructor signature (`client: httpx.Client`) is forward-compatible —
widening to `client: httpx.Client | ConnectionProtocol` is non-breaking.

### Integration with Existing Components

#### HTTPConnection — unchanged

HTTPConnection continues to create an authenticated httpx.Client from a
profile + auth strategy. The engine receives this client. No changes to
HTTPConnection's interface or lifecycle.

#### HTTPStorageBackend — primary consumer

The backend currently does inline `self._connection.client.get(url)` with
manual status-code checks. This is replaced with engine calls:

**Before:**
```python
def read_to_bytes(self, path: str) -> bytes:
    response = self._connection.client.get(path)
    if response.status_code == 404:
        raise PathNotFoundError(path)
    if response.status_code in (401, 403):
        raise AuthenticationError(path)
    response.raise_for_status()
    return response.content
```

**After:**
```python
def read_to_bytes(self, path: str) -> bytes:
    try:
        response = self._engine.request("GET", path)
        return response.content
    except HttpNotFoundError:
        raise PathNotFoundError(path)
    except HttpAuthenticationError:
        raise AuthenticationError(path)
    except HttpForbiddenError:
        raise AuthenticationError(path)
    except HttpTransportError as e:
        raise StorageError(str(e)) from e
```

**After (streaming read):**
```python
def read_to_stream(self, path: str) -> t.BinaryIO:
    try:
        with self._engine.stream("GET", path) as response:
            # True streaming — chunks arrive incrementally
            buffer = io.BytesIO()
            for chunk in response.iter_bytes():
                buffer.write(chunk)
            buffer.seek(0)
            return buffer
    except HttpNotFoundError:
        raise PathNotFoundError(path)
    except HttpTransportError as e:
        raise StorageError(str(e)) from e
```

Note: `read_to_stream` still returns a `BinaryIO` (per `StorageReadProtocol`),
but the download is now truly streamed — memory usage is bounded by chunk size
during transfer, not by file size. A future protocol revision could return an
iterator directly, but that's out of scope.

The backend becomes a thin mapping layer: translate HTTP semantics into
storage semantics. Retry, timeout, auth refresh are handled before the backend
sees the result.

The backend constructs the engine during initialization:

```python
class HTTPStorageBackend:
    def __init__(self, connection: HTTPConnection,
                 auth_strategy=None, policy=None):
        self._engine = HttpRequestEngine(
            client=connection.client,
            auth_strategy=auth_strategy,
            policy=policy or RequestPolicy(),
        )
```

#### StorageFacade — no changes

The facade delegates to backends. The engine is an internal detail of the HTTP
backend. The facade's public API is unaffected.

### Module Structure

Expanding the existing `_core/http.py` stub into a package:

```
_core/http/
├── __init__.py      # re-exports: HttpRequestEngine, RequestPolicy, HttpResponse, HttpStreamResponse
├── engine.py        # HttpRequestEngine
├── errors.py        # HttpTransportError hierarchy + HttpDecodeError
├── policy.py        # RequestPolicy, RetryPolicy, TimeoutPolicy, RedirectPolicy, SAFE_METHODS, IDEMPOTENT_METHODS
└── response.py      # HttpResponse, HttpStreamResponse
```

### Public API Exports

Package root `__init__.py` gains:

```python
from mountainash_transport._core.http import (
    HttpRequestEngine,
    RequestPolicy,
    RetryPolicy,
    TimeoutPolicy,
    RedirectPolicy,
    HttpResponse,
    HttpStreamResponse,
)
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
)
from mountainash_transport._core.http.policy import (
    SAFE_METHODS,
    IDEMPOTENT_METHODS,
)
```

These are public API — mountainash-http-client and other consumers import
directly from `mountainash_transport`.

### Test Strategy

**Engine tests** (`tests/_core/http/test_engine.py`):
- Happy path: 200 response → HttpResponse
- Retry on 5xx: mock returns 503 then 200, verify retry count and backoff
- Retry on transport error: mock raises TimeoutException, verify retry
- Retry exhaustion: mock returns 503 for all attempts, verify raises
  HttpServiceUnavailableError
- Retry respects method safety: POST + 503 → no retry by default
- Retry with `retry_unsafe_methods=True`: POST + 503 → retry
- 429 and auth refresh retry exempt from method safety check
- Body replayability: seekable BinaryIO retried with seek(0)
- Body replayability: non-seekable BinaryIO → no retry on 5xx
- Body replayability: bytes body always retried
- 401 with refreshable auth: mock returns 401, refresh succeeds, retry
  succeeds with new headers from get_headers()
- 401 with refreshable auth, refresh fails: verify raises
  HttpAuthenticationError
- 401 without refreshable auth: verify raises immediately
- 401 after refresh still 401: verify raises (no infinite loop)
- 429 with Retry-After header: verify sleep duration capped by max_retry_after
- 429 with Retry-After exceeding max_retry_after: verify clamped
- 429 without Retry-After: verify exponential backoff with jitter
- Backoff jitter: verify delay is in [0, calculated_backoff]
- Backoff cap: verify delay never exceeds backoff_max
- Per-request policy override: verify overridden policy is used
- Auth refresh not counted against max_attempts
- Redirect disabled: 302 → HttpRedirectError
- Redirect enabled: 302 followed transparently
- All httpx exceptions mapped: each httpx exception type → correct transport
  exception
- Header precedence: auth headers < default headers < per-request headers
- Streaming: context manager returns HttpStreamResponse
- Streaming: iter_bytes yields chunks
- Streaming: mid-stream disconnect → HttpConnectionError
- Streaming: body_preview is empty on streaming errors

**Error tests** (`tests/_core/http/test_errors.py`):
- Hierarchy: all exceptions are HttpTransportError
- HttpResponseError carries context fields
- HttpRateLimitError parses Retry-After (delta-seconds and HTTP-date)
- HttpRateLimitError clamps negative/past values to 0.0
- Status-code-to-exception mapping covers all defined codes
- Unmapped 4xx → HttpClientError, unmapped 5xx → HttpServerError
- HttpDecodeError raised on invalid JSON

**Policy tests** (`tests/_core/http/test_policy.py`):
- Frozen: verify immutability
- Defaults: verify default values
- Override composition: RequestPolicy with custom RetryPolicy
- with_timeout() / with_retry() / with_redirect() return new instances
- SAFE_METHODS and IDEMPOTENT_METHODS are correct sets

**Response tests** (`tests/_core/http/test_response.py`):
- `.text` decodes content
- `.json()` parses content
- `.json()` raises HttpDecodeError on invalid JSON
- HttpResponse frozen: verify immutability
- HttpStreamResponse: iter_bytes, iter_text, read, close

**Integration tests** (`tests/storage/backends/test_http.py`):
- Existing HTTP backend tests updated to verify engine-based implementation
- Error mapping: HttpNotFoundError → PathNotFoundError, etc.
- read_to_stream uses engine.stream() path

## Verification

After implementation:
1. `hatch run test:test` — all tests pass (existing + new)
2. `hatch run ruff:check` — lint clean
3. `hatch run mypy:check` — type check clean
4. HTTP backend uses engine exclusively (no inline status-code checks)
5. All HTTP error types importable from `mountainash_transport`
6. Engine composes with HTTPConnection, OAuth2Connection, TunnelledConnection
   clients without modification to those connections
7. No bare httpx exceptions leak through the engine boundary
8. Non-seekable upload bodies are not silently retried
9. Streaming responses work through the engine.stream() path
