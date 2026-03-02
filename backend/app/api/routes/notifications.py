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
from app.models.notification import NotificationEmail, DailyNotificationConfig
from app.schemas.notification import (
    SmtpConfigResponse,
    SmtpConfigUpdateRequest,
    NotificationEmailItem,
    NotificationEmailCreateRequest,
    DailyNotificationConfigResponse,
    DailyNotificationConfigUpdateRequest,
)
from app.api.deps import get_current_user
from app.api.response import ok

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# --- SMTP (stub: SMTP設定はDBテーブルなし、将来的に追加) ---

# In-memory SMTP config per user (stub)
_smtp_configs: dict[int, dict] = {}


@router.get("/smtp")
async def get_smtp_config(
    user: User = Depends(get_current_user),
):
    """SMTP設定取得."""
    config = _smtp_configs.get(user.id, {})
    return ok(SmtpConfigResponse(
        host=config.get("host"),
        port=config.get("port"),
        username=config.get("username"),
        use_tls=config.get("use_tls", True),
        from_address=config.get("from_address"),
    ))


@router.put("/smtp")
async def update_smtp_config(
    req: SmtpConfigUpdateRequest,
    user: User = Depends(get_current_user),
):
    """SMTP設定更新."""
    existing = _smtp_configs.get(user.id, {})
    update_data = req.model_dump(exclude_unset=True, by_alias=False)
    # Do not store password in response
    update_data.pop("password", None)
    existing.update(update_data)
    _smtp_configs[user.id] = existing

    return ok(SmtpConfigResponse(
        host=existing.get("host"),
        port=existing.get("port"),
        username=existing.get("username"),
        use_tls=existing.get("use_tls", True),
        from_address=existing.get("from_address"),
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
    await db.flush()
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

    await db.flush()
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
