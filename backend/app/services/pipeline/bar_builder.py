"""
Bar Builder: tick -> OHLC bar generation.

Reference: 02_データパイプライン Section 3
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.pipeline.data_types import OHLCV, BarClosedEvent

# Timeframe durations in seconds
TIMEFRAME_SECONDS: dict[str, int] = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}

# All supported timeframes (Section 3-2)
TIMEFRAMES = list(TIMEFRAME_SECONDS.keys())


def get_period_start(timestamp: datetime, timeframe: str, d1_base_hour_utc: int = 15) -> datetime:
    """Calculate the period start time for a given timestamp and timeframe."""
    from datetime import timedelta

    ts = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp

    if timeframe == "D1":
        # D1 base: configurable, default UTC 15:00 (= JST 00:00)
        base = ts.replace(hour=d1_base_hour_utc, minute=0, second=0, microsecond=0)
        if ts < base:
            base = base - timedelta(days=1)
        return base

    seconds = TIMEFRAME_SECONDS[timeframe]
    epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    total_seconds = (ts - epoch).total_seconds()
    period_start_seconds = (total_seconds // seconds) * seconds
    return epoch + timedelta(seconds=period_start_seconds)


@dataclass
class BarAccumulator:
    """Accumulates ticks into an in-progress bar. Reference: Section 3-3"""

    pair: str
    timeframe: str
    period_start: datetime
    open: float | None = None
    high: float = float("-inf")
    low: float = float("inf")
    close: float | None = None
    volume: float = 0.0
    tick_count: int = 0

    def update(self, price: float, volume: float = 0.0) -> None:
        """Called on each tick reception."""
        if self.open is None:
            self.open = price
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += volume
        self.tick_count += 1

    def finalize(self) -> OHLCV:
        """Emit finalized OHLCV bar."""
        return OHLCV(
            timestamp=self.period_start,
            open=self.open if self.open is not None else 0.0,
            high=self.high if self.high != float("-inf") else 0.0,
            low=self.low if self.low != float("inf") else 0.0,
            close=self.close if self.close is not None else 0.0,
            volume=self.volume,
        )


class BarBuilder:
    """
    Builds OHLC bars from ticks or KLine API data.

    Reference: 02_データパイプライン Section 3
    """

    def __init__(self, d1_base_hour_utc: int = 15):
        self.d1_base_hour_utc = d1_base_hour_utc
        # pair -> timeframe -> BarAccumulator
        self._accumulators: dict[str, dict[str, BarAccumulator]] = defaultdict(dict)

    def on_tick(self, pair: str, price: float, volume: float, timestamp: datetime) -> list[BarClosedEvent]:
        """
        Process a tick and return any bars that closed.
        Reference: Section 3-3 Method B
        """
        events: list[BarClosedEvent] = []

        for tf in TIMEFRAMES:
            period_start = get_period_start(timestamp, tf, self.d1_base_hour_utc)
            acc = self._accumulators[pair].get(tf)

            if acc is not None and acc.period_start != period_start:
                # Period changed -> finalize previous bar
                bar = acc.finalize()
                events.append(BarClosedEvent(
                    pair=pair, timeframe=tf, bar=bar, timestamp=timestamp
                ))
                acc = None

            if acc is None:
                acc = BarAccumulator(pair=pair, timeframe=tf, period_start=period_start)
                self._accumulators[pair][tf] = acc

            acc.update(price, volume)

        return events

    def on_bar(self, pair: str, timeframe: str, bar: OHLCV) -> BarClosedEvent:
        """
        Process a completed bar from KLine API (Method A).
        Reference: Section 3-3 Method A
        """
        return BarClosedEvent(
            pair=pair, timeframe=timeframe, bar=bar, timestamp=bar.timestamp
        )
