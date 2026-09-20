from __future__ import annotations

import time

import pytest

from backend.app.core.reliability import RetryPolicy, retry_call, run_with_timeout


def test_retry_call_retries_transient_failures_with_bounded_backoff():
    attempts = 0
    sleeps: list[float] = []

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary network failure")
        return "ok"

    result = retry_call(
        operation,
        policy=RetryPolicy(max_attempts=3, backoff_seconds=0.25),
        is_retryable=lambda error: isinstance(error, ConnectionError),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert attempts == 3
    assert sleeps == [0.25, 0.5]


def test_retry_call_does_not_retry_deterministic_failures():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        raise ValueError("wrong document type")

    with pytest.raises(ValueError, match="wrong document type"):
        retry_call(
            operation,
            policy=RetryPolicy(max_attempts=4, backoff_seconds=0),
            is_retryable=lambda _error: False,
            sleep=lambda _delay: pytest.fail("deterministic failures must not sleep"),
        )

    assert attempts == 1


def test_retry_call_exhaustion_is_finite_and_returns_final_error():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        raise TimeoutError("upstream timeout")

    with pytest.raises(TimeoutError, match="upstream timeout"):
        retry_call(
            operation,
            policy=RetryPolicy(max_attempts=3, backoff_seconds=0),
            is_retryable=lambda error: isinstance(error, TimeoutError),
            sleep=lambda _delay: None,
        )

    assert attempts == 3


def test_run_with_timeout_returns_result_before_deadline():
    assert run_with_timeout(lambda: "done", timeout_seconds=0.2) == "done"


def test_run_with_timeout_raises_bounded_timeout():
    started = time.perf_counter()

    with pytest.raises(TimeoutError, match="timed out"):
        run_with_timeout(lambda: time.sleep(0.2), timeout_seconds=0.01)

    assert time.perf_counter() - started < 0.1


def test_retry_policy_rejects_unbounded_configuration():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=2, backoff_seconds=-1)
