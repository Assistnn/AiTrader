"""
Tests for BarConfirmationScheduler.
Reference: 16_実行エンジンとUI接続 Section 4-2
"""

import asyncio
from datetime import datetime, timezone

import pytest

from app.services.engine.bar_scheduler import (
    BarClosedEvent,
    BarConfirmationScheduler,
)
from app.services.pipeline.data_types import OHLCV


class TestBarClosedEvent:
    def test_event_creation(self):
        ohlcv = OHLCV(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            open=150.0, high=151.0, low=149.0, close=150.5, volume=1000.0,
        )
        event = BarClosedEvent(
            pair="USD_JPY",
            timeframe="H1",
            timestamp=ohlcv.timestamp,
            ohlcv=ohlcv,
        )
        assert event.pair == "USD_JPY"
        assert event.timeframe == "H1"


class TestBarConfirmationScheduler:
    def test_init(self):
        scheduler = BarConfirmationScheduler()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_wait_for_next_event_timeout(self):
        scheduler = BarConfirmationScheduler()
        result = await scheduler.wait_for_next_event(timeout=0.05)
        assert result is None

    @pytest.mark.asyncio
    async def test_manual_event_injection(self):
        scheduler = BarConfirmationScheduler()
        ohlcv = OHLCV(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            open=150.0, high=151.0, low=149.0, close=150.5, volume=1000.0,
        )
        event = BarClosedEvent(
            pair="USD_JPY",
            timeframe="M5",
            timestamp=ohlcv.timestamp,
            ohlcv=ohlcv,
        )
        await scheduler._queue.put(event)
        received = await scheduler.wait_for_next_event(timeout=1.0)
        assert received is not None
        assert received.pair == "USD_JPY"
        assert received.timeframe == "M5"

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        scheduler = BarConfirmationScheduler()

        class MockDataProvider:
            async def get_ohlcv(self, pair, tf, limit):
                return []

        await scheduler.start(["USD_JPY"], MockDataProvider())
        assert scheduler._running is True
        assert len(scheduler._tasks) > 0

        await scheduler.stop()
        assert scheduler._running is False
        assert len(scheduler._tasks) == 0
