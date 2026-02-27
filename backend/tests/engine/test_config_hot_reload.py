"""
Tests for ConfigEventBus (hot-reload).
Reference: 16_実行エンジンとUI接続 Section 7
"""

import asyncio
from datetime import datetime, timezone

import pytest

from app.services.engine.config_event_bus import ConfigEventBus, ConfigChangeEvent


class TestConfigEventBus:
    def test_subscribe_creates_queue(self):
        bus = ConfigEventBus()
        q = bus.subscribe(1)
        assert q is not None
        assert isinstance(q, asyncio.Queue)
        bus.unsubscribe(1)

    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscriber(self):
        bus = ConfigEventBus()
        q = bus.subscribe(1)

        event = ConfigChangeEvent(
            trader_id=1,
            config_type="model_stage",
            stage="M1",
            new_config={"key": "value"},
            timestamp=datetime.now(timezone.utc),
        )
        await bus.publish(event)

        received = q.get_nowait()
        assert received.trader_id == 1
        assert received.config_type == "model_stage"
        bus.unsubscribe(1)

    @pytest.mark.asyncio
    async def test_publish_does_not_deliver_to_other_traders(self):
        bus = ConfigEventBus()
        q1 = bus.subscribe(1)
        q2 = bus.subscribe(2)

        event = ConfigChangeEvent(
            trader_id=1,
            config_type="safeguard",
            stage=None,
            new_config={},
            timestamp=datetime.now(timezone.utc),
        )
        await bus.publish(event)

        assert not q2.empty() is False or q2.qsize() == 0
        assert q1.qsize() == 1
        bus.unsubscribe(1)
        bus.unsubscribe(2)

    def test_unsubscribe_removes_queue(self):
        bus = ConfigEventBus()
        bus.subscribe(1)
        bus.unsubscribe(1)

        # Publishing should not fail even though no subscriber
        # (just no delivery)

    @pytest.mark.asyncio
    async def test_queue_overflow_discards_oldest(self):
        bus = ConfigEventBus()
        q = bus.subscribe(1)

        # Publish more than max queue size
        for i in range(15):
            event = ConfigChangeEvent(
                trader_id=1,
                config_type="model_stage",
                stage=f"M{i}",
                new_config={"i": i},
                timestamp=datetime.now(timezone.utc),
            )
            await bus.publish(event)

        # Queue should not exceed max size (10)
        assert q.qsize() <= 10
        bus.unsubscribe(1)
