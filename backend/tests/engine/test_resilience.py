"""
Tests for resilience module (RetryWithBackoff, CircuitBreaker).
Reference: 16_実行エンジンとUI接続 Section 11
"""

import asyncio
import pytest
from app.services.engine.resilience import (
    RetryWithBackoff,
    CircuitBreaker,
    RetryExhaustedError,
    CircuitOpenError,
)


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_succeeds_without_retry(self):
        call_count = 0

        async def success():
            nonlocal call_count
            call_count += 1
            return "ok"

        retry = RetryWithBackoff(max_retries=3, base_delay=0.01)
        result = await retry.execute(success)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        call_count = 0

        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        retry = RetryWithBackoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        result = await retry.execute(fail_twice)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausts_retries(self):
        async def always_fail():
            raise ConnectionError("fail")

        retry = RetryWithBackoff(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        with pytest.raises(RetryExhaustedError):
            await retry.execute(always_fail)

    @pytest.mark.asyncio
    async def test_non_retryable_exception_raises_immediately(self):
        call_count = 0

        async def fail_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        retry = RetryWithBackoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        with pytest.raises(ValueError):
            await retry.execute(fail_with_value_error)
        assert call_count == 1


class TestCircuitBreaker:
    """Tests using check/record_success/record_failure API."""

    def test_closed_state_passes_through(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        cb.check()  # Should not raise
        cb.record_success()
        assert cb.state == "closed"

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        cb.record_failure()
        cb.record_failure()

        assert cb.state == "open"

        with pytest.raises(CircuitOpenError):
            cb.check()

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        cb.record_failure()
        assert cb.state == "open"

        await asyncio.sleep(0.1)

        # Should be half-open now
        assert cb.state == "half_open"
        cb.check()  # Should not raise in half_open
        cb.record_success()
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        cb.record_failure()
        assert cb.state == "open"

        await asyncio.sleep(0.1)

        assert cb.state == "half_open"
        cb.record_failure()
        assert cb.state == "open"
