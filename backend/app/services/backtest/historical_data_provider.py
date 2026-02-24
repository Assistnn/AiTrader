"""
HistoricalDataProvider: DB からヒストリカル OHLCV を取得するプロバイダ.
全クエリに clock.now() 以前の時刻制限を強制し、Look-ahead Bias を物理的に排除する【監査2】.

Reference: 09_バックテストシミュレーション Section 3-1, 02_データパイプライン Section 2-3
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_ohlcv import HistoricalOhlcv
from app.services.backtest.simulation_clock import SimulationClock
from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.pipeline.data_types import OHLCV, Spread, Ticker


class HistoricalDataProvider(BaseDataProvider):
    """DB ベースのヒストリカルデータプロバイダ.

    全てのクエリは clock.now() 以前のデータのみ返す。
    これにより Look-ahead Bias を物理的に排除する。
    """

    def __init__(self, db: AsyncSession, clock: SimulationClock) -> None:
        self._db = db
        self._clock = clock

    def _max_timestamp(self) -> datetime:
        """取得可能な最大タイムスタンプ = clock.now()."""
        return self._clock.now()

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        """clock.now() 以前の直近 N 本の OHLCV バーを取得."""
        stmt = (
            select(HistoricalOhlcv)
            .where(
                HistoricalOhlcv.pair == pair,
                HistoricalOhlcv.timeframe == timeframe,
                HistoricalOhlcv.timestamp <= self._max_timestamp(),
            )
            .order_by(HistoricalOhlcv.timestamp.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()
        return [self._to_ohlcv(r) for r in reversed(rows)]

    async def get_historical_ohlcv(
        self, pair: str, timeframe: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        """指定期間の OHLCV を取得. end は clock.now() でクランプ."""
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        clamped_end = min(end, self._max_timestamp())
        if clamped_end < start:
            return []
        stmt = (
            select(HistoricalOhlcv)
            .where(
                HistoricalOhlcv.pair == pair,
                HistoricalOhlcv.timeframe == timeframe,
                HistoricalOhlcv.timestamp >= start,
                HistoricalOhlcv.timestamp <= clamped_end,
            )
            .order_by(HistoricalOhlcv.timestamp.asc())
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()
        return [self._to_ohlcv(r) for r in rows]

    async def get_ticker(self, pair: str) -> Ticker:
        """直近の OHLCV から Ticker を生成."""
        bars = await self.get_ohlcv(pair, "M1", limit=1)
        if not bars:
            return Ticker(
                timestamp=self._clock.now(),
                bid=0.0, ask=0.0, last=0.0, volume=0.0,
            )
        bar = bars[0]
        spread = 0.02 if "JPY" in pair else 0.0002
        return Ticker(
            timestamp=bar.timestamp,
            bid=bar.close,
            ask=bar.close + spread,
            last=bar.close,
            volume=bar.volume,
        )

    async def get_spread(self, pair: str) -> Spread:
        """直近の OHLCV から Spread を生成."""
        ticker = await self.get_ticker(pair)
        spread_raw = ticker.ask - ticker.bid
        pip_size = 0.01 if "JPY" in pair else 0.0001
        spread_pips = spread_raw / pip_size
        return Spread(
            timestamp=ticker.timestamp,
            bid=ticker.bid,
            ask=ticker.ask,
            spread_raw=spread_raw,
            spread_pips=spread_pips,
        )

    async def subscribe_ticks(
        self,
        pairs: list[str],
        callback: Callable[[str, Ticker], Awaitable[None]],
    ) -> None:
        """バックテストモードではティック購読は no-op."""

    async def unsubscribe_all(self) -> None:
        """バックテストモードでは no-op."""

    @staticmethod
    def _to_ohlcv(row: HistoricalOhlcv) -> OHLCV:
        ts = row.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return OHLCV(
            timestamp=ts,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
