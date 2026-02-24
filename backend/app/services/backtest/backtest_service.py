"""
BacktestService: バックテスト API から呼ばれるビジネスロジック層.
Reference: 09_バックテストシミュレーション Section 3-3, 6
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backtest import BacktestRun, BacktestTrade
from app.services.backtest.backtest_types import BacktestConfig
from app.services.backtest.db_recorder import BacktestDbRecorder
from app.services.backtest.engine import BacktestEngine
from app.services.backtest.evaluator import BacktestEvaluator
from app.services.backtest.historical_data_provider import HistoricalDataProvider
from app.services.backtest.simulation_clock import SimulationClock
from app.services.decision.m1_direction import M1DirectionJudge
from app.services.decision.m2_setup import M2SetupJudge
from app.services.decision.m3_entry import M3EntryJudge
from app.services.decision.m4_exit import M4ExitJudge
from app.services.decision.orchestrator import DecisionOrchestrator
from app.services.safeguard.guard_engine import GuardEngine


class BacktestService:
    """バックテスト実行のビジネスロジック."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._db_recorder = BacktestDbRecorder(db)
        self._evaluator = BacktestEvaluator()

    async def create_and_run(
        self,
        user_id: int,
        trader_id: int,
        config: BacktestConfig,
        config_snapshot: dict | None = None,
    ) -> int:
        """バックテスト作成・実行・保存. 返り値: run_id."""
        snapshot = config_snapshot or asdict(config)

        # 1. Run 作成 (pending)
        run_id = await self._db_recorder.create_run(
            user_id=user_id,
            trader_id=trader_id,
            config=config,
            config_snapshot=snapshot,
        )

        # 2. 開始
        now = datetime.now(timezone.utc)
        await self._db_recorder.update_run_status(
            run_id, "running", started_at=now,
        )

        try:
            # 3. ヒストリカルデータ取得
            start_dt = datetime.combine(
                config.start_date, datetime.min.time(), tzinfo=timezone.utc,
            )
            end_dt = datetime.combine(
                config.end_date, datetime.max.time(), tzinfo=timezone.utc,
            )
            clock = SimulationClock(start_dt, end_dt)
            provider = HistoricalDataProvider(self._db, clock)
            bars = await provider.get_historical_ohlcv(
                config.pair, config.timeframe, start_dt, end_dt,
            )

            # 4. パイプライン構築
            guard_engine = GuardEngine()
            for k, v in config.safeguard_overrides.items():
                setattr(guard_engine.settings, k, v)

            orchestrator = DecisionOrchestrator(
                m1=M1DirectionJudge(),
                m2=M2SetupJudge(),
                m3=M3EntryJudge(),
                m4=M4ExitJudge(),
                guard_engine=guard_engine,
            )

            engine = BacktestEngine(orchestrator=orchestrator)

            # 5. 実行
            result = engine.run(config, bars)

            # 6. 評価
            result.metrics = self._evaluator.calculate(result)

            # 7. DB 保存
            await self._db_recorder.save_results(
                run_id=run_id,
                user_id=user_id,
                metrics=result.metrics,
                trades=result.trades,
            )

            # 8. 完了
            await self._db_recorder.update_run_status(
                run_id, "completed",
                completed_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            await self._db_recorder.update_run_status(
                run_id, "failed",
                completed_at=datetime.now(timezone.utc),
                error_message=str(e),
            )
            raise

        return run_id

    async def get_run(self, run_id: int, user_id: int) -> BacktestRun | None:
        """バックテスト結果取得（user_id でフィルタ）."""
        stmt = select(BacktestRun).where(
            BacktestRun.id == run_id,
            BacktestRun.user_id == user_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_runs(
        self, user_id: int, page: int = 1, per_page: int = 20,
    ) -> tuple[list[BacktestRun], int]:
        """バックテスト一覧（ページネーション付き）."""
        # Count
        count_stmt = select(BacktestRun.id).where(BacktestRun.user_id == user_id)
        count_result = await self._db.execute(count_stmt)
        total = len(count_result.all())

        # Paginate
        stmt = (
            select(BacktestRun)
            .where(BacktestRun.user_id == user_id)
            .order_by(BacktestRun.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await self._db.execute(stmt)
        runs = result.scalars().all()
        return list(runs), total

    async def get_trades(
        self, run_id: int, user_id: int,
    ) -> list[BacktestTrade]:
        """バックテスト内トレード一覧."""
        stmt = (
            select(BacktestTrade)
            .where(
                BacktestTrade.backtest_run_id == run_id,
                BacktestTrade.user_id == user_id,
            )
            .order_by(BacktestTrade.entry_timestamp.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def delete_run(self, run_id: int, user_id: int) -> bool:
        """バックテスト削除."""
        run = await self.get_run(run_id, user_id)
        if run is None:
            return False

        # Delete trades first
        trades_stmt = select(BacktestTrade).where(
            BacktestTrade.backtest_run_id == run_id,
        )
        trades_result = await self._db.execute(trades_stmt)
        for trade in trades_result.scalars().all():
            await self._db.delete(trade)

        await self._db.delete(run)
        await self._db.flush()
        return True
