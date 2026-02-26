"""
Trade History API routes.
Reference: 08_API仕様 Section 3-10
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.trade_history import TradeHistory
from app.models.pipeline_log import PipelineLog
from app.models.safeguard_log import SafeguardLog
from app.schemas.history import TradeHistoryItem, TradeHistoryDetail
from app.api.deps import get_current_user
from app.api.response import ok, paginated

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("")
async def list_trade_history(
    trader_id: int | None = Query(None, alias="traderId"),
    pair: str | None = None,
    date_from: str | None = Query(None, alias="dateFrom"),
    date_to: str | None = Query(None, alias="dateTo"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100, alias="perPage"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """取引履歴一覧（ページネーション）."""
    base = select(TradeHistory).where(TradeHistory.user_id == user.id)

    if trader_id is not None:
        base = base.where(TradeHistory.trader_id == trader_id)
    if pair is not None:
        base = base.where(TradeHistory.pair == pair)

    # Total count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated data
    q = base.order_by(TradeHistory.opened_at.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(q)
    trades = result.scalars().all()

    items = [
        TradeHistoryItem(
            id=t.id,
            trader_id=t.trader_id,
            pair=t.pair,
            side=t.side,
            amount=float(t.amount) if t.amount else None,
            entry_price=float(t.entry_price) if t.entry_price else None,
            exit_price=float(t.exit_price) if t.exit_price else None,
            realized_pnl=float(t.realized_pnl) if t.realized_pnl else None,
            realized_pnl_pips=float(t.realized_pnl_pips) if t.realized_pnl_pips else None,
            rr_ratio=float(t.rr_ratio) if t.rr_ratio else None,
            exit_reason=t.exit_reason,
            opened_at=t.opened_at,
            closed_at=t.closed_at,
        )
        for t in trades
    ]

    return paginated(items, page, per_page, total)


@router.get("/chart-data")
async def get_chart_data(
    trader_id: int | None = Query(None, alias="traderId"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """チャート用損益データ."""
    q = select(TradeHistory).where(
        TradeHistory.user_id == user.id,
        TradeHistory.closed_at.isnot(None),
    )
    if trader_id is not None:
        q = q.where(TradeHistory.trader_id == trader_id)
    q = q.order_by(TradeHistory.closed_at.asc())

    result = await db.execute(q)
    trades = result.scalars().all()

    cumulative = 0.0
    data_points = []
    for t in trades:
        pnl = float(t.realized_pnl) if t.realized_pnl else 0
        cumulative += pnl
        data_points.append({
            "timestamp": t.closed_at.isoformat() if t.closed_at else None,
            "pnl": pnl,
            "cumulativePnl": round(cumulative, 2),
        })

    return ok(data_points)


@router.get("/export/csv")
async def export_csv(
    trader_id: int | None = Query(None, alias="traderId"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """CSV出力."""
    q = select(TradeHistory).where(TradeHistory.user_id == user.id)
    if trader_id is not None:
        q = q.where(TradeHistory.trader_id == trader_id)
    q = q.order_by(TradeHistory.opened_at.desc())

    result = await db.execute(q)
    trades = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "traderId", "pair", "side", "amount",
        "entryPrice", "exitPrice", "realizedPnl", "realizedPnlPips",
        "rrRatio", "exitReason", "openedAt", "closedAt",
    ])
    for t in trades:
        writer.writerow([
            t.id, t.trader_id, t.pair, t.side,
            float(t.amount) if t.amount else "",
            float(t.entry_price) if t.entry_price else "",
            float(t.exit_price) if t.exit_price else "",
            float(t.realized_pnl) if t.realized_pnl else "",
            float(t.realized_pnl_pips) if t.realized_pnl_pips else "",
            float(t.rr_ratio) if t.rr_ratio else "",
            t.exit_reason or "",
            t.opened_at.isoformat() if t.opened_at else "",
            t.closed_at.isoformat() if t.closed_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trade_history.csv"},
    )


@router.get("/{trade_id}")
async def get_trade_detail(
    trade_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """取引詳細（4段階判定含む）."""
    q = select(TradeHistory).where(
        TradeHistory.id == trade_id, TradeHistory.user_id == user.id
    )
    result = await db.execute(q)
    trade = result.scalar_one_or_none()

    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    # Pipeline logs for this trade
    pl_logs: list[dict] = []
    if trade.execution_id:
        pq = (
            select(PipelineLog)
            .where(PipelineLog.execution_id == trade.execution_id)
            .order_by(PipelineLog.stage)
        )
        pl_result = await db.execute(pq)
        for log in pl_result.scalars().all():
            pl_logs.append({
                "stage": log.stage,
                "output": log.output_snapshot,
                "config": log.config_snapshot,
                "elapsedMs": float(log.elapsed_ms) if log.elapsed_ms else None,
            })

    # Safeguard logs
    sg_logs: list[dict] = []
    if trade.opened_at:
        sq = (
            select(SafeguardLog)
            .where(SafeguardLog.trader_id == trade.trader_id)
            .where(SafeguardLog.timestamp == trade.opened_at)
        )
        sg_result = await db.execute(sq)
        for sg in sg_result.scalars().all():
            sg_logs.append({
                "guardId": sg.guard_id,
                "result": sg.result,
                "details": sg.details_json,
            })

    trade_item = TradeHistoryItem(
        id=trade.id,
        trader_id=trade.trader_id,
        pair=trade.pair,
        side=trade.side,
        amount=float(trade.amount) if trade.amount else None,
        entry_price=float(trade.entry_price) if trade.entry_price else None,
        exit_price=float(trade.exit_price) if trade.exit_price else None,
        realized_pnl=float(trade.realized_pnl) if trade.realized_pnl else None,
        realized_pnl_pips=float(trade.realized_pnl_pips) if trade.realized_pnl_pips else None,
        rr_ratio=float(trade.rr_ratio) if trade.rr_ratio else None,
        exit_reason=trade.exit_reason,
        opened_at=trade.opened_at,
        closed_at=trade.closed_at,
    )

    return ok(TradeHistoryDetail(
        trade=trade_item,
        pipeline_logs=pl_logs,
        safeguard_logs=sg_logs,
    ))
