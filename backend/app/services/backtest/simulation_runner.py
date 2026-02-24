"""
SimulationRunner: ペーパートレードモード（TRADING_MODE=simulation）.
本番価格フィード + MockExchange で動作し、simulation_history に記録する.
trade_history/positions には触れない【監査2: DB隔離】.

Reference: 09_バックテストシミュレーション Section 6
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.simulation_history import SimulationHistory


class SimulationRunner:
    """ペーパートレード結果を simulation_history に記録.

    live の trade_history/positions には一切書き込まない。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_trade(
        self,
        user_id: int,
        trader_id: int,
        pair: str,
        side: str,
        amount: float,
        entry_price: float,
        exit_price: float | None = None,
        realized_pnl: float | None = None,
        exit_reason: str | None = None,
        execution_id: str | None = None,
        opened_at: datetime | None = None,
        closed_at: datetime | None = None,
    ) -> int:
        """simulation_history にトレード記録. 返り値: record_id."""
        record = SimulationHistory(
            user_id=user_id,
            trader_id=trader_id,
            pair=pair,
            side=side,
            amount=amount,
            entry_price=entry_price,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            exit_reason=exit_reason,
            execution_id=execution_id,
            opened_at=opened_at or datetime.now(timezone.utc),
            closed_at=closed_at,
        )
        self._db.add(record)
        await self._db.flush()
        return record.id

    async def close_trade(
        self,
        record_id: int,
        exit_price: float,
        realized_pnl: float,
        exit_reason: str,
        closed_at: datetime | None = None,
    ) -> None:
        """ペーパートレードのクローズ."""
        record = await self._db.get(SimulationHistory, record_id)
        if record is None:
            return
        record.exit_price = exit_price
        record.realized_pnl = realized_pnl
        record.exit_reason = exit_reason
        record.closed_at = closed_at or datetime.now(timezone.utc)
