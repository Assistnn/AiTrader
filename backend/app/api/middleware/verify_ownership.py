"""
@verify_ownership decorator for API routes.

Reference: 08_API仕様 Section 2-2【監査1】

Ensures that a user can only access their own resources (traders, etc.).
Applied to all API endpoints that handle tenant-specific data.

Usage:
    @router.get("/traders/{trader_id}")
    async def get_trader(
        trader_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        await verify_trader_ownership(trader_id, user.id, db)
        ...
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trader import Trader


async def verify_trader_ownership(
    trader_id: int, user_id: int, db: AsyncSession,
) -> Trader:
    """
    Verify that the trader belongs to the authenticated user.

    Returns the Trader object if ownership is confirmed.
    Raises 403 Forbidden if trader does not belong to user.
    Raises 404 Not Found if trader does not exist.
    """
    result = await db.execute(
        select(Trader).where(Trader.id == trader_id)
    )
    trader = result.scalar_one_or_none()

    if trader is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trader not found",
        )

    if trader.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    return trader
