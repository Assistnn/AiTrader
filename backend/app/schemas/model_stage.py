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
    """PUT /api/v1/traders/{traderId}/model-stages/{stage} リクエスト.

    config_json はステージごとに異なる構造を持つため、
    任意のフィールドを受け付けてそのまま JSONB に保存する。
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    enabled: bool | None = None
    mode: str | None = None
