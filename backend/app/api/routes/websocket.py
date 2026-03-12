"""
WebSocket endpoint for real-time data channels.

Reference: 08_API仕様.md Section 4, 10_フロントエンドアーキテクチャ

Channels (08_API仕様 Section 4-2):
  - prices: Real-time price updates (bid/ask)
  - trader_updates: Trader state changes (position opened/closed, etc.)
  - alerts: Safeguard triggers, pipeline errors
  - pipeline_status: Pipeline execution status per trader
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self._subscriptions: Dict[WebSocket, Dict[str, Any]] = {}
        self._mock_task: asyncio.Task | None = None
        self._live_feed_active: bool = False

    @property
    def live_feed_active(self) -> bool:
        """Check if live data feed is active (vs mock)."""
        return self._live_feed_active

    def set_live_feed(self, active: bool) -> None:
        """Switch between live and mock price feed.

        Reference: 16書§8-1 — MarketDataFeed からの実データ切替
        """
        self._live_feed_active = active
        if active and self._mock_task and not self._mock_task.done():
            self._mock_task.cancel()
            self._mock_task = None
            logger.info("WebSocket: switched to live price feed")

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        self._subscriptions[websocket] = {}
        logger.info(
            "WebSocket connected. Total: %d", len(self.active_connections)
        )
        # Start mock price feed only if no live feed active
        if not self._live_feed_active:
            if self._mock_task is None or self._mock_task.done():
                self._mock_task = asyncio.create_task(self._mock_price_loop())

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        self._subscriptions.pop(websocket, None)
        logger.info(
            "WebSocket disconnected. Total: %d", len(self.active_connections)
        )
        if not self.active_connections and self._mock_task and not self._mock_task.done():
            self._mock_task.cancel()
            self._mock_task = None

    def _handle_subscribe(self, websocket: WebSocket, msg: Dict) -> None:
        """Handle subscribe action from client."""
        channel = msg.get("channel")
        if channel:
            self._subscriptions.setdefault(websocket, {})[channel] = {
                "pairs": msg.get("pairs", []),
                "traderIds": msg.get("traderIds", []),
            }

    def _handle_unsubscribe(self, websocket: WebSocket, msg: Dict) -> None:
        """Handle unsubscribe action from client."""
        channel = msg.get("channel")
        if channel and websocket in self._subscriptions:
            self._subscriptions[websocket].pop(channel, None)

    async def broadcast(self, channel: str, data: Dict) -> None:
        """Broadcast a message to all clients subscribed to the channel."""
        message = json.dumps({"channel": channel, **data})
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            # Check subscription (if subscriptions exist, filter; otherwise broadcast to all)
            subs = self._subscriptions.get(connection, {})
            if subs and channel not in subs:
                continue
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for ws in disconnected:
            self.active_connections.discard(ws)
            self._subscriptions.pop(ws, None)

    async def broadcast_to_trader(
        self, channel: str, trader_id: int, data: Dict
    ) -> None:
        """Broadcast to clients subscribed to a specific trader."""
        message = json.dumps({"channel": channel, "traderId": trader_id, **data})
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            subs = self._subscriptions.get(connection, {})
            ch_sub = subs.get(channel, {})
            trader_ids = ch_sub.get("traderIds", [])
            # Send if subscribed to channel with no filter or matching traderId
            if channel in subs and (not trader_ids or trader_id in trader_ids):
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.append(connection)
        for ws in disconnected:
            self.active_connections.discard(ws)
            self._subscriptions.pop(ws, None)

    async def send_to(
        self, websocket: WebSocket, channel: str, data: Dict
    ) -> None:
        """Send a message to a specific client."""
        message = json.dumps({"channel": channel, **data})
        await websocket.send_text(message)

    # --- Broadcast helpers for services ---

    async def send_trader_update(
        self, trader_id: int, update_type: str, data: Dict
    ) -> None:
        """Send trader_updates channel message (08_API仕様 Section 4-2)."""
        await self.broadcast_to_trader("trader_updates", trader_id, {
            "type": update_type,
            "data": data,
        })

    async def send_alert(
        self, alert_type: str, data: Dict
    ) -> None:
        """Send alerts channel message (08_API仕様 Section 4-2)."""
        await self.broadcast("alerts", {
            "type": alert_type,
            "data": data,
        })

    async def send_pipeline_status(
        self, trader_id: int, execution_id: str, stage: str, result: str
    ) -> None:
        """Send pipeline_status channel message (08_API仕様 Section 4-2)."""
        await self.broadcast_to_trader("pipeline_status", trader_id, {
            "executionId": execution_id,
            "stage": stage,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _mock_price_loop(self) -> None:
        """Broadcast mock prices every second for development/testing.

        Note: These are fallback values when no live engine is running.
        When engines are active, set_live_feed(True) stops this loop.
        """
        prices = {
            "USD_JPY": {"bid": 148.500, "ask": 148.503},
            "EUR_JPY": {"bid": 161.200, "ask": 161.205},
            "GBP_JPY": {"bid": 191.300, "ask": 191.308},
            "EUR_USD": {"bid": 1.08600, "ask": 1.08605},
            "CHF_JPY": {"bid": 168.400, "ask": 168.406},
            "BTC_JPY": {"bid": 12800000, "ask": 12802000},
            "ETH_JPY": {"bid": 310000, "ask": 310200},
            "XRP_JPY": {"bid": 340.0, "ask": 340.2},
        }
        try:
            while self.active_connections:
                ts = datetime.now(timezone.utc).isoformat()
                for pair, p in prices.items():
                    is_crypto = pair in ("BTC_JPY", "ETH_JPY", "XRP_JPY")
                    if is_crypto:
                        delta = random.uniform(-500, 500) if "BTC" in pair else random.uniform(-50, 50)
                        if "XRP" in pair:
                            delta = random.uniform(-0.1, 0.1)
                    else:
                        delta = random.uniform(-0.05, 0.05)
                    p["bid"] = round(
                        p["bid"] + delta,
                        3 if not is_crypto else 0 if "BTC" in pair or "ETH" in pair else 2,
                    )
                    spread = p["ask"] - p["bid"]
                    p["ask"] = round(
                        p["bid"] + abs(spread),
                        3 if not is_crypto else 0 if "BTC" in pair or "ETH" in pair else 2,
                    )

                    await self.broadcast("prices", {
                        "pair": pair,
                        "bid": p["bid"],
                        "ask": p["ask"],
                        "timestamp": ts,
                    })
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Mock price loop error")


manager = ConnectionManager()


@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action")
                if action == "subscribe":
                    manager._handle_subscribe(websocket, msg)
                elif action == "unsubscribe":
                    manager._handle_unsubscribe(websocket, msg)
                elif msg.get("type") == "ping":
                    await manager.send_to(
                        websocket, "system", {"type": "pong"}
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


def get_ws_manager() -> ConnectionManager:
    """Get the global ConnectionManager instance for broadcasting from services."""
    return manager
