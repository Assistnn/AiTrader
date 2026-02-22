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
