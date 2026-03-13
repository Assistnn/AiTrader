"""
Notification API schemas.
Reference: 08_API仕様 Section 3-9
"""

from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class SmtpConfigResponse(BaseModel):
    """GET /api/v1/notifications/smtp レスポンス (stub: SMTP未実装のためプレースホルダ)."""

    model_config = ConfigDict(populate_by_name=True)

    host: str | None = None
    port: int | None = None
    username: str | None = None
    use_tls: bool = Field(True, alias="useTls")
    from_address: str | None = Field(None, alias="fromAddress")


class SmtpConfigUpdateRequest(BaseModel):
    """PUT /api/v1/notifications/smtp リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    use_tls: bool | None = Field(None, alias="useTls")
    from_address: str | None = Field(None, alias="fromAddress")


class NotificationEmailItem(BaseModel):
    """GET /api/v1/notifications/emails 1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    email: str
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")


class NotificationEmailCreateRequest(BaseModel):
    """POST /api/v1/notifications/emails リクエスト."""

    email: str
    is_active: bool = Field(True, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class DailyNotificationConfigResponse(BaseModel):
    """GET /api/v1/notifications/daily レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    enabled: bool
    send_time_utc: time | None = Field(None, alias="sendTimeUtc")
    include_pnl: bool = Field(alias="includePnl")
    include_trades: bool = Field(alias="includeTrades")
    include_guards: bool = Field(alias="includeGuards")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class DailyNotificationConfigUpdateRequest(BaseModel):
    """PUT /api/v1/notifications/daily リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    enabled: bool | None = None
    send_time_utc: time | None = Field(None, alias="sendTimeUtc")
    include_pnl: bool | None = Field(None, alias="includePnl")
    include_trades: bool | None = Field(None, alias="includeTrades")
    include_guards: bool | None = Field(None, alias="includeGuards")


class TriggerConfigItem(BaseModel):
    """Notification trigger config item."""

    model_config = ConfigDict(populate_by_name=True)

    trigger_key: str = Field(alias="triggerKey")
    enabled: bool


class TriggerConfigUpdateRequest(BaseModel):
    """PUT /api/v1/notifications/triggers リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    triggers: list[TriggerConfigItem]
