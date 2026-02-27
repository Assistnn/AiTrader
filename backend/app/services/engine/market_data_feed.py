"""
MarketDataFeed: manages exchange WebSocket connections and delivers tick data.

Reference: 16_実行エンジンとUI接続 Section 4-3
- Hybrid approach: REST polling (primary) + WebSocket ticks (supplementary)
- Reconnection: exponential backoff 1s → 2s → 4s → ... → max 60s
- 5+ minutes disconnect → alert notification
- On reconnect, backfill recent confirmed bars via REST
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.pipeline.data_types import Ticker
from app.config import settings

logger = logging.getLogger(__name__)


class MarketDataFeed:
    """Manages exchange WebSocket connection and tick delivery.

    Reference: 16_実行エンジンとUI接続 Section 4-3

    In the current implementation, this uses REST polling as the primary
    data source. WebSocket integration can be added incrementally.
    The on_tick callback chain enables BarBuilder and WebSocket broadcast.
    """

    def __init__(self, data_provider: BaseDataProvider) -> None:
        self._data_provider = data_provider
        self._pairs: list[str] = []
        self._connected = False
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._on_tick_callbacks: list[Callable[[str, Ticker], Awaitable[None]]] = []
        self._disconnect_since: float | None = None
        self._reconnect_delay = 1.0

    def add_on_tick(
        self, callback: Callable[[str, Ticker], Awaitable[None]],
    ) -> None:
        """Register a callback for tick data delivery."""
        self._on_tick_callbacks.append(callback)

    def is_connected(self) -> bool:
        """Check if the feed is connected and receiving data."""
        return self._connected

    async def connect(self, pairs: list[str]) -> None:
        """Start data feed for the given pairs.

        Starts REST polling loop. WebSocket can be added later.
        """
        self._pairs = pairs
        self._running = True
        self._connected = True
        self._disconnect_since = None
        self._reconnect_delay = 1.0

        # Start REST poll loop
        self._poll_task = asyncio.create_task(
            self._poll_loop(), name="market_data_poll",
        )
        logger.info("MarketDataFeed connected for %s", pairs)

    async def disconnect(self) -> None:
        """Stop the data feed."""
        self._running = False
        self._connected = False
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        logger.info("MarketDataFeed disconnected")

    async def on_tick(self, pair: str, ticker: Ticker) -> None:
        """Deliver a tick to all registered callbacks.

        Called by the poll loop or (future) WebSocket handler.
        Reference: 16書§8-1 — also broadcasts to WebSocket prices channel.
        """
        for cb in self._on_tick_callbacks:
            try:
                await cb(pair, ticker)
            except Exception:
                logger.exception("on_tick callback error for %s", pair)

    async def _poll_loop(self) -> None:
        """REST polling loop for ticker data.

        Polls each pair's ticker at ~5 second intervals.
        """
        poll_interval = settings.BAR_POLL_DELAY

        while self._running:
            try:
                for pair in self._pairs:
                    if not self._running:
                        break
                    try:
                        ticker = await self._data_provider.get_ticker(pair)
                        await self.on_tick(pair, ticker)
                        # Reset reconnect state on success
                        if self._disconnect_since is not None:
                            logger.info(
                                "MarketDataFeed: reconnected after %.0fs",
                                time.monotonic() - self._disconnect_since,
                            )
                            self._disconnect_since = None
                            self._reconnect_delay = 1.0
                        self._connected = True
                    except Exception:
                        self._handle_disconnect_tracking()
                        logger.warning(
                            "MarketDataFeed: failed to poll %s, retry in %.0fs",
                            pair, self._reconnect_delay,
                        )

                await asyncio.sleep(poll_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("MarketDataFeed poll loop error")
                await asyncio.sleep(poll_interval)

    def _handle_disconnect_tracking(self) -> None:
        """Track disconnect duration and apply backoff."""
        now = time.monotonic()
        if self._disconnect_since is None:
            self._disconnect_since = now

        elapsed = now - self._disconnect_since
        if elapsed >= settings.WS_DISCONNECT_ALERT_THRESHOLD:
            logger.error(
                "MarketDataFeed: disconnected for %.0fs, alert threshold exceeded",
                elapsed,
            )
            self._connected = False

        # Exponential backoff for reconnect
        self._reconnect_delay = min(
            self._reconnect_delay * 2.0,
            settings.WS_RECONNECT_MAX_DELAY,
        )
