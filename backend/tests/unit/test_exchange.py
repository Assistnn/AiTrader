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
# PriceNormalizer — Crypto (Phase 4 Step 1)
# ===========================================================================


class TestPriceNormalizerCrypto:
    """Crypto pair tests proving existing PIP_DEFINITIONS work for BTC/XRP."""

    def test_to_pips_btc_jpy(self):
        n = PriceNormalizer()
        # BTC: pip_size=1, so 50000 JPY diff = 50000 pips
        assert n.to_pips(50000, "BTC_JPY") == 50000.0

    def test_to_pips_xrp_jpy(self):
        n = PriceNormalizer()
        # XRP: pip_size=0.001, so 0.5 JPY diff = 500 pips
        assert n.to_pips(0.5, "XRP_JPY") == 500.0

    def test_from_pips_btc_jpy(self):
        n = PriceNormalizer()
        # 50000 pips * pip_size(1) = 50000
        assert n.from_pips(50000.0, "BTC_JPY") == 50000.0

    def test_from_pips_xrp_jpy(self):
        n = PriceNormalizer()
        # 500 pips * pip_size(0.001) = 0.5
        assert abs(n.from_pips(500.0, "XRP_JPY") - 0.5) < 1e-8

    def test_pip_value_btc_jpy(self):
        n = PriceNormalizer()
        # pip_value_per_lot=1, lot=0.1 → 0.1
        assert n.pip_value("BTC_JPY", 0.1) == pytest.approx(0.1)
        assert n.pip_value("BTC_JPY", 1.0) == 1.0

    def test_pip_value_xrp_jpy(self):
        n = PriceNormalizer()
        # pip_value_per_lot=1000, lot=1.0 → 1000
        assert n.pip_value("XRP_JPY", 1.0) == 1000.0
        assert n.pip_value("XRP_JPY", 10.0) == 10000.0

    def test_round_price_btc_jpy(self):
        n = PriceNormalizer()
        # pip_digits=0, round to integer
        assert n.round_price(15000000.7, "BTC_JPY") == 15000001.0
        assert n.round_price(15000000.3, "BTC_JPY") == 15000000.0

    def test_round_price_xrp_jpy(self):
        n = PriceNormalizer()
        # pip_digits=3
        assert n.round_price(80.1234, "XRP_JPY") == 80.123
        assert n.round_price(80.1235, "XRP_JPY") == 80.124

    def test_calculate_pnl_btc_jpy(self):
        n = PriceNormalizer()
        # Buy BTC at 15,000,000, sell at 15,050,000, 0.1 lot
        # diff=50000, pips=50000, pip_value=0.1, pnl=5000
        pnl = n.calculate_pnl(15_000_000, 15_050_000, "BUY", 0.1, "BTC_JPY")
        assert abs(pnl - 5000.0) < 0.01

    def test_calculate_pnl_xrp_jpy(self):
        n = PriceNormalizer()
        # Buy XRP at 80.000, sell at 80.100, 1 lot
        # diff=0.1, pips=100, pip_value=1000, pnl=100000
        pnl = n.calculate_pnl(80.000, 80.100, "BUY", 1.0, "XRP_JPY")
        assert abs(pnl - 100000.0) < 0.01

    def test_get_pip_definition_btc(self):
        n = PriceNormalizer()
        defn = n.get_pip_definition("BTC_JPY")
        assert defn["pip_size"] == 1
        assert defn["pip_digits"] == 0
        assert defn["pip_value_per_lot"] == 1

    def test_get_pip_definition_eth(self):
        n = PriceNormalizer()
        defn = n.get_pip_definition("ETH_JPY")
        assert defn["pip_size"] == 1
        assert defn["pip_digits"] == 0


# ===========================================================================
# PositionSizer — Crypto (Phase 4 Step 2)
# ===========================================================================


class TestPositionSizerCrypto:
    """Crypto position sizing tests."""

    def test_btc_sizing(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="BTC_JPY", capital=1_000_000,
            risk_per_trade_pct=2.0, sl_pips=100_000, tp_pips=200_000,
            min_lot=0.001, max_lot=10.0,
        )
        # risk=20000, pip_value_per_lot=1, raw=20000/(100000*1)=0.2
        assert abs(result.lot_size - 0.2) < 0.001
        assert abs(result.rr_ratio - 2.0) < 0.01

    def test_xrp_sizing_clips_to_min(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="XRP_JPY", capital=500_000,
            risk_per_trade_pct=1.0, sl_pips=1000, tp_pips=2000,
            min_lot=1.0, max_lot=1000.0,
        )
        # risk=5000, pip_value_per_lot=1000, raw=5000/(1000*1000)=0.005 → min=1.0
        assert result.lot_size == 1.0

    def test_btc_clips_to_max(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="BTC_JPY", capital=100_000_000,
            risk_per_trade_pct=5.0, sl_pips=10000, tp_pips=20000,
            min_lot=0.001, max_lot=5.0,
        )
        # risk=5000000, raw=5000000/(10000*1)=500 → max=5.0
        assert result.lot_size == 5.0

    def test_xrp_rr_ratio(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="XRP_JPY", capital=1_000_000,
            risk_per_trade_pct=2.0, sl_pips=500, tp_pips=750,
            min_lot=1.0, max_lot=1000.0,
        )
        assert abs(result.rr_ratio - 1.5) < 0.01
        assert "capital" in result._debug


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
# MockExchange — Crypto Slippage (Phase 4 Step 3)
# ===========================================================================


class TestMockExchangeCryptoSlippage:
    """Verify PriceNormalizer-based slippage works for Crypto pairs."""

    @pytest.mark.asyncio
    async def test_btc_jpy_slippage(self):
        ex = MockExchange()
        ex.slippage_pips = 5.0  # 5 pips for BTC (pip_size=1 → 5 JPY)
        ex.set_price("BTC_JPY", bid=15_000_000, ask=15_000_100)
        order = await ex.place_order("BTC_JPY", OrderSide.BUY, 0.1, OrderType.MARKET)
        # ask=15000100 + slip(5*1)=5 → 15000105
        assert order.filled_price == pytest.approx(15_000_105.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_xrp_jpy_slippage(self):
        ex = MockExchange()
        ex.slippage_pips = 10.0  # 10 pips for XRP (pip_size=0.001 → 0.01 JPY)
        ex.set_price("XRP_JPY", bid=80.000, ask=80.002)
        order = await ex.place_order("XRP_JPY", OrderSide.BUY, 1.0, OrderType.MARKET)
        # ask=80.002 + slip(10*0.001)=0.01 → 80.012
        assert order.filled_price == pytest.approx(80.012, abs=0.0001)

    @pytest.mark.asyncio
    async def test_eur_usd_slippage(self):
        ex = MockExchange()
        ex.slippage_pips = 3.0  # 3 pips for EUR_USD (pip_size=0.0001 → 0.0003)
        ex.set_price("EUR_USD", bid=1.0800, ask=1.0802)
        order = await ex.place_order("EUR_USD", OrderSide.SELL, 1.0, OrderType.MARKET)
        # bid=1.0800 - slip(3*0.0001)=0.0003 → 1.0797
        assert order.filled_price == pytest.approx(1.0797, abs=0.00001)


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


# ===========================================================================
# OrderRateLimiter — Per-second (Phase 4 Step 4, bitbank)
# ===========================================================================


class TestOrderRateLimiterPerSecond:
    """Per-second rate limiting for bitbank (6 orders/sec)."""

    def test_bitbank_config(self):
        limiter = OrderRateLimiter(
            min_interval_sec=0.0, max_per_minute=60, max_per_second=6,
        )
        assert limiter.max_per_second == 6
        assert limiter.can_order_now() is True

    def test_per_second_exceeded(self):
        limiter = OrderRateLimiter(
            min_interval_sec=0.0, max_per_minute=100, max_per_second=3,
        )
        for _ in range(3):
            limiter.record_order()
        # Per-second limit reached (3/3), but per-minute still OK
        assert limiter.can_order_now() is False

    def test_default_unlimited_per_second(self):
        """Default max_per_second=0 means no per-second limit (FX compat)."""
        limiter = OrderRateLimiter(min_interval_sec=0.0, max_per_minute=100)
        assert limiter.max_per_second == 0
        # No per-second limit, so 10 rapid orders are fine (within per-minute)
        for _ in range(10):
            limiter.record_order()
        assert limiter.can_order_now() is True  # still under 100/min
