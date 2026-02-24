"""
HistoricalDataProvider tests.
Reference: 09_バックテストシミュレーション Section 3-4【監査2: Look-ahead Bias 防止】
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_ohlcv import HistoricalOhlcv
from app.services.backtest.historical_data_provider import HistoricalDataProvider
from app.services.backtest.simulation_clock import SimulationClock


async def _seed_bars(db: AsyncSession, pair: str, timeframe: str, count: int, base_ts: datetime) -> None:
    """テスト用に historical_ohlcv にバーを投入."""
    for i in range(count):
        ts = base_ts + timedelta(hours=i)
        record = HistoricalOhlcv(
            pair=pair,
            timeframe=timeframe,
            timestamp=ts,
            open=100.0 + i * 0.1,
            high=100.5 + i * 0.1,
            low=99.5 + i * 0.1,
            close=100.0 + i * 0.1,
            volume=1000.0,
            source="test",
        )
        db.add(record)
    await db.flush()


class TestHistoricalDataProvider:
    @pytest.mark.asyncio
    async def test_get_ohlcv_only_returns_before_clock(self, db_session: AsyncSession):
        """get_ohlcv は clock.now() 以前のバーのみ返す【監査2】."""
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        await _seed_bars(db_session, "USD_JPY", "H1", 10, base)

        # Clock at hour 5 → only bars 0-5 should be returned
        clock = SimulationClock(base, base + timedelta(hours=20))
        clock.advance_to(base + timedelta(hours=5))

        provider = HistoricalDataProvider(db_session, clock)
        bars = await provider.get_ohlcv("USD_JPY", "H1", limit=100)

        assert len(bars) == 6  # hours 0,1,2,3,4,5
        for bar in bars:
            assert bar.timestamp <= clock.now()

    @pytest.mark.asyncio
    async def test_get_historical_ohlcv_clamps_end(self, db_session: AsyncSession):
        """get_historical_ohlcv の end は clock.now() でクランプされる."""
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        await _seed_bars(db_session, "USD_JPY", "H1", 10, base)

        clock = SimulationClock(base, base + timedelta(hours=20))
        clock.advance_to(base + timedelta(hours=3))

        provider = HistoricalDataProvider(db_session, clock)
        # Requesting up to hour 10, but clock at hour 3 → clamped to hour 3
        bars = await provider.get_historical_ohlcv(
            "USD_JPY", "H1",
            start=base,
            end=base + timedelta(hours=10),
        )
        assert len(bars) == 4  # hours 0,1,2,3
        assert all(b.timestamp <= clock.now() for b in bars)

    @pytest.mark.asyncio
    async def test_empty_result_when_no_data(self, db_session: AsyncSession):
        """データがない場合は空リスト."""
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        clock = SimulationClock(base, base + timedelta(hours=10))

        provider = HistoricalDataProvider(db_session, clock)
        bars = await provider.get_ohlcv("UNKNOWN", "H1", limit=10)
        assert bars == []

    @pytest.mark.asyncio
    async def test_get_ticker_from_ohlcv(self, db_session: AsyncSession):
        """get_ticker は直近 OHLCV の close を使う."""
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        await _seed_bars(db_session, "USD_JPY", "M1", 3, base)

        clock = SimulationClock(base, base + timedelta(hours=10))
        clock.advance_to(base + timedelta(minutes=2))

        provider = HistoricalDataProvider(db_session, clock)
        ticker = await provider.get_ticker("USD_JPY")
        # M1 bars: minute 0, 60, 120. At minute 2, only minute 0 bar available.
        assert ticker.bid > 0
        assert ticker.ask > ticker.bid
