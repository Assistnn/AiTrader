"""
bitbank exchange implementation (stub).

Reference: 06_取引所抽象化 Section 6
- Spot trading (no leverage/margin)
- No native SL/TP → system-side monitoring + market close
- Rate limit: Private API 6 requests/sec
- Auth: API-KEY + HMAC-SHA256 (bitbank-specific signing)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

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
from app.services.exchange.pair_normalizer import PairNormalizer
from app.services.exchange.rate_limiter import OrderRateLimiter


class BitbankExchange(BaseExchange):
    """
    bitbank cryptocurrency exchange.

    Reference: Section 6
    Authentication: API Key + HMAC-SHA256 (nonce-based)
    Spot trading only (no margin). SL/TP handled system-side.
    """

    BASE_URL = "https://api.bitbank.cc"
    PUBLIC_URL = "https://public.bitbank.cc"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._rate_limiter = OrderRateLimiter(
            min_interval_sec=0.0, max_per_minute=300, max_per_second=6,
        )

    def _sign_get(self, nonce: str, path: str, query_params: str = "") -> str:
        """Generate HMAC-SHA256 signature for GET requests (bitbank format).

        bitbank GET: sign(nonce + path + query_string)
        """
        message = nonce + path
        if query_params:
            message += "?" + query_params
        return hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _sign_post(self, nonce: str, body: str) -> str:
        """Generate HMAC-SHA256 signature for POST requests (bitbank format).

        bitbank POST: sign(nonce + body_json)
        """
        message = nonce + body
        return hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _headers(self, method: str, path: str, body: str = "", query: str = "") -> dict:
        """Build authenticated headers for bitbank API."""
        nonce = str(int(time.time() * 1000))
        if method.upper() == "GET":
            sign = self._sign_get(nonce, path, query)
        else:
            sign = self._sign_post(nonce, body)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-NONCE": nonce,
            "ACCESS-SIGNATURE": sign,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _to_bitbank_pair(internal_pair: str) -> str:
        """Convert internal pair format to bitbank format."""
        return PairNormalizer.to_bitbank(internal_pair)

    # --- BaseExchange interface (stubs for Phase 4) ---

    async def get_ticker(self, pair: str) -> Ticker:
        raise NotImplementedError("BitbankExchange.get_ticker: requires API integration")

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        raise NotImplementedError("BitbankExchange.get_ohlcv: requires API integration")

    async def place_order(
        self, pair: str, side: OrderSide, amount: float,
        order_type: OrderType, price: float | None = None,
        client_order_id: str | None = None,
        tp_price: float | None = None, sl_price: float | None = None,
    ) -> Order:
        raise NotImplementedError("BitbankExchange.place_order: requires API integration")

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("BitbankExchange.cancel_order: requires API integration")

    async def get_order_status(self, order_id: str) -> Order:
        raise NotImplementedError("BitbankExchange.get_order_status: requires API integration")

    async def get_positions(self) -> list[ExchangePosition]:
        raise NotImplementedError("BitbankExchange.get_positions: requires API integration")

    async def close_position(self, position_id: str, amount: float | None = None) -> Order:
        raise NotImplementedError("BitbankExchange.close_position: requires API integration")

    async def get_balance(self) -> Balance:
        raise NotImplementedError("BitbankExchange.get_balance: requires API integration")

    async def modify_order(self, order_id: str, price: float | None = None) -> Order:
        raise NotImplementedError("BitbankExchange.modify_order: requires API integration")
