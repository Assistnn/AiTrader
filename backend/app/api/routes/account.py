"""
Account API routes.
Reference: 08_API仕様 Section 3-2
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.account import AccountResponse, AccountUpdateRequest
from app.api.deps import get_current_user
from app.api.response import ok

router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.get("")
async def get_account(
    user: User = Depends(get_current_user),
):
    """アカウント情報取得."""
    return ok(AccountResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=user.created_at,
    ))


@router.put("")
async def update_account(
    req: AccountUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """アカウント情報更新."""
    update_data = req.model_dump(exclude_unset=True, by_alias=False)
    for field, value in update_data.items():
        setattr(user, field, value)
    await db.flush()
    await db.commit()

    return ok(AccountResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=user.created_at,
    ))
