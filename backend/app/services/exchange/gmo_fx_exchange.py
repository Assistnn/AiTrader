"""
GMO Coin FX exchange implementation.

Reference: 06_取引所抽象化 Section 5, 16_実行エンジンとUI接続 Section 3-1
Public API: https://forex-api.coin.z.com/public
Private API: https://forex-api.coin.z.com/private
Authentication: API Key + HMAC-SHA256
Rate limit: Private API 1 req/sec (managed by OrderRateLimiter)
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
from app.services.exchange.rate_limiter import OrderRateLimiter

logger = logging.getLogger(__name__)

# GMO Coin timeframe mapping: internal → GMO interval
_TIMEFRAME_MAP: dict[str, str] = {
    "M1": "1min",
    "M5": "5min",
    "M10": "10min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1hour",
    "H4": "4hour",
    "H8": "8hour",
    "D1": "1day",
}

# GMO order status mapping
_ORDER_STATUS_MAP: dict[str, OrderStatus] = {
    "WAITING": OrderStatus.PENDING,
    "ORDERED": OrderStatus.PENDING,
    "MODIFYING": OrderStatus.PENDING,
    "CANCELLING": OrderStatus.PENDING,
    "CANCELED": OrderStatus.CANCELLED,
    "EXECUTED": OrderStatus.FILLED,
    "EXPIRED": OrderStatus.EXPIRED,
}


class GmoApiError(Exception):
    """GMO Coin API error."""

    def __init__(self, status_code: int, reason: str, response_data: dict | None = None):
        self.status_code = status_code
        self.reason = reason
        self.response_data = response_data
        super().__init__(f"GMO API error {status_code}: {reason}")


class GmoFxExchange(BaseExchange):
    """
    GMO Coin FX exchange.

    Reference: 06_取引所抽象化 Section 5, 16_実行エンジンとUI接続 Section 3-1
    Authentication: API Key + HMAC-SHA256
    """

    PUBLIC_URL = "https://forex-api.coin.z.com/public"
    PRIVATE_URL = "https://forex-api.coin.z.com/private"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._rate_limiter = OrderRateLimiter(
            min_interval_sec=1.0, max_per_minute=10,
        )
        self._client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    # --- Authentication ---

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

    # --- HTTP helpers ---

    async def _public_get(self, path: str, params: dict | None = None) -> dict:
        """Execute public GET request."""
        logger.debug("GMO public GET %s", path)
        start = time.monotonic()
        resp = await self._client.get(f"{self.PUBLIC_URL}{path}", params=params)
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
        if data.get("status") != 0:
            msg = data.get("messages", [{"message_string": "Unknown error"}])[0].get(
                "message_string", "Unknown error"
            )
            log_with_data(logger, logging.ERROR, "GMO API error", {
                "path": path, "status_code": resp.status_code, "error_message": msg,
            })
            raise GmoApiError(resp.status_code, msg, data)
        logger.debug("GMO public GET %s completed (%.0fms)", path, elapsed)
        return data

    async def _private_get(self, path: str, params: dict | None = None) -> dict:
        """Execute authenticated GET request."""
        logger.debug("GMO private GET %s", path)
        start = time.monotonic()
        headers = self._headers("GET", path)
        resp = await self._client.get(
            f"{self.PRIVATE_URL}{path}", headers=headers, params=params,
        )
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
        if data.get("status") != 0:
            msg = data.get("messages", [{"message_string": "Unknown error"}])[0].get(
                "message_string", "Unknown error"
            )
            log_with_data(logger, logging.ERROR, "GMO API error", {
                "path": path, "status_code": resp.status_code, "error_message": msg,
            })
            raise GmoApiError(resp.status_code, msg, data)
        logger.debug("GMO private GET %s completed (%.0fms)", path, elapsed)
        return data

    async def _private_post(self, path: str, body: dict) -> dict:
        """Execute authenticated POST request."""
        logger.debug("GMO private POST %s", path)
        start = time.monotonic()
        body_str = json.dumps(body)
        headers = self._headers("POST", path, body_str)
        headers["Content-Type"] = "application/json"
        resp = await self._client.post(
            f"{self.PRIVATE_URL}{path}", headers=headers, content=body_str,
        )
        elapsed = (time.monotonic() - start) * 1000
        data = resp.json()
        if data.get("status") != 0:
            msg = data.get("messages", [{"message_string": "Unknown error"}])[0].get(
                "message_string", "Unknown error"
            )
            log_with_data(logger, logging.ERROR, "GMO API error", {
                "path": path, "status_code": resp.status_code, "error_message": msg,
            })
            raise GmoApiError(resp.status_code, msg, data)
        logger.debug("GMO private POST %s completed (%.0fms)", path, elapsed)
        return data

    # --- BaseExchange interface ---

    async def get_ticker(self, pair: str) -> Ticker:
        """Get latest ticker. Reference: 16書§3-1 GET /v1/ticker"""
        data = await self._public_get("/v1/ticker", params={"symbol": pair})
        items = data.get("data", [])
        # GMO returns list; find matching symbol
        item = next((i for i in items if i.get("symbol") == pair), items[0] if items else None)
        if item is None:
            raise GmoApiError(404, f"Ticker not found for {pair}")
        bid = float(item["bid"])
        ask = float(item["ask"])
        return Ticker(
            timestamp=datetime.now(timezone.utc),
            bid=bid,
            ask=ask,
            last=float(item.get("last", (bid + ask) / 2)),
            volume=float(item.get("volume", 0)),
        )

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        """Get OHLCV bar data. Reference: 16書§3-1 GET /v1/klines"""
        interval = _TIMEFRAME_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"Unsupported timeframe for GMO: {timeframe}")

        # GMO FX klines requires date (YYYYMMDD) and priceType (BID/ASK)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        data = await self._public_get(
            "/v1/klines",
            params={"symbol": pair, "priceType": "BID", "interval": interval, "date": date_str},
        )
        bars_raw = data.get("data", [])

        bars: list[OHLCV] = []
        for b in bars_raw:
            bars.append(OHLCV(
                timestamp=datetime.fromtimestamp(
                    int(b["openTime"]) / 1000, tz=timezone.utc,
                ),
                open=float(b["open"]),
                high=float(b["high"]),
                low=float(b["low"]),
                close=float(b["close"]),
                volume=float(b.get("volume", 0)),
            ))

        # Return last `limit` bars, sorted by time ascending
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
        """Place an order. Reference: 16書§3-1 POST /v1/order

        Note: tp_price/sl_price are ignored at this layer.
        ExecutionEngine handles OCO orders separately (16書§3-1 TP/SL実装方式).
        """
        await self._rate_limiter.wait_if_needed()

        body: dict = {
            "symbol": pair,
            "side": side.value,
            "size": str(amount),
            "executionType": order_type.value,
            "settleType": "OPEN",
        }
        if price is not None and order_type != OrderType.MARKET:
            body["price"] = str(price)
        if client_order_id:
            body["clientOrderId"] = client_order_id

        data = await self._private_post("/v1/order", body)
        self._rate_limiter.record_order()

        # GMO returns data with order ID
        order_data = data.get("data", "")
        order_id = str(order_data) if isinstance(order_data, (str, int)) else ""

        log_with_data(logger, logging.INFO, "Order placed", {
            "pair": pair, "side": side.value, "amount": amount,
            "order_type": order_type.value, "client_order_id": client_order_id,
            "order_id": order_id,
        })
        return Order(
            order_id=order_id,
            client_order_id=client_order_id or "",
            pair=pair,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            status=OrderStatus.PENDING,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order. Reference: 16書§3-1 POST /v1/cancelOrders"""
        await self._rate_limiter.wait_if_needed()
        await self._private_post("/v1/cancelOrders", {"orderIds": [int(order_id)]})
        self._rate_limiter.record_order()
        log_with_data(logger, logging.INFO, "Order cancelled", {"order_id": order_id})
        return True

    async def get_order_status(self, order_id: str) -> Order:
        """Get order status. Reference: 16書§3-1 GET /v1/orders"""
        data = await self._private_get("/v1/orders", params={"orderId": order_id})
        orders = data.get("data", {}).get("list", [])
        if not orders:
            raise GmoApiError(404, f"Order not found: {order_id}")

        o = orders[0]
        status = _ORDER_STATUS_MAP.get(o.get("status", ""), OrderStatus.PENDING)
        filled_amount = float(o.get("executedSize", 0))
        filled_price = float(o.get("price", 0)) if filled_amount > 0 else None

        return Order(
            order_id=str(o["orderId"]),
            client_order_id=o.get("clientOrderId", ""),
            pair=o.get("symbol", ""),
            side=OrderSide(o["side"]),
            order_type=OrderType(o.get("executionType", "MARKET")),
            amount=float(o.get("size", 0)),
            price=float(o.get("price", 0)) if o.get("price") else None,
            status=status,
            filled_amount=filled_amount,
            filled_price=filled_price,
        )

    async def get_positions(self) -> list[ExchangePosition]:
        """Get open positions. Reference: 16書§3-1 GET /v1/openPositions"""
        data = await self._private_get("/v1/openPositions", params={"symbol": ""})
        positions_raw = data.get("data", {}).get("list", [])

        positions: list[ExchangePosition] = []
        for p in positions_raw:
            positions.append(ExchangePosition(
                position_id=str(p["positionId"]),
                pair=p.get("symbol", ""),
                side=OrderSide(p["side"]),
                amount=float(p.get("size", 0)),
                entry_price=float(p.get("price", 0)),
                unrealized_pnl=float(p.get("lossGain", 0)),
                created_at=datetime.fromisoformat(p["timestamp"])
                if p.get("timestamp")
                else datetime.now(timezone.utc),
            ))
        logger.debug("GMO get_positions: %d positions", len(positions))
        return positions

    async def close_position(
        self, position_id: str, amount: float | None = None,
    ) -> Order:
        """Close a position. Reference: 16書§3-1 POST /v1/closeOrder"""
        await self._rate_limiter.wait_if_needed()

        # First get position info to determine side and size
        positions = await self.get_positions()
        pos = next((p for p in positions if p.position_id == position_id), None)
        if pos is None:
            raise GmoApiError(404, f"Position not found: {position_id}")

        close_side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY
        close_amount = amount if amount is not None else pos.amount

        body = {
            "symbol": pos.pair,
            "side": close_side.value,
            "size": str(close_amount),
            "executionType": "MARKET",
            "closePositionId": int(position_id),
        }

        data = await self._private_post("/v1/closeOrder", body)
        self._rate_limiter.record_order()

        order_data = data.get("data", "")
        order_id = str(order_data) if isinstance(order_data, (str, int)) else ""

        log_with_data(logger, logging.INFO, "Position close requested", {
            "position_id": position_id, "amount": close_amount,
        })
        return Order(
            order_id=order_id,
            client_order_id="",
            pair=pos.pair,
            side=close_side,
            order_type=OrderType.MARKET,
            amount=close_amount,
            price=None,
            status=OrderStatus.PENDING,
        )

    async def get_balance(self) -> Balance:
        """Get account balance. Reference: 16書§3-1 GET /v1/account/assets"""
        data = await self._private_get("/v1/account/assets")
        assets = data.get("data", {})
        # FX API returns data as a dict (not a list)
        if isinstance(assets, list):
            assets = assets[0] if assets else {}
        return Balance(
            total=float(assets.get("equity", 0)),
            available=float(assets.get("availableAmount", 0)),
            margin_used=float(assets.get("margin", 0)),
            unrealized_pnl=float(assets.get("positionLossGain", 0)),
            currency="JPY",
        )

    async def modify_order(
        self, order_id: str, price: float | None = None,
    ) -> Order:
        """Modify an order. Reference: 16書§3-1 POST /v1/changeOrder"""
        await self._rate_limiter.wait_if_needed()

        body: dict = {"orderId": int(order_id)}
        if price is not None:
            body["price"] = str(price)

        await self._private_post("/v1/changeOrder", body)
        self._rate_limiter.record_order()

        # Return updated order status
        return await self.get_order_status(order_id)
