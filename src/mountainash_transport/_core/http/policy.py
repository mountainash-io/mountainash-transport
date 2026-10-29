"""HTTP request policy dataclasses.

Frozen dataclasses that control retry, timeout, and redirect behaviour for
HTTP requests. All instances are immutable; use the ``with_*`` helpers on
``RequestPolicy`` to derive modified copies.

Usage
-----
::

    from mountainash_transport._core.http.policy import RequestPolicy, RetryPolicy, TimeoutPolicy

    policy = (
        RequestPolicy()
        .with_timeout(TimeoutPolicy(connect=5.0, read=60.0))
        .with_retry(RetryPolicy(max_attempts=5))
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

# ---------------------------------------------------------------------------
# Method sets
# ---------------------------------------------------------------------------

SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
"""HTTP methods that are safe (no side effects)."""

IDEMPOTENT_METHODS: frozenset[str] = SAFE_METHODS | frozenset({"PUT", "DELETE"})
"""HTTP methods that are idempotent (safe + PUT + DELETE)."""


# ---------------------------------------------------------------------------
# Policy dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryPolicy:
    """Controls retry behaviour for HTTP requests.

    Attributes
    ----------
    max_attempts:
        Maximum number of total attempts (initial + retries).
    backoff_base:
        Base delay in seconds for exponential backoff.
    backoff_max:
        Maximum backoff delay in seconds.
    backoff_jitter:
        Whether to add random jitter to the backoff delay.
    retry_on_status:
        HTTP status codes that should trigger a retry.
    retry_on_transport:
        Whether to retry on transport-level errors (connection failures, timeouts).
    retry_unsafe_methods:
        Whether to retry non-idempotent methods (POST, PATCH).
    max_retry_after:
        Maximum number of seconds to honour a ``Retry-After`` header value.
        Requests with a ``Retry-After`` exceeding this value will not be retried.
    """

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
    """Controls per-phase timeouts for HTTP requests.

    Attributes
    ----------
    connect:
        Seconds to wait when establishing a connection.
    read:
        Seconds to wait between bytes received from the server.
    write:
        Seconds to wait between bytes sent to the server.
    pool:
        Seconds to wait for a connection from the connection pool.
    """

    connect: float = 10.0
    read: float = 30.0
    write: float = 30.0
    pool: float = 10.0


@dataclass(frozen=True)
class RedirectPolicy:
    """Controls redirect following behaviour for HTTP requests.

    Attributes
    ----------
    follow_redirects:
        Whether to automatically follow 3xx redirects.
    max_redirects:
        Maximum number of redirects to follow before raising an error.
    """

    follow_redirects: bool = True
    max_redirects: int = 10


@dataclass(frozen=True)
class RequestPolicy:
    """Composite policy governing retry, timeout, and redirect behaviour.

    All sub-policies default to their own defaults. Use the ``with_*``
    helpers to derive modified copies without mutating the original.

    Attributes
    ----------
    retry:
        Retry behaviour.
    timeout:
        Per-phase timeout values.
    redirect:
        Redirect following behaviour.
    auth_refresh_on_401:
        Whether to attempt an auth token refresh and re-send the request on a
        401 Unauthorized response.
    """

    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    redirect: RedirectPolicy = field(default_factory=RedirectPolicy)
    auth_refresh_on_401: bool = True

    def with_timeout(self, timeout: TimeoutPolicy) -> RequestPolicy:
        """Return a new ``RequestPolicy`` with the given timeout policy."""
        return replace(self, timeout=timeout)

    def with_retry(self, retry: RetryPolicy) -> RequestPolicy:
        """Return a new ``RequestPolicy`` with the given retry policy."""
        return replace(self, retry=retry)

    def with_redirect(self, redirect: RedirectPolicy) -> RequestPolicy:
        """Return a new ``RequestPolicy`` with the given redirect policy."""
        return replace(self, redirect=redirect)
