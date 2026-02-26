"""
Safeguard API schemas.
Reference: 08_API仕様 Section 3-6
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SafeguardConfigResponse(BaseModel):
    """GET /api/v1/traders/{traderId}/safeguards レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    trader_id: int = Field(alias="traderId")
    config_json: dict[str, Any] = Field(alias="configJson")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class SafeguardConfigUpdateRequest(BaseModel):
    """PUT /api/v1/traders/{traderId}/safeguards リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    max_daily_loss_pct: float | None = Field(None, alias="maxDailyLossPct")
    max_monthly_loss_pct: float | None = Field(None, alias="maxMonthlyLossPct")
    max_drawdown_pct: float | None = Field(None, alias="maxDrawdownPct")
    stop_on_profit: dict[str, Any] | None = Field(None, alias="stopOnProfit")
    consecutive_loss: dict[str, Any] | None = Field(None, alias="consecutiveLoss")
    spread: dict[str, Any] | None = None
    atr_spike: dict[str, Any] | None = Field(None, alias="atrSpike")
    range_spike: dict[str, Any] | None = Field(None, alias="rangeSpike")
    session: dict[str, Any] | None = None
    econ_stop: dict[str, Any] | None = Field(None, alias="econStop")
    regime: dict[str, Any] | None = None
    exec: dict[str, Any] | None = None
    ai_failsafe: dict[str, Any] | None = Field(None, alias="aiFailsafe")


class SafeguardLogItem(BaseModel):
    """GET /api/v1/traders/{traderId}/safeguards/logs 1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    trader_id: int = Field(alias="traderId")
    pair: str | None = None
    timestamp: datetime
    trigger_type: str = Field(alias="triggerType")
    guard_id: str = Field(alias="guardId")
    result: str
    reason: str | None = None
    details_json: dict[str, Any] | None = Field(None, alias="detailsJson")
    created_at: datetime = Field(alias="createdAt")
