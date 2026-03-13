"""Notification models. Reference: 07_データベーススキーマ Section 3-4"""

from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class NotificationEmail(Base):
    __tablename__ = "notification_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_ne_user_id", "user_id"),)


class DailyNotificationConfig(Base):
    __tablename__ = "daily_notification_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    enabled: Mapped[bool | None] = mapped_column(Boolean, default=False)
    send_time_utc: Mapped[time | None] = mapped_column(
        Time, default=time(22, 0)
    )  # UTC (JST 07:00)
    include_pnl: Mapped[bool | None] = mapped_column(Boolean, default=True)
    include_trades: Mapped[bool | None] = mapped_column(Boolean, default=True)
    include_guards: Mapped[bool | None] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id"),)


class SmtpConfig(Base):
    """SMTP settings per user. Reference: 07_データベーススキーマ §3-4"""
    __tablename__ = "smtp_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer, default=587)
    username: Mapped[str | None] = mapped_column(String(255))
    password_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    use_tls: Mapped[bool | None] = mapped_column(Boolean, default=True)
    from_address: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id"),)


class NotificationTriggerConfig(Base):
    """Notification trigger settings. Reference: 07_データベーススキーマ §3-4"""
    __tablename__ = "notification_trigger_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trigger_key: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool | None] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "trigger_key"),
        Index("idx_ntc_user_id", "user_id"),
    )
