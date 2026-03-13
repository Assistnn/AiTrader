"""
Notifications API routes.
Reference: 08_API仕様 Section 3-9
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.notification import NotificationEmail, DailyNotificationConfig, SmtpConfig, NotificationTriggerConfig
from app.schemas.notification import (
    SmtpConfigResponse,
    SmtpConfigUpdateRequest,
    NotificationEmailItem,
    NotificationEmailCreateRequest,
    DailyNotificationConfigResponse,
    DailyNotificationConfigUpdateRequest,
    TriggerConfigItem,
    TriggerConfigUpdateRequest,
)
from app.api.deps import get_current_user
from app.api.response import ok
from app.config import settings

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# --- SMTP (DB-backed: 07_データベーススキーマ §3-4) ---


@router.get("/smtp")
async def get_smtp_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """SMTP設定取得."""
    q = select(SmtpConfig).where(SmtpConfig.user_id == user.id)
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if config is None:
        return ok(SmtpConfigResponse())

    return ok(SmtpConfigResponse(
        host=config.host,
        port=config.port,
        username=config.username,
        use_tls=config.use_tls if config.use_tls is not None else True,
        from_address=config.from_address,
    ))


@router.put("/smtp")
async def update_smtp_config(
    req: SmtpConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """SMTP設定更新."""
    q = select(SmtpConfig).where(SmtpConfig.user_id == user.id)
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if config is None:
        config = SmtpConfig(user_id=user.id)
        db.add(config)

    update_data = req.model_dump(exclude_unset=True, by_alias=False)

    # Encrypt password if provided
    password = update_data.pop("password", None)
    if password:
        from app.services.auth.key_vault import KeyVault
        vault = KeyVault(settings.MASTER_ENCRYPTION_KEY)
        config.password_encrypted = vault.encrypt(password)

    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)

    return ok(SmtpConfigResponse(
        host=config.host,
        port=config.port,
        username=config.username,
        use_tls=config.use_tls if config.use_tls is not None else True,
        from_address=config.from_address,
    ))


# --- Notification Emails ---

@router.get("/emails")
async def list_notification_emails(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """通知メールアドレス一覧."""
    q = (
        select(NotificationEmail)
        .where(NotificationEmail.user_id == user.id)
        .order_by(NotificationEmail.id)
    )
    result = await db.execute(q)
    emails = result.scalars().all()

    return ok([
        NotificationEmailItem(
            id=e.id,
            email=e.email,
            is_active=e.is_active if e.is_active is not None else True,
            created_at=e.created_at,
        )
        for e in emails
    ])


@router.post("/emails", status_code=status.HTTP_201_CREATED)
async def add_notification_email(
    req: NotificationEmailCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """通知メールアドレス追加."""
    email = NotificationEmail(
        user_id=user.id,
        email=req.email,
        is_active=req.is_active,
    )
    db.add(email)
    await db.commit()
    await db.refresh(email)

    return ok(NotificationEmailItem(
        id=email.id,
        email=email.email,
        is_active=email.is_active if email.is_active is not None else True,
        created_at=email.created_at,
    ))


@router.delete("/emails/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_email(
    email_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """通知メールアドレス削除."""
    q = select(NotificationEmail).where(
        NotificationEmail.id == email_id,
        NotificationEmail.user_id == user.id,
    )
    result = await db.execute(q)
    email = result.scalar_one_or_none()

    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")

    await db.delete(email)
    await db.flush()
    await db.commit()


# --- Test send ---

@router.post("/test")
async def send_test_notification(
    user: User = Depends(get_current_user),
):
    """テスト送信 (stub)."""
    return ok({"sent": True, "message": "Test notification sent (stub)"})


# --- Daily Notification Config ---

@router.get("/daily")
async def get_daily_notification_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """デイリー通知設定取得."""
    q = select(DailyNotificationConfig).where(
        DailyNotificationConfig.user_id == user.id,
    )
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(status_code=404, detail="Daily notification config not found")

    return ok(DailyNotificationConfigResponse(
        id=config.id,
        enabled=config.enabled if config.enabled is not None else False,
        send_time_utc=config.send_time_utc,
        include_pnl=config.include_pnl if config.include_pnl is not None else True,
        include_trades=config.include_trades if config.include_trades is not None else True,
        include_guards=config.include_guards if config.include_guards is not None else True,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))


@router.put("/daily")
async def update_daily_notification_config(
    req: DailyNotificationConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """デイリー通知設定更新."""
    q = select(DailyNotificationConfig).where(
        DailyNotificationConfig.user_id == user.id,
    )
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if config is None:
        config = DailyNotificationConfig(user_id=user.id)
        db.add(config)

    update_data = req.model_dump(exclude_unset=True, by_alias=False)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)

    return ok(DailyNotificationConfigResponse(
        id=config.id,
        enabled=config.enabled if config.enabled is not None else False,
        send_time_utc=config.send_time_utc,
        include_pnl=config.include_pnl if config.include_pnl is not None else True,
        include_trades=config.include_trades if config.include_trades is not None else True,
        include_guards=config.include_guards if config.include_guards is not None else True,
        created_at=config.created_at,
        updated_at=config.updated_at,
    ))


# --- Notification Triggers (DB-backed: 07_データベーススキーマ §3-4) ---

_DEFAULT_TRIGGERS = [
    "notifyOnEntry", "notifyOnExit", "notifyOnGuardHalt",
    "notifyOnDailyReport", "notifyOnError",
]


@router.get("/triggers")
async def get_trigger_configs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """通知トリガー設定一覧."""
    q = select(NotificationTriggerConfig).where(
        NotificationTriggerConfig.user_id == user.id,
    )
    result = await db.execute(q)
    configs = result.scalars().all()

    config_map = {c.trigger_key: c.enabled for c in configs}

    items = [
        TriggerConfigItem(
            trigger_key=key,
            enabled=config_map.get(key, True),
        )
        for key in _DEFAULT_TRIGGERS
    ]
    return ok(items)


@router.put("/triggers")
async def update_trigger_configs(
    req: TriggerConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """通知トリガー設定一括更新."""
    for item in req.triggers:
        q = select(NotificationTriggerConfig).where(
            NotificationTriggerConfig.user_id == user.id,
            NotificationTriggerConfig.trigger_key == item.trigger_key,
        )
        result = await db.execute(q)
        config = result.scalar_one_or_none()

        if config is None:
            config = NotificationTriggerConfig(
                user_id=user.id,
                trigger_key=item.trigger_key,
            )
            db.add(config)

        config.enabled = item.enabled

    await db.commit()

    return ok({"updated": len(req.triggers)})
