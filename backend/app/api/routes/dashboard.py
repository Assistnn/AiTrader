"""
Dashboard API routes.
Reference: 08_API仕様 Section 3-3, 16_実行エンジンとUI接続 Section 6-4
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.trader import Trader
from app.models.position import Position
from app.models.trade_history import TradeHistory
from app.models.pipeline_log import PipelineLog
from app.models.safeguard_log import SafeguardLog
from app.models.exchange_config import ExchangeConfig
from app.schemas.dashboard import DashboardSummaryResponse, TraderSummary, PipelineStateResponse
from app.api.deps import get_current_user
from app.api.response import ok
from app.services.auth.key_vault import KeyVault
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """ダッシュボードサマリ取得."""
    q = select(Trader).where(Trader.user_id == user.id).order_by(Trader.id)
    result = await db.execute(q)
    traders = result.scalars().all()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    trader_ids = [t.id for t in traders]
    trader_id_set = set(trader_ids)

    # Batch: open positions per trader
    pos_counts: dict[int, int] = {}
    if trader_ids:
        pos_q = (
            select(Position.trader_id, func.count())
            .where(Position.user_id == user.id)
            .group_by(Position.trader_id)
        )
        for row in (await db.execute(pos_q)).all():
            pos_counts[row[0]] = row[1]

    # Batch: today PnL per trader
    pnl_today_map: dict[int, float] = {}
    if trader_ids:
        pnl_q = (
            select(TradeHistory.trader_id, func.sum(TradeHistory.realized_pnl))
            .where(
                TradeHistory.user_id == user.id,
                TradeHistory.closed_at >= today_start,
            )
            .group_by(TradeHistory.trader_id)
        )
        for row in (await db.execute(pnl_q)).all():
            pnl_today_map[row[0]] = float(row[1]) if row[1] else 0

    # Batch: month PnL total
    month_pnl_q = select(func.sum(TradeHistory.realized_pnl)).where(
        TradeHistory.user_id == user.id,
        TradeHistory.closed_at >= month_start,
    )
    total_pnl_month = (await db.execute(month_pnl_q)).scalar() or 0

    # Batch: latest pipeline logs per trader (M1+M2 in single query)
    pipeline_states: dict[int, dict] = {}
    if trader_ids:
        sub = (
            select(
                PipelineLog.trader_id,
                PipelineLog.stage,
                func.max(PipelineLog.id).label("max_id"),
            )
            .where(
                PipelineLog.user_id == user.id,
                PipelineLog.stage.in_(["m1", "m2"]),
            )
            .group_by(PipelineLog.trader_id, PipelineLog.stage)
            .subquery()
        )
        log_q = select(PipelineLog).join(
            sub, PipelineLog.id == sub.c.max_id
        )
        for log in (await db.execute(log_q)).scalars().all():
            key = "lastM1" if log.stage == "m1" else "lastM2"
            pipeline_states.setdefault(log.trader_id, {})[key] = log.output_snapshot

    # Batch: latest safeguard state per trader
    guard_states: dict[int, dict] = {}
    if trader_ids:
        sg_sub = (
            select(
                SafeguardLog.trader_id,
                func.max(SafeguardLog.id).label("max_id"),
            )
            .where(SafeguardLog.user_id == user.id)
            .group_by(SafeguardLog.trader_id)
            .subquery()
        )
        sg_q = select(SafeguardLog).join(
            sg_sub, SafeguardLog.id == sg_sub.c.max_id
        )
        for sg in (await db.execute(sg_q)).scalars().all():
            blocking = sg.result in ("block", "halt")
            guard_states[sg.trader_id] = {
                "entryAllowed": not blocking,
                "blockingGuards": [sg.guard_id] if blocking else [],
            }

    total_pnl_today = sum(pnl_today_map.values())
    total_open = sum(pos_counts.values())

    trader_summaries = []
    for t in traders:
        ps = pipeline_states.get(t.id, {})
        gs = guard_states.get(t.id, {"entryAllowed": True, "blockingGuards": []})

        pipeline_state = PipelineStateResponse(
            last_m1=ps.get("lastM1"),
            last_m2=ps.get("lastM2"),
            guard_state=gs,
        ) if ps or gs else None

        trader_summaries.append(TraderSummary(
            trader_id=t.id,
            trader_name=t.trader_name,
            status=t.status,
            pnl_today=pnl_today_map.get(t.id, 0),
            open_positions=pos_counts.get(t.id, 0),
            pipeline_state=pipeline_state,
        ))

    active = sum(1 for t in traders if t.status == "running")

    return ok(DashboardSummaryResponse(
        total_pnl_today=total_pnl_today,
        total_pnl_month=float(total_pnl_month),
        active_traders=active,
        open_positions=total_open,
        traders=trader_summaries,
    ))


@router.post("/close-all")
async def close_all_positions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全ポジション決済.

    Reference: 16書§6-4 — 全トレーダーの全ポジション決済後、停止
    """
    engine_manager = request.app.state.engine_manager
    exchange_closed = 0

    # Close exchange positions via engines
    q = select(Trader).where(Trader.user_id == user.id, Trader.status == "running")
    result = await db.execute(q)
    running_traders = result.scalars().all()

    for t in running_traders:
        engine = engine_manager._engines.get(t.id)
        if engine is not None:
            results = await engine.execution_engine.close_all_positions()
            exchange_closed += sum(1 for r in results if r.success)

    # Clean up DB position records
    pos_q = select(Position).where(Position.user_id == user.id)
    pos_result = await db.execute(pos_q)
    positions = pos_result.scalars().all()

    db_count = len(positions)
    for p in positions:
        await db.delete(p)
    await db.flush()

    return ok({"closedCount": max(exchange_closed, db_count)})


@router.post("/stop-all")
async def stop_all_traders(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全トレーダー停止.

    Reference: 16書§6-4
    """
    engine_manager = request.app.state.engine_manager

    q = select(Trader).where(Trader.user_id == user.id, Trader.status == "running")
    result = await db.execute(q)
    traders = result.scalars().all()

    for t in traders:
        try:
            await engine_manager.stop_trader(t.id, force_close=False)
        except Exception:
            logger.exception("Failed to stop engine for trader %d", t.id)
        t.status = "stopped"
    await db.flush()

    return ok({"stoppedCount": len(traders)})


@router.post("/start-all")
async def start_all_traders(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全トレーダー開始.

    Reference: 16書§6-4
    """
    engine_manager = request.app.state.engine_manager
    vault = KeyVault(settings.MASTER_ENCRYPTION_KEY)

    q = select(Trader).where(Trader.user_id == user.id, Trader.status == "stopped")
    result = await db.execute(q)
    traders = result.scalars().all()

    # Batch fetch exchange configs
    ec_q = select(ExchangeConfig).where(
        ExchangeConfig.user_id == user.id,
        ExchangeConfig.is_active == True,
    )
    ec_result = await db.execute(ec_q)
    ec_map: dict[str, ExchangeConfig] = {}
    for ec in ec_result.scalars().all():
        ec_map[ec.exchange_type] = ec

    started = 0
    for t in traders:
        exchange_type = "gmo_fx" if t.trade_type == "FX" else "bitbank"
        ec = ec_map.get(exchange_type)
        if ec is None:
            logger.warning("No API key for trader %d (%s), skipping", t.id, exchange_type)
            continue

        api_key = vault.decrypt(ec.api_key_encrypted)
        api_secret = vault.decrypt(ec.api_secret_encrypted)
        pair = t.symbols[0] if t.symbols else "USD_JPY"

        try:
            await engine_manager.start_trader(
                trader_id=t.id,
                pair=pair,
                trade_type=t.trade_type,
                api_key=api_key,
                api_secret=api_secret,
                trader_config={},
            )
            t.status = "running"
            started += 1
        except Exception:
            logger.exception("Failed to start engine for trader %d", t.id)

    await db.flush()
    return ok({"startedCount": started})
