"""
DataQualityGate: validate OHLCV data before IndicatorEngine.

Reference: 02_データパイプライン Section 6-2, 6-3 (audit addition)

2-level spike detection:
  Level 1: simple rate-of-change threshold
  Level 2: statistical deviation (mean +/- 3 sigma)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from app.services.pipeline.data_types import OHLCV, QualityReport

logger = logging.getLogger(__name__)


@dataclass
class DataQualityConfig:
    """Configuration for DataQualityGate. Reference: Section 11-1"""

    spike_threshold_pct: float = 0.5  # Level 1: % change threshold per bar
    spike_stat_window: int = 20  # Level 2: lookback window for sigma calc
    spike_sigma_mult: float = 3.0  # Level 2: sigma multiplier
    max_consecutive_missing: int = 3  # max consecutive missing bars before "missing"
    max_consecutive_spikes: int = 5  # max consecutive spikes before "missing"


class DataQualityGate:
    """
    Validates OHLCV data before passing to IndicatorEngine.

    Reference: 02_データパイプライン Section 6-3

    Processing flow:
      1. Missing bar check
      2. Spike check (Level 1 + Level 2)
      3. Zero/negative value check
      4. Compensation
      5. data_quality label assignment
    """

    def __init__(self, config: DataQualityConfig | None = None):
        self.config = config or DataQualityConfig()
        # pair -> timeframe -> deque of recent close prices
        self._history: dict[str, dict[str, deque]] = {}
        self._last_valid: dict[str, dict[str, OHLCV | None]] = {}

    def _get_history(self, pair: str, timeframe: str) -> deque:
        if pair not in self._history:
            self._history[pair] = {}
        if timeframe not in self._history[pair]:
            self._history[pair][timeframe] = deque(maxlen=self.config.spike_stat_window)
        return self._history[pair][timeframe]

    def _get_last_valid(self, pair: str, timeframe: str) -> OHLCV | None:
        return self._last_valid.get(pair, {}).get(timeframe)

    def _set_last_valid(self, pair: str, timeframe: str, bar: OHLCV) -> None:
        if pair not in self._last_valid:
            self._last_valid[pair] = {}
        self._last_valid[pair][timeframe] = bar

    def validate(
        self, pair: str, timeframe: str, bars: list[OHLCV]
    ) -> tuple[list[OHLCV], QualityReport, str]:
        """
        Validate a list of OHLCV bars.

        Returns:
            (validated_bars, quality_report, data_quality_label)
        """
        cfg = self.config
        history = self._get_history(pair, timeframe)
        validated: list[OHLCV] = []
        issues: list[str] = []
        total = len(bars)
        passed = 0
        degraded = 0
        replaced = 0
        missing = 0
        consecutive_spikes = 0

        for bar in bars:
            # --- Zero/negative check ---
            if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
                last_valid = self._get_last_valid(pair, timeframe)
                if last_valid is not None:
                    bar = OHLCV(
                        timestamp=bar.timestamp,
                        open=last_valid.close,
                        high=last_valid.close,
                        low=last_valid.close,
                        close=last_valid.close,
                        volume=0.0,
                    )
                    replaced += 1
                    issues.append(f"zero/negative value at {bar.timestamp}, replaced")
                else:
                    missing += 1
                    issues.append(f"zero/negative value at {bar.timestamp}, no prior data")
                    continue

            # --- Level 1: simple rate-of-change spike check ---
            is_spike = False
            last_valid = self._get_last_valid(pair, timeframe)
            if last_valid is not None and last_valid.close != 0:
                change_pct = abs(bar.close - last_valid.close) / last_valid.close * 100
                if change_pct > cfg.spike_threshold_pct:
                    is_spike = True
                    issues.append(
                        f"L1 spike at {bar.timestamp}: {change_pct:.2f}% (threshold {cfg.spike_threshold_pct}%)"
                    )

            # --- Level 2: statistical deviation spike check ---
            if len(history) >= cfg.spike_stat_window:
                arr = np.array(history, dtype=np.float32)
                mean = float(np.mean(arr))
                std = float(np.std(arr))
                if std > 0 and abs(bar.close - mean) > cfg.spike_sigma_mult * std:
                    is_spike = True
                    issues.append(
                        f"L2 spike at {bar.timestamp}: close={bar.close:.4f}, "
                        f"mean={mean:.4f}, 3sigma={cfg.spike_sigma_mult * std:.4f}"
                    )

            if is_spike:
                consecutive_spikes += 1
                if consecutive_spikes >= cfg.max_consecutive_spikes:
                    missing += (total - passed - degraded - replaced - missing)
                    break

                if last_valid is not None:
                    logger.warning(
                        "Spike replaced: pair=%s tf=%s ts=%s orig_close=%.4f -> %.4f",
                        pair, timeframe, bar.timestamp, bar.close, last_valid.close,
                    )
                    bar = OHLCV(
                        timestamp=bar.timestamp,
                        open=last_valid.close,
                        high=last_valid.close,
                        low=last_valid.close,
                        close=last_valid.close,
                        volume=bar.volume,
                    )
                    replaced += 1
                    degraded += 1
                else:
                    passed += 1
            else:
                consecutive_spikes = 0
                passed += 1

            history.append(bar.close)
            self._set_last_valid(pair, timeframe, bar)
            validated.append(bar)

        # Determine overall quality
        if missing > 0 or len(validated) == 0:
            quality = "missing"
        elif degraded > 0 or replaced > 0:
            quality = "degraded"
        else:
            quality = "ok"

        report = QualityReport(
            total=total, passed=passed, degraded=degraded, replaced=replaced, missing=missing,
        )
        return validated, report, quality
