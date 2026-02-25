"""
WebSocket endpoint for real-time data channels.

Reference: 08_API仕様.md Section WebSocket, 10_フロントエンドアーキテクチャ

Channels:
  - prices: Real-time price updates (bid/ask)
  - trader_updates: Trader state changes (position opened/closed, etc.)
  - alerts: Safeguard triggers, pipeline errors
  - pipeline_status: Pipeline execution status per trader
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(
            "WebSocket connected. Total: %d", len(self.active_connections)
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info(
            "WebSocket disconnected. Total: %d", len(self.active_connections)
        )

    async def broadcast(self, channel: str, data: Dict) -> None:
        """Broadcast a message to all connected clients."""
        message = json.dumps({"channel": channel, **data})
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for ws in disconnected:
            self.active_connections.discard(ws)

    async def send_to(
        self, websocket: WebSocket, channel: str, data: Dict
    ) -> None:
        """Send a message to a specific client."""
        message = json.dumps({"channel": channel, **data})
        await websocket.send_text(message)


manager = ConnectionManager()


@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; handle incoming messages (subscriptions, pings)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
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
