"""
Config Changes API routes.
Reference: 08_API仕様 Section 3-13
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.config_change import ConfigChange
from app.schemas.config_change import ConfigChangeItem, ConfigChangeDetail

router = APIRouter(prefix="/api/v1/config-changes", tags=["config-changes"])


def _get_user_id() -> int:
    """簡易: 認証済みユーザーID取得."""
    return 1


@router.get("", response_model=list[ConfigChangeItem])
async def list_config_changes(
    trader_id: int | None = Query(None, alias="traderId"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100, alias="perPage"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """変更履歴一覧."""
    q = select(ConfigChange).where(ConfigChange.user_id == user_id)

    if trader_id is not None:
        q = q.where(ConfigChange.trader_id == trader_id)

    q = q.order_by(ConfigChange.changed_at.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(q)
    changes = result.scalars().all()

    return [
        ConfigChangeItem(
            id=c.id,
            trader_id=c.trader_id,
            config_type=c.config_type,
            stage=c.stage,
            changed_at=c.changed_at,
            changed_by=c.changed_by,
            change_reason=c.change_reason,
        )
        for c in changes
    ]


@router.get("/{change_id}", response_model=ConfigChangeDetail)
async def get_config_change_detail(
    change_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """変更詳細（before/after diff）."""
    q = (
        select(ConfigChange)
        .where(ConfigChange.id == change_id)
        .where(ConfigChange.user_id == user_id)
    )
    result = await db.execute(q)
    change = result.scalar_one_or_none()

    if change is None:
        raise HTTPException(status_code=404, detail="Config change not found")

    return ConfigChangeDetail(
        id=change.id,
        trader_id=change.trader_id,
        config_type=change.config_type,
        stage=change.stage,
        config_before=change.config_before,
        config_after=change.config_after,
        changed_at=change.changed_at,
        changed_by=change.changed_by,
        change_reason=change.change_reason,
    )
