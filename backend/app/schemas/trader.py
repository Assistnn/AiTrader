"""
Trader API schemas (Pydantic).
Reference: 08_API仕様 Section 3-4
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TraderCreateRequest(BaseModel):
    """POST /api/v1/traders リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    trader_name: str = Field(alias="traderName")
    trade_type: str = Field(alias="tradeType")
    symbols: list[str]
    capital_jpy: float = Field(alias="capitalJpy")
    order_unit_lots: float = Field(alias="orderUnitLots")
    strategy_text: str | None = Field(None, alias="strategyText")
    notify_email: str | None = Field(None, alias="notifyEmail")
    notify_on_entry: bool = Field(True, alias="notifyOnEntry")
    notify_on_stop: bool = Field(True, alias="notifyOnStop")
    notify_on_error: bool = Field(True, alias="notifyOnError")
    notify_on_exit: bool = Field(True, alias="notifyOnExit")
    notify_on_target: bool = Field(True, alias="notifyOnTarget")


class TraderUpdateRequest(BaseModel):
    """PUT /api/v1/traders/{traderId} リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    trader_name: str | None = Field(None, alias="traderName")
    trade_type: str | None = Field(None, alias="tradeType")
    symbols: list[str] | None = None
    capital_jpy: float | None = Field(None, alias="capitalJpy")
    order_unit_lots: float | None = Field(None, alias="orderUnitLots")
    strategy_text: str | None = Field(None, alias="strategyText")
    notify_email: str | None = Field(None, alias="notifyEmail")
    notify_on_entry: bool | None = Field(None, alias="notifyOnEntry")
    notify_on_stop: bool | None = Field(None, alias="notifyOnStop")
    notify_on_error: bool | None = Field(None, alias="notifyOnError")
    notify_on_exit: bool | None = Field(None, alias="notifyOnExit")
    notify_on_target: bool | None = Field(None, alias="notifyOnTarget")


class TraderResponse(BaseModel):
    """GET /api/v1/traders/{traderId} レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    trader_name: str = Field(alias="traderName")
    trade_type: str = Field(alias="tradeType")
    symbols: list[str]
    capital_jpy: float = Field(alias="capitalJpy")
    order_unit_lots: float = Field(alias="orderUnitLots")
    strategy_text: str | None = Field(None, alias="strategyText")
    status: str
    created_at: datetime = Field(alias="createdAt")


class TraderListItem(BaseModel):
    """GET /api/v1/traders 一覧の1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    trader_name: str = Field(alias="traderName")
    trade_type: str = Field(alias="tradeType")
    status: str
    capital_jpy: float = Field(alias="capitalJpy")
    created_at: datetime = Field(alias="createdAt")
