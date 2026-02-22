"""
Bar Builder tests.
Reference: 02_データパイプライン Section 3, 13_テスト戦略
"""

from datetime import datetime, timezone

from app.services.pipeline.bar_builder import BarBuilder, get_period_start
from app.services.pipeline.data_types import OHLCV


class TestGetPeriodStart:
    def test_m1(self):
        ts = datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
        ps = get_period_start(ts, "M1")
        assert ps.minute == 34
        assert ps.second == 0

    def test_m5(self):
        ts = datetime(2024, 1, 1, 12, 37, 0, tzinfo=timezone.utc)
        ps = get_period_start(ts, "M5")
        assert ps.minute == 35

    def test_h1(self):
        ts = datetime(2024, 1, 1, 12, 37, 0, tzinfo=timezone.utc)
        ps = get_period_start(ts, "H1")
        assert ps.hour == 12
        assert ps.minute == 0

    def test_h4(self):
        ts = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        ps = get_period_start(ts, "H4")
        assert ps.hour == 8


class TestBarBuilder:
    def test_on_bar(self):
        bb = BarBuilder()
        bar = OHLCV(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1000.0,
        )
        event = bb.on_bar("USD_JPY", "H1", bar)
        assert event.pair == "USD_JPY"
        assert event.timeframe == "H1"
        assert event.bar.close == 100.5

    def test_on_tick_accumulates(self):
        bb = BarBuilder()
        ts = datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        events = bb.on_tick("USD_JPY", 100.0, 10.0, ts)
        # No bar should close on first tick
        assert len(events) == 0

    def test_on_tick_bar_close(self):
        bb = BarBuilder()
        # Tick in period 1
        ts1 = datetime(2024, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
        bb.on_tick("USD_JPY", 100.0, 10.0, ts1)

        # Tick in period 2 -> M1 bar should close
        ts2 = datetime(2024, 1, 1, 12, 1, 30, tzinfo=timezone.utc)
        events = bb.on_tick("USD_JPY", 101.0, 10.0, ts2)

        m1_events = [e for e in events if e.timeframe == "M1"]
        assert len(m1_events) == 1
        assert m1_events[0].bar.close == 100.0
        assert m1_events[0].bar.open == 100.0
