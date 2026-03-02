"""
Settings API routes.
Reference: 08_API仕様 Section 3-14
"""

from __future__ import annotations

import time as time_module

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.config import settings as app_settings
from app.models.user import User
from app.models.trader import Trader
from app.models.position import Position
from app.models.exchange_config import ExchangeConfig
from app.models.ai_model_config import AiModelConfig
from app.schemas.settings import (
    ExchangeConfigResponse,
    ExchangeConfigUpdateRequest,
    AiConfigResponse,
    AiConfigUpdateRequest,
    CostConfigResponse,
    SystemStatusResponse,
)
from app.api.deps import get_current_user
from app.api.response import ok
from app.services.auth.key_vault import KeyVault

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

_start_time = time_module.time()


def _mask_key(encrypted: bytes | None) -> str:
    """Mask API key for display: show last 4 chars only."""
    if encrypted is None:
        return "****"
    try:
        vault = KeyVault(app_settings.MASTER_ENCRYPTION_KEY)
        decrypted = vault.decrypt(encrypted)
        if len(decrypted) > 4:
            return "****" + decrypted[-4:]
        return "****"
    except Exception:
        return "****"


@router.get("/exchanges")
async def list_exchange_configs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """取引所API設定一覧取得."""
    q = select(ExchangeConfig).where(ExchangeConfig.user_id == user.id)
    result = await db.execute(q)
    configs = result.scalars().all()

    return ok([
        ExchangeConfigResponse(
            id=c.id,
            exchange_type=c.exchange_type,
            api_key_masked=_mask_key(c.api_key_encrypted),
            is_active=c.is_active if c.is_active is not None else True,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ])


@router.put("/exchanges/{exchange_type}")
async def update_exchange_config(
    exchange_type: str,
    req: ExchangeConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """取引所API設定更新."""
    vault = KeyVault(app_settings.MASTER_ENCRYPTION_KEY)

    q = select(ExchangeConfig).where(
        ExchangeConfig.user_id == user.id,
        ExchangeConfig.exchange_type == exchange_type,
    )
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    encrypted_key = vault.encrypt(req.api_key)
    encrypted_secret = vault.encrypt(req.api_secret)

    if config is None:
        config = ExchangeConfig(
            user_id=user.id,
            exchange_type=exchange_type,
            api_key_encrypted=encrypted_key,
            api_secret_encrypted=encrypted_secret,
            is_active=req.is_active if req.is_active is not None else True,
        )
        db.add(config)
    else:
        config.api_key_encrypted = encrypted_key
        config.api_secret_encrypted = encrypted_secret
        if req.is_active is not None:
            config.is_active = req.is_active

    await db.flush()
    await db.refresh(config)

    return ok(ExchangeConfigResponse(
        id=config.id,
        exchange_type=config.exchange_type,
        api_key_masked=_mask_key(config.api_key_encrypted),
        is_active=config.is_active if config.is_active is not None else True,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))


@router.get("/ai")
async def list_ai_configs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI API設定一覧取得."""
    q = select(AiModelConfig).where(AiModelConfig.user_id == user.id)
    result = await db.execute(q)
    configs = result.scalars().all()

    return ok([
        AiConfigResponse(
            id=c.id,
            provider=c.provider,
            api_key_masked=_mask_key(c.api_key_encrypted),
            default_model=c.default_model,
            is_active=c.is_active if c.is_active is not None else True,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ])


@router.put("/ai/{provider}")
async def update_ai_config(
    provider: str,
    req: AiConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI API設定更新."""
    vault = KeyVault(app_settings.MASTER_ENCRYPTION_KEY)

    q = select(AiModelConfig).where(
        AiModelConfig.user_id == user.id,
        AiModelConfig.provider == provider,
    )
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    encrypted_key = vault.encrypt(req.api_key)

    if config is None:
        config = AiModelConfig(
            user_id=user.id,
            provider=provider,
            api_key_encrypted=encrypted_key,
            default_model=req.default_model,
            is_active=req.is_active if req.is_active is not None else True,
        )
        db.add(config)
    else:
        config.api_key_encrypted = encrypted_key
        if req.default_model is not None:
            config.default_model = req.default_model
        if req.is_active is not None:
            config.is_active = req.is_active

    await db.flush()
    await db.refresh(config)

    return ok(AiConfigResponse(
        id=config.id,
        provider=config.provider,
        api_key_masked=_mask_key(config.api_key_encrypted),
        default_model=config.default_model,
        is_active=config.is_active if config.is_active is not None else True,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))


@router.get("/cost")
async def get_cost_config(
    user: User = Depends(get_current_user),
):
    """コスト管理設定取得（サーバー設定、読み取り専用）."""
    return ok(CostConfigResponse(
        daily_token_limit=app_settings.AI_DAILY_TOKEN_BUDGET,
        rate_limit_per_trader=app_settings.AI_RATE_LIMIT_PER_TRADER,
        rate_limit_global=app_settings.AI_RATE_LIMIT_GLOBAL,
        warning_threshold_pct=app_settings.AI_BUDGET_WARNING_PCT,
    ))


@router.get("/system-status")
async def get_system_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """システム状態取得."""
    # Active traders count
    active_q = select(func.count()).select_from(
        select(Trader)
        .where(Trader.user_id == user.id, Trader.status == "running")
        .subquery()
    )
    active_traders = (await db.execute(active_q)).scalar() or 0

    # Open positions count
    pos_q = select(func.count()).select_from(
        select(Position)
        .where(Position.user_id == user.id)
        .subquery()
    )
    open_positions = (await db.execute(pos_q)).scalar() or 0

    uptime = time_module.time() - _start_time

    # Test DB connection
    db_connected = True
    try:
        await db.execute(select(func.now()))
    except Exception:
        db_connected = False

    return ok(SystemStatusResponse(
        trading_mode=app_settings.TRADING_MODE.value,
        db_connected=db_connected,
        active_traders=active_traders,
        open_positions=open_positions,
        uptime_seconds=round(uptime, 2),
    ))
