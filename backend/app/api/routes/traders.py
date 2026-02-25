"""
Traders API routes.
Reference: 08_API仕様 Section 3-4
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.trader import Trader
from app.schemas.trader import TraderCreateRequest, TraderResponse, TraderListItem

router = APIRouter(prefix="/api/v1/traders", tags=["traders"])


def _get_user_id() -> int:
    """簡易: 認証済みユーザーID取得."""
    return 1


@router.get("", response_model=list[TraderListItem])
async def list_traders(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """トレーダー一覧取得."""
    q = select(Trader).where(Trader.user_id == user_id).order_by(Trader.id)
    result = await db.execute(q)
    traders = result.scalars().all()

    return [
        TraderListItem(
            id=t.id,
            trader_name=t.trader_name,
            trade_type=t.trade_type,
            status=t.status,
            capital_jpy=float(t.capital_jpy),
            created_at=t.created_at,
        )
        for t in traders
    ]


@router.post("", response_model=TraderResponse, status_code=status.HTTP_201_CREATED)
async def create_trader(
    req: TraderCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """トレーダー新規作成."""
    trader = Trader(
        user_id=user_id,
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

    return TraderResponse(
        id=trader.id,
        trader_name=trader.trader_name,
        trade_type=trader.trade_type,
        symbols=trader.symbols,
        capital_jpy=float(trader.capital_jpy),
        order_unit_lots=float(trader.order_unit_lots),
        strategy_text=trader.strategy_text,
        status=trader.status,
        created_at=trader.created_at,
    )


@router.get("/{trader_id}", response_model=TraderResponse)
async def get_trader(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """トレーダー詳細取得."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user_id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    return TraderResponse(
        id=trader.id,
        trader_name=trader.trader_name,
        trade_type=trader.trade_type,
        symbols=trader.symbols,
        capital_jpy=float(trader.capital_jpy),
        order_unit_lots=float(trader.order_unit_lots),
        strategy_text=trader.strategy_text,
        status=trader.status,
        created_at=trader.created_at,
    )


@router.delete("/{trader_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trader(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """トレーダー削除."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user_id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    await db.delete(trader)
    await db.flush()


@router.post("/{trader_id}/start", status_code=status.HTTP_200_OK)
async def start_trader(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """トレーダー開始."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user_id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    trader.status = "running"
    await db.flush()
    return {"status": "ok", "data": {"traderId": trader_id, "status": "running"}}


@router.post("/{trader_id}/stop", status_code=status.HTTP_200_OK)
async def stop_trader(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """トレーダー停止."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user_id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    trader.status = "stopped"
    await db.flush()
    return {"status": "ok", "data": {"traderId": trader_id, "status": "stopped"}}
