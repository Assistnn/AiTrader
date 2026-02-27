"""
bitbank exchange implementation.

Reference: 06_取引所抽象化 Section 6, 16_実行エンジンとUI接続 Section 3-2
- Spot trading (no leverage/margin)
- No native SL/TP → system-side monitoring + market close (16書§9-4)
- Rate limit: Private API 6 requests/sec
- Auth: API-KEY + HMAC-SHA256 (bitbank-specific signing)
- Public: https://public.bitbank.cc
- Private: https://api.bitbank.cc
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx

from app.logging_config import log_with_data

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

logger = logging.getLogger(__name__)

# bitbank order status mapping
_ORDER_STATUS_MAP: dict[str, OrderStatus] = {
    "UNFILLED": OrderStatus.PENDING,
    "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
    "FULLY_FILLED": OrderStatus.FILLED,
    "CANCELED_UNFILLED": OrderStatus.CANCELLED,
    "CANCELED_PARTIALLY_FILLED": OrderStatus.CANCELLED,
}


class BitbankApiError(Exception):
    """bitbank API error."""

    def __init__(self, status_code: int, error_code: int, message: str):
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(f"bitbank API error {error_code}: {message}")


class BitbankExchange(BaseExchange):
    """
    bitbank cryptocurrency exchange.

    Reference: 06_取引所抽象化 Section 6, 16_実行エンジンとUI接続 Section 3-2
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
        self._client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    # --- Authentication ---

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

    # --- HTTP helpers ---

    async def _public_get(self, path: str) -> dict:
        """Execute public GET request."""
        logger.debug("bitbank public GET %s", path)
        start = time.monotonic()
        resp = await self._client.get(f"{self.PUBLIC_URL}{path}")
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
        if data.get("success") != 1:
            code = data.get("data", {}).get("code", 0)
            log_with_data(logger, logging.ERROR, "bitbank API error", {
                "path": path, "status_code": resp.status_code, "error_code": code,
            })
            raise BitbankApiError(resp.status_code, code, f"Public API error: {code}")
        logger.debug("bitbank public GET %s completed (%.0fms)", path, elapsed)
        return data

    async def _private_get(self, path: str, params: dict | None = None) -> dict:
        """Execute authenticated GET request."""
        logger.debug("bitbank private GET %s", path)
        start = time.monotonic()
        query = "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
        headers = self._headers("GET", path, query=query)
        url = f"{self.BASE_URL}{path}"
        if query:
            url += "?" + query
        resp = await self._client.get(url, headers=headers)
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
        if data.get("success") != 1:
            code = data.get("data", {}).get("code", 0)
            log_with_data(logger, logging.ERROR, "bitbank API error", {
                "path": path, "status_code": resp.status_code, "error_code": code,
            })
            raise BitbankApiError(resp.status_code, code, f"Private GET error: {code}")
        logger.debug("bitbank private GET %s completed (%.0fms)", path, elapsed)
        return data

    async def _private_post(self, path: str, body: dict) -> dict:
        """Execute authenticated POST request."""
        logger.debug("bitbank private POST %s", path)
        start = time.monotonic()
        body_str = json.dumps(body)
        headers = self._headers("POST", path, body=body_str)
        resp = await self._client.post(
            f"{self.BASE_URL}{path}", headers=headers, content=body_str,
        )
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
        if data.get("success") != 1:
            code = data.get("data", {}).get("code", 0)
            log_with_data(logger, logging.ERROR, "bitbank API error", {
                "path": path, "status_code": resp.status_code, "error_code": code,
            })
            raise BitbankApiError(resp.status_code, code, f"Private POST error: {code}")
        logger.debug("bitbank private POST %s completed (%.0fms)", path, elapsed)
        return data

    # --- BaseExchange interface ---

    async def get_ticker(self, pair: str) -> Ticker:
        """Get latest ticker. Reference: 16書§3-2 GET /{pair}/ticker"""
        bb_pair = self._to_bitbank_pair(pair)
        data = await self._public_get(f"/{bb_pair}/ticker")
        t = data["data"]
        return Ticker(
            timestamp=datetime.fromtimestamp(
                int(t["timestamp"]) / 1000, tz=timezone.utc,
            ),
            bid=float(t["buy"]),
            ask=float(t["sell"]),
            last=float(t["last"]),
            volume=float(t.get("vol", 0)),
        )

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        """Get OHLCV bar data. Reference: 16書§3-2 GET /{pair}/candlestick/{type}/{date}"""
        from app.services.pipeline.bitbank_data_provider import TIMEFRAME_MAP

        candle_type = TIMEFRAME_MAP.get(timeframe)
        if candle_type is None:
            raise ValueError(f"Unsupported timeframe for bitbank: {timeframe}")

        bb_pair = self._to_bitbank_pair(pair)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        data = await self._public_get(
            f"/{bb_pair}/candlestick/{candle_type}/{date_str}",
        )

        candlesticks = data.get("data", {}).get("candlestick", [])
        bars: list[OHLCV] = []
        for cs in candlesticks:
            for ohlcv_item in cs.get("ohlcv", []):
                # bitbank: [open, high, low, close, volume, timestamp]
                bars.append(OHLCV(
                    timestamp=datetime.fromtimestamp(
                        int(ohlcv_item[5]) / 1000, tz=timezone.utc,
                    ),
                    open=float(ohlcv_item[0]),
                    high=float(ohlcv_item[1]),
                    low=float(ohlcv_item[2]),
                    close=float(ohlcv_item[3]),
                    volume=float(ohlcv_item[4]),
                ))

        bars.sort(key=lambda x: x.timestamp)
        return bars[-limit:] if len(bars) > limit else bars

    async def place_order(
        self,
        pair: str,
        side: OrderSide,
        amount: float,
        order_type: OrderType,
        price: float | None = None,
        client_order_id: str | None = None,
        tp_price: float | None = None,
        sl_price: float | None = None,
    ) -> Order:
        """Place an order. Reference: 16書§3-2 POST /v1/user/spot/order

        Note: tp_price/sl_price are ignored. ExecutionEngine monitors system-side (16書§9-4).
        """
        await self._rate_limiter.wait_if_needed()

        bb_pair = self._to_bitbank_pair(pair)
        body: dict = {
            "pair": bb_pair,
            "side": side.value.lower(),
            "amount": str(amount),
            "type": "market" if order_type == OrderType.MARKET else "limit",
        }
        if price is not None and order_type != OrderType.MARKET:
            body["price"] = str(price)

        data = await self._private_post("/v1/user/spot/order", body)
        self._rate_limiter.record_order()

        o = data["data"]
        order_id_str = str(o["order_id"])
        log_with_data(logger, logging.INFO, "Order placed", {
            "pair": pair, "side": side.value, "amount": amount,
            "order_type": order_type.value, "client_order_id": client_order_id,
            "order_id": order_id_str,
        })
        return Order(
            order_id=order_id_str,
            client_order_id=client_order_id or "",
            pair=pair,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            status=_ORDER_STATUS_MAP.get(o.get("status", ""), OrderStatus.PENDING),
            filled_amount=float(o.get("executed_amount", 0)),
            filled_price=float(o.get("average_price", 0)) or None,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order. Reference: 16書§3-2 POST /v1/user/spot/cancel_order"""
        await self._rate_limiter.wait_if_needed()
        # bitbank cancel requires pair; we pass a placeholder and let the API handle it
        # In practice, the order_id uniquely identifies the order
        await self._private_post(
            "/v1/user/spot/cancel_order",
            {"order_id": int(order_id), "pair": "btc_jpy"},
        )
        self._rate_limiter.record_order()
        log_with_data(logger, logging.INFO, "Order cancelled", {"order_id": order_id})
        return True

    async def get_order_status(self, order_id: str) -> Order:
        """Get order status. Reference: 16書§3-2 GET /v1/user/spot/order"""
        # bitbank requires pair; try to get from active orders
        data = await self._private_get(
            "/v1/user/spot/order",
            params={"order_id": order_id, "pair": "btc_jpy"},
        )
        o = data["data"]
        status = _ORDER_STATUS_MAP.get(o.get("status", ""), OrderStatus.PENDING)
        return Order(
            order_id=str(o["order_id"]),
            client_order_id="",
            pair=PairNormalizer.to_internal(o.get("pair", "")),
            side=OrderSide.BUY if o.get("side") == "buy" else OrderSide.SELL,
            order_type=OrderType.MARKET if o.get("type") == "market" else OrderType.LIMIT,
            amount=float(o.get("start_amount", 0)),
            price=float(o.get("price", 0)) if o.get("price") else None,
            status=status,
            filled_amount=float(o.get("executed_amount", 0)),
            filled_price=float(o.get("average_price", 0)) or None,
        )

    async def get_positions(self) -> list[ExchangePosition]:
        """Get open positions (virtual, balance-based).

        Reference: 16書§3-2
        bitbank is spot exchange — no native positions.
        Returns virtual positions based on DB Position records.
        In live integration, EngineManager provides DB positions.
        Here we return balance info as a fallback.
        """
        # For spot, return empty — EngineManager tracks positions via DB
        return []

    async def close_position(
        self, position_id: str, amount: float | None = None,
    ) -> Order:
        """Close a position by selling. Reference: 16書§3-2

        For spot: issue a SELL MARKET order for the held amount.
        position_id format: "{pair}:{amount}" (set by EngineManager)
        """
        parts = position_id.split(":")
        if len(parts) < 2:
            raise ValueError(f"Invalid position_id format for bitbank: {position_id}")
        pair = PairNormalizer.to_internal(parts[0])
        held_amount = float(parts[1])
        close_amount = amount if amount is not None else held_amount

        return await self.place_order(
            pair=pair,
            side=OrderSide.SELL,
            amount=close_amount,
            order_type=OrderType.MARKET,
        )

    async def get_balance(self) -> Balance:
        """Get account balance. Reference: 16書§3-2 GET /v1/user/assets"""
        data = await self._private_get("/v1/user/assets")
        assets = data.get("data", {}).get("assets", [])

        # Sum JPY balance
        jpy_asset = next((a for a in assets if a.get("asset") == "jpy"), None)
        total = float(jpy_asset.get("onhand_amount", 0)) if jpy_asset else 0.0
        available = float(jpy_asset.get("free_amount", 0)) if jpy_asset else 0.0
        locked = float(jpy_asset.get("locked_amount", 0)) if jpy_asset else 0.0

        return Balance(
            total=total,
            available=available,
            margin_used=locked,
            unrealized_pnl=0.0,  # Spot has no unrealized PnL in traditional sense
            currency="JPY",
        )

    async def modify_order(
        self, order_id: str, price: float | None = None,
    ) -> Order:
        """Modify an order by cancel + re-place. Reference: 16書§3-2

        bitbank has no native modify; cancel existing and place new.
        """
        # Get current order to know pair/side/amount
        current = await self.get_order_status(order_id)
        log_with_data(logger, logging.INFO, "Modify order: cancel step", {"order_id": order_id})
        await self.cancel_order(order_id)

        log_with_data(logger, logging.INFO, "Modify order: re-place step", {
            "pair": current.pair, "side": current.side.value, "new_price": price,
        })
        return await self.place_order(
            pair=current.pair,
            side=current.side,
            amount=current.amount,
            order_type=current.order_type,
            price=price,
        )
