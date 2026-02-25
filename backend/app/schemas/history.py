"""
Trade history API schemas (Pydantic).
Reference: 08_API仕様 Section 3-10
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TradeHistoryItem(BaseModel):
    """GET /api/v1/history 一覧の1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    trader_id: int = Field(alias="traderId")
    pair: str
    side: str
    amount: float | None = None
    entry_price: float | None = Field(None, alias="entryPrice")
    exit_price: float | None = Field(None, alias="exitPrice")
    realized_pnl: float | None = Field(None, alias="realizedPnl")
    realized_pnl_pips: float | None = Field(None, alias="realizedPnlPips")
    rr_ratio: float | None = Field(None, alias="rrRatio")
    exit_reason: str | None = Field(None, alias="exitReason")
    opened_at: datetime = Field(alias="openedAt")
    closed_at: datetime | None = Field(None, alias="closedAt")


class TradeHistoryDetail(BaseModel):
    """GET /api/v1/history/{tradeId} 詳細（4段階判定含む）."""

    model_config = ConfigDict(populate_by_name=True)

    trade: TradeHistoryItem
    pipeline_logs: list[dict] = Field(alias="pipelineLogs")
    safeguard_logs: list[dict] = Field(alias="safeguardLogs")
