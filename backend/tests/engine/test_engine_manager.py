"""
Tests for EngineManager.
Reference: 16_実行エンジンとUI接続 Section 2-2
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest

from app.services.engine.engine_manager import EngineManager
from app.services.engine.trade_execution_engine import EngineStatus


class TestEngineManager:
    def test_init(self):
        mgr = EngineManager()
        assert len(mgr._engines) == 0
        assert len(mgr._tasks) == 0

    @pytest.mark.asyncio
    async def test_startup_no_traders(self):
        mgr = EngineManager()
        await mgr.startup(None)
        assert len(mgr._engines) == 0

    @pytest.mark.asyncio
    async def test_shutdown_empty(self):
        mgr = EngineManager()
        await mgr.shutdown()
        # Should not raise

    def test_get_engine_status_not_found(self):
        mgr = EngineManager()
        status = mgr.get_engine_status(999)
        assert status is None

    def test_get_all_statuses_empty(self):
        mgr = EngineManager()
        statuses = mgr.get_all_statuses()
        assert statuses == {}

    @pytest.mark.asyncio
    async def test_stop_trader_not_running(self):
        mgr = EngineManager()
        await mgr.stop_trader(999)
        # Should not raise

    @pytest.mark.asyncio
    async def test_reload_config(self):
        mgr = EngineManager()
        q = mgr.config_bus.subscribe(1)

        await mgr.reload_config(
            trader_id=1,
            config_type="model_stage",
            new_config={"key": "value"},
            stage="M1",
        )

        event = q.get_nowait()
        assert event.trader_id == 1
        assert event.config_type == "model_stage"
        mgr.config_bus.unsubscribe(1)

    @pytest.mark.asyncio
    async def test_stop_all_empty(self):
        mgr = EngineManager()
        await mgr.stop_all()
        assert len(mgr._engines) == 0
