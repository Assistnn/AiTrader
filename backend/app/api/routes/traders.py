"""
Traders API routes.
Reference: 08_API仕様 Section 3-4, 16_実行エンジンとUI接続 Section 6
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.trader import Trader
from app.models.position import Position
from app.models.exchange_config import ExchangeConfig
from app.schemas.trader import TraderCreateRequest, TraderUpdateRequest, TraderResponse, TraderListItem
from app.api.deps import get_current_user
from app.api.response import ok
from app.services.auth.key_vault import KeyVault
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/traders", tags=["traders"])


def _trader_response(t: Trader) -> TraderResponse:
    return TraderResponse(
        id=t.id,
        trader_name=t.trader_name,
        trade_type=t.trade_type,
        symbols=t.symbols,
        capital_jpy=float(t.capital_jpy),
        order_unit_lots=float(t.order_unit_lots),
        strategy_text=t.strategy_text,
        status=t.status,
        created_at=t.created_at,
    )


@router.get("")
async def list_traders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー一覧取得."""
    q = select(Trader).where(Trader.user_id == user.id).order_by(Trader.id)
    result = await db.execute(q)
    traders = result.scalars().all()

    return ok([
        TraderListItem(
            id=t.id,
            trader_name=t.trader_name,
            trade_type=t.trade_type,
            symbols=t.symbols or [],
            status=t.status,
            capital_jpy=float(t.capital_jpy),
            created_at=t.created_at,
        )
        for t in traders
    ])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_trader(
    req: TraderCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー新規作成."""
    trader = Trader(
        user_id=user.id,
        trader_name=req.trader_name,
        trade_type=req.trade_type,
        symbols=req.symbols,
        capital_jpy=req.capital_jpy,
        order_unit_lots=req.order_unit_lots,
        strategy_text=req.strategy_text,
        status="stopped",
    )
    db.add(trader)
    await db.flush()
    await db.refresh(trader)

    return ok(_trader_response(trader))


@router.get("/{trader_id}")
async def get_trader(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー詳細取得."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    return ok(_trader_response(trader))


@router.put("/{trader_id}")
async def update_trader(
    trader_id: int,
    req: TraderUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー更新.

    エンジンが running の場合、設定変更を反映するため自動で再起動する。
    trade_type/symbols の変更にも対応。
    """
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    was_running = trader.status == "running"

    update_data = req.model_dump(exclude_unset=True, by_alias=False)
    for field, value in update_data.items():
        setattr(trader, field, value)
    await db.flush()
    await db.refresh(trader)

    # エンジンが稼働中なら再起動して設定を反映
    if was_running and update_data:
        engine_manager = request.app.state.engine_manager
        try:
            await engine_manager.stop_trader(trader_id, force_close=False)
        except Exception:
            logger.exception("Failed to stop engine for trader %d during update", trader_id)

        # 新しい設定でエンジン再起動
        exchange_type = "gmo_fx" if trader.trade_type == "FX" else "bitbank"
        ec_q = select(ExchangeConfig).where(
            ExchangeConfig.user_id == user.id,
            ExchangeConfig.exchange_type == exchange_type,
            ExchangeConfig.is_active == True,
        )
        ec = (await db.execute(ec_q)).scalar_one_or_none()
        if ec is not None:
            vault = KeyVault(settings.MASTER_ENCRYPTION_KEY)
            api_key = vault.decrypt(ec.api_key_encrypted)
            api_secret = vault.decrypt(ec.api_secret_encrypted)
            pair = trader.symbols[0] if trader.symbols else "USD_JPY"

            try:
                await engine_manager.start_trader(
                    trader_id=trader.id,
                    pair=pair,
                    trade_type=trader.trade_type,
                    api_key=api_key,
                    api_secret=api_secret,
                    trader_config={},
                    user_id=user.id,
                )
                logger.info(
                    "Engine for trader %d restarted with updated config (pair=%s, type=%s)",
                    trader_id, pair, trader.trade_type,
                )
            except Exception:
                logger.exception("Failed to restart engine for trader %d after update", trader_id)
                trader.status = "stopped"
                await db.flush()

    return ok(_trader_response(trader))


@router.delete("/{trader_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trader(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー削除."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    await db.delete(trader)
    await db.flush()


@router.post("/{trader_id}/start")
async def start_trader(
    trader_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー開始.

    Reference: 16書§6-1
    1. 所有権検証
    2. DB更新: trader.status = "running"
    3. EngineManager.start_trader()
    4. WebSocket通知
    """
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    if trader.status == "running":
        raise HTTPException(status_code=409, detail="Trader is already running")

    # Fetch exchange API keys (16書§6-1: 前提条件チェック)
    exchange_type = "gmo_fx" if trader.trade_type == "FX" else "bitbank"
    ec_q = select(ExchangeConfig).where(
        ExchangeConfig.user_id == user.id,
        ExchangeConfig.exchange_type == exchange_type,
        ExchangeConfig.is_active == True,
    )
    ec = (await db.execute(ec_q)).scalar_one_or_none()
    if ec is None:
        raise HTTPException(
            status_code=400,
            detail=f"Exchange API key for {exchange_type} is not configured",
        )

    vault = KeyVault(settings.MASTER_ENCRYPTION_KEY)
    api_key = vault.decrypt(ec.api_key_encrypted)
    api_secret = vault.decrypt(ec.api_secret_encrypted)

    pair = trader.symbols[0] if trader.symbols else "USD_JPY"

    # Start engine via EngineManager
    logger.info("Starting trader %d (%s, %s)", trader_id, trader.trade_type, pair)
    engine_manager = request.app.state.engine_manager
    try:
        await engine_manager.start_trader(
            trader_id=trader.id,
            pair=pair,
            trade_type=trader.trade_type,
            api_key=api_key,
            api_secret=api_secret,
            trader_config={},
            user_id=user.id,
        )
    except Exception as e:
        logger.exception("Failed to start engine for trader %d", trader_id)
        raise HTTPException(status_code=500, detail=f"Engine start failed: {e}")

    trader.status = "running"
    await db.flush()

    # WebSocket notification (16書§8-2)
    from app.api.routes.websocket import get_ws_manager
    ws = get_ws_manager()
    await ws.send_trader_update(trader_id, "status_changed", {
        "traderId": trader_id, "status": "running",
    })

    return ok({"traderId": trader_id, "status": "running"})


@router.post("/{trader_id}/stop")
async def stop_trader(
    trader_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー停止.

    Reference: 16書§6-2
    """
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    # Stop engine via EngineManager (16書§6-2)
    logger.info("Stopping trader %d", trader_id)
    engine_manager = request.app.state.engine_manager
    try:
        await engine_manager.stop_trader(trader_id, force_close=False)
    except Exception:
        logger.exception("Failed to stop engine for trader %d", trader_id)

    trader.status = "stopped"
    await db.flush()

    # WebSocket notification
    from app.api.routes.websocket import get_ws_manager
    ws = get_ws_manager()
    await ws.send_trader_update(trader_id, "status_changed", {
        "traderId": trader_id, "status": "stopped",
    })

    return ok({"traderId": trader_id, "status": "stopped"})


@router.post("/{trader_id}/close-all")
async def close_all_positions(
    trader_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダーの全ポジション決済.

    Reference: 16書§6-3
    """
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    # Close via EngineManager if engine is running (16書§6-3)
    logger.info("Close all positions for trader %d", trader_id)
    engine_manager = request.app.state.engine_manager
    engine_status = engine_manager.get_engine_status(trader_id)
    closed_count = 0

    if engine_status is not None and engine_status.state == "running":
        engine = engine_manager._engines.get(trader_id)
        if engine is not None:
            results = await engine.execution_engine.close_all_positions()
            closed_count = sum(1 for r in results if r.success)

    # Also clean up DB position records
    pos_q = select(Position).where(
        Position.trader_id == trader_id,
        Position.user_id == user.id,
    )
    pos_result = await db.execute(pos_q)
    positions = pos_result.scalars().all()

    db_count = len(positions)
    for p in positions:
        await db.delete(p)
    await db.flush()

    total_closed = max(closed_count, db_count)

    # WebSocket notification (16書§8-2)
    from app.api.routes.websocket import get_ws_manager
    ws = get_ws_manager()
    await ws.send_trader_update(trader_id, "positions_closed", {
        "traderId": trader_id, "closedCount": total_closed,
    })

    return ok({"traderId": trader_id, "closedCount": total_closed})
