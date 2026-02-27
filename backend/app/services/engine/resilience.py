"""
Resilience utilities: RetryWithBackoff and CircuitBreaker.

Reference: 16_実行エンジンとUI接続 Section 11
- RetryWithBackoff: exponential backoff retry decorator
- CircuitBreaker: suspend requests after consecutive failures
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retryable exceptions (16書§11-1)
RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.NetworkError,
    ConnectionError,
    OSError,
)


class RetryExhaustedError(Exception):
    """All retry attempts exhausted."""

    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_error}")


class CircuitOpenError(Exception):
    """Circuit breaker is open — requests are blocked."""

    def __init__(self, recovery_at: float):
        self.recovery_at = recovery_at
        super().__init__("Circuit breaker is open")


class RetryWithBackoff:
    """Exponential backoff retry.

    Reference: 16_実行エンジンとUI接続 Section 11-1

    Usage:
        retry = RetryWithBackoff(max_retries=3)
        result = await retry.execute(some_async_func, arg1, arg2)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        retryable_exceptions: tuple[type[Exception], ...] = RETRYABLE_EXCEPTIONS,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retryable_exceptions = retryable_exceptions

    async def execute(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any,
    ) -> T:
        """Execute function with retry."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.backoff_factor ** attempt),
                        self.max_delay,
                    )
                    logger.warning(
                        "Retry %d/%d after %.1fs: %s",
                        attempt + 1, self.max_retries, delay, e,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Retry exhausted after %d attempts: %s",
                        self.max_retries + 1, e,
                    )
        raise RetryExhaustedError(self.max_retries + 1, last_error)  # type: ignore[arg-type]


class CircuitBreaker:
    """Circuit breaker pattern.

    Reference: 16_実行エンジンとUI接続 Section 11-2

    States:
    - closed: normal operation, requests pass through
    - open: requests blocked, waiting for recovery timeout
    - half_open: one test request allowed, success → closed, failure → open

    Usage:
        cb = CircuitBreaker(failure_threshold=5)
        cb.check()           # raises CircuitOpenError if open
        try:
            result = await some_func()
            cb.record_success()
        except Exception:
            cb.record_failure()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state: str = "closed"
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> str:
        """Current circuit state."""
        if self._state == "open":
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = "half_open"
        return self._state

    def check(self) -> None:
        """Check if request is allowed. Raises CircuitOpenError if circuit is open."""
        current = self.state
        if current == "open":
            raise CircuitOpenError(self._last_failure_time + self.recovery_timeout)

    def record_success(self) -> None:
        """Record a successful operation."""
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        """Record a failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                "CircuitBreaker opened after %d consecutive failures",
                self._failure_count,
            )

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._failure_count = 0
        self._state = "closed"
