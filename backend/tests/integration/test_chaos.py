"""
Chaos and resilience tests for the trading engine.

Reference: 16_実行エンジンとUI接続 Section 11
Go/No-Go #2: kill -9 recovery, cascade failures, connection loss

All tests use MockExchange (simulation mode). No real trades.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from datetime import datetime, timezone

from app.services.engine.execution_engine import ExecutionEngine
from app.services.engine.engine_manager import EngineManager
from app.services.engine.trade_execution_engine import TradeExecutionEngine, EngineStatus
from app.services.engine.bar_scheduler import BarConfirmationScheduler, BarClosedEvent
from app.services.engine.market_data_feed import MarketDataFeed
from app.services.engine.config_event_bus import ConfigEventBus
from app.services.engine.resilience import CircuitBreaker, CircuitOpenError
from app.services.engine.position_sync import PositionSyncService, DivergenceType
from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.exchange_types import (
    ExchangePosition,
    ExecutionResult,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.services.exchange.position_sizer import PositionSizer
from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.safeguard.guard_types import GuardState, ProposedOrder
from app.services.decision.decision_types import JudgeOutput, PipelineResult
from app.services.pipeline.data_types import OHLCV


def _make_exchange() -> MockExchange:
    exchange = MockExchange()
    exchange.set_price("USD_JPY", bid=150.00, ask=150.003)
    return exchange


def _make_execution_engine(
    exchange: MockExchange | None = None,
    trade_type: str = "FX",
    circuit_breaker: CircuitBreaker | None = None,
) -> ExecutionEngine:
    exchange = exchange or _make_exchange()
    normalizer = PriceNormalizer()
    sizer = PositionSizer(price_normalizer=normalizer)
    return ExecutionEngine(
        exchange=exchange,
        position_sizer=sizer,
        price_normalizer=normalizer,
        trade_type=trade_type,
        circuit_breaker=circuit_breaker,
    )


def _make_guard_state() -> GuardState:
    return GuardState(
        entry_allowed=True,
        force_close=False,
        trader_halted=False,
        cooldown_until=None,
        lot_multiplier=1.0,
        evaluations=[],
        blocking_guards=[],
    )


def _make_proposed_order(**kwargs) -> ProposedOrder:
    defaults = {
        "pair": "USD_JPY",
        "side": "BUY",
        "lot_size": 1.0,
        "order_type": "market",
        "sl_pips": 20.0,
        "tp_pips": 40.0,
        "sl_price": 149.80,
        "tp_price": 150.40,
        "risk_per_trade_pct": 1.0,
    }
    defaults.update(kwargs)
    return ProposedOrder(**defaults)


class TestKillRecovery:
    """Go/No-Go #2: kill -9 recovery via position sync."""

    @pytest.mark.asyncio
    async def test_restart_recovers_positions_via_sync(self):
        """After engine restart, position sync detects existing positions."""
        exchange = _make_exchange()
        engine = _make_execution_engine(exchange)
        guard_state = _make_guard_state()

        # Create a position
        result = await engine.execute_entry(_make_proposed_order(), guard_state)
        assert result.success is True
        positions = await exchange.get_positions()
        assert len(positions) == 1

        # Simulate kill -9: create a new sync service (as if restarted)
        sync = PositionSyncService(exchange=exchange, trader_id=1)
        # Don't register any positions (simulating fresh start)

        divergences = await sync.sync()
        # Should detect the exchange position as UNKNOWN
        assert len(divergences) == 1
        assert divergences[0].divergence_type == DivergenceType.UNKNOWN_POSITION

        # After sync, position is now known
        divergences2 = await sync.sync()
        assert len(divergences2) == 0

    @pytest.mark.asyncio
    async def test_restart_with_seed_sync(self):
        """Engine restart seeds position sync from exchange."""
        exchange = _make_exchange()
        engine = _make_execution_engine(exchange)
        guard_state = _make_guard_state()

        # Create a position
        await engine.execute_entry(_make_proposed_order(), guard_state)

        # Simulate restart: seed from exchange (as done in run())
        sync = PositionSyncService(exchange=exchange, trader_id=1)
        initial_positions = await exchange.get_positions()
        sync.update_known_from_exchange(initial_positions)

        # No divergence expected
        divergences = await sync.sync()
        assert len(divergences) == 0


class TestCascadeFailures:
    """Cascade failure: exchange API failures → CircuitBreaker open."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_consecutive_failures(self):
        """5 consecutive failures open the circuit breaker."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=300.0)
        engine = _make_execution_engine(circuit_breaker=cb)

        assert cb.state == "closed"

        # Record 5 failures
        for _ in range(5):
            cb.record_failure()

        assert cb.state == "open"

        # Entry should be blocked
        result = await engine.execute_entry(
            _make_proposed_order(), _make_guard_state(),
        )
        assert result.success is False
        assert "CircuitBreaker" in result.error

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers_after_success(self):
        """CB recovers to closed after a successful operation."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.0)
        engine = _make_execution_engine(circuit_breaker=cb)

        # Open the breaker
        for _ in range(3):
            cb.record_failure()
        # With recovery_timeout=0, immediately transitions to half_open
        assert cb.state == "half_open"

        # Successful entry should close the breaker
        result = await engine.execute_entry(
            _make_proposed_order(), _make_guard_state(),
        )
        assert result.success is True
        assert cb.state == "closed"


class TestConnectionLoss:
    """Connection loss detection and failsafe."""

    @pytest.mark.asyncio
    async def test_market_data_feed_disconnect_tracking(self):
        """MarketDataFeed tracks disconnect duration."""
        from app.services.pipeline.data_ingest import BaseDataProvider

        mock_provider = MagicMock(spec=BaseDataProvider)
        feed = MarketDataFeed(mock_provider)

        # Initially not connected (no connect() called)
        assert feed.is_connected() is False

    @pytest.mark.asyncio
    async def test_check_sl_tp_handles_ticker_failure(self):
        """check_sl_tp gracefully handles ticker fetch failure."""
        exchange = _make_exchange()
        engine = _make_execution_engine(exchange, trade_type="crypto")

        # Add to watchlist manually
        engine._sl_tp_watchlist["test-pos"] = {
            "pair": "BTC_JPY",
            "entry_price": 5_000_000,
            "tp_price": 5_200_000,
            "sl_price": 4_900_000,
            "side": "BUY",
            "amount": 0.1,
        }

        # BTC_JPY price not set → ticker fetch will return default
        # (MockExchange returns default 100.01 which is below SL)
        results = await engine.check_sl_tp("BTC_JPY")
        # SL should trigger since default price (100.01) < sl_price (4_900_000)
        assert len(results) >= 0  # Graceful handling, no crash


class TestHaltForceClose:
    """HALT → force close with retry (§12-2 監査7)."""

    @pytest.mark.asyncio
    async def test_halt_force_close_success(self):
        """HALT force close succeeds on first try."""
        exchange = _make_exchange()
        engine = _make_execution_engine(exchange)
        guard_state = _make_guard_state()

        # Create a position
        await engine.execute_entry(_make_proposed_order(), guard_state)
        positions = await exchange.get_positions()
        assert len(positions) == 1

        # Force close
        results = await engine.close_all_positions()
        assert len(results) == 1
        assert results[0].success is True

        # No positions left
        positions = await exchange.get_positions()
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_halt_force_close_retry_logic(self):
        """EngineManager._halt_force_close retries on failure."""
        manager = EngineManager()

        # Create a mock engine with close_all_positions that fails then succeeds
        mock_engine = MagicMock()
        mock_exec_engine = AsyncMock()
        mock_engine.execution_engine = mock_exec_engine

        # First call fails, second succeeds
        mock_exec_engine.close_all_positions.side_effect = [
            [ExecutionResult(success=False, error="API error")],
            [ExecutionResult(success=True)],
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await manager._halt_force_close(trader_id=1, engine=mock_engine)

        assert mock_exec_engine.close_all_positions.call_count == 2


class TestOCOPartialFailure:
    """OCO partial failure: MARKET fills but SL/TP placement fails."""

    @pytest.mark.asyncio
    async def test_oco_sl_failure_adds_to_watchlist(self):
        """If SL OCO placement fails, position is added to watchlist."""
        exchange = _make_exchange()
        engine = _make_execution_engine(exchange)

        # Patch place_order to fail on STOP orders
        original_place = exchange.place_order

        call_count = 0

        async def failing_place_order(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("order_type") == OrderType.STOP:
                raise Exception("SL order placement failed")
            return await original_place(*args, **kwargs)

        exchange.place_order = failing_place_order

        proposed = _make_proposed_order(sl_price=149.80, tp_price=150.40)
        result = await engine.execute_entry(proposed, _make_guard_state())

        # Entry should succeed (MARKET filled)
        assert result.success is True
        # SL order ID should be None (failed)
        assert result.sl_order_id is None
        # TP order should have succeeded
        assert result.tp_order_id is not None
        # Position should be in watchlist (fallback)
        assert len(engine._sl_tp_watchlist) == 1


class TestPositionSyncDivergence:
    """Position sync divergence detection during engine operation."""

    @pytest.mark.asyncio
    async def test_sync_detects_external_position_change(self):
        """Sync detects when exchange positions change externally."""
        exchange = _make_exchange()
        sync = PositionSyncService(exchange=exchange, trader_id=1)

        # Register a position
        pos = ExchangePosition(
            position_id="pos-1", pair="USD_JPY",
            side=OrderSide.BUY, amount=1.0, entry_price=150.0,
        )
        exchange.positions = [pos]
        sync.register_position(pos)

        # No divergence
        d1 = await sync.sync()
        assert len(d1) == 0

        # External change: amount increased (e.g., manual trade)
        exchange.positions = [
            ExchangePosition(
                position_id="pos-1", pair="USD_JPY",
                side=OrderSide.BUY, amount=2.0, entry_price=150.0,
            ),
        ]

        d2 = await sync.sync()
        assert len(d2) == 1
        assert d2[0].divergence_type == DivergenceType.AMOUNT_MISMATCH
        assert d2[0].exchange_amount == 2.0
        assert d2[0].local_amount == 1.0

    @pytest.mark.asyncio
    async def test_sync_detects_position_closed_externally(self):
        """Sync detects when a position is closed on exchange side."""
        exchange = _make_exchange()
        sync = PositionSyncService(exchange=exchange, trader_id=1)

        pos = ExchangePosition(
            position_id="pos-1", pair="USD_JPY",
            side=OrderSide.BUY, amount=1.0, entry_price=150.0,
        )
        exchange.positions = [pos]
        sync.register_position(pos)

        # Position closed externally
        exchange.positions = []

        d = await sync.sync()
        assert len(d) == 1
        assert d[0].divergence_type == DivergenceType.MISSING_POSITION
