"""
Model Stages API routes.
Reference: 08_API仕様 Section 3-5, 16_実行エンジンとUI接続 Section 7-2
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.trader import Trader
from app.models.model_stage_config import ModelStageConfig
from app.models.config_change import ConfigChange
from app.schemas.model_stage import ModelStageResponse, ModelStageUpdateRequest
from app.api.deps import get_current_user
from app.api.response import ok

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/traders/{trader_id}/model-stages",
    tags=["model-stages"],
)


async def _verify_trader_ownership(
    trader_id: int, user: User, db: AsyncSession,
) -> Trader:
    """@verify_ownership: トレーダー所有権検証."""
    q = select(Trader).where(Trader.id == trader_id, Trader.user_id == user.id)
    result = await db.execute(q)
    trader = result.scalar_one_or_none()
    if trader is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    return trader


@router.get("")
async def get_all_model_stages(
    trader_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全段階の設定取得."""
    await _verify_trader_ownership(trader_id, user, db)

    q = (
        select(ModelStageConfig)
        .where(ModelStageConfig.trader_id == trader_id)
        .order_by(ModelStageConfig.stage)
    )
    result = await db.execute(q)
    configs = result.scalars().all()

    return ok([
        ModelStageResponse(
            id=c.id,
            trader_id=c.trader_id,
            stage=c.stage,
            config_json=c.config_json,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ])


@router.get("/{stage}")
async def get_model_stage(
    trader_id: int,
    stage: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """指定段階の設定取得."""
    await _verify_trader_ownership(trader_id, user, db)

    q = select(ModelStageConfig).where(
        ModelStageConfig.trader_id == trader_id,
        ModelStageConfig.stage == stage,
    )
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(status_code=404, detail="Model stage config not found")

    return ok(ModelStageResponse(
        id=config.id,
        trader_id=config.trader_id,
        stage=config.stage,
        config_json=config.config_json,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))


@router.put("/{stage}")
async def update_model_stage(
    trader_id: int,
    stage: str,
    req: ModelStageUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """指定段階の設定更新."""
    await _verify_trader_ownership(trader_id, user, db)

    q = select(ModelStageConfig).where(
        ModelStageConfig.trader_id == trader_id,
        ModelStageConfig.stage == stage,
    )
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    new_config = req.model_dump(exclude_unset=True, by_alias=False)

    if config is None:
        # Create new config
        config = ModelStageConfig(
            user_id=user.id,
            trader_id=trader_id,
            stage=stage,
            config_json=new_config,
        )
        db.add(config)
    else:
        # Record config change
        old_config = dict(config.config_json) if config.config_json else {}
        config.config_json = {**old_config, **new_config}

        change = ConfigChange(
            user_id=user.id,
            trader_id=trader_id,
            config_type="model_stage",
            stage=stage,
            config_before=old_config,
            config_after=config.config_json,
            changed_by="user",
            change_reason="Model stage config updated via API",
        )
        db.add(change)

    await db.flush()
    await db.commit()

    # Notify running engine via ConfigEventBus (16書§7-2)
    engine_manager = request.app.state.engine_manager
    try:
        await engine_manager.reload_config(
            trader_id=trader_id,
            config_type="model_stage",
            new_config=config.config_json,
            stage=stage,
        )
    except Exception:
        logger.warning("ConfigEventBus publish failed for trader %d", trader_id)

    return ok({
        **ModelStageResponse(
            id=config.id,
            trader_id=config.trader_id,
            stage=config.stage,
            config_json=config.config_json,
            created_at=config.created_at,
            updated_at=config.updated_at,
        ).model_dump(by_alias=True, mode="json"),
        "configChange": {
            "id": change.id if 'change' in dir() else None,
            "changedAt": config.updated_at.isoformat() if config.updated_at else None,
        },
    })
