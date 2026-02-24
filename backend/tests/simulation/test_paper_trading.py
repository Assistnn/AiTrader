"""
Paper trading (simulation mode) tests.
Reference: 09_バックテストシミュレーション Section 6【監査2: DB隔離】
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.simulation_history import SimulationHistory
from app.models.user import User
from app.models.trader import Trader
from app.services.backtest.simulation_runner import SimulationRunner


async def _setup(db: AsyncSession) -> tuple[int, int]:
    """テスト用ユーザー・トレーダー."""
    user = User(email="sim@test.com", password_hash="h", display_name="SimUser")
    db.add(user)
    await db.flush()
    trader = Trader(user_id=user.id, trader_name="SimTrader", trade_type="FX")
    db.add(trader)
    await db.flush()
    return user.id, trader.id


class TestPaperTrading:
    @pytest.mark.asyncio
    async def test_records_to_simulation_history(self, db_session: AsyncSession):
        """SimulationRunner は simulation_history に記録する."""
        user_id, trader_id = await _setup(db_session)
        runner = SimulationRunner(db_session)

        record_id = await runner.record_trade(
            user_id=user_id, trader_id=trader_id,
            pair="USD_JPY", side="BUY", amount=1.0,
            entry_price=150.0,
        )

        stmt = select(SimulationHistory).where(SimulationHistory.id == record_id)
        result = await db_session.execute(stmt)
        record = result.scalar_one()

        assert record.pair == "USD_JPY"
        assert record.side == "BUY"
        assert float(record.entry_price) == 150.0
        assert record.user_id == user_id

    @pytest.mark.asyncio
    async def test_close_trade(self, db_session: AsyncSession):
        """close_trade で exit 情報が更新される."""
        user_id, trader_id = await _setup(db_session)
        runner = SimulationRunner(db_session)

        record_id = await runner.record_trade(
            user_id=user_id, trader_id=trader_id,
            pair="USD_JPY", side="BUY", amount=1.0,
            entry_price=150.0,
        )

        await runner.close_trade(
            record_id=record_id,
            exit_price=150.50,
            realized_pnl=5000.0,
            exit_reason="TP",
        )

        record = await db_session.get(SimulationHistory, record_id)
        assert float(record.exit_price) == 150.50
        assert float(record.realized_pnl) == 5000.0
        assert record.exit_reason == "TP"
        assert record.closed_at is not None
