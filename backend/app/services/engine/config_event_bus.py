"""
ConfigEventBus: asyncio.Queue-based lightweight event bus for config hot-reload.

Reference: 16_実行エンジンとUI接続 Section 7
- API routes publish ConfigChangeEvent on settings update
- TradeExecutionEngine consumes events in its main loop
- Thread-safe via asyncio.Queue per trader
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Maximum events per queue to prevent memory bloat (WARNING #6 from review)
_MAX_QUEUE_SIZE = 10


@dataclass
class ConfigChangeEvent:
    """Configuration change event."""

    trader_id: int
    config_type: str  # "model_stage" | "safeguard" | "trader"
    stage: str | None  # "M1" | "M2" | "M3" | "M4" | None
    new_config: dict
    timestamp: datetime


class ConfigEventBus:
    """asyncio.Queue-based config change event bus.

    Reference: 16_実行エンジンとUI接続 Section 7-1
    """

    def __init__(self) -> None:
        self._queues: dict[int, asyncio.Queue[ConfigChangeEvent]] = {}

    def subscribe(self, trader_id: int) -> asyncio.Queue[ConfigChangeEvent]:
        """Subscribe a trader to config change events."""
        if trader_id not in self._queues:
            self._queues[trader_id] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        return self._queues[trader_id]

    def unsubscribe(self, trader_id: int) -> None:
        """Unsubscribe a trader from config change events."""
        self._queues.pop(trader_id, None)

    async def publish(self, event: ConfigChangeEvent) -> None:
        """Publish a config change event to the target trader's queue.

        If the queue is full, the oldest event is discarded (fire-and-forget).
        """
        queue = self._queues.get(event.trader_id)
        if queue is None:
            logger.debug(
                "ConfigEventBus: no subscriber for trader %d, event dropped",
                event.trader_id,
            )
            return

        if queue.full():
            # Discard oldest to make room
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            logger.warning(
                "ConfigEventBus: queue full for trader %d, oldest event discarded",
                event.trader_id,
            )

        await queue.put(event)
        logger.info(
            "ConfigEventBus: published %s event for trader %d",
            event.config_type,
            event.trader_id,
        )

    async def publish_to_all(self, config_type: str, new_config: dict) -> None:
        """Publish a config change to all subscribed traders."""
        now = datetime.now(timezone.utc)
        for trader_id in list(self._queues.keys()):
            event = ConfigChangeEvent(
                trader_id=trader_id,
                config_type=config_type,
                stage=None,
                new_config=new_config,
                timestamp=now,
            )
            await self.publish(event)
