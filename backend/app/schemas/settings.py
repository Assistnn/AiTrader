"""
Settings API schemas.
Reference: 08_API仕様 Section 3-14
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExchangeConfigResponse(BaseModel):
    """GET /api/v1/settings/exchanges 1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    exchange_type: str = Field(alias="exchangeType")
    api_key_masked: str = Field(alias="apiKeyMasked")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ExchangeConfigUpdateRequest(BaseModel):
    """PUT /api/v1/settings/exchanges/{exchangeType} リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    api_key: str = Field(alias="apiKey")
    api_secret: str = Field(alias="apiSecret")
    is_active: bool | None = Field(None, alias="isActive")


class AiConfigResponse(BaseModel):
    """GET /api/v1/settings/ai 1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    provider: str
    api_key_masked: str = Field(alias="apiKeyMasked")
    default_model: str | None = Field(None, alias="defaultModel")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AiConfigUpdateRequest(BaseModel):
    """PUT /api/v1/settings/ai/{provider} リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    api_key: str = Field(alias="apiKey")
    default_model: str | None = Field(None, alias="defaultModel")
    is_active: bool | None = Field(None, alias="isActive")


class CostConfigResponse(BaseModel):
    """GET /api/v1/settings/cost レスポンス（読み取り専用）."""

    model_config = ConfigDict(populate_by_name=True)

    daily_token_limit: int = Field(alias="dailyTokenLimit")
    rate_limit_per_trader: int = Field(alias="rateLimitPerTrader")
    rate_limit_global: int = Field(alias="rateLimitGlobal")
    warning_threshold_pct: int = Field(alias="warningThresholdPct")


class SystemStatusResponse(BaseModel):
    """GET /api/v1/settings/system-status レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    trading_mode: str = Field(alias="tradingMode")
    db_connected: bool = Field(alias="dbConnected")
    active_traders: int = Field(alias="activeTraders")
    open_positions: int = Field(alias="openPositions")
    uptime_seconds: float = Field(alias="uptimeSeconds")
