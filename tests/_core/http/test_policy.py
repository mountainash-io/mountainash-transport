"""Tests for HTTP request policy dataclasses."""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from mountainash_transport._core.http.policy import (
    IDEMPOTENT_METHODS,
    SAFE_METHODS,
    RedirectPolicy,
    RequestPolicy,
    RetryPolicy,
    TimeoutPolicy,
)


# ---------------------------------------------------------------------------
# Method sets
# ---------------------------------------------------------------------------


class TestMethodSets:
    def test_safe_methods_contains_expected(self) -> None:
        assert SAFE_METHODS == frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

    def test_idempotent_methods_is_superset_of_safe(self) -> None:
        assert SAFE_METHODS.issubset(IDEMPOTENT_METHODS)

    def test_idempotent_methods_contains_put_and_delete(self) -> None:
        assert "PUT" in IDEMPOTENT_METHODS
        assert "DELETE" in IDEMPOTENT_METHODS

    def test_post_not_in_idempotent(self) -> None:
        assert "POST" not in IDEMPOTENT_METHODS

    def test_patch_not_in_idempotent(self) -> None:
        assert "PATCH" not in IDEMPOTENT_METHODS

    def test_post_not_in_safe(self) -> None:
        assert "POST" not in SAFE_METHODS

    def test_safe_methods_is_frozenset(self) -> None:
        assert isinstance(SAFE_METHODS, frozenset)

    def test_idempotent_methods_is_frozenset(self) -> None:
        assert isinstance(IDEMPOTENT_METHODS, frozenset)


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


class TestRetryPolicy:
    def test_default_max_attempts(self) -> None:
        assert RetryPolicy().max_attempts == 3

    def test_default_backoff_base(self) -> None:
        assert RetryPolicy().backoff_base == 1.0

    def test_default_backoff_max(self) -> None:
        assert RetryPolicy().backoff_max == 60.0

    def test_default_backoff_jitter(self) -> None:
        assert RetryPolicy().backoff_jitter is True

    def test_default_retry_on_status(self) -> None:
        assert RetryPolicy().retry_on_status == (429, 500, 502, 503, 504)

    def test_default_retry_on_transport(self) -> None:
        assert RetryPolicy().retry_on_transport is True

    def test_default_retry_unsafe_methods(self) -> None:
        assert RetryPolicy().retry_unsafe_methods is False

    def test_default_max_retry_after(self) -> None:
        assert RetryPolicy().max_retry_after == 120.0

    def test_frozen_max_attempts(self) -> None:
        policy = RetryPolicy()
        with pytest.raises(FrozenInstanceError):
            policy.max_attempts = 5  # type: ignore[misc]

    def test_frozen_retry_on_status(self) -> None:
        policy = RetryPolicy()
        with pytest.raises(FrozenInstanceError):
            policy.retry_on_status = (500,)  # type: ignore[misc]

    def test_custom_values(self) -> None:
        policy = RetryPolicy(max_attempts=5, backoff_base=2.0, retry_unsafe_methods=True)
        assert policy.max_attempts == 5
        assert policy.backoff_base == 2.0
        assert policy.retry_unsafe_methods is True


# ---------------------------------------------------------------------------
# TimeoutPolicy
# ---------------------------------------------------------------------------


class TestTimeoutPolicy:
    def test_default_connect(self) -> None:
        assert TimeoutPolicy().connect == 10.0

    def test_default_read(self) -> None:
        assert TimeoutPolicy().read == 30.0

    def test_default_write(self) -> None:
        assert TimeoutPolicy().write == 30.0

    def test_default_pool(self) -> None:
        assert TimeoutPolicy().pool == 10.0

    def test_frozen_connect(self) -> None:
        policy = TimeoutPolicy()
        with pytest.raises(FrozenInstanceError):
            policy.connect = 5.0  # type: ignore[misc]

    def test_custom_values(self) -> None:
        policy = TimeoutPolicy(connect=5.0, read=60.0)
        assert policy.connect == 5.0
        assert policy.read == 60.0
        assert policy.write == 30.0  # default unchanged


# ---------------------------------------------------------------------------
# RedirectPolicy
# ---------------------------------------------------------------------------


class TestRedirectPolicy:
    def test_default_follow_redirects(self) -> None:
        assert RedirectPolicy().follow_redirects is True

    def test_default_max_redirects(self) -> None:
        assert RedirectPolicy().max_redirects == 10

    def test_frozen_follow_redirects(self) -> None:
        policy = RedirectPolicy()
        with pytest.raises(FrozenInstanceError):
            policy.follow_redirects = False  # type: ignore[misc]

    def test_custom_values(self) -> None:
        policy = RedirectPolicy(follow_redirects=False, max_redirects=5)
        assert policy.follow_redirects is False
        assert policy.max_redirects == 5


# ---------------------------------------------------------------------------
# RequestPolicy
# ---------------------------------------------------------------------------


class TestRequestPolicy:
    def test_default_retry_is_retry_policy(self) -> None:
        assert isinstance(RequestPolicy().retry, RetryPolicy)

    def test_default_retry_uses_defaults(self) -> None:
        assert RequestPolicy().retry == RetryPolicy()

    def test_default_timeout_is_timeout_policy(self) -> None:
        assert isinstance(RequestPolicy().timeout, TimeoutPolicy)

    def test_default_timeout_uses_defaults(self) -> None:
        assert RequestPolicy().timeout == TimeoutPolicy()

    def test_default_redirect_is_redirect_policy(self) -> None:
        assert isinstance(RequestPolicy().redirect, RedirectPolicy)

    def test_default_redirect_uses_defaults(self) -> None:
        assert RequestPolicy().redirect == RedirectPolicy()

    def test_default_auth_refresh_on_401(self) -> None:
        assert RequestPolicy().auth_refresh_on_401 is True

    def test_frozen_auth_refresh_on_401(self) -> None:
        policy = RequestPolicy()
        with pytest.raises(FrozenInstanceError):
            policy.auth_refresh_on_401 = False  # type: ignore[misc]

    def test_each_instance_gets_independent_sub_policies(self) -> None:
        p1 = RequestPolicy()
        p2 = RequestPolicy()
        # Both equal but independent (frozen, so equality is by value)
        assert p1.retry == p2.retry
        assert p1.timeout == p2.timeout
        assert p1.redirect == p2.redirect


# ---------------------------------------------------------------------------
# RequestPolicy.with_* mutation helpers
# ---------------------------------------------------------------------------


class TestRequestPolicyWithHelpers:
    def test_with_timeout_returns_new_instance(self) -> None:
        original = RequestPolicy()
        new_timeout = TimeoutPolicy(connect=5.0)
        result = original.with_timeout(new_timeout)
        assert result is not original

    def test_with_timeout_sets_timeout(self) -> None:
        new_timeout = TimeoutPolicy(connect=5.0)
        result = RequestPolicy().with_timeout(new_timeout)
        assert result.timeout == new_timeout

    def test_with_timeout_preserves_other_fields(self) -> None:
        original = RequestPolicy(auth_refresh_on_401=False)
        result = original.with_timeout(TimeoutPolicy(connect=5.0))
        assert result.retry == original.retry
        assert result.redirect == original.redirect
        assert result.auth_refresh_on_401 is False

    def test_with_retry_returns_new_instance(self) -> None:
        original = RequestPolicy()
        new_retry = RetryPolicy(max_attempts=5)
        result = original.with_retry(new_retry)
        assert result is not original

    def test_with_retry_sets_retry(self) -> None:
        new_retry = RetryPolicy(max_attempts=5)
        result = RequestPolicy().with_retry(new_retry)
        assert result.retry == new_retry

    def test_with_retry_preserves_other_fields(self) -> None:
        original = RequestPolicy(auth_refresh_on_401=False)
        result = original.with_retry(RetryPolicy(max_attempts=5))
        assert result.timeout == original.timeout
        assert result.redirect == original.redirect
        assert result.auth_refresh_on_401 is False

    def test_with_redirect_returns_new_instance(self) -> None:
        original = RequestPolicy()
        new_redirect = RedirectPolicy(follow_redirects=False)
        result = original.with_redirect(new_redirect)
        assert result is not original

    def test_with_redirect_sets_redirect(self) -> None:
        new_redirect = RedirectPolicy(follow_redirects=False)
        result = RequestPolicy().with_redirect(new_redirect)
        assert result.redirect == new_redirect

    def test_with_redirect_preserves_other_fields(self) -> None:
        original = RequestPolicy(auth_refresh_on_401=False)
        result = original.with_redirect(RedirectPolicy(follow_redirects=False))
        assert result.retry == original.retry
        assert result.timeout == original.timeout
        assert result.auth_refresh_on_401 is False

    def test_chaining_with_helpers(self) -> None:
        result = (
            RequestPolicy()
            .with_timeout(TimeoutPolicy(connect=5.0))
            .with_retry(RetryPolicy(max_attempts=1))
            .with_redirect(RedirectPolicy(follow_redirects=False))
        )
        assert result.timeout.connect == 5.0
        assert result.retry.max_attempts == 1
        assert result.redirect.follow_redirects is False
        assert result.auth_refresh_on_401 is True  # default preserved
