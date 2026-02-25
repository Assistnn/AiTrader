"""
Config change API schemas (Pydantic).
Reference: 08_API仕様 Section 3-13
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConfigChangeItem(BaseModel):
    """GET /api/v1/config-changes 一覧の1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    trader_id: int = Field(alias="traderId")
    config_type: str = Field(alias="configType")
    stage: str | None = None
    changed_at: datetime = Field(alias="changedAt")
    changed_by: int = Field(alias="changedBy")
    change_reason: str | None = Field(None, alias="changeReason")


class ConfigChangeDetail(BaseModel):
    """GET /api/v1/config-changes/{changeId} 詳細（before/after diff）."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    trader_id: int = Field(alias="traderId")
    config_type: str = Field(alias="configType")
    stage: str | None = None
    config_before: dict = Field(alias="configBefore")
    config_after: dict = Field(alias="configAfter")
    changed_at: datetime = Field(alias="changedAt")
    changed_by: int = Field(alias="changedBy")
    change_reason: str | None = Field(None, alias="changeReason")
