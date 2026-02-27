"""
Tests for ExecutionEngine (order placement).
Reference: 16_実行エンジンとUI接続 Section 9
"""

import pytest
from datetime import datetime, timezone

from app.services.engine.execution_engine import ExecutionEngine
from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.exchange_types import (
    OrderSide,
    OrderStatus,
    OrderType,
    ExchangePosition,
    PositionSizeResult,
)
from app.services.exchange.position_sizer import PositionSizer
from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.safeguard.guard_types import GuardState, ProposedOrder
from app.services.decision.decision_types import JudgeOutput


def _make_execution_engine() -> tuple[ExecutionEngine, MockExchange]:
    exchange = MockExchange()
    exchange.set_price("USD_JPY", bid=150.00, ask=150.003)
    normalizer = PriceNormalizer()
    sizer = PositionSizer(price_normalizer=normalizer)
    engine = ExecutionEngine(
        exchange=exchange,
        position_sizer=sizer,
        price_normalizer=normalizer,
    )
    return engine, exchange


def _make_guard_state(
    entry_allowed: bool = True,
    lot_multiplier: float = 1.0,
) -> GuardState:
    return GuardState(
        entry_allowed=entry_allowed,
        force_close=False,
        trader_halted=False,
        cooldown_until=None,
        lot_multiplier=lot_multiplier,
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


class TestExecutionEngine:
    @pytest.mark.asyncio
    async def test_execute_entry_success(self):
        engine, exchange = _make_execution_engine()

        proposed = _make_proposed_order()
        guard_state = _make_guard_state()

        result = await engine.execute_entry(proposed, guard_state)
        assert result.success is True
        assert result.order is not None
        assert result.order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_execute_entry_with_lot_multiplier(self):
        engine, exchange = _make_execution_engine()

        proposed = _make_proposed_order()
        guard_state = _make_guard_state(lot_multiplier=0.5)

        result = await engine.execute_entry(proposed, guard_state)
        assert result.success is True
        assert result.size_result is not None

    @pytest.mark.asyncio
    async def test_execute_exit_success(self):
        engine, exchange = _make_execution_engine()

        # First create a position via entry
        proposed = _make_proposed_order()
        guard_state = _make_guard_state()
        entry_result = await engine.execute_entry(proposed, guard_state)
        assert entry_result.success is True

        positions = await exchange.get_positions()
        assert len(positions) > 0

        m4_output = JudgeOutput(
            result={"action": "EXIT"},
            confidence=0.9,
            reason_codes=["TP_REACHED"],
        )

        result = await engine.execute_exit(positions[0], m4_output)
        assert result.success is True
        assert result.order is not None
        assert result.order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_close_all_positions(self):
        engine, exchange = _make_execution_engine()
        results = await engine.close_all_positions()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_adjust_stop_loss(self):
        engine, _ = _make_execution_engine()
        pos = ExchangePosition(
            position_id="test-1",
            pair="USD_JPY",
            side=OrderSide.BUY,
            amount=1.0,
            entry_price=150.0,
        )
        result = await engine.adjust_stop_loss(pos, 149.50)
        assert result is True


class TestOCOOrders:
    """OCO order tests (§3-1, §9-2)."""

    @pytest.mark.asyncio
    async def test_execute_entry_places_oco_after_fill(self):
        """After MARKET fill, TP (LIMIT) and SL (STOP) orders are placed."""
        engine, exchange = _make_execution_engine()
        proposed = _make_proposed_order(sl_price=149.80, tp_price=150.40)
        guard_state = _make_guard_state()

        result = await engine.execute_entry(proposed, guard_state)
        assert result.success is True
        assert result.tp_order_id is not None
        assert result.sl_order_id is not None

        # Verify TP and SL orders exist in exchange
        pending_orders = [
            o for o in exchange.orders
            if o.status == OrderStatus.PENDING
        ]
        assert len(pending_orders) == 2

        tp_orders = [o for o in pending_orders if o.order_type == OrderType.LIMIT]
        sl_orders = [o for o in pending_orders if o.order_type == OrderType.STOP]
        assert len(tp_orders) == 1
        assert len(sl_orders) == 1

        # TP order: opposite side, correct price
        assert tp_orders[0].side == OrderSide.SELL  # opposite of BUY
        assert tp_orders[0].price == 150.40

        # SL order: opposite side, correct price
        assert sl_orders[0].side == OrderSide.SELL
        assert sl_orders[0].price == 149.80

    @pytest.mark.asyncio
    async def test_oco_client_order_id_matching(self):
        """clientOrderId prefix matches: entry-xxx, tp-xxx, sl-xxx."""
        engine, exchange = _make_execution_engine()
        proposed = _make_proposed_order(sl_price=149.80, tp_price=150.40)
        guard_state = _make_guard_state()

        result = await engine.execute_entry(proposed, guard_state)
        assert result.success is True

        # Extract client_order_ids
        entry_coid = result.order.client_order_id
        assert entry_coid.startswith("entry-")
        uuid_suffix = entry_coid.replace("entry-", "")

        # Find TP and SL orders
        pending = [o for o in exchange.orders if o.status == OrderStatus.PENDING]
        tp_order = next(o for o in pending if o.order_type == OrderType.LIMIT)
        sl_order = next(o for o in pending if o.order_type == OrderType.STOP)

        assert tp_order.client_order_id == f"tp-{uuid_suffix}"
        assert sl_order.client_order_id == f"sl-{uuid_suffix}"

    @pytest.mark.asyncio
    async def test_no_oco_when_prices_none(self):
        """No OCO orders when sl_price/tp_price are None."""
        engine, exchange = _make_execution_engine()
        proposed = _make_proposed_order(sl_price=None, tp_price=None)
        guard_state = _make_guard_state()

        result = await engine.execute_entry(proposed, guard_state)
        assert result.success is True
        assert result.tp_order_id is None
        assert result.sl_order_id is None

        # No pending orders
        pending = [o for o in exchange.orders if o.status == OrderStatus.PENDING]
        assert len(pending) == 0


class TestBitbankWatchlist:
    """System-side SL/TP watchlist tests (§9-4)."""

    def _make_crypto_engine(self) -> tuple[ExecutionEngine, MockExchange]:
        exchange = MockExchange()
        exchange.set_price("BTC_JPY", bid=5_000_000, ask=5_000_100)
        normalizer = PriceNormalizer()
        sizer = PositionSizer(price_normalizer=normalizer)
        engine = ExecutionEngine(
            exchange=exchange,
            position_sizer=sizer,
            price_normalizer=normalizer,
            trade_type="crypto",
        )
        return engine, exchange

    @pytest.mark.asyncio
    async def test_bitbank_entry_adds_to_watchlist(self):
        """Crypto entry adds position to SL/TP watchlist."""
        engine, exchange = self._make_crypto_engine()
        proposed = _make_proposed_order(
            pair="BTC_JPY", sl_price=4_900_000, tp_price=5_200_000,
        )
        guard_state = _make_guard_state()

        result = await engine.execute_entry(proposed, guard_state)
        assert result.success is True
        # No exchange-side OCO for crypto
        assert result.tp_order_id is None
        assert result.sl_order_id is None
        # Watchlist entry exists
        assert len(engine._sl_tp_watchlist) == 1

    @pytest.mark.asyncio
    async def test_bitbank_sl_triggered(self):
        """SL triggers close when price drops below threshold."""
        engine, exchange = self._make_crypto_engine()
        proposed = _make_proposed_order(
            pair="BTC_JPY", sl_price=4_900_000, tp_price=5_200_000,
        )
        guard_state = _make_guard_state()

        await engine.execute_entry(proposed, guard_state)
        assert len(engine._sl_tp_watchlist) == 1

        # Price drops below SL
        exchange.set_price("BTC_JPY", bid=4_800_000, ask=4_800_100)
        results = await engine.check_sl_tp("BTC_JPY")
        assert len(results) == 1
        assert results[0].success is True
        # Watchlist should be cleared
        assert len(engine._sl_tp_watchlist) == 0

    @pytest.mark.asyncio
    async def test_bitbank_tp_triggered(self):
        """TP triggers close when price rises above threshold."""
        engine, exchange = self._make_crypto_engine()
        proposed = _make_proposed_order(
            pair="BTC_JPY", sl_price=4_900_000, tp_price=5_200_000,
        )
        guard_state = _make_guard_state()

        await engine.execute_entry(proposed, guard_state)
        assert len(engine._sl_tp_watchlist) == 1

        # Price rises above TP
        exchange.set_price("BTC_JPY", bid=5_300_000, ask=5_300_100)
        results = await engine.check_sl_tp("BTC_JPY")
        assert len(results) == 1
        assert results[0].success is True
        assert len(engine._sl_tp_watchlist) == 0

    @pytest.mark.asyncio
    async def test_watchlist_no_trigger_when_price_in_range(self):
        """No close when price is between SL and TP."""
        engine, exchange = self._make_crypto_engine()
        proposed = _make_proposed_order(
            pair="BTC_JPY", sl_price=4_900_000, tp_price=5_200_000,
        )
        guard_state = _make_guard_state()

        await engine.execute_entry(proposed, guard_state)
        # Price stays in range
        exchange.set_price("BTC_JPY", bid=5_050_000, ask=5_050_100)
        results = await engine.check_sl_tp("BTC_JPY")
        assert len(results) == 0
        assert len(engine._sl_tp_watchlist) == 1
