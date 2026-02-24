"""
BacktestDbRecorder: バックテスト結果の DB 永続化.
Reference: 09_バックテストシミュレーション Section 6【監査2: DB隔離】
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backtest import BacktestRun, BacktestTrade
from app.services.backtest.backtest_types import BacktestConfig, BacktestMetrics, BacktestTradeRecord


class BacktestDbRecorder:
    """バックテスト結果を backtest_runs / backtest_trades に保存.

    live の trade_history には一切触れない【監査2】。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_run(
        self,
        user_id: int,
        trader_id: int,
        config: BacktestConfig,
        config_snapshot: dict,
    ) -> int:
        """backtest_runs にレコード作成. 返り値: run_id."""
        run = BacktestRun(
            user_id=user_id,
            trader_id=trader_id,
            status="pending",
            config_snapshot=config_snapshot,
            pair=config.pair,
            timeframe=config.timeframe,
            start_date=config.start_date,
            end_date=config.end_date,
        )
        self._db.add(run)
        await self._db.flush()
        return run.id

    async def update_run_status(
        self,
        run_id: int,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
    ) -> None:
        """backtest_runs のステータス更新."""
        run = await self._db.get(BacktestRun, run_id)
        if run is None:
            return
        run.status = status
        if started_at is not None:
            run.started_at = started_at
        if completed_at is not None:
            run.completed_at = completed_at
        if error_message is not None:
            run.error_message = error_message

    async def save_results(
        self,
        run_id: int,
        user_id: int,
        metrics: BacktestMetrics,
        trades: list[BacktestTradeRecord],
    ) -> None:
        """評価指標と個別トレードを保存."""
        # Update run with metrics
        run = await self._db.get(BacktestRun, run_id)
        if run is not None:
            run.total_trades = metrics.total_trades
            run.win_rate = metrics.win_rate
            run.profit_factor = metrics.profit_factor
            run.max_drawdown_pct = metrics.max_drawdown_pct
            run.sharpe_ratio = metrics.sharpe_ratio
            run.total_pnl = metrics.total_pnl
            run.avg_rr_ratio = metrics.avg_rr_ratio

        # Insert individual trades into backtest_trades【監査2: DB隔離】
        for t in trades:
            bt = BacktestTrade(
                user_id=user_id,
                backtest_run_id=run_id,
                pair=t.pair,
                side=t.side,
                amount=t.amount,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                realized_pnl=t.realized_pnl,
                realized_pnl_pips=t.realized_pnl_pips,
                rr_ratio=t.rr_ratio,
                exit_reason=t.exit_reason,
                entry_timestamp=t.entry_timestamp,
                exit_timestamp=t.exit_timestamp,
                pipeline_log_json=t.pipeline_log_json,
            )
            self._db.add(bt)

        await self._db.flush()
