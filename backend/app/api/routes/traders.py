"""
Traders API routes.
Reference: 08_API仕様 Section 3-4
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.trader import Trader
from app.models.position import Position
from app.schemas.trader import TraderCreateRequest, TraderUpdateRequest, TraderResponse, TraderListItem
from app.api.deps import get_current_user
from app.api.response import ok

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
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー更新."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    update_data = req.model_dump(exclude_unset=True, by_alias=False)
    for field, value in update_data.items():
        setattr(trader, field, value)
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
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー開始."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    trader.status = "running"
    await db.flush()
    return {"status": "ok", "data": {"traderId": trader_id, "status": "running"}}


@router.post("/{trader_id}/stop")
async def stop_trader(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダー停止."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    trader.status = "stopped"
    await db.flush()
    return {"status": "ok", "data": {"traderId": trader_id, "status": "stopped"}}


@router.post("/{trader_id}/close-all")
async def close_all_positions(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """トレーダーの全ポジション決済."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    # Get open positions for this trader
    pos_q = select(Position).where(
        Position.trader_id == trader_id,
        Position.user_id == user.id,
    )
    pos_result = await db.execute(pos_q)
    positions = pos_result.scalars().all()

    closed_count = len(positions)
    for p in positions:
        await db.delete(p)
    await db.flush()

    return {"status": "ok", "data": {"traderId": trader_id, "closedCount": closed_count}}
