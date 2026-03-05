"""
Safeguards API routes.
Reference: 08_API仕様 Section 3-6, 16_実行エンジンとUI接続 Section 7-2
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.trader import Trader
from app.models.safeguard_config import SafeguardConfig
from app.models.safeguard_log import SafeguardLog
from app.models.config_change import ConfigChange
from app.schemas.safeguard import (
    SafeguardConfigResponse,
    SafeguardConfigUpdateRequest,
    SafeguardLogItem,
)
from app.api.deps import get_current_user
from app.api.response import ok, paginated

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/traders/{trader_id}/safeguards",
    tags=["safeguards"],
)


async def _verify_trader_ownership(
    trader_id: int, user: User, db: AsyncSession,
) -> Trader:
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()
    if trader is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    return trader


@router.get("")
async def get_safeguard_config(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """セーフガード設定取得."""
    await _verify_trader_ownership(trader_id, user, db)

    q = select(SafeguardConfig).where(SafeguardConfig.trader_id == trader_id)
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if config is None:
        # Return default empty config instead of 404
        return ok(SafeguardConfigResponse(
            id=0,
            trader_id=trader_id,
            config_json={},
            created_at=None,
            updated_at=None,
        ))

    return ok(SafeguardConfigResponse(
        id=config.id,
        trader_id=config.trader_id,
        config_json=config.config_json,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))


@router.put("")
async def update_safeguard_config(
    trader_id: int,
    req: SafeguardConfigUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """セーフガード設定更新."""
    logger.info("Updating safeguard config for trader %d", trader_id)
    await _verify_trader_ownership(trader_id, user, db)

    q = select(SafeguardConfig).where(SafeguardConfig.trader_id == trader_id)
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    new_data = req.model_dump(exclude_unset=True, by_alias=False)

    if config is None:
        config = SafeguardConfig(
            user_id=user.id,
            trader_id=trader_id,
            config_json=new_data,
        )
        db.add(config)
    else:
        old_config = dict(config.config_json) if config.config_json else {}
        config.config_json = {**old_config, **new_data}

        change = ConfigChange(
            user_id=user.id,
            trader_id=trader_id,
            config_type="safeguard",
            stage="safeguard",
            config_before=old_config,
            config_after=config.config_json,
            changed_by=user.id,
            change_reason="Safeguard config updated via API",
        )
        db.add(change)

    await db.flush()
    await db.refresh(config)

    # Notify running engine via ConfigEventBus (16書§7-2)
    try:
        engine_manager = request.app.state.engine_manager
        await engine_manager.reload_config(
            trader_id=trader_id,
            config_type="safeguard",
            new_config=config.config_json,
        )
    except Exception:
        logger.warning("ConfigEventBus publish failed for trader %d", trader_id)

    return ok(SafeguardConfigResponse(
        id=config.id,
        trader_id=config.trader_id,
        config_json=config.config_json,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))


@router.get("/logs")
async def get_safeguard_logs(
    trader_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100, alias="perPage"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """セーフガード発動履歴."""
    await _verify_trader_ownership(trader_id, user, db)

    base = select(SafeguardLog).where(
        SafeguardLog.trader_id == trader_id,
        SafeguardLog.user_id == user.id,
    )

    # Total count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated data
    q = base.order_by(SafeguardLog.timestamp.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    logs = result.scalars().all()

    items = [
        SafeguardLogItem(
            id=log.id,
            trader_id=log.trader_id,
            pair=log.pair,
            timestamp=log.timestamp,
            trigger_type=log.trigger_type,
            guard_id=log.guard_id,
            result=log.result,
            reason=log.reason,
            details_json=log.details_json,
            created_at=log.created_at,
        )
        for log in logs
    ]

    return paginated(items, page, per_page, total)
