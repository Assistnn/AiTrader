"""
Indicator Engine tests.
Reference: 02_データパイプライン Section 4, 13_テスト戦略
"""

from datetime import datetime, timezone

from app.services.pipeline.data_types import OHLCV
from app.services.pipeline.indicator_engine import (
    ATRState,
    BollingerState,
    DonchianState,
    EMAState,
    IndicatorEngine,
    RSIState,
)


def _bar(close: float, high: float | None = None, low: float | None = None, ts_offset: int = 0) -> OHLCV:
    """Helper to create a simple OHLCV bar."""
    h = high if high is not None else close + 0.5
    lo = low if low is not None else close - 0.5
    return OHLCV(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        open=close,
        high=h,
        low=lo,
        close=close,
        volume=100.0,
    )


class TestEMA:
    def test_warmup_returns_none(self):
        ema = EMAState(period=3)
        assert ema.update(10.0) is None
        assert ema.update(11.0) is None

    def test_initial_value_is_sma(self):
        ema = EMAState(period=3)
        ema.update(10.0)
        ema.update(11.0)
        val = ema.update(12.0)
        assert val == (10.0 + 11.0 + 12.0) / 3  # SMA

    def test_subsequent_updates(self):
        ema = EMAState(period=3)
        for v in [10.0, 11.0, 12.0]:
            ema.update(v)
        val = ema.update(13.0)
        k = 2.0 / (3 + 1)
        expected = 13.0 * k + 11.0 * (1 - k)
        assert abs(val - expected) < 1e-6


class TestATR:
    def test_warmup_returns_none(self):
        atr = ATRState(period=3)
        assert atr.update(_bar(100.0)) is None  # first bar: sets prev_close
        assert atr.update(_bar(101.0)) is None  # count=1
        assert atr.update(_bar(102.0)) is None  # count=2

    def test_initial_atr(self):
        atr = ATRState(period=3)
        bars = [_bar(100.0 + i) for i in range(5)]
        results = [atr.update(b) for b in bars]
        # After period+1 bars, ATR should be available
        assert results[3] is not None  # 4th bar completes warmup


class TestRSI:
    def test_warmup_returns_none(self):
        rsi = RSIState(period=3)
        assert rsi.update(100.0) is None
        assert rsi.update(101.0) is None
        assert rsi.update(102.0) is None

    def test_all_gains_returns_100(self):
        rsi = RSIState(period=3)
        for v in [100.0, 101.0, 102.0, 103.0]:
            result = rsi.update(v)
        assert result == 100.0

    def test_rsi_range(self):
        rsi = RSIState(period=14)
        prices = [100 + i * 0.1 * ((-1) ** i) for i in range(20)]
        result = None
        for p in prices:
            result = rsi.update(p)
        assert result is not None
        assert 0 <= result <= 100


class TestDonchian:
    def test_warmup(self):
        don = DonchianState(period=3)
        r = don.update(_bar(100.0, high=101.0, low=99.0))
        assert r["donchian20_upper"] is None

    def test_values(self):
        don = DonchianState(period=3)
        don.update(_bar(100.0, high=102.0, low=98.0))
        don.update(_bar(101.0, high=103.0, low=99.0))
        r = don.update(_bar(100.5, high=101.5, low=100.0))
        assert r["donchian20_upper"] == 103.0
        assert r["donchian20_lower"] == 98.0


class TestBollinger:
    def test_warmup(self):
        bb = BollingerState(period=3, stddev_mult=2.0)
        r = bb.update(100.0)
        assert r["bb20_upper"] is None

    def test_values(self):
        bb = BollingerState(period=3, stddev_mult=2.0)
        bb.update(100.0)
        bb.update(101.0)
        r = bb.update(102.0)
        assert r["bb20_middle"] is not None
        assert r["bb20_upper"] > r["bb20_middle"] > r["bb20_lower"]


class TestIndicatorEngine:
    def test_full_pipeline(self):
        from datetime import timedelta

        engine = IndicatorEngine()
        pair = "USD_JPY"
        tf = "H1"

        # Feed enough bars for warmup (EMA200 needs 200+)
        base_ts = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        for i in range(210):
            bar = OHLCV(
                timestamp=base_ts + timedelta(hours=i),
                open=100.0 + i * 0.1,
                high=100.5 + i * 0.1,
                low=99.5 + i * 0.1,
                close=100.0 + i * 0.1,
                volume=1000.0,
            )
            snapshot = engine.update(pair, tf, bar)

        # After 210 bars, all indicators should be available
        v = snapshot.values
        assert v["ema20"] is not None
        assert v["ema50"] is not None
        assert v["ema200"] is not None
        assert v["adx14"] is not None
        assert v["atr14"] is not None
        assert v["rsi14"] is not None
        assert v["bb20_upper"] is not None
        assert v["donchian20_upper"] is not None

    def test_get_snapshot(self):
        engine = IndicatorEngine()
        bar = _bar(100.0)
        engine.update("USD_JPY", "H1", bar)
        snap = engine.get_snapshot("USD_JPY", "H1")
        assert snap is not None
        assert snap.pair == "USD_JPY"

    def test_nonexistent_snapshot_returns_none(self):
        engine = IndicatorEngine()
        assert engine.get_snapshot("XYZ", "H1") is None
