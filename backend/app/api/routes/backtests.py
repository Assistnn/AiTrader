"""
Backtest API routes.
Reference: 08_API仕様 Section 3-11
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.backtest import (
    BacktestCreateRequest,
    BacktestCreateResponse,
    BacktestDetailResponse,
    BacktestListItem,
    BacktestMetricsResponse,
    BacktestTradeResponse,
)
from app.services.backtest.backtest_service import BacktestService
from app.services.backtest.backtest_types import BacktestConfig

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])


def _get_user_id() -> int:
    """簡易: 認証済みユーザーID取得（Phase 3 で JWT Depends に置換）."""
    return 1


@router.post("", response_model=BacktestCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_backtest(
    req: BacktestCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """バックテスト実行開始. バックグラウンドタスクで非同期実行."""
    config = BacktestConfig(
        pair=req.pair,
        timeframe=req.timeframe,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    service = BacktestService(db)

    # 同期的に run 作成だけ先に行い、実行はバックグラウンドに委譲
    from app.services.backtest.db_recorder import BacktestDbRecorder
    from dataclasses import asdict

    recorder = BacktestDbRecorder(db)
    run_id = await recorder.create_run(
        user_id=user_id,
        trader_id=req.trader_id,
        config=config,
        config_snapshot=asdict(config),
    )
    await db.commit()

    # Background execution
    background_tasks.add_task(
        _run_backtest_bg, run_id, user_id, req.trader_id, config,
    )

    return BacktestCreateResponse(backtest_id=run_id, status="pending")


async def _run_backtest_bg(
    run_id: int, user_id: int, trader_id: int, config: BacktestConfig,
) -> None:
    """バックグラウンドでバックテスト実行."""
    from app.db.session import async_session_factory

    async with async_session_factory() as db:
        service = BacktestService(db)
        try:
            await service.create_and_run(
                user_id=user_id,
                trader_id=trader_id,
                config=config,
            )
            await db.commit()
        except Exception:
            await db.rollback()


@router.get("", response_model=list[BacktestListItem])
async def list_backtests(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100, alias="perPage"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """バックテスト一覧取得."""
    service = BacktestService(db)
    runs, _ = await service.list_runs(user_id, page, per_page)
    return [
        BacktestListItem(
            backtest_id=r.id,
            trader_id=r.trader_id,
            status=r.status,
            pair=r.pair,
            timeframe=r.timeframe,
            start_date=r.start_date,
            end_date=r.end_date,
            total_trades=r.total_trades,
            win_rate=float(r.win_rate) if r.win_rate is not None else None,
            total_pnl=float(r.total_pnl) if r.total_pnl is not None else None,
            created_at=r.created_at,
        )
        for r in runs
    ]


@router.get("/{backtest_id}", response_model=BacktestDetailResponse)
async def get_backtest(
    backtest_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """バックテスト詳細取得."""
    service = BacktestService(db)
    run = await service.get_run(backtest_id, user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest not found")

    metrics = None
    if run.total_trades is not None:
        metrics = BacktestMetricsResponse(
            total_pnl=float(run.total_pnl) if run.total_pnl else None,
            total_trades=run.total_trades,
            win_rate=float(run.win_rate) if run.win_rate else None,
            profit_factor=float(run.profit_factor) if run.profit_factor else None,
            max_drawdown_pct=float(run.max_drawdown_pct) if run.max_drawdown_pct else None,
            sharpe_ratio=float(run.sharpe_ratio) if run.sharpe_ratio else None,
            avg_rr_ratio=float(run.avg_rr_ratio) if run.avg_rr_ratio else None,
        )

    return BacktestDetailResponse(
        backtest_id=run.id,
        trader_id=run.trader_id,
        status=run.status,
        pair=run.pair,
        timeframe=run.timeframe,
        start_date=run.start_date,
        end_date=run.end_date,
        config_snapshot=run.config_snapshot,
        metrics=metrics,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        created_at=run.created_at,
    )


@router.get("/{backtest_id}/trades", response_model=list[BacktestTradeResponse])
async def get_backtest_trades(
    backtest_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """バックテスト内トレード一覧."""
    service = BacktestService(db)
    # Verify ownership
    run = await service.get_run(backtest_id, user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest not found")

    trades = await service.get_trades(backtest_id, user_id)
    return [
        BacktestTradeResponse(
            trade_id=t.id,
            pair=t.pair,
            side=t.side,
            amount=float(t.amount) if t.amount else None,
            entry_price=float(t.entry_price) if t.entry_price else None,
            exit_price=float(t.exit_price) if t.exit_price else None,
            realized_pnl=float(t.realized_pnl) if t.realized_pnl else None,
            realized_pnl_pips=float(t.realized_pnl_pips) if t.realized_pnl_pips else None,
            rr_ratio=float(t.rr_ratio) if t.rr_ratio else None,
            exit_reason=t.exit_reason,
            entry_timestamp=t.entry_timestamp,
            exit_timestamp=t.exit_timestamp,
        )
        for t in trades
    ]


@router.delete("/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backtest(
    backtest_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """バックテスト削除."""
    service = BacktestService(db)
    deleted = await service.delete_run(backtest_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backtest not found")
    await db.commit()
