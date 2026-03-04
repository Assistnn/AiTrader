"""
Trader API schemas (Pydantic).
Reference: 08_API仕様 Section 3-4
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.exchange.pair_normalizer import PairNormalizer


def _normalize_trade_type(v: str) -> str:
    """trade_type を正規化: fx->FX, crypto->Crypto."""
    low = v.lower()
    if low == "fx":
        return "FX"
    if low == "crypto":
        return "Crypto"
    return v


def _validate_symbols_for_trade_type(
    trade_type: str, symbols: list[str]
) -> list[str]:
    """symbols が trade_type に合致するか検証."""
    if not symbols:
        raise ValueError("symbols must contain at least one pair")

    if trade_type.lower() == "crypto":
        valid = PairNormalizer.CRYPTO_PAIRS
        label = "Crypto"
    else:
        valid = PairNormalizer.FX_PAIRS
        label = "FX"

    invalid = [s for s in symbols if s not in valid]
    if invalid:
        raise ValueError(
            f"Invalid symbols for {label}: {invalid}. "
            f"Valid: {sorted(valid)}"
        )
    return symbols


class TraderCreateRequest(BaseModel):
    """POST /api/v1/traders リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    trader_name: str = Field(alias="traderName")
    trade_type: str = Field(alias="tradeType")
    symbols: list[str]
    capital_jpy: float = Field(alias="capitalJpy")
    order_unit_lots: float = Field(alias="orderUnitLots")
    strategy_text: str | None = Field(None, alias="strategyText", max_length=2000)
    notify_email: str | None = Field(None, alias="notifyEmail")
    notify_on_entry: bool = Field(True, alias="notifyOnEntry")
    notify_on_stop: bool = Field(True, alias="notifyOnStop")
    notify_on_error: bool = Field(True, alias="notifyOnError")
    notify_on_exit: bool = Field(True, alias="notifyOnExit")
    notify_on_target: bool = Field(True, alias="notifyOnTarget")

    @field_validator("trade_type")
    @classmethod
    def normalize_trade_type(cls, v: str) -> str:
        return _normalize_trade_type(v)

    @model_validator(mode="after")
    def check_symbols_match_trade_type(self) -> TraderCreateRequest:
        _validate_symbols_for_trade_type(self.trade_type, self.symbols)
        return self


class TraderUpdateRequest(BaseModel):
    """PUT /api/v1/traders/{traderId} リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    trader_name: str | None = Field(None, alias="traderName")
    trade_type: str | None = Field(None, alias="tradeType")
    symbols: list[str] | None = None
    capital_jpy: float | None = Field(None, alias="capitalJpy")
    order_unit_lots: float | None = Field(None, alias="orderUnitLots")
    strategy_text: str | None = Field(None, alias="strategyText", max_length=2000)
    notify_email: str | None = Field(None, alias="notifyEmail")
    notify_on_entry: bool | None = Field(None, alias="notifyOnEntry")
    notify_on_stop: bool | None = Field(None, alias="notifyOnStop")
    notify_on_error: bool | None = Field(None, alias="notifyOnError")
    notify_on_exit: bool | None = Field(None, alias="notifyOnExit")
    notify_on_target: bool | None = Field(None, alias="notifyOnTarget")

    @field_validator("trade_type")
    @classmethod
    def normalize_trade_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _normalize_trade_type(v)

    @model_validator(mode="after")
    def check_symbols_match_trade_type(self) -> TraderUpdateRequest:
        if self.trade_type is not None and self.symbols is not None:
            _validate_symbols_for_trade_type(self.trade_type, self.symbols)
        return self


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
