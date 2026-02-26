"""
Model Stage API schemas.
Reference: 08_API仕様 Section 3-5
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModelStageResponse(BaseModel):
    """GET /api/v1/traders/{traderId}/model-stages/{stage} レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    trader_id: int = Field(alias="traderId")
    stage: str
    config_json: dict[str, Any] = Field(alias="configJson")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ModelStageUpdateRequest(BaseModel):
    """PUT /api/v1/traders/{traderId}/model-stages/{stage} リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    enabled: bool | None = None
    timeframes: list[str] | None = None
    use_trend_direction: bool | None = Field(None, alias="useTrendDirection")
    use_range_avoid: bool | None = Field(None, alias="useRangeAvoid")
    use_volatility: bool | None = Field(None, alias="useVolatility")
    mode: str | None = None
    ai: dict[str, Any] | None = None
    # Additional stage-specific fields stored as-is in config_json
    extra: dict[str, Any] | None = None
