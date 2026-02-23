"""
GMO Coin FX exchange implementation (stub).

Reference: 06_取引所抽象化 Section 5
Full API integration will be implemented when API access is available.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from app.services.pipeline.data_types import OHLCV, Ticker
from app.services.exchange.base_exchange import BaseExchange
from app.services.exchange.exchange_types import (
    Balance,
    ExchangePosition,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)


class GmoFxExchange(BaseExchange):
    """
    GMO Coin FX exchange.

    Reference: Section 5
    Authentication: API Key + HMAC-SHA256
    """

    BASE_URL = "https://api.coin.z.com"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """Generate HMAC-SHA256 signature. Reference: Section 5-1"""
        text = timestamp + method + path + body
        return hmac.new(
            self.api_secret.encode(),
            text.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        """Build authenticated headers."""
        timestamp = str(int(time.time() * 1000))
        sign = self._sign(timestamp, method, path, body)
        return {
            "API-KEY": self.api_key,
            "API-TIMESTAMP": timestamp,
            "API-SIGN": sign,
        }

    # --- BaseExchange interface (stubs for Phase 1) ---

    async def get_ticker(self, pair: str) -> Ticker:
        raise NotImplementedError("GmoFxExchange.get_ticker: requires API integration")

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        raise NotImplementedError("GmoFxExchange.get_ohlcv: requires API integration")

    async def place_order(
        self, pair: str, side: OrderSide, amount: float,
        order_type: OrderType, price: float | None = None,
        client_order_id: str | None = None,
        tp_price: float | None = None, sl_price: float | None = None,
    ) -> Order:
        raise NotImplementedError("GmoFxExchange.place_order: requires API integration")

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("GmoFxExchange.cancel_order: requires API integration")

    async def get_order_status(self, order_id: str) -> Order:
        raise NotImplementedError("GmoFxExchange.get_order_status: requires API integration")

    async def get_positions(self) -> list[ExchangePosition]:
        raise NotImplementedError("GmoFxExchange.get_positions: requires API integration")

    async def close_position(self, position_id: str, amount: float | None = None) -> Order:
        raise NotImplementedError("GmoFxExchange.close_position: requires API integration")

    async def get_balance(self) -> Balance:
        raise NotImplementedError("GmoFxExchange.get_balance: requires API integration")

    async def modify_order(self, order_id: str, price: float | None = None) -> Order:
        raise NotImplementedError("GmoFxExchange.modify_order: requires API integration")
