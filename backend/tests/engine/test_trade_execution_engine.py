"""
Tests for TradeExecutionEngine.
Reference: 16_実行エンジンとUI接続 Section 2-3, 5
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.engine.trade_execution_engine import (
    TradeExecutionEngine,
    EngineStatus,
    PipelineCacheEntry,
)
from app.services.engine.bar_scheduler import BarClosedEvent
from app.services.engine.config_event_bus import ConfigEventBus
from app.services.pipeline.data_types import OHLCV
from app.services.decision.decision_types import JudgeOutput


def _make_ohlcv():
    return OHLCV(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        open=150.0, high=151.0, low=149.0, close=150.5, volume=1000.0,
    )


def _make_judge_output(**kwargs):
    """Create JudgeOutput with correct signature (no stage/decision fields)."""
    defaults = {
        "result": {},
        "confidence": 0.8,
        "reason_codes": [],
    }
    defaults.update(kwargs)
    return JudgeOutput(**defaults)


def _make_engine():
    exchange = AsyncMock()
    exchange.get_positions = AsyncMock(return_value=[])

    data_provider = AsyncMock()
    data_provider.get_ohlcv = AsyncMock(return_value=[])

    orchestrator = AsyncMock()
    orchestrator.execute_pipeline = AsyncMock()
    orchestrator.execute_exit_management = AsyncMock()

    execution_engine = AsyncMock()
    bar_scheduler = AsyncMock()
    bar_scheduler.start = AsyncMock()
    bar_scheduler.stop = AsyncMock()

    market_data_feed = AsyncMock()
    market_data_feed.connect = AsyncMock()
    market_data_feed.disconnect = AsyncMock()

    config_bus = ConfigEventBus()

    engine = TradeExecutionEngine(
        trader_id=1,
        pair="USD_JPY",
        exchange=exchange,
        data_provider=data_provider,
        orchestrator=orchestrator,
        execution_engine=execution_engine,
        bar_scheduler=bar_scheduler,
        market_data_feed=market_data_feed,
        config_bus=config_bus,
    )
    return engine


class TestEngineStatus:
    def test_default_status(self):
        status = EngineStatus(trader_id=1)
        assert status.state == "stopped"
        assert status.restart_count == 0


class TestPipelineCacheEntry:
    def test_creation(self):
        output = _make_judge_output(
            result={"tradeAllowed": True},
            reason_codes=["TREND_UP"],
        )
        now = datetime.now(timezone.utc)
        cache = PipelineCacheEntry(
            output=output, timestamp=now,
            valid_until=now, bar_timestamp=now,
        )
        assert cache.output.result["tradeAllowed"] is True


class TestTradeExecutionEngine:
    def test_init(self):
        engine = _make_engine()
        assert engine.trader_id == 1
        assert engine.pair == "USD_JPY"
        assert engine.status.state == "stopped"

    @pytest.mark.asyncio
    async def test_warmup(self):
        engine = _make_engine()
        await engine.warmup()
        assert engine.status.state == "starting"

    @pytest.mark.asyncio
    async def test_cleanup(self):
        engine = _make_engine()
        engine._running = True
        await engine.cleanup()
        assert engine._running is False

    def test_is_m1_pass_no_cache(self):
        engine = _make_engine()
        assert engine._is_m1_pass() is False

    def test_is_m1_pass_with_cache(self):
        engine = _make_engine()
        now = datetime.now(timezone.utc)
        engine._m1_cache = PipelineCacheEntry(
            output=_make_judge_output(result={"tradeAllowed": True}),
            timestamp=now, valid_until=now, bar_timestamp=now,
        )
        assert engine._is_m1_pass() is True

    def test_is_m2_pass_no_cache(self):
        engine = _make_engine()
        assert engine._is_m2_pass() is False

    def test_is_m2_pass_with_cache(self):
        engine = _make_engine()
        now = datetime.now(timezone.utc)
        engine._m2_cache = PipelineCacheEntry(
            output=_make_judge_output(result={"setupValid": True}),
            timestamp=now, valid_until=now, bar_timestamp=now,
        )
        assert engine._is_m2_pass() is True

    @pytest.mark.asyncio
    async def test_handle_bar_event_h1_runs_m1(self):
        engine = _make_engine()
        pipeline_result = MagicMock()
        pipeline_result.m1_output = _make_judge_output(
            result={"tradeAllowed": True},
        )
        engine.orchestrator.execute_pipeline.return_value = pipeline_result

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="H1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(),
        )
        await engine._handle_bar_event(event)
        engine.orchestrator.execute_pipeline.assert_called_once()
        assert engine._m1_cache is not None

    @pytest.mark.asyncio
    async def test_handle_bar_event_m15_skips_without_m1(self):
        engine = _make_engine()
        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M15",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(),
        )
        await engine._handle_bar_event(event)
        engine.orchestrator.execute_pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_bar_event_m1_runs_m4_with_positions(self):
        engine = _make_engine()
        engine.exchange.get_positions.return_value = [MagicMock()]

        exit_result = MagicMock()
        exit_result.action = "HOLD"
        exit_result.m4_output = None
        engine.orchestrator.execute_exit_management.return_value = exit_result

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(),
        )
        await engine._handle_bar_event(event)
        engine.orchestrator.execute_exit_management.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_config_events_empty(self):
        engine = _make_engine()
        engine._config_queue = asyncio.Queue()
        await engine._process_config_events()
        # Should not raise
