"""The shared retry executor: attempts, transient classification, recovery, nesting."""
from __future__ import annotations

import typing as t
from unittest.mock import patch

import pytest

from mountainash_transport._core.retry import ExecutorRetry, RetryPolicy, backoff_delay


class Transient(Exception):
    pass


class Permanent(Exception):
    pass


def _flaky(failures: list[BaseException], result: str = "ok") -> tuple[t.Callable[[], str], list[int]]:
    calls: list[int] = []

    def operation() -> str:
        calls.append(len(calls) + 1)
        if failures:
            raise failures.pop(0)
        return result

    return operation, calls


def _executor(policy: RetryPolicy, recoveries: list[int] | None = None,
              recover: t.Callable[[], None] | None = None) -> ExecutorRetry:
    def default_recover() -> None:
        if recoveries is not None:
            recoveries.append(1)

    return ExecutorRetry(policy, is_transient=lambda exc: isinstance(exc, Transient),
                         recover=recover or default_recover)


@pytest.fixture(autouse=True)
def no_sleep() -> t.Iterator[t.Any]:
    with patch("mountainash_transport._core.retry.time.sleep") as sleep:
        yield sleep


def test_transient_failures_are_retried_with_recovery_between_attempts() -> None:
    recoveries: list[int] = []
    operation, calls = _flaky([Transient(), Transient()])
    assert _executor(RetryPolicy(max_attempts=3), recoveries).call(operation) == "ok"
    assert calls == [1, 2, 3]
    assert recoveries == [1, 1]


def test_gives_up_after_max_attempts_with_the_last_error() -> None:
    last = Transient("third")
    operation, calls = _flaky([Transient(), Transient(), last])
    with pytest.raises(Transient) as caught:
        _executor(RetryPolicy(max_attempts=3)).call(operation)
    assert caught.value is last
    assert calls == [1, 2, 3]


def test_permanent_failure_is_not_retried() -> None:
    recoveries: list[int] = []
    operation, calls = _flaky([Permanent()])
    with pytest.raises(Permanent):
        _executor(RetryPolicy(max_attempts=3), recoveries).call(operation)
    assert calls == [1]
    assert recoveries == []


@pytest.mark.parametrize("policy, replayable", [
    (RetryPolicy(max_attempts=3), False),
    (RetryPolicy(max_attempts=3, retry_on_transport=False), True),
    (RetryPolicy(max_attempts=1), True),
])
def test_single_attempt_cases(policy: RetryPolicy, replayable: bool) -> None:
    operation, calls = _flaky([Transient()])
    with pytest.raises(Transient):
        _executor(policy).call(operation, replayable=replayable)
    assert calls == [1]


def test_transient_recovery_failure_counts_as_that_attempt() -> None:
    attempts_at_recovery: list[int] = []
    operation, calls = _flaky([Transient()])

    def recover() -> None:
        attempts_at_recovery.append(len(calls))
        if len(attempts_at_recovery) == 1:
            raise Transient("reconnect refused")

    assert _executor(RetryPolicy(max_attempts=3), recover=recover).call(operation) == "ok"
    assert calls == [1, 2]                 # attempt 2 was lost to the failed reconnect
    assert attempts_at_recovery == [1, 1]


def test_nested_calls_run_once_and_the_outer_call_retries() -> None:
    executor = _executor(RetryPolicy(max_attempts=3))
    inner, inner_calls = _flaky([Transient()])
    outer_calls: list[int] = []

    def outer() -> str:
        outer_calls.append(1)
        return executor.call(inner)

    assert executor.call(outer) == "ok"
    assert inner_calls == [1, 2]
    assert outer_calls == [1, 1]


def test_waits_follow_backoff(no_sleep: t.Any) -> None:
    policy = RetryPolicy(max_attempts=3, backoff_base=0.5, backoff_max=0.75, backoff_jitter=False)
    operation, _ = _flaky([Transient(), Transient()])
    _executor(policy).call(operation)
    assert [c.args[0] for c in no_sleep.call_args_list] == [0.5, 0.75]


def test_backoff_delay_is_capped_and_jitter_stays_below_the_cap() -> None:
    policy = RetryPolicy(backoff_base=1.0, backoff_max=3.0, backoff_jitter=False)
    assert [backoff_delay(policy, n) for n in (1, 2, 3, 4)] == [1.0, 2.0, 3.0, 3.0]
    jittered = RetryPolicy(backoff_base=1.0, backoff_max=3.0)
    assert all(0 <= backoff_delay(jittered, 4) <= 3.0 for _ in range(50))
