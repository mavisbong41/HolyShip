from __future__ import annotations

import queue
import time
import urllib.error
from dataclasses import dataclass
from threading import Thread
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Finite retry settings shared by technical integration boundaries."""

    max_attempts: int = 3
    backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        if self.max_backoff_seconds < self.backoff_seconds:
            raise ValueError("max_backoff_seconds must not be below backoff_seconds")

    def delay_for_retry(self, retry_number: int) -> float:
        """Return capped exponential delay for a 1-based retry number."""
        if retry_number < 1:
            raise ValueError("retry_number must be positive")
        return min(
            self.max_backoff_seconds,
            self.backoff_seconds * (2 ** (retry_number - 1)),
        )


def retry_call(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    is_retryable: Callable[[Exception], bool],
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """Run an operation with finite retries for explicitly transient errors."""

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= policy.max_attempts or not is_retryable(exc):
                raise
            delay = policy.delay_for_retry(attempt)
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            sleep(delay)

    raise AssertionError("retry loop must return or raise")


def run_with_timeout(operation: Callable[[], T], *, timeout_seconds: float) -> T:
    """Run a synchronous boundary with a bounded caller wait.

    The helper thread is daemonized because Python cannot safely interrupt an
    arbitrary provider call. A timed-out provider therefore cannot hold up the
    processing worker or prevent the batch from progressing.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    results: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            results.put((True, operation()))
        except BaseException as exc:  # propagate provider failures to caller
            results.put((False, exc))

    Thread(target=invoke, name="holyship-time-limited-call", daemon=True).start()
    try:
        succeeded, value = results.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise TimeoutError(f"operation timed out after {timeout_seconds:.3f}s") from exc
    if succeeded:
        return value  # type: ignore[return-value]
    raise value  # type: ignore[misc]


def is_retryable_http_error(error: Exception) -> bool:
    """Retry network errors and HTTP statuses that conventionally recover."""

    if isinstance(error, (TimeoutError, ConnectionError, urllib.error.URLError)):
        return True
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 425, 429} or error.code >= 500
    return False
