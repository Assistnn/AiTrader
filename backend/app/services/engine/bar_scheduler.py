"""
BarConfirmationScheduler: manages bar close timing and emits BarClosedEvent.

Reference: 16_実行エンジンとUI接続 Section 4-2
- Monitors wall clock for bar close boundaries
- After close time + poll_delay, fetches confirmed bar via REST API
- Emits BarClosedEvent into an asyncio.Queue for the engine to consume
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.pipeline.data_types import OHLCV
from app.config import settings

logger = logging.getLogger(__name__)

# Timeframe definitions: (minutes, poll_delay_seconds)
_TIMEFRAME_SPECS: dict[str, tuple[int, float]] = {
    "M1": (1, settings.BAR_POLL_DELAY),
    "M5": (5, settings.BAR_POLL_DELAY),
    "M15": (15, settings.BAR_POLL_DELAY),
    "M30": (30, settings.BAR_POLL_DELAY),
    "H1": (60, 10.0),
    "H4": (240, 10.0),
    "D1": (1440, 30.0),
}


@dataclass
class BarClosedEvent:
    """A confirmed bar close event."""

    pair: str
    timeframe: str  # "M1" | "M5" | "M15" | "M30" | "H1" | "H4" | "D1"
    timestamp: datetime  # bar open time (UTC)
    ohlcv: OHLCV


class BarConfirmationScheduler:
    """Manages bar close timing and polls for confirmed bars.

    Reference: 16_実行エンジンとUI接続 Section 4-2
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[BarClosedEvent] = asyncio.Queue()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._pairs: list[str] = []
        self._data_provider: BaseDataProvider | None = None
        # Track last emitted bar per (pair, timeframe) to avoid duplicates
        self._last_emitted: dict[tuple[str, str], datetime] = {}

    async def start(
        self, pairs: list[str], data_provider: BaseDataProvider,
    ) -> None:
        """Start monitoring bar close timings for the given pairs."""
        self._pairs = pairs
        self._data_provider = data_provider
        self._running = True

        for tf in _TIMEFRAME_SPECS:
            task = asyncio.create_task(
                self._monitor_timeframe(tf), name=f"bar_scheduler_{tf}",
            )
            self._tasks.append(task)
        logger.info("BarConfirmationScheduler started for %s", pairs)

    async def stop(self) -> None:
        """Stop all monitoring tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("BarConfirmationScheduler stopped")

    async def wait_for_next_event(
        self, timeout: float = 60.0,
    ) -> BarClosedEvent | None:
        """Wait for the next bar closed event.

        Returns None on timeout.
        """
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def _monitor_timeframe(self, timeframe: str) -> None:
        """Monitor a single timeframe for bar close events."""
        minutes, poll_delay = _TIMEFRAME_SPECS[timeframe]

        while self._running:
            try:
                # Calculate time until next bar close
                now = datetime.now(timezone.utc)
                seconds_since_midnight = (
                    now.hour * 3600 + now.minute * 60 + now.second
                )
                interval_seconds = minutes * 60
                elapsed_in_bar = seconds_since_midnight % interval_seconds
                wait_seconds = interval_seconds - elapsed_in_bar

                if wait_seconds <= 0:
                    wait_seconds = interval_seconds

                # Wait until bar close + poll_delay
                await asyncio.sleep(wait_seconds + poll_delay)

                if not self._running:
                    break

                # Fetch confirmed bars for each pair
                for pair in self._pairs:
                    await self._fetch_and_emit(pair, timeframe)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(
                    "BarConfirmationScheduler error for %s", timeframe,
                )
                await asyncio.sleep(5.0)

    async def _fetch_and_emit(self, pair: str, timeframe: str) -> None:
        """Fetch the latest confirmed bar and emit event."""
        if self._data_provider is None:
            return

        try:
            bars = await self._data_provider.get_ohlcv(pair, timeframe, limit=1)
            if not bars:
                return

            bar = bars[-1]
            key = (pair, timeframe)

            # Deduplicate: don't re-emit the same bar
            if key in self._last_emitted and self._last_emitted[key] >= bar.timestamp:
                return

            self._last_emitted[key] = bar.timestamp

            event = BarClosedEvent(
                pair=pair,
                timeframe=timeframe,
                timestamp=bar.timestamp,
                ohlcv=bar,
            )
            await self._queue.put(event)
            logger.debug(
                "BarClosedEvent: %s %s @ %s",
                pair, timeframe, bar.timestamp.isoformat(),
            )
        except Exception:
            logger.exception(
                "Failed to fetch bar for %s %s", pair, timeframe,
            )
