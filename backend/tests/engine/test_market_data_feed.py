"""
Tests for MarketDataFeed.
Reference: 16_実行エンジンとUI接続 Section 4-3
"""

import asyncio
from datetime import datetime, timezone

import pytest

from app.services.engine.market_data_feed import MarketDataFeed
from app.services.pipeline.data_types import Ticker


class MockDataProvider:
    def __init__(self, fail_after: int = -1):
        self.call_count = 0
        self._fail_after = fail_after

    async def get_ticker(self, pair: str) -> Ticker:
        self.call_count += 1
        if 0 < self._fail_after < self.call_count:
            raise ConnectionError("Mock failure")
        return Ticker(
            bid=150.0,
            ask=150.003,
            last=150.001,
            volume=1000.0,
            timestamp=datetime.now(timezone.utc),
        )


class TestMarketDataFeed:
    def test_init(self):
        feed = MarketDataFeed(MockDataProvider())
        assert not feed.is_connected()

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        provider = MockDataProvider()
        feed = MarketDataFeed(provider)

        await feed.connect(["USD_JPY"])
        assert feed.is_connected()

        await feed.disconnect()
        assert not feed.is_connected()

    @pytest.mark.asyncio
    async def test_on_tick_callback_called_directly(self):
        """Test on_tick delivery by calling it directly (bypassing poll loop)."""
        received = []

        async def callback(pair, ticker):
            received.append((pair, ticker))

        provider = MockDataProvider()
        feed = MarketDataFeed(provider)
        feed.add_on_tick(callback)

        ticker = Ticker(
            bid=150.0,
            ask=150.003,
            last=150.001,
            volume=1000.0,
            timestamp=datetime.now(timezone.utc),
        )
        await feed.on_tick("USD_JPY", ticker)

        assert len(received) == 1
        assert received[0][0] == "USD_JPY"
        assert received[0][1].bid == 150.0

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self):
        received_a = []
        received_b = []

        async def cb_a(pair, ticker):
            received_a.append(pair)

        async def cb_b(pair, ticker):
            received_b.append(pair)

        feed = MarketDataFeed(MockDataProvider())
        feed.add_on_tick(cb_a)
        feed.add_on_tick(cb_b)

        ticker = Ticker(
            bid=162.0, ask=162.005, last=162.002,
            volume=500.0, timestamp=datetime.now(timezone.utc),
        )
        await feed.on_tick("EUR_JPY", ticker)

        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_disconnect_tracking(self):
        provider = MockDataProvider()
        feed = MarketDataFeed(provider)
        feed._handle_disconnect_tracking()
        assert feed._disconnect_since is not None
        assert feed._reconnect_delay > 1.0

    @pytest.mark.asyncio
    async def test_poll_loop_disconnect(self):
        """Test that poll task is cleaned up on disconnect."""
        feed = MarketDataFeed(MockDataProvider())
        await feed.connect(["USD_JPY"])
        assert feed._poll_task is not None

        await feed.disconnect()
        assert feed._poll_task is None
