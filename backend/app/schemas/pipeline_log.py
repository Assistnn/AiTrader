"""
Pipeline log API schemas (Pydantic).
Reference: 08_API仕様 Section 3-12
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineLogItem(BaseModel):
    """GET /api/v1/pipeline-logs 一覧の1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    execution_id: str = Field(alias="executionId")
    trader_id: int = Field(alias="traderId")
    pair: str
    timestamp: datetime
    stage: str
    mode: str | None = None
    elapsed_ms: float | None = Field(None, alias="elapsedMs")
    created_at: datetime = Field(alias="createdAt")


class PipelineLogDetail(BaseModel):
    """GET /api/v1/pipeline-logs/{executionId} 詳細."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    execution_id: str = Field(alias="executionId")
    trader_id: int = Field(alias="traderId")
    pair: str
    timestamp: datetime
    stage: str
    mode: str | None = None
    input_snapshot: dict = Field(alias="inputSnapshot")
    output_snapshot: dict = Field(alias="outputSnapshot")
    config_snapshot: dict = Field(alias="configSnapshot")
    elapsed_ms: float | None = Field(None, alias="elapsedMs")
    created_at: datetime = Field(alias="createdAt")
