"""
State Builder tests.
Reference: 02_データパイプライン Section 5, 13_テスト戦略
"""

from datetime import datetime, timezone

from app.services.pipeline.data_types import IndicatorSnapshot
from app.services.pipeline.state_builder import StateBuilder, StateBuilderConfig


def _snapshot(values: dict[str, float | None]) -> IndicatorSnapshot:
    """Helper to create an IndicatorSnapshot with given values."""
    return IndicatorSnapshot(
        pair="USD_JPY",
        timeframe="H1",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        values=values,
    )


class TestTrend:
    def test_uptrend(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "ema200": 145.0, "adx14": 30.0,
                          "atr14": 1.0, "rsi14": 55.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trend == "UP"

    def test_downtrend(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 145.0, "ema50": 148.0, "ema200": 150.0, "adx14": 30.0,
                          "atr14": 1.0, "rsi14": 45.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trend == "DOWN"

    def test_neutral_low_adx(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 149.0, "ema200": 148.0, "adx14": 15.0,
                          "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trend == "NEUTRAL"


class TestRegime:
    def test_trending(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 30.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.regime == "trend"

    def test_ranging(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 149.5, "adx14": 15.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.regime == "range"


class TestVolatility:
    def test_normal_volatility(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        # Feed enough ATR history
        for _ in range(5):
            sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.volatility == "normal"


class TestRSIZone:
    def test_oversold(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 25.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.rsi_zone == "oversold"

    def test_overbought(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 75.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.rsi_zone == "overbought"


class TestTradeAllowed:
    def test_missing_data_quality(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap}, data_quality="missing")
        assert result.trade_allowed is False

    def test_warmup_insufficient(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": None, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trade_allowed is False

    def test_no_primary_timeframe(self):
        sb = StateBuilder()
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {})
        assert result.trade_allowed is False

    def test_ok_when_all_present(self):
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trade_allowed is True


# ===========================================================================
# Boundary value tests (Step 4)
# ===========================================================================


class TestTrendBoundary:
    def test_adx_at_threshold_25(self):
        """ADX exactly at 25.0 → trend detected."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "ema200": 145.0, "adx14": 25.0,
                          "atr14": 1.0, "rsi14": 55.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trend == "UP"

    def test_adx_just_below_25(self):
        """ADX at 24.9 → NEUTRAL."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "ema200": 145.0, "adx14": 24.9,
                          "atr14": 1.0, "rsi14": 55.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trend == "NEUTRAL"

    def test_up_without_ema200(self):
        """EMA200=None, ema20 > ema50 + ADX >= 25 → UP."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 30.0,
                          "atr14": 1.0, "rsi14": 55.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trend == "UP"

    def test_down_without_ema200(self):
        """EMA200=None, ema20 < ema50 + ADX >= 25 → DOWN."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 146.0, "ema50": 148.0, "adx14": 30.0,
                          "atr14": 1.0, "rsi14": 45.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.trend == "DOWN"

    def test_neutral_when_essential_none(self):
        """Any essential indicator is None → NEUTRAL."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": None, "ema50": 148.0, "adx14": 30.0,
                          "atr14": 1.0, "rsi14": 55.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        # trade_allowed is False due to warmup, but trend calc gets "NEUTRAL"
        assert result.trend == "NEUTRAL"


class TestRegimeBoundary:
    def test_adx_at_range_threshold(self):
        """ADX = 20.0 → range."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 20.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.regime == "range"

    def test_adx_between_20_and_25(self):
        """ADX = 22.0 → range (below trend_adx_threshold)."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 22.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.regime == "range"

    def test_adx_none(self):
        """ADX = None → range."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": None, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        # trade_allowed False because adx14 is None
        assert result.regime == "range"


class TestRSIZoneBoundary:
    def test_rsi_at_30(self):
        """RSI = 30.0 → neutral (< 30 for oversold)."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 30.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.rsi_zone == "neutral"

    def test_rsi_at_29_9(self):
        """RSI = 29.9 → oversold."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 29.9})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.rsi_zone == "oversold"

    def test_rsi_at_70(self):
        """RSI = 70.0 → neutral (> 70 for overbought)."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 70.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.rsi_zone == "neutral"

    def test_rsi_at_70_1(self):
        """RSI = 70.1 → overbought."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 70.1})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.rsi_zone == "overbought"


class TestVolatilityBoundary:
    def _build_with_atr_history(self, atr_values: list[float]) -> str:
        """Build state with ATR history and return volatility label."""
        sb = StateBuilder()
        for atr in atr_values:
            snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0,
                              "atr14": atr, "rsi14": 50.0})
            result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        return result.volatility

    def test_extreme_volatility(self):
        """ATR ratio > 2.0 → extreme."""
        # history of 1.0, then spike to 3.0 → ratio = 3.0/avg(1,1,1,1,3)=3/1.4 ≈ 2.14
        vol = self._build_with_atr_history([1.0, 1.0, 1.0, 1.0, 3.0])
        assert vol == "extreme"

    def test_high_volatility(self):
        """ATR ratio > 1.3 → high."""
        # history of 1.0, then moderate spike to 1.5
        vol = self._build_with_atr_history([1.0, 1.0, 1.0, 1.0, 1.5])
        assert vol == "high"

    def test_low_volatility(self):
        """ATR ratio < 0.7 → low."""
        # history of 1.0, then drop to 0.5
        vol = self._build_with_atr_history([1.0, 1.0, 1.0, 1.0, 0.5])
        assert vol == "low"

    def test_atr_none(self):
        """ATR=None → normal."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0,
                          "atr14": None, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        # trade_allowed False because atr14 is None, volatility defaults
        assert result.volatility == "normal"

    def test_avg_atr_zero(self):
        """avg_atr=0 → normal."""
        vol = self._build_with_atr_history([0.0, 0.0, 0.0])
        assert vol == "normal"


class TestEmaAlignmentBoundary:
    def test_bearish_without_ema200(self):
        """EMA200=None, ema20 < ema50 → bearish."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 146.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.ema_alignment == "bearish"

    def test_bullish_without_ema200(self):
        """EMA200=None, ema20 > ema50 → bullish."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.ema_alignment == "bullish"

    def test_mixed_when_ema20_none(self):
        """EMA20=None → mixed."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": None, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.ema_alignment == "mixed"

    def test_bearish_with_ema200(self):
        """ema20 < ema50 < ema200 → bearish."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 145.0, "ema50": 148.0, "ema200": 150.0,
                          "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.ema_alignment == "bearish"

    def test_mixed_when_not_aligned(self):
        """ema20 > ema50 but ema200 > ema20 → mixed."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 149.0, "ema50": 148.0, "ema200": 150.0,
                          "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.ema_alignment == "mixed"


class TestBBPositionBoundary:
    def test_below_lower(self):
        """close < bb_lower → below_lower."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 145.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0,
                          "rsi14": 25.0, "bb20_upper": 152.0, "bb20_lower": 146.0, "bb20_middle": 149.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.bb_position == "below_lower"

    def test_above_upper(self):
        """close > bb_upper → above_upper."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 155.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0,
                          "rsi14": 75.0, "bb20_upper": 152.0, "bb20_lower": 146.0, "bb20_middle": 149.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.bb_position == "above_upper"

    def test_lower_half(self):
        """bb_lower <= close < bb_middle → lower_half."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 147.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0,
                          "rsi14": 45.0, "bb20_upper": 152.0, "bb20_lower": 146.0, "bb20_middle": 149.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.bb_position == "lower_half"

    def test_upper_half(self):
        """bb_middle < close <= bb_upper → upper_half."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 151.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0,
                          "rsi14": 55.0, "bb20_upper": 152.0, "bb20_lower": 146.0, "bb20_middle": 149.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.bb_position == "upper_half"

    def test_middle_when_bb_none(self):
        """BB values None → middle."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": 150.0, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0, "rsi14": 50.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.bb_position == "middle"

    def test_middle_when_close_none(self):
        """ema20 (proxy for close) is None → middle."""
        sb = StateBuilder()
        snap = _snapshot({"ema20": None, "ema50": 148.0, "adx14": 25.0, "atr14": 1.0,
                          "rsi14": 50.0, "bb20_upper": 152.0, "bb20_lower": 146.0, "bb20_middle": 149.0})
        result = sb.build("USD_JPY", datetime.now(timezone.utc), {"H1": snap})
        assert result.bb_position == "middle"
