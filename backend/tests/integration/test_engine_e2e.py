"""
E2E integration test for the execution engine pipeline.

Reference: 16_実行エンジンとUI接続 Section 2, 5, 6, 13

Tests the full flow:
  Trader create → start → bar data injection → pipeline execution → order → stop
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.engine.engine_manager import EngineManager
from app.services.engine.trade_execution_engine import (
    TradeExecutionEngine,
    EngineStatus,
    PipelineCacheEntry,
)
from app.services.engine.config_event_bus import ConfigEventBus, ConfigChangeEvent
from app.services.engine.bar_scheduler import BarClosedEvent
from app.services.pipeline.data_types import OHLCV, StateSnapshot
from app.services.pipeline.indicator_engine import IndicatorEngine
from app.services.pipeline.state_builder import StateBuilder
from app.services.decision.decision_types import JudgeOutput, PipelineResult
from app.services.safeguard.guard_types import GuardState, ProposedOrder


def _make_ohlcv(close: float = 150.5, ts: datetime | None = None):
    return OHLCV(
        timestamp=ts or datetime(2026, 1, 1, tzinfo=timezone.utc),
        open=close - 0.5, high=close + 0.5, low=close - 1.0, close=close, volume=1000.0,
    )


def _make_ohlcv_series(n: int = 200, base_price: float = 140.0) -> list[OHLCV]:
    """Generate n OHLCV bars with uptrend pattern for indicator warmup."""
    bars = []
    for i in range(n):
        price = base_price + i * 0.05  # gentle uptrend
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        bars.append(OHLCV(
            timestamp=ts,
            open=price - 0.2,
            high=price + 0.3,
            low=price - 0.4,
            close=price,
            volume=1000.0 + i * 10,
        ))
    return bars


def _make_engine_with_indicators():
    """Create engine with real IndicatorEngine and StateBuilder."""
    exchange = AsyncMock()
    exchange.get_positions = AsyncMock(return_value=[])

    data_provider = AsyncMock()
    data_provider.get_ohlcv = AsyncMock(return_value=_make_ohlcv_series(200))

    orchestrator = AsyncMock()
    execution_engine = AsyncMock()

    indicator_engine = IndicatorEngine()
    state_builder = StateBuilder()

    engine = TradeExecutionEngine(
        trader_id=1,
        pair="USD_JPY",
        exchange=exchange,
        data_provider=data_provider,
        orchestrator=orchestrator,
        execution_engine=execution_engine,
        bar_scheduler=AsyncMock(),
        market_data_feed=AsyncMock(),
        config_bus=ConfigEventBus(),
        indicator_engine=indicator_engine,
        state_builder=state_builder,
    )
    return engine


class TestEngineManagerLifecycle:
    """Tests EngineManager startup/shutdown lifecycle."""

    @pytest.mark.asyncio
    async def test_startup_shutdown_empty(self):
        mgr = EngineManager()
        await mgr.startup(None)
        assert len(mgr._engines) == 0
        await mgr.shutdown()
        assert len(mgr._engines) == 0

    @pytest.mark.asyncio
    async def test_config_bus_integration(self):
        """Test config change propagation through ConfigEventBus."""
        mgr = EngineManager()
        q = mgr.config_bus.subscribe(1)

        await mgr.reload_config(
            trader_id=1,
            config_type="model_stage",
            new_config={"timeframe": "H1"},
            stage="M1",
        )

        event = q.get_nowait()
        assert event.trader_id == 1
        assert event.config_type == "model_stage"
        assert event.stage == "M1"
        assert event.new_config == {"timeframe": "H1"}

        mgr.config_bus.unsubscribe(1)


class TestPipelineDispatch:
    """Tests TradeExecutionEngine bar event dispatching."""

    @pytest.mark.asyncio
    async def test_h1_triggers_m1(self):
        """H1 bar close should trigger M1 direction judgment."""
        from app.services.engine.trade_execution_engine import TradeExecutionEngine
        from app.services.decision.decision_types import JudgeOutput

        exchange = AsyncMock()
        exchange.get_positions = AsyncMock(return_value=[])
        data_provider = AsyncMock()
        data_provider.get_ohlcv = AsyncMock(return_value=[])

        orchestrator = AsyncMock()
        pipeline_result = MagicMock()
        pipeline_result.m1_output = JudgeOutput(
            result={"tradeAllowed": True},
            confidence=0.85,
            reason_codes=["TREND_BULLISH"],
        )
        orchestrator.execute_pipeline = AsyncMock(return_value=pipeline_result)

        engine = TradeExecutionEngine(
            trader_id=1,
            pair="USD_JPY",
            exchange=exchange,
            data_provider=data_provider,
            orchestrator=orchestrator,
            execution_engine=AsyncMock(),
            bar_scheduler=AsyncMock(),
            market_data_feed=AsyncMock(),
            config_bus=ConfigEventBus(),
        )

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="H1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(),
        )
        await engine._handle_bar_event(event)

        orchestrator.execute_pipeline.assert_called_once()
        assert engine._m1_cache is not None
        assert engine._is_m1_pass() is True

    @pytest.mark.asyncio
    async def test_m15_skips_without_m1_pass(self):
        """M15 bar close should skip M2 if M1 hasn't passed."""
        from app.services.engine.trade_execution_engine import TradeExecutionEngine

        engine = TradeExecutionEngine(
            trader_id=1,
            pair="USD_JPY",
            exchange=AsyncMock(),
            data_provider=AsyncMock(),
            orchestrator=AsyncMock(),
            execution_engine=AsyncMock(),
            bar_scheduler=AsyncMock(),
            market_data_feed=AsyncMock(),
            config_bus=ConfigEventBus(),
        )

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M15",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(),
        )
        await engine._handle_bar_event(event)
        engine.orchestrator.execute_pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_m5_skips_without_m1_and_m2(self):
        """M5 bar close should skip full pipeline without M1+M2 pass."""
        from app.services.engine.trade_execution_engine import TradeExecutionEngine

        engine = TradeExecutionEngine(
            trader_id=1,
            pair="USD_JPY",
            exchange=AsyncMock(),
            data_provider=AsyncMock(),
            orchestrator=AsyncMock(),
            execution_engine=AsyncMock(),
            bar_scheduler=AsyncMock(),
            market_data_feed=AsyncMock(),
            config_bus=ConfigEventBus(),
        )

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M5",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(),
        )
        await engine._handle_bar_event(event)
        engine.orchestrator.execute_pipeline.assert_not_called()


class TestConfigHotReloadE2E:
    """Tests end-to-end config hot-reload flow."""

    @pytest.mark.asyncio
    async def test_config_event_consumed_by_engine(self):
        """Config events should be consumed in engine's main loop."""
        from app.services.engine.trade_execution_engine import TradeExecutionEngine

        config_bus = ConfigEventBus()

        engine = TradeExecutionEngine(
            trader_id=1,
            pair="USD_JPY",
            exchange=AsyncMock(),
            data_provider=AsyncMock(),
            orchestrator=AsyncMock(),
            execution_engine=AsyncMock(),
            bar_scheduler=AsyncMock(),
            market_data_feed=AsyncMock(),
            config_bus=config_bus,
        )

        # Simulate subscribing (normally done in run())
        engine._config_queue = config_bus.subscribe(1)

        # Publish config change
        event = ConfigChangeEvent(
            trader_id=1,
            config_type="safeguard",
            stage=None,
            new_config={"max_daily_loss_pct": 5.0},
            timestamp=datetime.now(timezone.utc),
        )
        await config_bus.publish(event)

        # Process events
        await engine._process_config_events()

        # Queue should be empty after processing
        assert engine._config_queue.empty()

        config_bus.unsubscribe(1)


class TestResilience:
    """Tests retry and circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_retry_with_backoff_integration(self):
        from app.services.engine.resilience import RetryWithBackoff

        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("temporary")
            return "success"

        retry = RetryWithBackoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        result = await retry.execute(flaky)
        assert result == "success"
        assert call_count == 2

    def test_circuit_breaker_state_transitions(self):
        from app.services.engine.resilience import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=300.0)

        # Closed → still closed after 1 failure
        cb.record_failure()
        assert cb.state == "closed"

        # Closed → open after threshold
        cb.record_failure()
        assert cb.state == "open"

        # Reset
        cb.record_success()
        assert cb.state == "closed"


class TestFullPipelineE2E:
    """Full pipeline E2E: warmup → M1 → M2 → M3 → Entry → M4.

    Tests the complete flow up to (but not executing) actual trades.
    Uses real IndicatorEngine and StateBuilder with mock orchestrator.
    """

    @pytest.mark.asyncio
    async def test_warmup_populates_indicators(self):
        """After warmup, IndicatorEngine should have snapshots for each timeframe."""
        engine = _make_engine_with_indicators()

        # warmup fetches bars and feeds them to indicator engine
        await engine.warmup()

        # Check that indicator engine has snapshots
        snapshots = engine._indicator_engine.get_all_snapshots("USD_JPY")
        # data_provider.get_ohlcv returns same series for all timeframes
        assert len(snapshots) > 0
        assert engine._status.state == "starting"

    @pytest.mark.asyncio
    async def test_state_built_from_bar_event(self):
        """BarClosedEvent should update indicators and build a StateSnapshot."""
        engine = _make_engine_with_indicators()

        # Warmup to seed indicators
        await engine.warmup()

        # Feed a bar event (H1)
        event = BarClosedEvent(
            pair="USD_JPY", timeframe="H1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(close=152.0),
        )

        # Build state directly
        state = engine._build_state(event)
        assert isinstance(state, StateSnapshot)
        assert state.pair == "USD_JPY"
        assert state.trade_allowed is True or state.trade_allowed is False
        assert state.trend in ("UP", "DOWN", "NEUTRAL")

    @pytest.mark.asyncio
    async def test_h1_passes_state_to_orchestrator(self):
        """H1 bar event should pass a real StateSnapshot (not None) to orchestrator."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        # Set up mock orchestrator return
        pipeline_result = MagicMock(spec=PipelineResult)
        pipeline_result.m1_output = JudgeOutput(
            result={"tradeAllowed": True},
            confidence=0.85,
            reason_codes=["TREND_BULLISH"],
        )
        pipeline_result.action = "NO_TRADE"
        pipeline_result.order = None
        engine.orchestrator.execute_pipeline = AsyncMock(return_value=pipeline_result)

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="H1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(close=152.0),
        )
        await engine._handle_bar_event(event)

        # Verify orchestrator was called with a StateSnapshot, not None
        call_args = engine.orchestrator.execute_pipeline.call_args
        state_arg = call_args.kwargs.get("state") or call_args[1].get("state")
        assert state_arg is not None
        assert isinstance(state_arg, StateSnapshot)

    @pytest.mark.asyncio
    async def test_full_pipeline_h1_m15_m5_sequence(self):
        """Full H1→M15→M5 sequence triggers M1→M2→M3 in order."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        # M1 pass
        m1_result = MagicMock(spec=PipelineResult)
        m1_result.m1_output = JudgeOutput(
            result={"tradeAllowed": True}, confidence=0.9, reason_codes=["TREND_UP"],
        )
        m1_result.action = "NO_TRADE"
        m1_result.order = None

        # M2 pass
        m2_result = MagicMock(spec=PipelineResult)
        m2_result.m2_output = JudgeOutput(
            result={"setupValid": True}, confidence=0.8, reason_codes=["SETUP_OK"],
        )
        m2_result.action = "NO_TRADE"
        m2_result.order = None

        # M3 entry signal
        guard_state = GuardState(
            entry_allowed=True, force_close=False, trader_halted=False,
            cooldown_until=None, lot_multiplier=1.0,
            evaluations=[], blocking_guards=[],
        )
        m3_result = MagicMock(spec=PipelineResult)
        m3_result.action = "ENTRY"
        m3_result.order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0,
            order_type="market", sl_pips=20.0, tp_pips=40.0,
            sl_price=149.80, tp_price=150.40, risk_per_trade_pct=1.0,
        )
        m3_result.guard_state = guard_state
        m3_result.m1_output = m1_result.m1_output
        m3_result.m2_output = m2_result.m2_output
        m3_result.m3_output = JudgeOutput(
            result={"entry": True, "lotSize": 1.0}, confidence=0.75, reason_codes=["ENTRY_OK"],
        )

        # Set up sequence of returns
        engine.orchestrator.execute_pipeline = AsyncMock(
            side_effect=[m1_result, m2_result, m3_result],
        )
        engine.execution_engine.execute_entry = AsyncMock(
            return_value=MagicMock(success=True),
        )

        now = datetime.now(timezone.utc)

        # H1 → triggers M1
        await engine._handle_bar_event(BarClosedEvent(
            pair="USD_JPY", timeframe="H1", timestamp=now, ohlcv=_make_ohlcv(152.0),
        ))
        assert engine._is_m1_pass() is True

        # M15 → triggers M2 (since M1 passed)
        await engine._handle_bar_event(BarClosedEvent(
            pair="USD_JPY", timeframe="M15", timestamp=now, ohlcv=_make_ohlcv(152.1),
        ))
        assert engine._is_m2_pass() is True

        # M5 → triggers full pipeline (since M1+M2 passed)
        await engine._handle_bar_event(BarClosedEvent(
            pair="USD_JPY", timeframe="M5", timestamp=now, ohlcv=_make_ohlcv(152.2),
        ))

        # Verify entry was triggered (but not actually executed in live)
        engine.execution_engine.execute_entry.assert_called_once()
        call_args = engine.execution_engine.execute_entry.call_args
        proposed = call_args.kwargs.get("proposed_order") or call_args[1].get("proposed_order")
        assert proposed.pair == "USD_JPY"
        assert proposed.side == "BUY"
        assert proposed.sl_pips == 20.0
        assert proposed.tp_pips == 40.0

    @pytest.mark.asyncio
    async def test_m4_exit_judge_output_handling(self):
        """M4 should correctly handle JudgeOutput with action=EXIT."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        # Simulate having positions
        mock_pos = MagicMock()
        mock_pos.position_id = "pos-1"
        mock_pos.amount = 1.0
        engine.exchange.get_positions = AsyncMock(return_value=[mock_pos])

        # M4 returns JudgeOutput (not PipelineResult)
        m4_output = JudgeOutput(
            result={"action": "EXIT", "reason": "TP_REACHED"},
            confidence=0.95,
            reason_codes=["TP_REACHED"],
        )
        engine.orchestrator.execute_exit_management = AsyncMock(return_value=m4_output)
        engine.execution_engine.execute_exit = AsyncMock(
            return_value=MagicMock(success=True),
        )

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(152.0),
        )
        await engine._handle_bar_event(event)

        # execute_exit should have been called for the position
        engine.execution_engine.execute_exit.assert_called_once()
        call_args = engine.execution_engine.execute_exit.call_args
        assert call_args.kwargs.get("m4_output") is m4_output or call_args[1].get("m4_output") is m4_output

    @pytest.mark.asyncio
    async def test_m4_hold_action_no_exit(self):
        """M4 with action=HOLD should not trigger any exit."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        mock_pos = MagicMock()
        mock_pos.position_id = "pos-1"
        engine.exchange.get_positions = AsyncMock(return_value=[mock_pos])

        m4_output = JudgeOutput(
            result={"action": "HOLD"},
            confidence=0.6,
            reason_codes=["TREND_CONTINUES"],
        )
        engine.orchestrator.execute_exit_management = AsyncMock(return_value=m4_output)

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(152.0),
        )
        await engine._handle_bar_event(event)

        engine.execution_engine.execute_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_m4_adjust_trail_calls_adjust_stop_loss(self):
        """M4 with action=ADJUST_TRAIL should call adjust_stop_loss."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        mock_pos = MagicMock()
        mock_pos.position_id = "pos-1"
        engine.exchange.get_positions = AsyncMock(return_value=[mock_pos])

        m4_output = JudgeOutput(
            result={"action": "ADJUST_TRAIL", "newSlPrice": 150.50},
            confidence=0.7,
            reason_codes=["TRAIL_ADJUST"],
        )
        engine.orchestrator.execute_exit_management = AsyncMock(return_value=m4_output)
        engine.execution_engine.adjust_stop_loss = AsyncMock(return_value=True)

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(152.0),
        )
        await engine._handle_bar_event(event)

        engine.execution_engine.adjust_stop_loss.assert_called_once_with(mock_pos, 150.50)

    @pytest.mark.asyncio
    async def test_simulation_mode_uses_mock_exchange(self):
        """TRADING_MODE=simulation should create MockExchange via ExchangeFactory."""
        from app.services.exchange.exchange_factory import ExchangeFactory
        from app.services.exchange.mock_exchange import MockExchange

        exchange = ExchangeFactory.create_exchange(
            mode="simulation",
            trade_type="FX",
            api_key="",
            api_secret="",
        )
        assert isinstance(exchange, MockExchange)

        exchange_crypto = ExchangeFactory.create_exchange(
            mode="simulation",
            trade_type="Crypto",
        )
        assert isinstance(exchange_crypto, MockExchange)


class TestActionEnumUnification:
    """E2E tests for M4 Action Enum unification (監査Go条件).

    Verifies that AI action names (CLOSE, PARTIAL_CLOSE, ADJUST_SL, ADJUST_TP)
    are correctly mapped and executed by the engine.
    """

    @pytest.mark.asyncio
    async def test_ai_close_triggers_exit(self):
        """AI says CLOSE → engine actually calls execute_exit (監査Go条件2)."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        mock_pos = MagicMock()
        mock_pos.position_id = "pos-close-1"
        mock_pos.amount = 1.0
        engine.exchange.get_positions = AsyncMock(return_value=[mock_pos])

        # AI returns CLOSE (not EXIT)
        m4_output = JudgeOutput(
            result={"action": "CLOSE", "reason": "AI_TREND_REVERSAL"},
            confidence=0.9,
            reason_codes=["AI_TREND_REVERSAL"],
        )
        engine.orchestrator.execute_exit_management = AsyncMock(return_value=m4_output)
        engine.execution_engine.execute_exit = AsyncMock(
            return_value=MagicMock(success=True),
        )

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(150.0),
        )
        await engine._handle_bar_event(event)

        # execute_exit MUST have been called
        engine.execution_engine.execute_exit.assert_called_once()
        call_kwargs = engine.execution_engine.execute_exit.call_args.kwargs
        assert call_kwargs["position"] is mock_pos

    @pytest.mark.asyncio
    async def test_ai_partial_close_triggers_exit(self):
        """AI says PARTIAL_CLOSE → engine calls execute_exit."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        mock_pos = MagicMock()
        mock_pos.position_id = "pos-partial-1"
        mock_pos.amount = 2.0
        engine.exchange.get_positions = AsyncMock(return_value=[mock_pos])

        m4_output = JudgeOutput(
            result={"action": "PARTIAL_CLOSE", "partialPct": 0.5},
            confidence=0.8,
            reason_codes=["PARTIAL_TP"],
        )
        engine.orchestrator.execute_exit_management = AsyncMock(return_value=m4_output)
        engine.execution_engine.execute_exit = AsyncMock(
            return_value=MagicMock(success=True),
        )

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(151.0),
        )
        await engine._handle_bar_event(event)

        engine.execution_engine.execute_exit.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_adjust_sl_calls_adjust_stop_loss(self):
        """AI says ADJUST_SL → engine calls adjust_stop_loss with newSlPrice."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        mock_pos = MagicMock()
        mock_pos.position_id = "pos-sl-1"
        engine.exchange.get_positions = AsyncMock(return_value=[mock_pos])

        m4_output = JudgeOutput(
            result={"action": "ADJUST_SL", "newSlPrice": 149.5},
            confidence=0.85,
            reason_codes=["AI_SL_TIGHTEN"],
        )
        engine.orchestrator.execute_exit_management = AsyncMock(return_value=m4_output)
        engine.execution_engine.adjust_stop_loss = AsyncMock(return_value=True)

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(150.5),
        )
        await engine._handle_bar_event(event)

        engine.execution_engine.adjust_stop_loss.assert_called_once_with(
            mock_pos, 149.5,
        )

    @pytest.mark.asyncio
    async def test_ai_adjust_tp_calls_adjust_take_profit(self):
        """AI says ADJUST_TP → engine calls adjust_take_profit with newTpPrice."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        mock_pos = MagicMock()
        mock_pos.position_id = "pos-tp-1"
        engine.exchange.get_positions = AsyncMock(return_value=[mock_pos])

        m4_output = JudgeOutput(
            result={"action": "ADJUST_TP", "newTpPrice": 153.0},
            confidence=0.8,
            reason_codes=["AI_TP_EXTEND"],
        )
        engine.orchestrator.execute_exit_management = AsyncMock(return_value=m4_output)
        engine.execution_engine.adjust_take_profit = AsyncMock(return_value=True)

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(152.0),
        )
        await engine._handle_bar_event(event)

        engine.execution_engine.adjust_take_profit.assert_called_once_with(
            mock_pos, 153.0,
        )

    @pytest.mark.asyncio
    async def test_exit_unregisters_position_from_sync(self):
        """After EXIT, position should be unregistered from sync service."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        mock_pos = MagicMock()
        mock_pos.position_id = "pos-unreg-1"
        mock_pos.amount = 1.0
        engine.exchange.get_positions = AsyncMock(return_value=[mock_pos])

        m4_output = JudgeOutput(
            result={"action": "EXIT"},
            confidence=1.0,
            reason_codes=["MAX_HOLD"],
        )
        engine.orchestrator.execute_exit_management = AsyncMock(return_value=m4_output)
        engine.execution_engine.execute_exit = AsyncMock(
            return_value=MagicMock(success=True),
        )

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M1",
            timestamp=datetime.now(timezone.utc),
            ohlcv=_make_ohlcv(150.0),
        )
        await engine._handle_bar_event(event)

        # Position should be unregistered
        assert engine._position_sync.known_position_count == 0

    @pytest.mark.asyncio
    async def test_entry_registers_position_immediately(self):
        """After successful entry, position registered immediately (監査指摘3)."""
        engine = _make_engine_with_indicators()
        await engine.warmup()

        # Setup M1 + M2 caches so M5 pipeline runs
        now = datetime.now(timezone.utc)
        engine._m1_cache = PipelineCacheEntry(
            output=JudgeOutput(
                result={"tradeAllowed": True}, confidence=0.9,
                reason_codes=["M1_PASS"],
            ),
            timestamp=now, valid_until=now,
            bar_timestamp=now,
        )
        engine._m2_cache = PipelineCacheEntry(
            output=JudgeOutput(
                result={"setupValid": True}, confidence=0.9,
                reason_codes=["M2_PASS"],
            ),
            timestamp=now, valid_until=now,
            bar_timestamp=now,
        )

        # Mock orchestrator to return ENTRY
        from app.services.exchange.exchange_types import OrderSide
        mock_order = MagicMock()
        mock_order.pair = "USD_JPY"
        mock_order.side = OrderSide.BUY
        mock_order.amount = 1.0
        pipeline_result = PipelineResult(
            action="ENTRY",
            order=mock_order,
            guard_state=MagicMock(),
        )
        engine.orchestrator.execute_pipeline = AsyncMock(return_value=pipeline_result)

        # Mock execution engine to return success with filled order
        filled_order = MagicMock()
        filled_order.order_id = "filled-123"
        filled_order.filled_price = 150.0
        filled_order.filled_amount = 1.0
        exec_result = MagicMock(success=True, order=filled_order)
        engine.execution_engine.execute_entry = AsyncMock(return_value=exec_result)

        event = BarClosedEvent(
            pair="USD_JPY", timeframe="M5",
            timestamp=now,
            ohlcv=_make_ohlcv(150.0),
        )
        await engine._handle_bar_event(event)

        # Position must be immediately registered
        assert engine._position_sync.known_position_count == 1
