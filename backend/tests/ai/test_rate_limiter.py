"""
AIRateLimiter tests: per-trader and global rate limiting.
Reference: 14_コスト管理 Section 2-1【監査4】
"""

import time
from unittest.mock import patch

from app.services.ai.rate_limiter import AIRateLimiter


class TestPerTraderLimit:
    """Per-trader rate limit: 10 calls/minute."""

    def test_allows_under_limit(self):
        limiter = AIRateLimiter(per_trader_per_minute=10, global_per_minute=100)
        for _ in range(9):
            assert limiter.can_call(trader_id=1)
            limiter.record_call(trader_id=1)
        assert limiter.can_call(trader_id=1)  # 10th allowed to check

    def test_blocks_at_limit(self):
        limiter = AIRateLimiter(per_trader_per_minute=3, global_per_minute=100)
        for _ in range(3):
            limiter.record_call(trader_id=1)
        assert not limiter.can_call(trader_id=1)

    def test_other_trader_not_affected(self):
        limiter = AIRateLimiter(per_trader_per_minute=2, global_per_minute=100)
        limiter.record_call(trader_id=1)
        limiter.record_call(trader_id=1)
        assert not limiter.can_call(trader_id=1)
        assert limiter.can_call(trader_id=2)  # Different trader unaffected

    def test_get_trader_count(self):
        limiter = AIRateLimiter()
        limiter.record_call(trader_id=5)
        limiter.record_call(trader_id=5)
        assert limiter.get_trader_count(5) == 2
        assert limiter.get_trader_count(99) == 0


class TestGlobalLimit:
    """Global rate limit: 30 calls/minute."""

    def test_global_limit_reached(self):
        limiter = AIRateLimiter(per_trader_per_minute=100, global_per_minute=5)
        for i in range(5):
            limiter.record_call(trader_id=i)  # different traders
        assert not limiter.can_call(trader_id=99)

    def test_get_global_count(self):
        limiter = AIRateLimiter()
        limiter.record_call(trader_id=1)
        limiter.record_call(trader_id=2)
        limiter.record_call(trader_id=3)
        assert limiter.get_global_count() == 3


class TestWindowExpiry:
    """Sliding window: calls expire after 60 seconds."""

    def test_expired_calls_cleaned_up(self):
        limiter = AIRateLimiter(per_trader_per_minute=2, global_per_minute=100)
        # Record calls
        limiter.record_call(trader_id=1)
        limiter.record_call(trader_id=1)
        assert not limiter.can_call(trader_id=1)

        # Simulate time passing (61 seconds)
        now = time.monotonic()
        # Manually set timestamps to old values
        limiter._trader_timestamps[1] = [now - 61, now - 61]
        limiter._global_timestamps = [now - 61, now - 61]

        # After cleanup, should be allowed
        assert limiter.can_call(trader_id=1)
        assert limiter.get_trader_count(1) == 0
