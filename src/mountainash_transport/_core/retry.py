"""Retry contract shared by every backend.

``RetryPolicy`` says how often and how patiently to retry. Each backend
implements the ``RetryStrategy`` contract in the way its SDK allows: SFTP runs
operations through ``ExecutorRetry`` (reconnecting between attempts), S3 hands
the attempt count to botocore, and ``HttpRequestEngine`` runs its own loop
because statuses, ``Retry-After`` and the 401 refresh are HTTP-specific. All of
them wait ``backoff_delay`` between attempts, except S3, which uses botocore's.

A body or input that cannot be sent again is never retried: callers pass
``replayable=False`` for it.
"""
from __future__ import annotations

import random
import threading
import time
import typing as t
from dataclasses import dataclass

T = t.TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """How many times to try an operation and how long to wait between tries.

    Attributes
    ----------
    max_attempts:
        Maximum number of total attempts (initial + retries).
    backoff_base:
        Base delay in seconds for exponential backoff.
    backoff_max:
        Maximum backoff delay in seconds.
    backoff_jitter:
        Whether to replace the delay with a random value between 0 and the delay.
    retry_on_status:
        HTTP only: status codes that should trigger a retry.
    retry_on_transport:
        Whether to retry transport-level errors (connection failures, timeouts).
    retry_unsafe_methods:
        HTTP only: whether to retry non-idempotent methods (POST, PATCH).
    max_retry_after:
        HTTP only: maximum number of seconds to wait for a ``Retry-After`` value.
        A longer ``Retry-After`` is capped at this value; the request is still retried.
    """

    max_attempts: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 60.0
    backoff_jitter: bool = True
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_on_transport: bool = True
    retry_unsafe_methods: bool = False
    max_retry_after: float = 120.0


def backoff_delay(policy: RetryPolicy, attempt: int) -> float:
    """Seconds to wait after failed attempt number *attempt* (1-based)."""
    delay = min(policy.backoff_base * 2 ** (attempt - 1), policy.backoff_max)
    return random.uniform(0, delay) if policy.backoff_jitter else delay


_PROFILE_FIELDS = (
    ("RETRY_MAX_ATTEMPTS", "max_attempts"),
    ("RETRY_BACKOFF_BASE", "backoff_base"),
    ("RETRY_BACKOFF_MAX", "backoff_max"),
)


def retry_policy_from(profile: object) -> RetryPolicy:
    """A ``RetryPolicy`` from a storage profile's ``RETRY_*`` fields; unset fields keep the defaults."""
    settings = {arg: value for field, arg in _PROFILE_FIELDS
                if (value := getattr(profile, field, None)) is not None}
    return RetryPolicy(**settings)


class RetryStrategy(t.Protocol):
    """Runs one storage operation, re-running it on transient failure."""

    def call(self, operation: t.Callable[[], T], *, replayable: bool = True) -> T: ...


class ExecutorRetry:
    """``RetryStrategy`` for SDKs without their own retries.

    Runs *operation* up to ``policy.max_attempts`` times, waiting
    ``backoff_delay`` and then calling *recover* before each re-attempt. Errors
    for which *is_transient* is false propagate at once. A transient failure
    of *recover* counts as the failure of the attempt it preceded.

    An operation that calls other operations of the same backend is retried as
    a whole: calls made while a ``call`` is running on the same thread run once.
    """

    def __init__(
        self,
        policy: RetryPolicy,
        *,
        is_transient: t.Callable[[BaseException], bool],
        recover: t.Callable[[], None],
    ) -> None:
        self._policy = policy
        self._is_transient = is_transient
        self._recover = recover
        self._active = threading.local()

    def call(self, operation: t.Callable[[], T], *, replayable: bool = True) -> T:
        if getattr(self._active, "running", False):
            return operation()
        retrying = replayable and self._policy.retry_on_transport
        attempts = self._policy.max_attempts if retrying else 1
        self._active.running = True
        try:
            attempt = 0
            while True:
                attempt += 1
                try:
                    if attempt > 1:
                        self._recover()
                    return operation()
                except Exception as exc:
                    if attempt >= attempts or not self._is_transient(exc):
                        raise
                time.sleep(backoff_delay(self._policy, attempt))
        finally:
            self._active.running = False
