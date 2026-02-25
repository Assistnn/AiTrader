"""
Crypto trading integration tests.
Reference: 06_取引所抽象化, Phase 4 Step 9

Verify MockExchange works end-to-end with crypto pairs,
including slippage, PnL calculation, and FX/Crypto coexistence.
"""

import pytest

from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.exchange.position_sizer import PositionSizer
from app.services.exchange.exchange_types import OrderSide, OrderType


class TestCryptoTradingFlow:
    """End-to-end crypto trading on MockExchange."""

    @pytest.mark.asyncio
    async def test_btc_jpy_buy_sell(self):
        ex = MockExchange(initial_balance=10_000_000)
        ex.slippage_pips = 2.0
        ex.set_price("BTC_JPY", bid=15_000_000, ask=15_000_100)

        order = await ex.place_order("BTC_JPY", OrderSide.BUY, 0.1, OrderType.MARKET)
        assert order.filled_price == pytest.approx(15_000_102.0, abs=0.01)
        assert len(ex.positions) == 1

        pos_id = ex.positions[0].position_id
        ex.set_price("BTC_JPY", bid=15_100_000, ask=15_100_100)
        close = await ex.close_position(pos_id)
        assert close.filled_price == 15_100_000  # bid for SELL
        assert len(ex.positions) == 0

    @pytest.mark.asyncio
    async def test_xrp_jpy_buy_sell(self):
        ex = MockExchange()
        ex.set_price("XRP_JPY", bid=80.000, ask=80.002)

        order = await ex.place_order("XRP_JPY", OrderSide.BUY, 100, OrderType.MARKET)
        assert order.filled_price == 80.002
        assert len(ex.positions) == 1

        pos_id = ex.positions[0].position_id
        ex.set_price("XRP_JPY", bid=80.500, ask=80.502)
        await ex.close_position(pos_id)
        assert len(ex.positions) == 0

    @pytest.mark.asyncio
    async def test_btc_pnl_calculation(self):
        """PnL via PriceNormalizer matches trade outcome."""
        n = PriceNormalizer()
        entry = 15_000_000.0
        exit_ = 15_050_000.0
        lot = 0.1

        pnl = n.calculate_pnl(entry, exit_, "BUY", lot, "BTC_JPY")
        # diff=50000, pips=50000, pip_value=0.1, pnl=5000
        assert abs(pnl - 5000.0) < 0.01


class TestFxCryptoCoexistence:
    """Verify FX and Crypto can trade on same MockExchange."""

    @pytest.mark.asyncio
    async def test_mixed_pairs(self):
        ex = MockExchange()
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        ex.set_price("BTC_JPY", bid=15_000_000, ask=15_000_100)

        # Open FX position
        await ex.place_order("USD_JPY", OrderSide.BUY, 1.0, OrderType.MARKET)
        # Open Crypto position
        await ex.place_order("BTC_JPY", OrderSide.BUY, 0.01, OrderType.MARKET)

        assert len(ex.positions) == 2
        pairs = {p.pair for p in ex.positions}
        assert pairs == {"USD_JPY", "BTC_JPY"}


class TestCryptoPositionSizing:
    """PositionSizer integration with crypto."""

    def test_btc_sizing_then_trade(self):
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="BTC_JPY", capital=5_000_000,
            risk_per_trade_pct=1.0, sl_pips=50000, tp_pips=100000,
            min_lot=0.001, max_lot=10.0,
        )
        # risk=50000, raw=50000/(50000*1)=1.0
        assert abs(result.lot_size - 1.0) < 0.001
        assert abs(result.rr_ratio - 2.0) < 0.01


class TestCryptoSlippageAccuracy:
    """Verify slippage uses PriceNormalizer.from_pips correctly."""

    @pytest.mark.asyncio
    async def test_fx_slippage_unchanged(self):
        """FX regression: slippage behavior identical to before refactor."""
        ex = MockExchange()
        ex.slippage_pips = 2.0
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        order = await ex.place_order("USD_JPY", OrderSide.BUY, 1.0, OrderType.MARKET)
        # 2 pips * 0.01 = 0.02; ask 150.02 + 0.02 = 150.04
        assert order.filled_price == pytest.approx(150.04, abs=0.001)
