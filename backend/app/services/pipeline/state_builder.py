"""
State Builder: numeric indicators -> state labels.

Reference: 02_データパイプライン Section 5

Converts IndicatorEngine numeric output to categorical state labels
consumed by the Decision Pipeline and Guard Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.services.pipeline.data_types import IndicatorSnapshot, StateSnapshot


@dataclass
class StateBuilderConfig:
    """Configuration for StateBuilder. Reference: Section 11-1"""

    trend_adx_threshold: float = 25.0
    range_adx_threshold: float = 20.0
    volatility_low_ratio: float = 0.7
    volatility_high_ratio: float = 1.3
    volatility_extreme_ratio: float = 2.0
    volatility_atr_lookback: int = 20

    # Timeframe mapping per decision stage (Section 4-6)
    # M1 direction: D1, H4, H1
    # M2 setup: H1, M30, M15
    # M3 entry: M5, M1
    # M4 exit: M5, M1
    primary_timeframe: str = "H1"


class StateBuilder:
    """
    Converts numeric indicators to state labels.

    Reference: 02_データパイプライン Section 5
    """

    def __init__(self, config: StateBuilderConfig | None = None):
        self.config = config or StateBuilderConfig()
        # pair -> deque of recent ATR values for volatility ratio
        self._atr_history: dict[str, list[float]] = {}

    def build(
        self,
        pair: str,
        timestamp: datetime,
        indicators: dict[str, IndicatorSnapshot],
        data_quality: str = "ok",
        quality_issues: list[str] | None = None,
    ) -> StateSnapshot:
        """
        Build a StateSnapshot from indicator snapshots.

        Args:
            pair: currency pair
            timestamp: current time (UTC)
            indicators: timeframe -> IndicatorSnapshot
            data_quality: from DataQualityGate
            quality_issues: list of quality issue descriptions
        """
        cfg = self.config
        issues = quality_issues or []

        # Check if essential indicators are available
        trade_allowed = True
        primary = indicators.get(cfg.primary_timeframe)

        if primary is None or data_quality == "missing":
            return self._empty_snapshot(pair, timestamp, data_quality, issues)

        v = primary.values

        # Check warmup: essential indicators must not be None
        essential_keys = ["ema20", "ema50", "adx14", "atr14", "rsi14"]
        for key in essential_keys:
            if v.get(key) is None:
                trade_allowed = False
                issues.append(f"warmup: {key} is None")

        if not trade_allowed:
            return self._empty_snapshot(
                pair, timestamp, data_quality if data_quality != "ok" else "degraded",
                issues, trade_allowed=False, indicators=indicators,
            )

        # --- State label conversions (Section 5-3) ---

        # trend
        trend = self._calc_trend(v)

        # regime
        regime = self._calc_regime(v)

        # volatility
        volatility = self._calc_volatility(pair, v)

        # ema_alignment
        ema_alignment = self._calc_ema_alignment(v)

        # rsi_zone
        rsi_zone = self._calc_rsi_zone(v)

        # bb_position
        bb_position = self._calc_bb_position(v, primary)

        return StateSnapshot(
            pair=pair,
            timestamp=timestamp,
            trade_allowed=trade_allowed and data_quality != "missing",
            trend=trend,
            regime=regime,
            volatility=volatility,
            indicators=indicators,
            ema_alignment=ema_alignment,
            rsi_zone=rsi_zone,
            bb_position=bb_position,
            swing_high=v.get("swing_high"),
            swing_low=v.get("swing_low"),
            data_quality=data_quality,
            quality_issues=issues,
        )

    def _calc_trend(self, v: dict[str, float | None]) -> str:
        """Reference: Section 5-3 trend"""
        ema20 = v.get("ema20")
        ema50 = v.get("ema50")
        ema200 = v.get("ema200")
        adx = v.get("adx14")

        if any(x is None for x in (ema20, ema50, adx)):
            return "NEUTRAL"

        if ema200 is not None:
            if ema20 > ema50 > ema200 and adx >= self.config.trend_adx_threshold:
                return "UP"
            if ema20 < ema50 < ema200 and adx >= self.config.trend_adx_threshold:
                return "DOWN"
        else:
            # EMA200 not yet available, use EMA20/50 only
            if ema20 > ema50 and adx >= self.config.trend_adx_threshold:
                return "UP"
            if ema20 < ema50 and adx >= self.config.trend_adx_threshold:
                return "DOWN"

        return "NEUTRAL"

    def _calc_regime(self, v: dict[str, float | None]) -> str:
        """Reference: Section 5-3 regime"""
        adx = v.get("adx14")
        if adx is None:
            return "range"
        if adx >= self.config.trend_adx_threshold:
            return "trend"
        if adx < self.config.range_adx_threshold:
            return "range"
        return "range"

    def _calc_volatility(self, pair: str, v: dict[str, float | None]) -> str:
        """Reference: Section 5-3 volatility"""
        cfg = self.config
        atr = v.get("atr14")
        if atr is None:
            return "normal"

        if pair not in self._atr_history:
            self._atr_history[pair] = []

        self._atr_history[pair].append(atr)
        # Keep only lookback window
        if len(self._atr_history[pair]) > cfg.volatility_atr_lookback:
            self._atr_history[pair] = self._atr_history[pair][-cfg.volatility_atr_lookback:]

        if len(self._atr_history[pair]) < 2:
            return "normal"

        avg_atr = sum(self._atr_history[pair]) / len(self._atr_history[pair])
        if avg_atr == 0:
            return "normal"

        ratio = atr / avg_atr
        if ratio > cfg.volatility_extreme_ratio:
            return "extreme"
        if ratio > cfg.volatility_high_ratio:
            return "high"
        if ratio < cfg.volatility_low_ratio:
            return "low"
        return "normal"

    def _calc_ema_alignment(self, v: dict[str, float | None]) -> str:
        """Reference: Section 5-3 ema_alignment"""
        ema20 = v.get("ema20")
        ema50 = v.get("ema50")
        ema200 = v.get("ema200")

        if any(x is None for x in (ema20, ema50)):
            return "mixed"

        if ema200 is not None:
            if ema20 > ema50 > ema200:
                return "bullish"
            if ema20 < ema50 < ema200:
                return "bearish"
        else:
            if ema20 > ema50:
                return "bullish"
            if ema20 < ema50:
                return "bearish"

        return "mixed"

    def _calc_rsi_zone(self, v: dict[str, float | None]) -> str:
        """Reference: Section 5-3 rsi_zone"""
        rsi = v.get("rsi14")
        if rsi is None:
            return "neutral"
        if rsi < 30:
            return "oversold"
        if rsi > 70:
            return "overbought"
        return "neutral"

    def _calc_bb_position(self, v: dict[str, float | None], snapshot: IndicatorSnapshot) -> str:
        """Reference: Section 5-3 bb_position"""
        bb_upper = v.get("bb20_upper")
        bb_lower = v.get("bb20_lower")
        bb_middle = v.get("bb20_middle")

        if any(x is None for x in (bb_upper, bb_lower, bb_middle)):
            return "middle"

        # Use the close price from the latest bar via the snapshot
        # We use bb_middle as approximation since we don't store close directly
        # The caller should pass close price; for now we check relative to bands
        close = v.get("ema20")  # best available proxy for current close
        if close is None:
            return "middle"

        if close < bb_lower:
            return "below_lower"
        if close < bb_middle:
            return "lower_half"
        if close > bb_upper:
            return "above_upper"
        if close > bb_middle:
            return "upper_half"
        return "middle"

    def _empty_snapshot(
        self,
        pair: str,
        timestamp: datetime,
        data_quality: str,
        issues: list[str],
        trade_allowed: bool = False,
        indicators: dict[str, IndicatorSnapshot] | None = None,
    ) -> StateSnapshot:
        return StateSnapshot(
            pair=pair,
            timestamp=timestamp,
            trade_allowed=trade_allowed,
            trend="NEUTRAL",
            regime="range",
            volatility="normal",
            indicators=indicators or {},
            ema_alignment="mixed",
            rsi_zone="neutral",
            bb_position="middle",
            data_quality=data_quality,
            quality_issues=issues,
        )
