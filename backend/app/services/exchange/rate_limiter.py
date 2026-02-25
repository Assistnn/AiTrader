"""
OrderRateLimiter: order frequency control (GMO Coin measures).

Reference: 06_取引所抽象化 Section 8-3
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone


class OrderRateLimiter:
    """
    Order rate limiter.

    Reference: Section 8-3
    GMO Coin restrictions:
    - Min interval: 2 seconds between orders
    - Max per minute: 10 orders
    - Cancel+re-place: 3 seconds
    """

    def __init__(
        self,
        min_interval_sec: float = 2.0,
        max_per_minute: int = 10,
        max_per_second: int = 0,
    ):
        self.min_interval = min_interval_sec
        self.max_per_minute = max_per_minute
        self.max_per_second = max_per_second  # 0 = unlimited (default for FX)
        self.recent_orders: list[datetime] = []
        self.last_order_time: datetime | None = None

    async def wait_if_needed(self) -> float:
        """
        Wait if rate limit would be exceeded.

        Returns:
            Actual wait time in seconds (0 if no wait needed).
        """
        now = datetime.now(timezone.utc)
        total_wait = 0.0

        # Min interval check
        if self.last_order_time is not None:
            last = self.last_order_time
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (now - last).total_seconds()
            if elapsed < self.min_interval:
                wait = self.min_interval - elapsed
                await asyncio.sleep(wait)
                total_wait += wait
                now = datetime.now(timezone.utc)

        # Per-second rate check (bitbank: 6/sec)
        if self.max_per_second > 0:
            one_sec_ago = now - timedelta(seconds=1)
            recent_sec = [t for t in self.recent_orders if t > one_sec_ago]
            if len(recent_sec) >= self.max_per_second:
                wait_until = recent_sec[0] + timedelta(seconds=1)
                wait = (wait_until - now).total_seconds()
                if wait > 0:
                    await asyncio.sleep(wait)
                    total_wait += wait
                    now = datetime.now(timezone.utc)

        # Per-minute rate check
        one_min_ago = now - timedelta(minutes=1)
        self.recent_orders = [t for t in self.recent_orders if t > one_min_ago]

        if len(self.recent_orders) >= self.max_per_minute:
            wait_until = self.recent_orders[0] + timedelta(minutes=1)
            wait = (wait_until - now).total_seconds()
            if wait > 0:
                await asyncio.sleep(wait)
                total_wait += wait

        return total_wait

    def record_order(self) -> None:
        """Record that an order was placed."""
        now = datetime.now(timezone.utc)
        self.last_order_time = now
        self.recent_orders.append(now)

    def can_order_now(self) -> bool:
        """Check if an order can be placed right now (non-blocking)."""
        now = datetime.now(timezone.utc)

        if self.last_order_time is not None:
            last = self.last_order_time
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() < self.min_interval:
                return False

        # Per-second check
        if self.max_per_second > 0:
            one_sec_ago = now - timedelta(seconds=1)
            recent_sec = [t for t in self.recent_orders if t > one_sec_ago]
            if len(recent_sec) >= self.max_per_second:
                return False

        one_min_ago = now - timedelta(minutes=1)
        recent = [t for t in self.recent_orders if t > one_min_ago]
        return len(recent) < self.max_per_minute
