"""
Safeguard engine data types.

Reference: 03_セーフガードエンジン Section 2-1, 2-2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GuardResult(Enum):
    """Individual guard evaluation result. Reference: Section 2-1"""

    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    HALT = "halt"


@dataclass
class GuardEvaluation:
    """Single guard evaluation result. Reference: Section 2-1"""

    guard_id: str  # "SG-001", "INTERNAL-PRICE-SANITY", etc.
    result: GuardResult
    reason: str  # human-readable reason
    details: dict = field(default_factory=dict)  # numeric details (_debug)
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())


@dataclass
class GuardState:
    """Aggregated guard engine result. Reference: Section 2-2"""

    entry_allowed: bool
    force_close: bool
    trader_halted: bool
    cooldown_until: datetime | None
    lot_multiplier: float  # 1.0 normal, 0.5 halved

    evaluations: list[GuardEvaluation]
    blocking_guards: list[str]  # guard_ids with BLOCK or HALT


@dataclass
class AccountState:
    """Account state for capital protection guards."""

    capital: float  # initial capital (JPY)
    daily_realized_pnl: float  # today's realized P&L
    daily_unrealized_pnl: float  # today's unrealized P&L
    monthly_pnl: float  # month-to-date P&L
    peak_capital: float  # historical peak capital
    current_capital: float  # capital + cumulative realized + unrealized
    consecutive_losses: int  # consecutive losing trades count
    last_trade_was_loss: bool  # for lot halving logic
    daily_profit_pct: float  # today's realized profit %


@dataclass
class ProposedOrder:
    """Order proposal from M3 (entry) stage."""

    pair: str
    side: str  # "BUY" / "SELL"
    lot_size: float
    order_type: str  # "market" / "limit"
    limit_price: float | None = None  # for limit orders
    sl_price: float | None = None  # stop-loss price
    tp_price: float | None = None  # take-profit price
    sl_pips: float | None = None  # SL distance in pips
    tp_pips: float | None = None  # TP distance in pips
    risk_per_trade_pct: float | None = None  # from trader config


@dataclass
class SafeguardSettings:
    """
    Safeguard configuration mapped from config_json.

    Reference: 03_セーフガードエンジン Section 3 (all SG-xxx API keys)
    """

    # Category 1: Capital protection (SG-001~SG-009)
    max_daily_loss_pct: float = 10.0  # SG-001
    max_monthly_loss_pct: float = 20.0  # SG-002
    max_drawdown_pct: float = 30.0  # SG-003
    stop_on_profit_enabled: bool = False  # SG-004
    stop_on_profit_target_pct: float = 10.0  # SG-005
    consecutive_loss_enabled: bool = True  # SG-006
    consecutive_loss_max: int = 3  # SG-007
    consecutive_loss_cooldown_min: int = 60  # SG-008
    consecutive_loss_halve_lot: bool = False  # SG-009

    # Category 2: Market anomaly (SG-010~SG-018)
    spread_show_avg: bool = True  # SG-010 (UI only)
    spread_show_current: bool = True  # SG-011 (UI only)
    spread_max_multiple: float = 2.0  # SG-012
    atr_spike_enabled: bool = True  # SG-013
    atr_spike_lookback_bars: int = 20  # SG-014
    atr_spike_max_multiple: float = 1.8  # SG-015
    range_spike_enabled: bool = True  # SG-016
    range_spike_window_min: int = 5  # SG-017
    range_spike_max_pips: float = 50.0  # SG-018

    # Category 3: Session time control (SG-019~SG-026)
    session_block_outside_tokyo: bool = False  # SG-019
    session_block_outside_london: bool = False  # SG-020
    session_block_outside_newyork: bool = False  # SG-021
    session_start_buffer_enabled: bool = False  # SG-022
    session_start_buffer_minutes: int = 15  # SG-023
    session_end_buffer_enabled: bool = False  # SG-024
    session_end_buffer_minutes: int = 30  # SG-025
    low_vol_stop_enabled: bool = False  # SG-026

    # Category 4: Economic event filter (SG-027~SG-031)
    econ_stop_enabled: bool = True  # SG-027
    econ_stop_min_importance: int = 3  # SG-028
    econ_stop_before_min: int = 30  # SG-029
    econ_stop_after_min: int = 15  # SG-030
    econ_stop_currency_scope: str = "USD_ONLY"  # SG-031

    # Category 5: Regime protection (SG-032~SG-034)
    regime_break_stop_enabled: bool = False  # SG-032
    regime_break_stop_count: int = 3  # consecutive NEUTRAL count
    regime_adx_drop_stop_enabled: bool = False  # SG-033
    regime_adx_drop_threshold: float = 20.0  # ADX threshold
    regime_range_stop_enabled: bool = False  # SG-034

    # Category 6: Execution protection (SG-035~SG-040)
    exec_max_positions: int = 3  # SG-035
    exec_max_same_direction: int = 2  # SG-036
    exec_block_correlated: bool = True  # SG-037
    ai_failsafe_timeout_stop: bool = True  # SG-038
    ai_failsafe_invalid_output_stop: bool = True  # SG-039
    ai_failsafe_low_confidence_fallback: bool = True  # SG-040

    # Internal rules (no SG-ID, always evaluated)
    # 【監査4】Price sanity check
    price_sanity_atr_multiple: float = 3.0

    # 【監査】AI failure timeout
    ai_failsafe_hold_timeout_minutes: int = 30
    ai_failsafe_emergency_close_all: bool = True

    # 【生存性】RR sanity check
    rr_min_threshold: float = 0.8

    # 【生存性】Position size limit
    position_size_margin_pct: float = 10.0  # 10% margin over risk_per_trade_pct

    @classmethod
    def from_config_json(cls, config_json: dict) -> SafeguardSettings:
        """Create SafeguardSettings from the JSON stored in safeguard_configs table."""
        mapping = {
            "sg.maxDailyLossPct": "max_daily_loss_pct",
            "sg.maxMonthlyLossPct": "max_monthly_loss_pct",
            "sg.maxDrawdownPct": "max_drawdown_pct",
            "sg.stopOnProfit.enabled": "stop_on_profit_enabled",
            "sg.stopOnProfit.targetPct": "stop_on_profit_target_pct",
            "sg.consecutiveLoss.enabled": "consecutive_loss_enabled",
            "sg.consecutiveLoss.max": "consecutive_loss_max",
            "sg.consecutiveLoss.cooldownMin": "consecutive_loss_cooldown_min",
            "sg.consecutiveLoss.halveLot": "consecutive_loss_halve_lot",
            "sg.spread.showAvg": "spread_show_avg",
            "sg.spread.showCurrent": "spread_show_current",
            "sg.spread.maxMultiple": "spread_max_multiple",
            "sg.atrSpike.enabled": "atr_spike_enabled",
            "sg.atrSpike.lookbackBars": "atr_spike_lookback_bars",
            "sg.atrSpike.maxMultiple": "atr_spike_max_multiple",
            "sg.rangeSpike.enabled": "range_spike_enabled",
            "sg.rangeSpike.windowMin": "range_spike_window_min",
            "sg.rangeSpike.maxPips": "range_spike_max_pips",
            "sg.session.blockOutsideTokyo": "session_block_outside_tokyo",
            "sg.session.blockOutsideLondon": "session_block_outside_london",
            "sg.session.blockOutsideNewyork": "session_block_outside_newyork",
            "sg.session.startBuffer.enabled": "session_start_buffer_enabled",
            "sg.session.startBuffer.minutes": "session_start_buffer_minutes",
            "sg.session.endBuffer.enabled": "session_end_buffer_enabled",
            "sg.session.endBuffer.minutes": "session_end_buffer_minutes",
            "sg.lowVolStop.enabled": "low_vol_stop_enabled",
            "sg.econStop.enabled": "econ_stop_enabled",
            "sg.econStop.minImportance": "econ_stop_min_importance",
            "sg.econStop.beforeMin": "econ_stop_before_min",
            "sg.econStop.afterMin": "econ_stop_after_min",
            "sg.econStop.currencyScope": "econ_stop_currency_scope",
            "sg.regime.breakStop.enabled": "regime_break_stop_enabled",
            "sg.regime.adxDropStop.enabled": "regime_adx_drop_stop_enabled",
            "sg.regime.rangeStop.enabled": "regime_range_stop_enabled",
            "sg.exec.maxPositions": "exec_max_positions",
            "sg.exec.maxSameDirection": "exec_max_same_direction",
            "sg.exec.blockCorrelated": "exec_block_correlated",
            "sg.aiFailsafe.timeoutStop": "ai_failsafe_timeout_stop",
            "sg.aiFailsafe.invalidOutputStop": "ai_failsafe_invalid_output_stop",
            "sg.aiFailsafe.lowConfidenceFallback": "ai_failsafe_low_confidence_fallback",
            "sg.aiFailsafe.holdTimeoutMinutes": "ai_failsafe_hold_timeout_minutes",
            "sg.aiFailsafe.emergencyCloseAll": "ai_failsafe_emergency_close_all",
        }
        kwargs = {}
        for api_key, attr_name in mapping.items():
            if api_key in config_json:
                kwargs[attr_name] = config_json[api_key]
        return cls(**kwargs)
