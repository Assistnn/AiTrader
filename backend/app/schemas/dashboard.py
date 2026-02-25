"""
Dashboard API schemas (Pydantic).
Reference: 08_API仕様 Section 3-3
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PipelineStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    last_m1: dict | None = Field(None, alias="lastM1")
    last_m2: dict | None = Field(None, alias="lastM2")
    guard_state: dict | None = Field(None, alias="guardState")


class TraderSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trader_id: int = Field(alias="traderId")
    trader_name: str = Field(alias="traderName")
    status: str
    pnl_today: float = Field(0, alias="pnlToday")
    open_positions: int = Field(0, alias="openPositions")
    pipeline_state: PipelineStateResponse | None = Field(None, alias="pipelineState")


class DashboardSummaryResponse(BaseModel):
    """GET /api/v1/dashboard/summary レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    total_pnl_today: float = Field(0, alias="totalPnlToday")
    total_pnl_month: float = Field(0, alias="totalPnlMonth")
    active_traders: int = Field(0, alias="activeTraders")
    open_positions: int = Field(0, alias="openPositions")
    traders: list[TraderSummary] = []
