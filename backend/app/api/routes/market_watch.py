"""
Market Watch API routes.
Reference: 08_API仕様 Section 3-7
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.market_watch_config import MarketWatchConfig
from app.schemas.market_watch import (
    MarketWatchItem,
    MarketWatchCreateRequest,
    MarketWatchReorderRequest,
)
from app.api.deps import get_current_user
from app.api.response import ok

router = APIRouter(prefix="/api/v1/market-watch", tags=["market-watch"])


@router.get("")
async def list_market_watch(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """マーケットウォッチ一覧取得."""
    q = (
        select(MarketWatchConfig)
        .where(MarketWatchConfig.user_id == user.id)
        .order_by(MarketWatchConfig.display_order)
    )
    result = await db.execute(q)
    items = result.scalars().all()

    return ok([
        MarketWatchItem(
            id=mw.id,
            pair=mw.pair,
            display_order=mw.display_order,
            is_visible=mw.is_visible if mw.is_visible is not None else True,
            created_at=mw.created_at,
        )
        for mw in items
    ])


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_market_watch(
    req: MarketWatchCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """マーケットウォッチにペア追加."""
    mw = MarketWatchConfig(
        user_id=user.id,
        pair=req.pair,
        display_order=req.display_order,
        is_visible=req.is_visible,
    )
    db.add(mw)
    await db.flush()
    await db.commit()

    return ok(MarketWatchItem(
        id=mw.id,
        pair=mw.pair,
        display_order=mw.display_order,
        is_visible=mw.is_visible if mw.is_visible is not None else True,
        created_at=mw.created_at,
    ))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_market_watch(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """マーケットウォッチからペア削除."""
    q = select(MarketWatchConfig).where(
        MarketWatchConfig.id == item_id,
        MarketWatchConfig.user_id == user.id,
    )
    result = await db.execute(q)
    mw = result.scalar_one_or_none()

    if mw is None:
        raise HTTPException(status_code=404, detail="Market watch item not found")

    await db.delete(mw)
    await db.flush()
    await db.commit()


@router.put("/reorder")
async def reorder_market_watch(
    req: MarketWatchReorderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """マーケットウォッチ並び替え."""
    for item in req.order:
        item_id = item.get("id")
        new_order = item.get("displayOrder", 0)
        if item_id is None:
            continue

        q = select(MarketWatchConfig).where(
            MarketWatchConfig.id == item_id,
            MarketWatchConfig.user_id == user.id,
        )
        result = await db.execute(q)
        mw = result.scalar_one_or_none()
        if mw is not None:
            mw.display_order = new_order

    await db.flush()
    await db.commit()

    return ok({"reordered": True})
