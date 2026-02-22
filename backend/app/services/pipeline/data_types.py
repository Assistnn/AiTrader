"""
Shared data types for the data pipeline.

Reference: 02_データパイプライン Section 2-3, 3-6, 4-5, 5-2
"""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

# CLAUDE.md: float32 for price/indicator data (sufficient for FX 3-5 decimal precision)
PRICE_DTYPE = np.float32
INDICATOR_DTYPE = np.float32


@dataclass
class OHLCV:
    """OHLCV bar data. Reference: Section 2-3"""

    timestamp: datetime  # UTC
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Ticker:
    """Ticker information. Reference: Section 2-3"""

    timestamp: datetime  # UTC
    bid: float
    ask: float
    last: float
    volume: float


@dataclass
class Spread:
    """Spread information. Reference: Section 2-3"""

    timestamp: datetime  # UTC
    bid: float
    ask: float
    spread_raw: float  # ask - bid
    spread_pips: float  # converted by PriceNormalizer


@dataclass
class BarClosedEvent:
    """Bar closed event. Reference: Section 3-6"""

    pair: str
    timeframe: str  # M1, M5, M15, M30, H1, H4, D1
    bar: OHLCV
    timestamp: datetime  # event emission time (UTC)


@dataclass
class IndicatorSnapshot:
    """Indicator values at a point in time. Reference: Section 4-5"""

    pair: str
    timeframe: str
    timestamp: datetime  # bar close time (UTC)
    values: dict[str, float | None]  # indicator_name -> value


@dataclass
class QualityReport:
    """Data quality report from DataQualityGate. Reference: Section 6-3"""

    total: int
    passed: int
    degraded: int
    replaced: int
    missing: int


@dataclass
class StateSnapshot:
    """State snapshot for the decision pipeline. Reference: Section 5-2"""

    pair: str
    timestamp: datetime  # UTC
    trade_allowed: bool  # False if warmup insufficient or data quality issue

    # State labels
    trend: str  # "UP" | "DOWN" | "NEUTRAL"
    regime: str  # "trend" | "range"
    volatility: str  # "low" | "normal" | "high" | "extreme"

    # Indicator snapshots per timeframe
    indicators: dict[str, IndicatorSnapshot]  # timeframe -> IndicatorSnapshot

    # EMA alignment (for M1)
    ema_alignment: str  # "bullish" | "bearish" | "mixed"

    # RSI zone (for M2)
    rsi_zone: str  # "oversold" | "neutral" | "overbought"

    # Bollinger Band position (for M2)
    bb_position: str  # "below_lower" | "lower_half" | "middle" | "upper_half" | "above_upper"

    # Swing info
    swing_high: float | None = None
    swing_low: float | None = None

    # Data quality
    data_quality: str = "ok"  # "ok" | "degraded" | "missing"
    quality_issues: list[str] = field(default_factory=list)
