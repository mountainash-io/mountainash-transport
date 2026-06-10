"""HTTP request engine — retry, auth refresh, error mapping, streaming.

The ``HttpRequestEngine`` wraps an ``httpx.Client`` and applies a
``RequestPolicy`` to every request. It handles:

- Exponential backoff with jitter on retryable status codes and transport errors
- Auth token refresh on 401 responses (via ``RefreshableAuthStrategy``)
- ``Retry-After`` header parsing and capping
- Body replayability checks (seekable streams, bytes, None)
- httpx exception → transport exception mapping
- Streaming responses via a context-manager API
"""

from __future__ import annotations

import contextlib
import email.utils
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
)
from mountainash_transport._core.http.policy import IDEMPOTENT_METHODS, RequestPolicy
from mountainash_transport._core.http.response import HttpResponse, HttpStreamResponse

if t.TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import BinaryIO


# ---------------------------------------------------------------------------
# httpx exception → transport exception mapping (order: specific before base)
# ---------------------------------------------------------------------------

_HTTPX_EXCEPTION_MAP: list[tuple[type[httpx.HTTPError], type[HttpTransportError]]] = [
    # Timeouts (subclasses of httpx.TimeoutException)
    (httpx.ConnectTimeout, HttpTimeoutError),
    (httpx.ReadTimeout, HttpTimeoutError),
    (httpx.WriteTimeout, HttpTimeoutError),
    (httpx.PoolTimeout, HttpTimeoutError),
    # Redirects
    (httpx.TooManyRedirects, HttpRedirectError),
    # Connection (ProxyError before ConnectError — ProxyError is a subclass)
    (httpx.ProxyError, HttpConnectionError),
    (httpx.ConnectError, HttpConnectionError),
    # Protocol
    (httpx.ProtocolError, HttpProtocolError),
    (httpx.DecodingError, HttpProtocolError),
    # Request-level
    (httpx.UnsupportedProtocol, HttpRequestError),
    (httpx.InvalidURL, HttpRequestError),
    # Stream
    (httpx.StreamError, HttpConnectionError),
    # Catch-all
    (httpx.HTTPError, HttpTransportError),
]

# Transport exceptions that are retryable
_RETRYABLE_TRANSPORT_TYPES: tuple[type[HttpTransportError], ...] = (
    HttpTimeoutError,
    HttpConnectionError,
)


def _map_httpx_exception(exc: httpx.HTTPError) -> HttpTransportError:
    """Map an httpx exception to the corresponding transport exception."""
    for httpx_cls, transport_cls in _HTTPX_EXCEPTION_MAP:
        if isinstance(exc, httpx_cls):
            return transport_cls(str(exc))
    return HttpTransportError(str(exc))  # pragma: no cover


# ---------------------------------------------------------------------------
# Retry-After parsing
# ---------------------------------------------------------------------------


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header value.

    Tries float first, then HTTP-date. Returns None if unparseable.
    Clamps negative values to 0.0.
    """
    if value is None:
        return None

    # Try numeric seconds
    try:
        seconds = float(value)
        return max(seconds, 0.0)
    except ValueError:
        pass

    # Try HTTP-date
    try:
        dt = email.utils.parsedate_to_datetime(value)
        delta = (dt - email.utils.parsedate_to_datetime(email.utils.formatdate())).total_seconds()
        return max(delta, 0.0)
    except (ValueError, TypeError):
        pass

    return None


# ---------------------------------------------------------------------------
# Body helpers
# ---------------------------------------------------------------------------


def _is_body_replayable(content: bytes | None, stream: BinaryIO | None) -> bool:
    """Check whether the request body can be replayed for retries."""
    if content is not None or stream is None:
        # None body or bytes body → always replayable
        return True
    # Stream body — replayable only if seekable
    return hasattr(stream, "seekable") and stream.seekable()


def _resolve_body(content: bytes | None, stream: BinaryIO | None) -> bytes | None:
    """Resolve the request body to bytes.

    For ``request()`` (buffered), we read streams into bytes upfront.
    """
    if stream is not None:
        return stream.read()
    return content


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class HttpRequestEngine:
    """Execute HTTP requests with retry, auth refresh, and error mapping.

    Parameters
    ----------
    client:
        An ``httpx.Client`` instance to use for sending requests.
    policy:
        Default request policy. If ``None``, a ``RequestPolicy()`` with all
        defaults is used.
    auth_strategy:
        Optional auth strategy for injecting credentials into request headers.
    """

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
        """The engine's default request policy."""
        return self._policy

    # ------------------------------------------------------------------
    # Header merging
    # ------------------------------------------------------------------

    def _merge_headers(self, caller_headers: dict[str, str] | None = None) -> dict[str, str]:
        """Merge auth strategy headers with caller-provided headers.

        Caller headers win on conflict.
        """
        merged: dict[str, str] = {}
        if isinstance(self._auth_strategy, RefreshableAuthStrategy):
            merged.update(self._auth_strategy.get_headers())
        if caller_headers:
            merged.update(caller_headers)
        return merged

    # ------------------------------------------------------------------
    # Error raising helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """Raise the appropriate transport error for a non-2xx response."""
        status = response.status_code
        url = str(response.url)
        method = response.request.method
        headers_dict = dict(response.headers)
        body_preview = response.text[:500] if response.content else None

        error_cls = map_status_to_error(status)

        kwargs: dict[str, t.Any] = dict(
            status_code=status,
            headers=headers_dict,
            body_preview=body_preview,
            url=url,
            method=method,
        )

        if error_cls.__name__ == "HttpRateLimitError":
            kwargs["retry_after"] = _parse_retry_after(
                response.headers.get("retry-after")
            )

        raise error_cls(
            f"HTTP {status} {method} {url}",
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Buffered request
    # ------------------------------------------------------------------

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
    ) -> HttpResponse:
        """Send a buffered HTTP request with retry and error handling.

        Parameters
        ----------
        method:
            HTTP method (GET, POST, PUT, etc.).
        url:
            Target URL.
        headers:
            Caller-provided headers (override auth headers on conflict).
        content:
            Request body as bytes.
        stream:
            Request body as a binary stream (read into bytes upfront).
        params:
            URL query parameters.
        policy:
            Per-request policy override. If ``None``, the engine default is used.

        Returns
        -------
        HttpResponse
            The buffered response.
        """
        pol = policy or self._policy
        retry = pol.retry
        method_upper = method.upper()

        # Check body replayability BEFORE reading the stream
        body_replayable = _is_body_replayable(content, stream)

        # Resolve body to bytes (reads stream if present)
        body = _resolve_body(content, stream)

        merged_headers = self._merge_headers(headers)
        timeout = httpx.Timeout(
            connect=pol.timeout.connect,
            read=pol.timeout.read,
            write=pol.timeout.write,
            pool=pol.timeout.pool,
        )

        auth_refreshed = False
        attempt = 0

        while True:
            attempt += 1

            try:
                response = self._client.request(
                    method_upper,
                    url,
                    headers=merged_headers,
                    content=body,
                    params=params,
                    timeout=timeout,
                    follow_redirects=pol.redirect.follow_redirects,
                )
            except httpx.InvalidURL as exc:
                raise HttpRequestError(str(exc)) from exc
            except httpx.HTTPError as exc:
                transport_exc = _map_httpx_exception(exc)

                # Check if retryable
                can_retry = (
                    retry.retry_on_transport
                    and isinstance(transport_exc, _RETRYABLE_TRANSPORT_TYPES)
                    and (method_upper in IDEMPOTENT_METHODS or retry.retry_unsafe_methods)
                    and body_replayable
                    and attempt < retry.max_attempts
                )
                if can_retry:
                    delay = min(
                        retry.backoff_base * (2 ** (attempt - 1)),
                        retry.backoff_max,
                    )
                    if retry.backoff_jitter:
                        delay = random.uniform(0, delay)
                    time.sleep(delay)
                    continue

                raise transport_exc from exc

            status = response.status_code

            # 2xx → success
            if 200 <= status < 300:
                return HttpResponse(
                    status_code=status,
                    headers=dict(response.headers),
                    content=response.content,
                    url=str(response.url),
                    method=method_upper,
                )

            # 401 + auth refresh
            if (
                status == 401
                and pol.auth_refresh_on_401
                and not auth_refreshed
                and isinstance(self._auth_strategy, RefreshableAuthStrategy)
            ):
                if self._auth_strategy.refresh():
                    auth_refreshed = True
                    merged_headers = self._merge_headers(headers)
                    # Auth refresh retry does NOT count against max_attempts
                    attempt -= 1
                    continue
                else:
                    self._raise_for_status(response)

            # 429 rate limit — exempt from method safety check
            if status == 429 and status in retry.retry_on_status and attempt < retry.max_attempts:
                retry_after = _parse_retry_after(response.headers.get("retry-after"))
                if retry_after is not None:
                    delay = min(retry_after, retry.max_retry_after)
                else:
                    delay = min(
                        retry.backoff_base * (2 ** (attempt - 1)),
                        retry.backoff_max,
                    )
                    if retry.backoff_jitter:
                        delay = random.uniform(0, delay)
                time.sleep(delay)
                continue

            # 3xx not followed
            if 300 <= status < 400:
                raise HttpRedirectError(
                    f"HTTP {status} redirect from {method_upper} {url}"
                )

            # Other retryable status codes
            if (
                status in retry.retry_on_status
                and (method_upper in IDEMPOTENT_METHODS or retry.retry_unsafe_methods)
                and body_replayable
                and attempt < retry.max_attempts
            ):
                delay = min(
                    retry.backoff_base * (2 ** (attempt - 1)),
                    retry.backoff_max,
                )
                if retry.backoff_jitter:
                    delay = random.uniform(0, delay)
                time.sleep(delay)
                continue

            # Non-retryable error
            self._raise_for_status(response)

        # Unreachable, but satisfies type checkers
        raise AssertionError("unreachable")  # pragma: no cover

    # ------------------------------------------------------------------
    # Streaming request
    # ------------------------------------------------------------------

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
    ) -> Iterator[HttpStreamResponse]:
        """Open a streaming HTTP response as a context manager.

        No retry logic — single attempt only.

        Parameters
        ----------
        method:
            HTTP method.
        url:
            Target URL.
        headers:
            Caller-provided headers.
        content:
            Request body as bytes.
        params:
            URL query parameters.
        policy:
            Per-request policy override (only timeout/redirect used).

        Yields
        ------
        HttpStreamResponse
            A streaming response wrapper.
        """
        pol = policy or self._policy
        method_upper = method.upper()
        merged_headers = self._merge_headers(headers)
        timeout = httpx.Timeout(
            connect=pol.timeout.connect,
            read=pol.timeout.read,
            write=pol.timeout.write,
            pool=pol.timeout.pool,
        )

        try:
            with self._client.stream(
                method_upper,
                url,
                headers=merged_headers,
                content=content,
                params=params,
                timeout=timeout,
                follow_redirects=pol.redirect.follow_redirects,
            ) as response:
                status = response.status_code

                # 3xx not followed
                if 300 <= status < 400:
                    raise HttpRedirectError(
                        f"HTTP {status} redirect from {method_upper} {url}"
                    )

                # 4xx/5xx
                if status >= 400:
                    # Read body for error details
                    response.read()
                    url_str = str(response.url)
                    headers_dict = dict(response.headers)
                    body_preview = response.text[:500] if response.content else None
                    error_cls = map_status_to_error(status)

                    kwargs: dict[str, t.Any] = dict(
                        status_code=status,
                        headers=headers_dict,
                        body_preview=body_preview,
                        url=url_str,
                        method=method_upper,
                    )
                    if error_cls.__name__ == "HttpRateLimitError":
                        kwargs["retry_after"] = _parse_retry_after(
                            response.headers.get("retry-after")
                        )

                    raise error_cls(
                        f"HTTP {status} {method_upper} {url_str}",
                        **kwargs,
                    )

                yield HttpStreamResponse(response)

        except httpx.InvalidURL as exc:
            raise HttpRequestError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise _map_httpx_exception(exc) from exc
