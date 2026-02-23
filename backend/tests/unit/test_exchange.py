"""
Exchange layer tests.
Reference: 06_取引所抽象化, 13_テスト戦略
"""

import pytest
from datetime import datetime, timezone

from app.services.exchange.exchange_types import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.exchange.position_sizer import PositionSizer
from app.services.exchange.rate_limiter import OrderRateLimiter


# ===========================================================================
# PriceNormalizer
# ===========================================================================


class TestPriceNormalizer:
    def test_to_pips_jpy_pair(self):
        n = PriceNormalizer()
        # 150.50 - 150.00 = 0.50 → 50 pips
        assert n.to_pips(0.50, "USD_JPY") == 50.0

    def test_to_pips_usd_pair(self):
        n = PriceNormalizer()
        # 1.0850 - 1.0800 = 0.0050 → 50 pips
        assert n.to_pips(0.0050, "EUR_USD") == 50.0

    def test_from_pips(self):
        n = PriceNormalizer()
        assert n.from_pips(50.0, "USD_JPY") == 0.50
        assert abs(n.from_pips(50.0, "EUR_USD") - 0.0050) < 1e-8

    def test_pip_value(self):
        n = PriceNormalizer()
        # 1 lot, 1 pip = 100 JPY for JPY pairs
        assert n.pip_value("USD_JPY", 1.0) == 100.0
        # 2 lots
        assert n.pip_value("USD_JPY", 2.0) == 200.0

    def test_round_price(self):
        n = PriceNormalizer()
        assert n.round_price(150.123, "USD_JPY") == 150.12
        assert n.round_price(1.08765, "EUR_USD") == 1.0877

    def test_calculate_pnl_buy(self):
        n = PriceNormalizer()
        # Buy at 150.00, sell at 150.50, 1 lot → 50 pips * 100 = 5000 JPY
        pnl = n.calculate_pnl(150.00, 150.50, "BUY", 1.0, "USD_JPY")
        assert abs(pnl - 5000.0) < 0.01

    def test_calculate_pnl_sell(self):
        n = PriceNormalizer()
        # Sell at 150.50, buy at 150.00, 1 lot → 50 pips * 100 = 5000 JPY
        pnl = n.calculate_pnl(150.50, 150.00, "SELL", 1.0, "USD_JPY")
        assert abs(pnl - 5000.0) < 0.01

    def test_calculate_pnl_loss(self):
        n = PriceNormalizer()
        # Buy at 150.50, sell at 150.00, 1 lot → -50 pips * 100 = -5000 JPY
        pnl = n.calculate_pnl(150.50, 150.00, "BUY", 1.0, "USD_JPY")
        assert abs(pnl - (-5000.0)) < 0.01

    def test_unknown_pair_raises(self):
        n = PriceNormalizer()
        with pytest.raises(KeyError):
            n.to_pips(0.5, "UNKNOWN_PAIR")

    def test_get_pip_definition(self):
        n = PriceNormalizer()
        defn = n.get_pip_definition("USD_JPY")
        assert defn["pip_size"] == 0.01
        assert defn["pip_digits"] == 2

    def test_get_pip_definition_unknown(self):
        n = PriceNormalizer()
        with pytest.raises(KeyError):
            n.get_pip_definition("UNKNOWN_XYZ")


# ===========================================================================
# PositionSizer
# ===========================================================================


class TestPositionSizer:
    def test_basic_sizing(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="USD_JPY", capital=1_000_000,
            risk_per_trade_pct=2.0, sl_pips=50.0, tp_pips=75.0,
            min_lot=0.01, max_lot=100.0,
        )
        # risk = 1M * 2% = 20,000. raw_lot = 20000/(50*100) = 4.0
        assert abs(result.lot_size - 4.0) < 0.01
        assert abs(result.rr_ratio - 1.5) < 0.01
        assert result.risk_amount > 0
        assert "capital" in result._debug

    def test_clips_to_min_lot(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="USD_JPY", capital=10_000,
            risk_per_trade_pct=0.5, sl_pips=200.0, tp_pips=300.0,
            min_lot=0.01, max_lot=100.0,
        )
        # risk=50, raw_lot=50/(200*100)=0.0025 → min 0.01
        assert result.lot_size == 0.01

    def test_clips_to_max_lot(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="USD_JPY", capital=100_000_000,
            risk_per_trade_pct=5.0, sl_pips=10.0, tp_pips=15.0,
            min_lot=0.01, max_lot=50.0,
        )
        assert result.lot_size == 50.0

    def test_zero_sl_uses_min_lot(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="USD_JPY", capital=1_000_000,
            risk_per_trade_pct=2.0, sl_pips=0.0, tp_pips=50.0,
            min_lot=0.01, max_lot=100.0,
        )
        assert result.lot_size == 0.01  # safety fallback


# ===========================================================================
# MockExchange
# ===========================================================================


class TestMockExchange:
    @pytest.mark.asyncio
    async def test_place_market_order(self):
        ex = MockExchange(initial_balance=1_000_000)
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        order = await ex.place_order(
            pair="USD_JPY", side=OrderSide.BUY,
            amount=1.0, order_type=OrderType.MARKET,
        )
        assert order.status == OrderStatus.FILLED
        assert order.filled_price == 150.02  # ask for BUY
        assert len(ex.positions) == 1
        assert ex.positions[0].side == OrderSide.BUY

    @pytest.mark.asyncio
    async def test_close_position_full(self):
        ex = MockExchange()
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        await ex.place_order("USD_JPY", OrderSide.BUY, 1.0, OrderType.MARKET)
        assert len(ex.positions) == 1

        pos_id = ex.positions[0].position_id
        ex.set_price("USD_JPY", bid=150.50, ask=150.52)
        close_order = await ex.close_position(pos_id)
        assert close_order.status == OrderStatus.FILLED
        assert len(ex.positions) == 0

    @pytest.mark.asyncio
    async def test_close_position_partial(self):
        ex = MockExchange()
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        await ex.place_order("USD_JPY", OrderSide.BUY, 2.0, OrderType.MARKET)
        pos_id = ex.positions[0].position_id

        ex.set_price("USD_JPY", bid=150.50, ask=150.52)
        await ex.close_position(pos_id, amount=1.0)
        assert len(ex.positions) == 1
        assert ex.positions[0].amount == 1.0

    @pytest.mark.asyncio
    async def test_limit_order_pending(self):
        ex = MockExchange()
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        order = await ex.place_order(
            "USD_JPY", OrderSide.BUY, 1.0, OrderType.LIMIT, price=149.50,
        )
        assert order.status == OrderStatus.PENDING
        assert len(ex.positions) == 0

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        ex = MockExchange()
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        order = await ex.place_order(
            "USD_JPY", OrderSide.BUY, 1.0, OrderType.LIMIT, price=149.50,
        )
        result = await ex.cancel_order(order.order_id)
        assert result is True
        status = await ex.get_order_status(order.order_id)
        assert status.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_balance(self):
        ex = MockExchange(initial_balance=1_000_000)
        balance = await ex.get_balance()
        assert balance.total == 1_000_000
        assert balance.currency == "JPY"

    @pytest.mark.asyncio
    async def test_slippage(self):
        ex = MockExchange()
        ex.slippage_pips = 2.0  # 2 pips slippage
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        order = await ex.place_order("USD_JPY", OrderSide.BUY, 1.0, OrderType.MARKET)
        # Expected: ask 150.02 + slip 0.02 = 150.04
        assert order.filled_price == pytest.approx(150.04, abs=0.001)

    @pytest.mark.asyncio
    async def test_sell_order(self):
        ex = MockExchange()
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        order = await ex.place_order("USD_JPY", OrderSide.SELL, 1.0, OrderType.MARKET)
        assert order.filled_price == 150.00  # bid for SELL
        assert ex.positions[0].side == OrderSide.SELL


# ===========================================================================
# OrderRateLimiter
# ===========================================================================


class TestOrderRateLimiter:
    def test_can_order_initially(self):
        limiter = OrderRateLimiter(min_interval_sec=2.0, max_per_minute=10)
        assert limiter.can_order_now() is True

    def test_cannot_order_immediately_after(self):
        limiter = OrderRateLimiter(min_interval_sec=2.0, max_per_minute=10)
        limiter.record_order()
        assert limiter.can_order_now() is False

    def test_max_per_minute_limit(self):
        limiter = OrderRateLimiter(min_interval_sec=0.0, max_per_minute=3)
        for _ in range(3):
            limiter.record_order()
        assert limiter.can_order_now() is False
