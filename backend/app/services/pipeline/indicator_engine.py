"""
Indicator Engine: incremental technical indicator calculation.

Reference: 02_データパイプライン Section 4
All indicators use O(1) incremental updates (except ring-buffer based ones which are O(window)).
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.services.pipeline.data_types import INDICATOR_DTYPE, IndicatorSnapshot, OHLCV


# ---------------------------------------------------------------------------
# Individual indicator state objects
# ---------------------------------------------------------------------------


@dataclass
class EMAState:
    """EMA incremental state. Reference: Section 4-3"""

    period: int
    k: float = 0.0
    value: float | None = None
    count: int = 0
    _sum: float = 0.0

    def __post_init__(self):
        self.k = 2.0 / (self.period + 1)

    def update(self, close: float) -> float | None:
        self.count += 1
        if self.count < self.period:
            self._sum += close
            return None
        if self.count == self.period:
            self._sum += close
            self.value = self._sum / self.period
            return self.value
        self.value = close * self.k + self.value * (1 - self.k)
        return self.value


@dataclass
class ADXState:
    """ADX incremental state. Reference: Section 4-3"""

    period: int = 14
    smoothed_plus_dm: float = 0.0
    smoothed_minus_dm: float = 0.0
    smoothed_tr: float = 0.0
    prev_adx: float | None = None
    prev_bar: OHLCV | None = None
    count: int = 0
    _dx_sum: float = 0.0
    _dx_count: int = 0
    _init_plus_dm: float = 0.0
    _init_minus_dm: float = 0.0
    _init_tr: float = 0.0

    def update(self, bar: OHLCV) -> dict[str, float | None]:
        """Returns dict with 'adx14', 'plus_di', 'minus_di'."""
        result: dict[str, float | None] = {"adx14": None, "plus_di": None, "minus_di": None}

        if self.prev_bar is None:
            self.prev_bar = bar
            return result

        # Calculate +DM, -DM, TR
        high_diff = bar.high - self.prev_bar.high
        low_diff = self.prev_bar.low - bar.low
        plus_dm = max(high_diff, 0.0) if high_diff > low_diff else 0.0
        minus_dm = max(low_diff, 0.0) if low_diff > high_diff else 0.0
        tr = max(
            bar.high - bar.low,
            abs(bar.high - self.prev_bar.close),
            abs(bar.low - self.prev_bar.close),
        )

        self.count += 1
        self.prev_bar = bar

        if self.count < self.period:
            self._init_plus_dm += plus_dm
            self._init_minus_dm += minus_dm
            self._init_tr += tr
            return result

        if self.count == self.period:
            self.smoothed_plus_dm = self._init_plus_dm + plus_dm
            self.smoothed_minus_dm = self._init_minus_dm + minus_dm
            self.smoothed_tr = self._init_tr + tr
        else:
            self.smoothed_plus_dm = self.smoothed_plus_dm - (self.smoothed_plus_dm / self.period) + plus_dm
            self.smoothed_minus_dm = self.smoothed_minus_dm - (self.smoothed_minus_dm / self.period) + minus_dm
            self.smoothed_tr = self.smoothed_tr - (self.smoothed_tr / self.period) + tr

        if self.smoothed_tr == 0:
            return result

        plus_di = (self.smoothed_plus_dm / self.smoothed_tr) * 100
        minus_di = (self.smoothed_minus_dm / self.smoothed_tr) * 100
        di_sum = plus_di + minus_di
        dx = (abs(plus_di - minus_di) / di_sum * 100) if di_sum != 0 else 0.0

        self._dx_count += 1
        if self._dx_count < self.period:
            self._dx_sum += dx
            result["plus_di"] = plus_di
            result["minus_di"] = minus_di
            return result

        if self._dx_count == self.period:
            self.prev_adx = self._dx_sum + dx
            self.prev_adx /= self.period
        else:
            self.prev_adx = (self.prev_adx * (self.period - 1) + dx) / self.period

        result["adx14"] = self.prev_adx
        result["plus_di"] = plus_di
        result["minus_di"] = minus_di
        return result


@dataclass
class ATRState:
    """ATR incremental state. Reference: Section 4-3"""

    period: int = 14
    prev_atr: float | None = None
    prev_close: float | None = None
    count: int = 0
    _tr_sum: float = 0.0

    def update(self, bar: OHLCV) -> float | None:
        if self.prev_close is None:
            self.prev_close = bar.close
            return None

        tr = max(
            bar.high - bar.low,
            abs(bar.high - self.prev_close),
            abs(bar.low - self.prev_close),
        )
        self.prev_close = bar.close
        self.count += 1

        if self.count < self.period:
            self._tr_sum += tr
            return None
        if self.count == self.period:
            self._tr_sum += tr
            self.prev_atr = self._tr_sum / self.period
            return self.prev_atr

        self.prev_atr = self.prev_atr * (self.period - 1) / self.period + tr / self.period
        return self.prev_atr


@dataclass
class DonchianState:
    """Donchian Channel state with ring buffer. Reference: Section 4-3"""

    period: int = 20
    highs: deque = field(default_factory=lambda: deque(maxlen=20))
    lows: deque = field(default_factory=lambda: deque(maxlen=20))

    def __post_init__(self):
        self.highs = deque(maxlen=self.period)
        self.lows = deque(maxlen=self.period)

    def update(self, bar: OHLCV) -> dict[str, float | None]:
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        if len(self.highs) < self.period:
            return {"donchian20_upper": None, "donchian20_lower": None, "donchian20_middle": None}

        upper = max(self.highs)
        lower = min(self.lows)
        return {
            "donchian20_upper": upper,
            "donchian20_lower": lower,
            "donchian20_middle": (upper + lower) / 2,
        }


@dataclass
class RSIState:
    """RSI incremental state. Reference: Section 4-3"""

    period: int = 14
    avg_gain: float = 0.0
    avg_loss: float = 0.0
    prev_close: float | None = None
    count: int = 0
    _gain_sum: float = 0.0
    _loss_sum: float = 0.0

    def update(self, close: float) -> float | None:
        if self.prev_close is None:
            self.prev_close = close
            return None

        change = close - self.prev_close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self.prev_close = close
        self.count += 1

        if self.count < self.period:
            self._gain_sum += gain
            self._loss_sum += loss
            return None
        if self.count == self.period:
            self._gain_sum += gain
            self._loss_sum += loss
            self.avg_gain = self._gain_sum / self.period
            self.avg_loss = self._loss_sum / self.period
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period

        if self.avg_loss == 0:
            return 100.0
        rs = self.avg_gain / self.avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


@dataclass
class BollingerState:
    """Bollinger Bands state with ring buffer. Reference: Section 4-3"""

    period: int = 20
    stddev_mult: float = 2.0
    closes: deque = field(default_factory=lambda: deque(maxlen=20))

    def __post_init__(self):
        self.closes = deque(maxlen=self.period)

    def update(self, close: float) -> dict[str, float | None]:
        self.closes.append(close)

        if len(self.closes) < self.period:
            return {
                "bb20_upper": None, "bb20_middle": None,
                "bb20_lower": None, "bb20_bandwidth": None,
            }

        arr = np.array(self.closes, dtype=INDICATOR_DTYPE)
        middle = float(np.mean(arr))
        sigma = float(np.std(arr, ddof=0))
        upper = middle + self.stddev_mult * sigma
        lower = middle - self.stddev_mult * sigma

        bandwidth = (upper - lower) / middle * 100 if middle != 0 else 0.0
        return {
            "bb20_upper": upper,
            "bb20_middle": middle,
            "bb20_lower": lower,
            "bb20_bandwidth": bandwidth,
        }


@dataclass
class SwingState:
    """Swing High/Low detection. Reference: Section 4-3"""

    lookback: int = 5
    highs: deque = field(default_factory=lambda: deque(maxlen=5))
    lows: deque = field(default_factory=lambda: deque(maxlen=5))
    last_swing_high: float | None = None
    last_swing_low: float | None = None

    def __post_init__(self):
        self.highs = deque(maxlen=self.lookback)
        self.lows = deque(maxlen=self.lookback)

    def update(self, bar: OHLCV) -> dict[str, float | None]:
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        if len(self.highs) >= self.lookback:
            mid = self.lookback // 2  # center index
            h = self.highs
            if h[mid] > h[mid - 1] and h[mid] > h[mid - 2] and h[mid] > h[mid + 1] and h[mid] > h[mid + 2]:
                self.last_swing_high = h[mid]

            lo = self.lows
            if lo[mid] < lo[mid - 1] and lo[mid] < lo[mid - 2] and lo[mid] < lo[mid + 1] and lo[mid] < lo[mid + 2]:
                self.last_swing_low = lo[mid]

        return {"swing_high": self.last_swing_high, "swing_low": self.last_swing_low}


# ---------------------------------------------------------------------------
# Indicator Engine
# ---------------------------------------------------------------------------


@dataclass
class IndicatorConfig:
    """Configuration for IndicatorEngine. Reference: Section 11-1"""

    ema_periods: list[int] = field(default_factory=lambda: [20, 50, 200])
    adx_period: int = 14
    atr_period: int = 14
    donchian_period: int = 20
    rsi_period: int = 14
    bb_period: int = 20
    bb_stddev: float = 2.0
    swing_lookback: int = 5


class IndicatorEngine:
    """
    Incremental technical indicator calculation engine.

    Reference: 02_データパイプライン Section 4
    Calculates all indicators for all pair/timeframe combinations.
    """

    def __init__(self, config: IndicatorConfig | None = None):
        self.config = config or IndicatorConfig()
        # pair -> timeframe -> indicator states
        self._states: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
        # pair -> timeframe -> latest IndicatorSnapshot
        self._snapshots: dict[str, dict[str, IndicatorSnapshot]] = defaultdict(dict)

    def _get_states(self, pair: str, timeframe: str) -> dict:
        """Lazy-initialize indicator states for a pair/timeframe."""
        states = self._states[pair][timeframe]
        if not states:
            cfg = self.config
            states["ema"] = {p: EMAState(period=p) for p in cfg.ema_periods}
            states["adx"] = ADXState(period=cfg.adx_period)
            states["atr"] = ATRState(period=cfg.atr_period)
            states["donchian"] = DonchianState(period=cfg.donchian_period)
            states["rsi"] = RSIState(period=cfg.rsi_period)
            states["bollinger"] = BollingerState(period=cfg.bb_period, stddev_mult=cfg.bb_stddev)
            states["swing"] = SwingState(lookback=cfg.swing_lookback)
            self._states[pair][timeframe] = states
        return states

    def update(self, pair: str, timeframe: str, bar: OHLCV) -> IndicatorSnapshot:
        """
        Update all indicators with a new bar and return the snapshot.

        This is the main entry point, called on each BarClosedEvent.
        """
        states = self._get_states(pair, timeframe)
        values: dict[str, float | None] = {}

        # EMA
        for period, ema_state in states["ema"].items():
            val = ema_state.update(bar.close)
            values[f"ema{period}"] = val

        # ADX
        adx_result = states["adx"].update(bar)
        values.update(adx_result)

        # ATR
        values["atr14"] = states["atr"].update(bar)

        # Donchian
        donchian_result = states["donchian"].update(bar)
        values.update(donchian_result)

        # RSI
        values["rsi14"] = states["rsi"].update(bar.close)

        # Bollinger Bands
        bb_result = states["bollinger"].update(bar.close)
        values.update(bb_result)

        # Swing
        swing_result = states["swing"].update(bar)
        values.update(swing_result)

        snapshot = IndicatorSnapshot(
            pair=pair,
            timeframe=timeframe,
            timestamp=bar.timestamp,
            values=values,
        )
        self._snapshots[pair][timeframe] = snapshot
        return snapshot

    def get_snapshot(self, pair: str, timeframe: str) -> IndicatorSnapshot | None:
        """Get the latest indicator snapshot for a pair/timeframe."""
        return self._snapshots.get(pair, {}).get(timeframe)

    def get_all_snapshots(self, pair: str) -> dict[str, IndicatorSnapshot]:
        """Get all timeframe snapshots for a pair."""
        return dict(self._snapshots.get(pair, {}))
