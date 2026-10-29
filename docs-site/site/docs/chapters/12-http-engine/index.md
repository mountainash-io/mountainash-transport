---
title: The HTTP request engine
---

# The HTTP request engine

`HttpRequestEngine` sends HTTP requests through an `httpx.Client` and adds what a bare client leaves to you: retries with exponential backoff, per-request timeouts and redirect limits, one credential refresh on `401 Unauthorized`, a typed error for every failure, and removal of URL credentials from error messages. The HTTP storage backend uses it for every request, and you can use it directly for any HTTP API.

The engine and its policy, response and error types are exported from `mountainash_transport`. The engine needs the `[http]` extra; the policies, responses and errors are standard library only. This page assumes you know what an `HTTPConnection` provides ([HTTPConnection](../11-connections/index.md#httpconnection)). The examples run against a local `http.server` started in the same process; its setup is not shown, and `base_url` is its address.

## Making requests

<!-- concept:191 -->

Construct the engine around a client you own: `HttpRequestEngine(client, policy=None, auth_strategy=None, *, location_check=None)`. The engine never closes the client. It offers two calls:

- `request(method, url, *, headers=None, content=None, stream=None, params=None, policy=None)` sends a request and returns a fully buffered `HttpResponse`. A `stream=` body is read into bytes before sending.
- `stream(method, url, *, headers=None, content=None, params=None, policy=None)` is a context manager that yields an `HttpStreamResponse` without loading the body. Its body must be `bytes`.

`url` may be relative when the client has a `base_url`. Every call can pass its own `RequestPolicy` through `policy=`, which replaces the engine's default for that call only. Caller `headers` override auth headers with the same name.

```python
import httpx

from mountainash_transport import HttpRequestEngine

with httpx.Client(base_url=base_url) as client:
    engine = HttpRequestEngine(client)

    response = engine.request("GET", "/reports/summary.json")
    print(response.status_code, response.headers["content-type"], response.json())

    with engine.stream("GET", "/reports/sales.csv") as streamed:
        for chunk in streamed.iter_bytes(chunk_size=16):
            print(chunk)
```

Output:

```text
200 application/json {'regions': 2, 'total': 215}
b'region,total\nnor'
b'th,120\nsouth,95\n'
```

### Policies

A `RequestPolicy` is a frozen dataclass composed of three sub-policies, plus one flag. Derive variations with `with_retry()`, `with_timeout()` and `with_redirect()`, which return new instances.

| Field | Type | Defaults |
|---|---|---|
| `retry` | `RetryPolicy` | see [Retries](#retries) |
| `timeout` | `TimeoutPolicy` | `connect=10.0`, `read=30.0`, `write=30.0`, `pool=10.0` seconds |
| `redirect` | `RedirectPolicy` | `follow_redirects=True`, `max_redirects=10` |
| `auth_refresh_on_401` | `bool` | `True` |

The engine applies the timeout policy to each request, overriding the client's own timeout. Redirects are followed by the engine one hop at a time, under the call's limit; going over it raises `HttpRedirectError`, and so does a 3xx response when following is turned off.

### Checking every URL

`location_check` is a callable that receives each URL the engine is about to send, including redirect targets, and raises to refuse it. The facade passes its location policy check here when a policy is active ([Policy on the facade](../08-location-policy/index.md#policy-on-the-facade)). Any callable works:

```python
from urllib.parse import urlsplit

import httpx

from mountainash_transport import HttpRequestEngine


def only_loopback_ip(url: str) -> None:
    if urlsplit(url).hostname != "127.0.0.1":
        raise PermissionError(f"refusing {url}")


with httpx.Client(base_url=base_url) as client:
    engine = HttpRequestEngine(client, location_check=only_loopback_ip)
    print(engine.request("GET", "/reports/sales.csv").status_code)
    try:
        engine.request("GET", "/moved")         # 302 to http://localhost:<port>/...
    except PermissionError as exc:
        print(exc)
```

Output (the port differs on each run):

```text
200
refusing http://localhost:38579/reports/sales.csv
```

The first hop to `127.0.0.1` passed; the redirect to `localhost` was refused before it was sent. The exception raised by your check propagates unchanged.

<!-- concept:193 -->

### Responses and errors

`HttpResponse` is a frozen dataclass with `status_code`, `headers` (a plain `dict`), `content` (bytes), `url` (the final URL, after redirects) and `method`. `text` decodes the body as UTF-8; `json()` parses it and raises `HttpDecodeError` if it cannot. `HttpStreamResponse` exposes the same metadata and reads the body through `iter_bytes(chunk_size=65536)`, `iter_text()` or `read()`; leaving the `with` block closes it.

Only 2xx responses are returned. Anything else raises a subclass of `HttpTransportError`:

| Exception | Cause |
|---|---|
| `HttpNotFoundError`, `HttpAuthenticationError`, `HttpForbiddenError`, `HttpConflictError`, `HttpRateLimitError` | 404, 401, 403, 409, 429 |
| `HttpClientError` | any other 4xx (base of the 4xx classes above) |
| `HttpBadGatewayError`, `HttpServiceUnavailableError`, `HttpGatewayTimeoutError` | 502, 503, 504 |
| `HttpServerError` | any other 5xx (base of the 5xx classes above) |
| `HttpConnectionError` | DNS, TCP, TLS or proxy failure |
| `HttpTimeoutError` | connect, read, write or pool timeout |
| `HttpRedirectError` | unfollowed 3xx, or too many redirects |
| `HttpProtocolError` | malformed HTTP or content decoding |
| `HttpRequestError` | invalid URL or unsupported scheme |
| `HttpDecodeError` | `json()` could not parse the body |

Status errors share the base `HttpResponseError`, which carries `status_code`, `headers`, `url`, `method` and `body_preview` (the first 500 characters of the body from `request()`; always `None` from `stream()`, which does not drain error bodies). `HttpRateLimitError` adds `retry_after` in seconds when the server sent one.

These classes do not subclass `StorageError`. When you read through `StorageFacade`, the HTTP backend translates them into the storage errors described in [Errors](../03-installation/index.md#errors); when you use the engine directly, catch the HTTP classes.

## Retries

<!-- concept:192 -->

`RetryPolicy` decides which failures are tried again. `max_attempts` counts the first attempt, so the default of 3 means up to two retries.

| Field | Default | Meaning |
|---|---|---|
| `max_attempts` | `3` | Total attempts, including the first. |
| `backoff_base`, `backoff_max` | `1.0`, `60.0` | Wait before retry *n* is `backoff_base * 2**(n-1)`, capped at `backoff_max`. |
| `backoff_jitter` | `True` | Replace the wait with a random value between 0 and that wait. |
| `retry_on_status` | `(429, 500, 502, 503, 504)` | Statuses that are retried. |
| `retry_on_transport` | `True` | Retry `HttpConnectionError` and `HttpTimeoutError`. |
| `retry_unsafe_methods` | `False` | Also retry methods outside `IDEMPOTENT_METHODS`, such as POST and PATCH. |
| `max_retry_after` | `120.0` | Longest `Retry-After` wait honoured, in seconds. |

Statuses other than 429 and transport errors are retried only for methods in `IDEMPOTENT_METHODS` (GET, HEAD, OPTIONS, TRACE, PUT, DELETE) and only when the body can be sent again: no body, a `bytes` body, or a seekable stream. A 429 is retried for any method; the engine waits for the server's `Retry-After` value (seconds or an HTTP date), capped at `max_retry_after`, or uses the backoff when there is none. A `401` followed by a successful credential refresh is not counted as an attempt (see [Authentication strategies](#authentication-strategies)).

The example turns backoff off so that it runs instantly. The server answers `/flaky` with 503 on the first request, `/limited` with 429 and `Retry-After: 0` on the first request, and every POST with 503.

```python
import httpx

from mountainash_transport import (
    HttpServiceUnavailableError, HttpRequestEngine, RequestPolicy, RetryPolicy,
)

policy = RequestPolicy(retry=RetryPolicy(max_attempts=3, backoff_base=0, backoff_jitter=False))

with httpx.Client(base_url=base_url) as client:
    engine = HttpRequestEngine(client, policy)

    print(engine.request("GET", "/flaky").text)       # 503, then 200
    print(engine.request("GET", "/limited").text)     # 429 with Retry-After: 0, then 200
    try:
        engine.request("POST", "/flaky", content=b"{}")
    except HttpServiceUnavailableError as exc:
        print(type(exc).__name__, exc.status_code, exc.body_preview)

print(dict(hits))
```

Output (`hits` is the test server's request counter):

```text
ok
ok
HttpServiceUnavailableError 503 busy
{('GET', '/flaky'): 2, ('GET', '/limited'): 2, ('POST', '/flaky'): 1}
```

Both GETs succeeded on their second attempt; the POST was sent once and failed without a retry.

Waits use `time.sleep` in the calling thread, so large `backoff_max` or `max_retry_after` values block the caller for that long. `stream()` retries only until it yields the response; once you start reading the body, failures propagate without replay. A `request()` body passed as a non-seekable stream is read into memory first but still counts as not replayable, so it is never retried; pass `content=` bytes when you want retries.

## Authentication strategies

<!-- concept:194 -->

Static credentials, such as a fixed bearer token or basic auth, are rendered into the `httpx.Client` when the connection is built and need nothing from the engine. The engine's `auth_strategy` is for credentials that expire. A refreshable strategy implements the `RefreshableAuthStrategy` protocol (`src/mountainash_transport/_core/http/auth_protocol.py`) with three methods:

- `get_headers()` returns the current auth headers. The engine calls it before each request.
- `refresh()` obtains new credentials and returns `True` on success. The engine calls it once, on the first `401`, and resends the request with fresh headers.
- `apply(kwargs)` returns a new dict of client keyword arguments. The engine does not call it; it exists for client construction.

Implementations must be thread-safe. If the refresh fails or the retried request also gets `401`, the engine raises `HttpAuthenticationError`. Set `auth_refresh_on_401=False` in the policy to skip the refresh.

The example implements a strategy whose first token the server has already expired:

```python
import threading

import httpx

from mountainash_transport import HttpRequestEngine


class RotatingToken:
    """A RefreshableAuthStrategy: apply(), get_headers() and refresh()."""

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = iter(tokens)
        self._current = next(self._tokens)
        self._lock = threading.Lock()
        self.refreshes = 0

    def apply(self, kwargs: dict) -> dict:
        return dict(kwargs)

    def get_headers(self) -> dict[str, str]:
        with self._lock:
            return {"Authorization": f"Bearer {self._current}"}

    def refresh(self) -> bool:
        with self._lock:
            self._current = next(self._tokens)
            self.refreshes += 1
            return True


auth = RotatingToken(["token-1", "token-2"])
with httpx.Client(base_url=base_url) as client:
    engine = HttpRequestEngine(client, auth_strategy=auth)
    print(engine.request("GET", "/secure").text, "after", auth.refreshes, "refresh")
```

Output:

```text
secret report after 1 refresh
```

For OAuth 2.0 you do not write a strategy. `mountainash-auth-client` owns token acquisition, storage and refresh (see [credentials come from auth-client](../02-mountainash-ecosystem/index.md#credentials-come-from-auth-client)); transport adapts its token manager to this protocol as `OAuth2RefreshableAuthStrategy`, built by `create_auth_strategy(auth_profile, oauth_provider=..., token_store=...)` in `mountainash_transport.connections`. `StorageFacade.from_path` does this for you when you pass an OAuth2 auth profile together with `oauth_provider=` and `token_store=`. The token store stays yours to open and close.

## Error redaction

<!-- concept:195 -->

URLs sometimes carry credentials as userinfo: `https://user:password@host/path`. The engine keeps that part out of what errors display. Every `HttpTransportError` replaces the userinfo in its message with `***`, as do `HttpResponseError.url`, `HttpResponse.url` and `HttpStreamResponse.url`. When the request URL or the underlying httpx exception contains userinfo, the engine raises its error without a displayed cause, so a standard traceback does not print the native exception either. Without userinfo, the httpx exception remains attached as `__cause__` for debugging.

```python
import socket

import httpx

from mountainash_transport import (
    HttpConnectionError, HttpNotFoundError, HttpRequestEngine, RequestPolicy, RetryPolicy,
)

port = base_url.rsplit(":", 1)[1]
with socket.socket() as probe:                   # a local port nobody listens on
    probe.bind(("127.0.0.1", 0))
    closed_port = probe.getsockname()[1]

no_retry = RequestPolicy(retry=RetryPolicy(max_attempts=1))
with httpx.Client() as client:
    engine = HttpRequestEngine(client, no_retry)
    try:
        engine.request("GET", f"http://analyst:s3cret@127.0.0.1:{port}/reports/old.csv")
    except HttpNotFoundError as exc:
        print(exc)
        print(exc.url, "|", exc.body_preview)

    for label, userinfo in (("with userinfo", "analyst:s3cret@"), ("no userinfo", "")):
        try:
            engine.request("GET", f"http://{userinfo}127.0.0.1:{closed_port}/x")
        except HttpConnectionError as exc:
            print(f"{label}: cause shown = {exc.__cause__ is not None}")
```

Output (the port differs on each run):

```text
HTTP 404 GET http://***@127.0.0.1:43981/reports/old.csv
http://***@127.0.0.1:43981/reports/old.csv | no such report
with userinfo: cause shown = False
no userinfo: cause shown = True
```

!!! warning "Redaction covers display, not memory"
    Only URL userinfo is redacted. Tokens in query strings, headers and response bodies (including `body_preview`) are not. The hidden `__context__` of an exception, httpx request objects and traceback locals can still hold the credential, so configure error reporters that capture locals or full exception state accordingly. See the [support matrix and known limits](../../reference/support-matrix.md#known-limits).

Location-policy errors redact credentials the same way ([Policy on the facade](../08-location-policy/index.md#policy-on-the-facade)). The redaction helper is `src/mountainash_transport/_core/http/redact.py`; its tests are in `tests/_core/http/test_url_userinfo_redaction.py`.
