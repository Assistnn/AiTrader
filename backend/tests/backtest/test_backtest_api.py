"""
Backtest API route tests.
Reference: 08_API仕様 Section 3-11
"""

import pytest
import pytest_asyncio
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backtest import BacktestRun, BacktestTrade
from app.models.user import User
from app.models.trader import Trader
from app.services.backtest.backtest_service import BacktestService
from app.services.backtest.backtest_types import BacktestConfig


async def _setup_user_trader(db: AsyncSession) -> tuple[int, int]:
    """テスト用ユーザー・トレーダー作成."""
    user = User(email="bt_test@test.com", password_hash="h", display_name="BTUser")
    db.add(user)
    await db.flush()
    trader = Trader(user_id=user.id, trader_name="BTTrader", trade_type="FX")
    db.add(trader)
    await db.flush()
    return user.id, trader.id


class TestBacktestServiceCRUD:
    @pytest.mark.asyncio
    async def test_create_run(self, db_session: AsyncSession):
        """backtest_runs に pending レコードが作成される."""
        from app.services.backtest.db_recorder import BacktestDbRecorder
        user_id, trader_id = await _setup_user_trader(db_session)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 6, 30),
        )
        recorder = BacktestDbRecorder(db_session)
        run_id = await recorder.create_run(user_id, trader_id, config, {"pair": "USD_JPY"})

        run = await db_session.get(BacktestRun, run_id)
        assert run is not None
        assert run.status == "pending"
        assert run.pair == "USD_JPY"
        assert run.user_id == user_id

    @pytest.mark.asyncio
    async def test_list_runs_filters_by_user(self, db_session: AsyncSession):
        """一覧は user_id でフィルタされる."""
        user1_id, trader1_id = await _setup_user_trader(db_session)
        user2 = User(email="bt_other@test.com", password_hash="h2", display_name="Other")
        db_session.add(user2)
        await db_session.flush()
        trader2 = Trader(user_id=user2.id, trader_name="OtherTrader", trade_type="FX")
        db_session.add(trader2)
        await db_session.flush()

        from app.services.backtest.db_recorder import BacktestDbRecorder
        recorder = BacktestDbRecorder(db_session)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 6, 30),
        )
        await recorder.create_run(user1_id, trader1_id, config, {})
        await recorder.create_run(user2.id, trader2.id, config, {})

        service = BacktestService(db_session)
        runs, total = await service.list_runs(user1_id)
        assert total == 1
        assert all(r.user_id == user1_id for r in runs)

    @pytest.mark.asyncio
    async def test_get_run_other_user_returns_none(self, db_session: AsyncSession):
        """他ユーザーの run は取得できない."""
        user_id, trader_id = await _setup_user_trader(db_session)
        from app.services.backtest.db_recorder import BacktestDbRecorder
        recorder = BacktestDbRecorder(db_session)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 6, 30),
        )
        run_id = await recorder.create_run(user_id, trader_id, config, {})

        service = BacktestService(db_session)
        result = await service.get_run(run_id, user_id=999)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_run(self, db_session: AsyncSession):
        """削除が成功する."""
        user_id, trader_id = await _setup_user_trader(db_session)
        from app.services.backtest.db_recorder import BacktestDbRecorder
        recorder = BacktestDbRecorder(db_session)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 6, 30),
        )
        run_id = await recorder.create_run(user_id, trader_id, config, {})

        service = BacktestService(db_session)
        deleted = await service.delete_run(run_id, user_id)
        assert deleted is True

        # Confirm gone
        result = await service.get_run(run_id, user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, db_session: AsyncSession):
        """存在しないIDの削除は False."""
        service = BacktestService(db_session)
        deleted = await service.delete_run(99999, user_id=1)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_save_results_metrics(self, db_session: AsyncSession):
        """save_results でメトリクスが保存される."""
        user_id, trader_id = await _setup_user_trader(db_session)
        from app.services.backtest.db_recorder import BacktestDbRecorder
        from app.services.backtest.backtest_types import BacktestMetrics
        recorder = BacktestDbRecorder(db_session)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 6, 30),
        )
        run_id = await recorder.create_run(user_id, trader_id, config, {})

        metrics = BacktestMetrics(
            total_pnl=50000, total_trades=20,
            win_rate=55.0, profit_factor=1.8,
            max_drawdown_pct=8.5, sharpe_ratio=1.2,
            avg_rr_ratio=1.5,
        )
        await recorder.save_results(run_id, user_id, metrics, [])

        run = await db_session.get(BacktestRun, run_id)
        assert run.total_trades == 20
        assert float(run.win_rate) == 55.0
        assert float(run.total_pnl) == 50000

    @pytest.mark.asyncio
    async def test_pagination(self, db_session: AsyncSession):
        """ページネーションが動作する."""
        user_id, trader_id = await _setup_user_trader(db_session)
        from app.services.backtest.db_recorder import BacktestDbRecorder
        recorder = BacktestDbRecorder(db_session)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 6, 30),
        )
        for _ in range(5):
            await recorder.create_run(user_id, trader_id, config, {})

        service = BacktestService(db_session)
        runs, total = await service.list_runs(user_id, page=1, per_page=2)
        assert len(runs) == 2
        assert total == 5

        runs2, _ = await service.list_runs(user_id, page=2, per_page=2)
        assert len(runs2) == 2
