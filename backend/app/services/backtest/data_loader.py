"""
DataLoader: ヒストリカルデータの取得・蓄積.
Reference: 09_バックテストシミュレーション Section 2-3
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_ohlcv import HistoricalOhlcv
from app.services.pipeline.data_types import OHLCV


class DataLoader:
    """ヒストリカルデータの DB 蓄積・品質チェック."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def store_bars(
        self,
        pair: str,
        timeframe: str,
        bars: list[OHLCV],
        source: str = "api",
    ) -> int:
        """OHLCV バーを DB に一括保存（重複スキップ）. 返り値: 新規挿入数."""
        inserted = 0
        for bar in bars:
            ts = bar.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            # 重複チェック
            stmt = select(HistoricalOhlcv.id).where(
                HistoricalOhlcv.pair == pair,
                HistoricalOhlcv.timeframe == timeframe,
                HistoricalOhlcv.timestamp == ts,
            )
            result = await self._db.execute(stmt)
            if result.scalar_one_or_none() is not None:
                continue

            record = HistoricalOhlcv(
                pair=pair,
                timeframe=timeframe,
                timestamp=ts,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                source=source,
            )
            self._db.add(record)
            inserted += 1

        if inserted > 0:
            await self._db.flush()
        return inserted

    async def check_data_availability(
        self,
        pair: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> dict:
        """データ利用可能性チェック. 返り値: {available, total_bars, missing_estimate}."""
        start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)

        stmt = select(func.count(HistoricalOhlcv.id)).where(
            HistoricalOhlcv.pair == pair,
            HistoricalOhlcv.timeframe == timeframe,
            HistoricalOhlcv.timestamp >= start_dt,
            HistoricalOhlcv.timestamp <= end_dt,
        )
        result = await self._db.execute(stmt)
        count = result.scalar_one()

        # 期待本数の概算
        days = (end - start).days + 1
        tf_map = {"M1": 1440, "M5": 288, "M15": 96, "M30": 48, "H1": 24, "H4": 6, "D1": 1}
        bars_per_day = tf_map.get(timeframe, 24)
        expected = days * bars_per_day

        return {
            "available": count > 0,
            "total_bars": count,
            "expected_bars": expected,
            "missing_estimate": max(0, expected - count),
            "coverage_pct": round(count / expected * 100, 1) if expected > 0 else 0.0,
        }

    async def get_date_range(
        self, pair: str, timeframe: str,
    ) -> tuple[datetime | None, datetime | None]:
        """DB に保存済みのデータ範囲を取得."""
        min_stmt = select(func.min(HistoricalOhlcv.timestamp)).where(
            HistoricalOhlcv.pair == pair,
            HistoricalOhlcv.timeframe == timeframe,
        )
        max_stmt = select(func.max(HistoricalOhlcv.timestamp)).where(
            HistoricalOhlcv.pair == pair,
            HistoricalOhlcv.timeframe == timeframe,
        )
        min_result = await self._db.execute(min_stmt)
        max_result = await self._db.execute(max_stmt)
        return min_result.scalar_one_or_none(), max_result.scalar_one_or_none()
