"""
Dashboard API routes.
Reference: 08_API仕様 Section 3-3
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.trader import Trader
from app.schemas.dashboard import DashboardSummaryResponse, TraderSummary

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _get_user_id() -> int:
    """簡易: 認証済みユーザーID取得."""
    return 1


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """ダッシュボードサマリ取得."""
    q = select(Trader).where(Trader.user_id == user_id).order_by(Trader.id)
    result = await db.execute(q)
    traders = result.scalars().all()

    trader_summaries = [
        TraderSummary(
            trader_id=t.id,
            trader_name=t.trader_name,
            status=t.status,
            pnl_today=0,
            open_positions=0,
            pipeline_state=None,
        )
        for t in traders
    ]

    active = sum(1 for t in traders if t.status == "running")

    return DashboardSummaryResponse(
        total_pnl_today=0,
        total_pnl_month=0,
        active_traders=active,
        open_positions=0,
        traders=trader_summaries,
    )


@router.post("/stop-all")
async def stop_all_traders(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """全トレーダー停止."""
    q = select(Trader).where(Trader.user_id == user_id, Trader.status == "running")
    result = await db.execute(q)
    traders = result.scalars().all()

    for t in traders:
        t.status = "stopped"
    await db.flush()

    return {"status": "ok", "data": {"stoppedCount": len(traders)}}


@router.post("/start-all")
async def start_all_traders(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """全トレーダー開始."""
    q = select(Trader).where(Trader.user_id == user_id, Trader.status == "stopped")
    result = await db.execute(q)
    traders = result.scalars().all()

    for t in traders:
        t.status = "running"
    await db.flush()

    return {"status": "ok", "data": {"startedCount": len(traders)}}
