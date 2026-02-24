"""
Look-ahead Bias 排除テスト【監査2核心】.
Reference: 09_バックテストシミュレーション Section 3-4, 13_テスト戦略
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_ohlcv import HistoricalOhlcv
from app.services.backtest.historical_data_provider import HistoricalDataProvider
from app.services.backtest.simulation_clock import SimulationClock


async def _seed_hourly_bars(db: AsyncSession, pair: str, count: int) -> datetime:
    """H1バーをcount本作成. 返り値: 開始時刻."""
    base = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(count):
        ts = base + timedelta(hours=i)
        record = HistoricalOhlcv(
            pair=pair, timeframe="H1", timestamp=ts,
            open=150.0 + i * 0.01, high=150.5 + i * 0.01,
            low=149.5 + i * 0.01, close=150.0 + i * 0.01,
            volume=1000.0, source="test",
        )
        db.add(record)
    await db.flush()
    return base


class TestLookAheadBias:
    @pytest.mark.asyncio
    async def test_no_future_data_access(self, db_session: AsyncSession):
        """時刻T=12:00 で T 以降のデータがアクセス不可であること【監査2】."""
        base = await _seed_hourly_bars(db_session, "USD_JPY", 24)
        t12 = base + timedelta(hours=12)

        clock = SimulationClock(base, base + timedelta(hours=24))
        clock.advance_to(t12)

        provider = HistoricalDataProvider(db_session, clock)
        bars = await provider.get_ohlcv("USD_JPY", "H1", limit=100)

        # 13 bars: hours 0-12
        assert len(bars) == 13
        for bar in bars:
            assert bar.timestamp <= t12, f"Future bar found: {bar.timestamp}"

    @pytest.mark.asyncio
    async def test_data_isolation_per_step(self, db_session: AsyncSession):
        """各ステップで利用可能なデータが段階的に増える."""
        base = await _seed_hourly_bars(db_session, "USD_JPY", 10)

        clock = SimulationClock(base, base + timedelta(hours=10))
        provider = HistoricalDataProvider(db_session, clock)

        counts = []
        for hour in range(10):
            clock.advance_to(base + timedelta(hours=hour))
            bars = await provider.get_ohlcv("USD_JPY", "H1", limit=100)
            counts.append(len(bars))

        # 各ステップで利用可能バー数が単調増加
        for i in range(1, len(counts)):
            assert counts[i] >= counts[i - 1], (
                f"Step {i}: count {counts[i]} < prev {counts[i-1]}"
            )

    @pytest.mark.asyncio
    async def test_historical_ohlcv_end_clamp(self, db_session: AsyncSession):
        """get_historical_ohlcv の end がclock.now()でクランプされ、未来データが含まれない."""
        base = await _seed_hourly_bars(db_session, "USD_JPY", 24)

        clock = SimulationClock(base, base + timedelta(hours=24))
        clock.advance_to(base + timedelta(hours=6))

        provider = HistoricalDataProvider(db_session, clock)
        bars = await provider.get_historical_ohlcv(
            "USD_JPY", "H1",
            start=base,
            end=base + timedelta(hours=23),  # far future
        )
        assert len(bars) == 7  # hours 0-6 only
        assert bars[-1].timestamp == base + timedelta(hours=6)

    @pytest.mark.asyncio
    async def test_clock_cannot_go_backwards(self, db_session: AsyncSession):
        """SimulationClock が逆方向に進めないことを検証."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        clock = SimulationClock(base, base + timedelta(hours=24))
        clock.advance_to(base + timedelta(hours=12))

        with pytest.raises(ValueError, match="Cannot go back"):
            clock.advance_to(base + timedelta(hours=6))
