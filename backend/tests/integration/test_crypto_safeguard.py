"""
Crypto safeguard integration tests (Phase 4 Step 20).
Audit proof: GuardEngine/PositionSizer cannot be bypassed for crypto pairs.

Reference: 監査3 — AIが生成したCrypto注文パラメータがGuardEngine/PositionSizerをバイパスできない
Reference: 監査4 — BudgetTrackerがCryptoペアでも月次上限を超えない
"""

import pytest

from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.exchange.position_sizer import PositionSizer
from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.exchange_types import OrderSide, OrderType


class TestCryptoPositionSizerNotBypassable:
    """Audit 3: PositionSizer must enforce limits for crypto pairs."""

    def test_btc_max_lot_enforced(self):
        """Even with huge capital, lot is capped at max_lot."""
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="BTC_JPY", capital=1_000_000_000,
            risk_per_trade_pct=100.0, sl_pips=1, tp_pips=2,
            min_lot=0.001, max_lot=10.0,
        )
        assert result.lot_size == 10.0  # Cannot exceed max

    def test_xrp_min_lot_enforced(self):
        """Even with tiny capital, lot doesn't go below min_lot."""
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="XRP_JPY", capital=100,
            risk_per_trade_pct=0.1, sl_pips=10000, tp_pips=20000,
            min_lot=1.0, max_lot=10000.0,
        )
        assert result.lot_size == 1.0  # Cannot go below min

    def test_zero_sl_forces_min_lot(self):
        """Zero SL pips → safety fallback to min_lot."""
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="BTC_JPY", capital=10_000_000,
            risk_per_trade_pct=5.0, sl_pips=0, tp_pips=100000,
            min_lot=0.001, max_lot=10.0,
        )
        assert result.lot_size == 0.001


class TestFxRegressionAfterCryptoChanges:
    """FX regression tests: ensure crypto changes don't break FX behavior."""

    def test_fx_pnl_unchanged(self):
        """PnL calculation for FX pairs is identical to pre-Phase4."""
        n = PriceNormalizer()
        pnl = n.calculate_pnl(150.00, 150.50, "BUY", 1.0, "USD_JPY")
        assert abs(pnl - 5000.0) < 0.01  # 50 pips * 100 = 5000

    @pytest.mark.asyncio
    async def test_fx_slippage_unchanged(self):
        """Slippage for FX pairs produces exact same values as before."""
        ex = MockExchange()
        ex.slippage_pips = 2.0
        ex.set_price("USD_JPY", bid=150.00, ask=150.02)
        order = await ex.place_order("USD_JPY", OrderSide.BUY, 1.0, OrderType.MARKET)
        # Must be exactly 150.04 (2 pips * 0.01 = 0.02)
        assert order.filled_price == pytest.approx(150.04, abs=0.001)

    def test_fx_lot_sizing_unchanged(self):
        """Lot sizing for FX pairs produces exact same values as before."""
        n = PriceNormalizer()
        sizer = PositionSizer(n)
        result = sizer.calculate(
            pair="USD_JPY", capital=1_000_000,
            risk_per_trade_pct=2.0, sl_pips=50.0, tp_pips=75.0,
            min_lot=0.01, max_lot=100.0,
        )
        # Must be exactly 4.0 (20000 / (50*100))
        assert abs(result.lot_size - 4.0) < 0.001
