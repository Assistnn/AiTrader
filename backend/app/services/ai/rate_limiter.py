"""
AIRateLimiter: per-trader and global rate limiting for AI calls.

Reference: 14_コスト管理 Section 2-1【監査4】
"""

from __future__ import annotations

import time
from collections import defaultdict


class AIRateLimiter:
    """Rate limiter for AI API calls.

    Reference: 14_コスト管理 Section 2-1

    - Per trader: max 10 calls/minute (configurable)
    - Global: max 30 calls/minute (configurable)
    """

    def __init__(
        self,
        per_trader_per_minute: int = 10,
        global_per_minute: int = 30,
    ) -> None:
        self._per_trader_limit = per_trader_per_minute
        self._global_limit = global_per_minute
        self._trader_timestamps: dict[int, list[float]] = defaultdict(list)
        self._global_timestamps: list[float] = []

    def can_call(self, trader_id: int) -> bool:
        """Check if an AI call is allowed for this trader.

        Returns True if both per-trader and global limits allow.
        """
        now = time.monotonic()
        self._cleanup(now)

        # Check per-trader limit
        trader_calls = self._trader_timestamps[trader_id]
        if len(trader_calls) >= self._per_trader_limit:
            return False

        # Check global limit
        if len(self._global_timestamps) >= self._global_limit:
            return False

        return True

    def record_call(self, trader_id: int) -> None:
        """Record an AI call for rate limiting."""
        now = time.monotonic()
        self._trader_timestamps[trader_id].append(now)
        self._global_timestamps.append(now)

    def _cleanup(self, now: float) -> None:
        """Remove timestamps older than 60 seconds."""
        cutoff = now - 60.0

        # Cleanup global
        self._global_timestamps = [t for t in self._global_timestamps if t > cutoff]

        # Cleanup per-trader
        for trader_id in list(self._trader_timestamps.keys()):
            self._trader_timestamps[trader_id] = [
                t for t in self._trader_timestamps[trader_id] if t > cutoff
            ]
            if not self._trader_timestamps[trader_id]:
                del self._trader_timestamps[trader_id]

    def get_trader_count(self, trader_id: int) -> int:
        """Get current call count for a trader (within the window)."""
        self._cleanup(time.monotonic())
        return len(self._trader_timestamps.get(trader_id, []))

    def get_global_count(self) -> int:
        """Get current global call count (within the window)."""
        self._cleanup(time.monotonic())
        return len(self._global_timestamps)
