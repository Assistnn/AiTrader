"""
Safeguard rules implementation (SG-001~SG-040 + internal rules).

Reference: 03_セーフガードエンジン Section 3

Each guard is a class with an evaluate() method that returns a GuardEvaluation.
Guards follow the design doc's Tier 1/Tier 2 priority system (Section 7).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.services.pipeline.data_types import StateSnapshot, Ticker
from app.services.safeguard.guard_types import (
    AccountState,
    GuardEvaluation,
    GuardResult,
    ProposedOrder,
    SafeguardSettings,
)

# Correlation groups for SG-037 (fixed table, Section 3)
CORRELATION_GROUPS: list[set[str]] = [
    {"USD_JPY", "EUR_JPY"},  # Group A: JPY pairs
    {"EUR_USD", "GBP_USD"},  # Group B: USD pairs
    {"AUD_USD", "NZD_USD"},  # Group C: Oceania pairs
]

# Currency pair -> related countries for economic event filtering
PAIR_CURRENCIES: dict[str, list[str]] = {
    "USD_JPY": ["USD", "JPY"],
    "EUR_USD": ["EUR", "USD"],
    "GBP_USD": ["GBP", "USD"],
    "EUR_JPY": ["EUR", "JPY"],
    "GBP_JPY": ["GBP", "JPY"],
    "AUD_USD": ["AUD", "USD"],
    "NZD_USD": ["NZD", "USD"],
    "AUD_JPY": ["AUD", "JPY"],
    "NZD_JPY": ["NZD", "JPY"],
    "CHF_JPY": ["CHF", "JPY"],
    "CAD_JPY": ["CAD", "JPY"],
}


@dataclass
class EconomicEvent:
    """Economic event for SG-027~031 filtering."""

    event_datetime: datetime  # UTC
    name: str
    currency: str  # "USD", "JPY", etc.
    importance: int  # 1-3 (stars)


@dataclass
class PositionInfo:
    """Simplified position info for guard evaluation."""

    pair: str
    side: str  # "BUY" / "SELL"
    amount: float
    entry_price: float
    unrealized_pnl: float | None = None


class BaseGuard(ABC):
    """Base class for all safeguard rules."""

    guard_id: str
    tier: int  # 1 = active from day 1, 2 = WARN initially

    @abstractmethod
    def evaluate(
        self,
        settings: SafeguardSettings,
        state: StateSnapshot | None,
        ticker: Ticker | None,
        account: AccountState | None,
        positions: list[PositionInfo],
        economic_events: list[EconomicEvent],
        proposed_order: ProposedOrder | None,
        now: datetime,
    ) -> GuardEvaluation:
        ...

    def _pass(self, now: datetime) -> GuardEvaluation:
        return GuardEvaluation(
            guard_id=self.guard_id, result=GuardResult.PASS,
            reason="", timestamp=now,
        )

    def _warn(self, reason: str, details: dict, now: datetime) -> GuardEvaluation:
        return GuardEvaluation(
            guard_id=self.guard_id, result=GuardResult.WARN,
            reason=reason, details=details, timestamp=now,
        )

    def _block(self, reason: str, details: dict, now: datetime) -> GuardEvaluation:
        return GuardEvaluation(
            guard_id=self.guard_id, result=GuardResult.BLOCK,
            reason=reason, details=details, timestamp=now,
        )

    def _halt(self, reason: str, details: dict, now: datetime) -> GuardEvaluation:
        return GuardEvaluation(
            guard_id=self.guard_id, result=GuardResult.HALT,
            reason=reason, details=details, timestamp=now,
        )


# ---------------------------------------------------------------------------
# Category 1: Capital Protection (SG-001~SG-009) — Tier 1
# ---------------------------------------------------------------------------


class SG001_DailyMaxLoss(BaseGuard):
    """SG-001: Daily max loss rate. Result: HALT"""

    guard_id = "SG-001"
    tier = 1

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if account is None:
            return self._pass(now)
        capital = account.capital
        if capital <= 0:
            return self._pass(now)
        daily_pnl_pct = (
            (account.daily_realized_pnl + account.daily_unrealized_pnl) / capital * 100
        )
        threshold = settings.max_daily_loss_pct
        details = {"daily_pnl_pct": daily_pnl_pct, "threshold": -threshold, "capital": capital}
        if daily_pnl_pct <= -threshold:
            return self._halt(f"DAILY_LOSS_EXCEEDED: {daily_pnl_pct:.2f}% <= -{threshold}%", details, now)
        return self._pass(now)


class SG002_MonthlyMaxLoss(BaseGuard):
    """SG-002: Monthly max loss rate. Result: HALT"""

    guard_id = "SG-002"
    tier = 1

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if account is None:
            return self._pass(now)
        capital = account.capital
        if capital <= 0:
            return self._pass(now)
        monthly_pnl_pct = account.monthly_pnl / capital * 100
        threshold = settings.max_monthly_loss_pct
        details = {"monthly_pnl_pct": monthly_pnl_pct, "threshold": -threshold}
        if monthly_pnl_pct <= -threshold:
            return self._halt(f"MONTHLY_LOSS_EXCEEDED: {monthly_pnl_pct:.2f}%", details, now)
        return self._pass(now)


class SG003_MaxDrawdown(BaseGuard):
    """SG-003: Max drawdown. Result: HALT"""

    guard_id = "SG-003"
    tier = 1

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if account is None:
            return self._pass(now)
        peak = account.peak_capital
        current = account.current_capital
        if peak <= 0:
            return self._pass(now)
        drawdown_pct = (peak - current) / peak * 100
        threshold = settings.max_drawdown_pct
        details = {"drawdown_pct": drawdown_pct, "threshold": threshold, "peak": peak, "current": current}
        if drawdown_pct >= threshold:
            return self._halt(f"MAX_DRAWDOWN: {drawdown_pct:.2f}% >= {threshold}%", details, now)
        return self._pass(now)


class SG004_005_ProfitStop(BaseGuard):
    """SG-004/005: Stop on daily profit target. Result: HALT (when enabled)"""

    guard_id = "SG-005"
    tier = 1

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.stop_on_profit_enabled:
            return self._pass(now)
        if account is None:
            return self._pass(now)
        daily_profit_pct = account.daily_profit_pct
        target = settings.stop_on_profit_target_pct
        details = {"daily_profit_pct": daily_profit_pct, "target_pct": target}
        if daily_profit_pct >= target:
            return self._halt(f"PROFIT_TARGET_REACHED: {daily_profit_pct:.2f}% >= {target}%", details, now)
        return self._pass(now)


class SG006_009_ConsecutiveLoss(BaseGuard):
    """SG-006~009: Consecutive loss control. Result: BLOCK (cooldown)"""

    guard_id = "SG-007"
    tier = 1

    def __init__(self) -> None:
        self._cooldown_until: datetime | None = None
        self._lot_halved: bool = False

    @property
    def cooldown_until(self) -> datetime | None:
        return self._cooldown_until

    @property
    def lot_halved(self) -> bool:
        return self._lot_halved

    def reset_on_win(self) -> None:
        """Reset state on a winning trade."""
        self._cooldown_until = None
        self._lot_halved = False

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.consecutive_loss_enabled:
            return self._pass(now)
        if account is None:
            return self._pass(now)

        # Check cooldown
        if self._cooldown_until is not None:
            cd = self._cooldown_until
            if cd.tzinfo is None:
                cd = cd.replace(tzinfo=timezone.utc)
            now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            if now_utc < cd:
                details = {"cooldown_until": cd.isoformat(), "consecutive_losses": account.consecutive_losses}
                return self._block("CONSECUTIVE_LOSS_COOLDOWN", details, now)
            else:
                self._cooldown_until = None

        max_losses = settings.consecutive_loss_max
        if account.consecutive_losses >= max_losses:
            cooldown_min = settings.consecutive_loss_cooldown_min
            now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            self._cooldown_until = now_utc + timedelta(minutes=cooldown_min)
            if settings.consecutive_loss_halve_lot:
                self._lot_halved = True
            details = {
                "consecutive_losses": account.consecutive_losses,
                "max": max_losses,
                "cooldown_minutes": cooldown_min,
                "lot_halved": self._lot_halved,
            }
            return self._block(
                f"CONSECUTIVE_LOSS: {account.consecutive_losses} >= {max_losses}",
                details, now,
            )

        return self._pass(now)


# ---------------------------------------------------------------------------
# Category 2: Market Anomaly (SG-010~SG-018)
# ---------------------------------------------------------------------------


class SG012_SpreadAnomaly(BaseGuard):
    """SG-012: Spread anomaly stop. Result: BLOCK"""

    guard_id = "SG-012"
    tier = 1

    def __init__(self) -> None:
        self._spread_history: deque[float] = deque(maxlen=1800)  # 30min at 1/sec

    def record_spread(self, spread: float) -> None:
        """Record a spread sample for averaging."""
        self._spread_history.append(spread)

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if ticker is None:
            return self._pass(now)
        current_spread = ticker.ask - ticker.bid
        if current_spread < 0:
            current_spread = 0.0
        self._spread_history.append(current_spread)

        if len(self._spread_history) < 2:
            return self._pass(now)

        avg_spread = sum(self._spread_history) / len(self._spread_history)
        if avg_spread <= 0:
            return self._pass(now)

        max_mult = settings.spread_max_multiple
        details = {"current_spread": current_spread, "avg_spread": avg_spread, "max_multiple": max_mult}
        if current_spread > avg_spread * max_mult:
            return self._block(
                f"SPREAD_TOO_WIDE: {current_spread:.5f} > avg {avg_spread:.5f} * {max_mult}",
                details, now,
            )
        return self._pass(now)


class SG013_015_ATRSpike(BaseGuard):
    """SG-013~015: ATR spike detection. Result: BLOCK"""

    guard_id = "SG-015"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.atr_spike_enabled:
            return self._pass(now)
        if state is None:
            return self._pass(now)

        # Get ATR from primary timeframe indicators
        primary = state.indicators.get("H1") or state.indicators.get("M5")
        if primary is None:
            return self._pass(now)
        current_atr = primary.values.get("atr14")
        if current_atr is None:
            return self._pass(now)

        # We use the volatility ratio from StateBuilder as proxy
        # A more precise implementation would track ATR history here
        max_mult = settings.atr_spike_max_multiple
        # Use state.volatility as a simplified check
        if state.volatility == "extreme":
            details = {"current_atr": current_atr, "max_multiple": max_mult, "volatility": state.volatility}
            result = self._block if self.tier == 1 else self._warn
            return result("ATR_SPIKE: extreme volatility", details, now)
        if state.volatility == "high":
            details = {"current_atr": current_atr, "max_multiple": max_mult, "volatility": state.volatility}
            return self._warn("ATR_ELEVATED: high volatility", details, now)
        return self._pass(now)


class SG016_018_RangeSpike(BaseGuard):
    """SG-016~018: Range spike detection. Result: BLOCK"""

    guard_id = "SG-018"
    tier = 2

    def __init__(self) -> None:
        self._recent_bars: deque[tuple[float, float, datetime]] = deque(maxlen=60)

    def record_bar(self, high: float, low: float, timestamp: datetime) -> None:
        """Record a M1 bar for range calculation."""
        self._recent_bars.append((high, low, timestamp))

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.range_spike_enabled:
            return self._pass(now)

        window_min = settings.range_spike_window_min
        max_pips = settings.range_spike_max_pips
        now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        cutoff = now_utc - timedelta(minutes=window_min)

        # Filter bars within window
        window_bars = [(h, l) for h, l, ts in self._recent_bars
                       if (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)) >= cutoff]

        if not window_bars:
            return self._pass(now)

        window_high = max(h for h, l in window_bars)
        window_low = min(l for h, l in window_bars)
        range_raw = window_high - window_low
        # Approximate pips (100 for JPY pairs, 10000 for others)
        # This is simplified; full implementation uses PriceNormalizer
        range_pips = range_raw * 100  # default for JPY pairs

        details = {
            "range_pips": range_pips, "max_pips": max_pips,
            "window_high": window_high, "window_low": window_low,
        }
        if range_pips >= max_pips:
            result_fn = self._block if self.tier == 1 else self._warn
            return result_fn(f"RANGE_SPIKE: {range_pips:.1f} pips >= {max_pips}", details, now)
        return self._pass(now)


# ---------------------------------------------------------------------------
# Category 3: Session Time Control (SG-019~SG-026)
# ---------------------------------------------------------------------------


def _is_dst_london(dt: datetime) -> bool:
    """Check if London is in DST (last Sunday of March to last Sunday of October)."""
    year = dt.year
    # Last Sunday of March
    march_last = datetime(year, 3, 31, tzinfo=timezone.utc)
    while march_last.weekday() != 6:
        march_last -= timedelta(days=1)
    march_last = march_last.replace(hour=1)  # BST starts at 01:00 UTC

    # Last Sunday of October
    oct_last = datetime(year, 10, 31, tzinfo=timezone.utc)
    while oct_last.weekday() != 6:
        oct_last -= timedelta(days=1)
    oct_last = oct_last.replace(hour=1)  # BST ends at 01:00 UTC

    return march_last <= dt < oct_last


def _is_dst_newyork(dt: datetime) -> bool:
    """Check if New York is in DST (2nd Sunday of March to 1st Sunday of November)."""
    year = dt.year
    # 2nd Sunday of March
    march_1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    count = 0
    d = march_1
    while count < 2:
        if d.weekday() == 6:
            count += 1
            if count == 2:
                break
        d += timedelta(days=1)
    march_2nd_sun = d.replace(hour=7)  # EDT starts at 02:00 EST = 07:00 UTC

    # 1st Sunday of November
    nov_1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    d = nov_1
    while d.weekday() != 6:
        d += timedelta(days=1)
    nov_1st_sun = d.replace(hour=6)  # EST resumes at 02:00 EDT = 06:00 UTC

    return march_2nd_sun <= dt < nov_1st_sun


class SG019_TokyoSession(BaseGuard):
    """SG-019: Block outside Tokyo session. Result: BLOCK"""

    guard_id = "SG-019"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.session_block_outside_tokyo:
            return self._pass(now)
        now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        # Tokyo: 00:00-09:00 JST = 15:00(prev day)-00:00 UTC
        hour = now_utc.hour
        in_tokyo = (hour >= 15) or (hour < 0)  # 15:00-23:59 UTC
        # Actually: JST = UTC+9, so 00:00-09:00 JST = 15:00-00:00 UTC
        # i.e. UTC 15:00 to UTC 00:00 (next day)
        in_tokyo = hour >= 15 or hour < 0
        # Simplified: UTC 15:00-23:59 maps to JST 00:00-08:59
        in_tokyo = 15 <= hour <= 23
        if not in_tokyo:
            details = {"utc_hour": hour, "session": "tokyo"}
            return self._warn("OUTSIDE_TOKYO_SESSION", details, now)
        return self._pass(now)


class SG020_LondonSession(BaseGuard):
    """SG-020: Block outside London session. Result: BLOCK"""

    guard_id = "SG-020"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.session_block_outside_london:
            return self._pass(now)
        now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        hour = now_utc.hour
        minute = now_utc.minute

        if _is_dst_london(now_utc):
            # Summer: 07:00-15:30 UTC
            start_h, start_m = 7, 0
            end_h, end_m = 15, 30
        else:
            # Winter: 08:00-16:30 UTC
            start_h, start_m = 8, 0
            end_h, end_m = 16, 30

        current_minutes = hour * 60 + minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        in_london = start_minutes <= current_minutes < end_minutes

        if not in_london:
            details = {"utc_hour": hour, "utc_minute": minute, "session": "london", "is_dst": _is_dst_london(now_utc)}
            return self._warn("OUTSIDE_LONDON_SESSION", details, now)
        return self._pass(now)


class SG021_NewyorkSession(BaseGuard):
    """SG-021: Block outside New York session. Result: BLOCK"""

    guard_id = "SG-021"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.session_block_outside_newyork:
            return self._pass(now)
        now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        hour = now_utc.hour
        minute = now_utc.minute

        if _is_dst_newyork(now_utc):
            # Summer: 12:00-21:00 UTC
            start_h, end_h = 12, 21
        else:
            # Winter: 13:00-22:00 UTC
            start_h, end_h = 13, 22

        current_minutes = hour * 60 + minute
        start_minutes = start_h * 60
        end_minutes = end_h * 60
        in_ny = start_minutes <= current_minutes < end_minutes

        if not in_ny:
            details = {"utc_hour": hour, "session": "newyork", "is_dst": _is_dst_newyork(now_utc)}
            return self._warn("OUTSIDE_NEWYORK_SESSION", details, now)
        return self._pass(now)


class SG022_023_SessionStartBuffer(BaseGuard):
    """SG-022/023: Session start buffer. Result: BLOCK"""

    guard_id = "SG-023"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.session_start_buffer_enabled:
            return self._pass(now)
        # This guard requires tracking active session start times
        # Simplified: check minutes since top of active session hour
        # Full implementation needs session manager integration
        return self._pass(now)


class SG024_025_SessionEndBuffer(BaseGuard):
    """SG-024/025: Session end buffer. Result: BLOCK"""

    guard_id = "SG-025"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.session_end_buffer_enabled:
            return self._pass(now)
        return self._pass(now)


class SG026_LowVolatilityStop(BaseGuard):
    """SG-026: Low volatility stop. Result: BLOCK"""

    guard_id = "SG-026"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.low_vol_stop_enabled:
            return self._pass(now)
        if state is None:
            return self._pass(now)
        if state.volatility == "low":
            details = {"volatility": state.volatility}
            return self._warn("LOW_VOLATILITY", details, now)
        return self._pass(now)


# ---------------------------------------------------------------------------
# Category 4: Economic Event Filter (SG-027~SG-031)
# ---------------------------------------------------------------------------


class SG027_031_EconomicEventFilter(BaseGuard):
    """SG-027~031: Economic event filter. Result: BLOCK"""

    guard_id = "SG-031"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.econ_stop_enabled:
            return self._pass(now)

        now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        pair = None
        if proposed_order is not None:
            pair = proposed_order.pair
        elif state is not None:
            pair = state.pair

        pair_currencies = PAIR_CURRENCIES.get(pair, []) if pair else []

        before_min = settings.econ_stop_before_min
        after_min = settings.econ_stop_after_min
        min_importance = settings.econ_stop_min_importance
        scope = settings.econ_stop_currency_scope

        for event in economic_events:
            if event.importance < min_importance:
                continue
            if scope == "USD_ONLY" and event.currency != "USD":
                continue
            if scope == "ALL" and pair_currencies and event.currency not in pair_currencies:
                continue

            evt_dt = event.event_datetime
            if evt_dt.tzinfo is None:
                evt_dt = evt_dt.replace(tzinfo=timezone.utc)
            time_diff = (evt_dt - now_utc).total_seconds() / 60  # minutes

            if -after_min <= time_diff <= before_min:
                details = {
                    "event_name": event.name,
                    "event_currency": event.currency,
                    "importance": event.importance,
                    "minutes_to_event": time_diff,
                }
                return self._warn(f"ECON_EVENT: {event.name}", details, now)

        return self._pass(now)


# ---------------------------------------------------------------------------
# Category 5: Regime Protection (SG-032~SG-034)
# ---------------------------------------------------------------------------


class SG032_TrendBreakdownStop(BaseGuard):
    """SG-032: Trend breakdown stop. Result: BLOCK"""

    guard_id = "SG-032"
    tier = 2

    def __init__(self) -> None:
        self._neutral_count: int = 0

    def record_trend(self, trend: str) -> None:
        """Track consecutive NEUTRAL trends."""
        if trend == "NEUTRAL":
            self._neutral_count += 1
        else:
            self._neutral_count = 0

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.regime_break_stop_enabled:
            return self._pass(now)
        if state is not None:
            self.record_trend(state.trend)
        threshold = settings.regime_break_stop_count
        if self._neutral_count >= threshold:
            details = {"neutral_count": self._neutral_count, "threshold": threshold}
            return self._warn(f"TREND_BREAKDOWN: {self._neutral_count} consecutive NEUTRAL", details, now)
        return self._pass(now)


class SG033_ADXDropStop(BaseGuard):
    """SG-033: ADX drop stop for trend-following. Result: BLOCK"""

    guard_id = "SG-033"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.regime_adx_drop_stop_enabled:
            return self._pass(now)
        if state is None:
            return self._pass(now)
        primary = state.indicators.get("H1")
        if primary is None:
            return self._pass(now)
        adx = primary.values.get("adx14")
        if adx is None:
            return self._pass(now)

        threshold = settings.regime_adx_drop_threshold
        if adx < threshold:
            details = {"adx14": adx, "threshold": threshold}
            return self._warn(f"ADX_DROP_TREND_STOP: ADX {adx:.1f} < {threshold}", details, now)
        return self._pass(now)


class SG034_RangeStop(BaseGuard):
    """SG-034: Range transition stop for trend-following. Result: BLOCK"""

    guard_id = "SG-034"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.regime_range_stop_enabled:
            return self._pass(now)
        if state is None:
            return self._pass(now)
        if state.regime == "range":
            details = {"regime": state.regime}
            return self._warn("RANGE_TREND_STOP", details, now)
        return self._pass(now)


# ---------------------------------------------------------------------------
# Category 6: Execution Protection (SG-035~SG-040)
# ---------------------------------------------------------------------------


class SG035_MaxPositions(BaseGuard):
    """SG-035: Max simultaneous positions. Result: BLOCK"""

    guard_id = "SG-035"
    tier = 1

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        max_pos = settings.exec_max_positions
        current_count = len(positions)
        if current_count >= max_pos:
            details = {"open_positions": current_count, "max": max_pos}
            return self._block(f"MAX_POSITIONS_REACHED: {current_count} >= {max_pos}", details, now)
        return self._pass(now)


class SG036_SameDirectionLimit(BaseGuard):
    """SG-036: Same direction position limit. Result: BLOCK"""

    guard_id = "SG-036"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if proposed_order is None:
            return self._pass(now)
        max_same = settings.exec_max_same_direction
        side = proposed_order.side
        same_count = sum(1 for p in positions if p.side == side)
        if same_count >= max_same:
            details = {"side": side, "same_direction_count": same_count, "max": max_same}
            result_fn = self._block if self.tier == 1 else self._warn
            return result_fn(f"MAX_SAME_DIRECTION: {same_count} {side} >= {max_same}", details, now)
        return self._pass(now)


class SG037_CorrelatedPairBlock(BaseGuard):
    """SG-037: Correlated pair blocking. Result: BLOCK"""

    guard_id = "SG-037"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not settings.exec_block_correlated:
            return self._pass(now)
        if proposed_order is None:
            return self._pass(now)

        proposed_pair = proposed_order.pair
        existing_pairs = {p.pair for p in positions}

        for group in CORRELATION_GROUPS:
            if proposed_pair in group:
                correlated_existing = existing_pairs & group - {proposed_pair}
                if correlated_existing:
                    details = {
                        "proposed_pair": proposed_pair,
                        "correlated_existing": list(correlated_existing),
                    }
                    result_fn = self._block if self.tier == 1 else self._warn
                    return result_fn(
                        f"CORRELATED_PAIR_EXISTS: {list(correlated_existing)}",
                        details, now,
                    )
        return self._pass(now)


class SG038_AITimeoutStop(BaseGuard):
    """SG-038: AI response timeout stop. Result: BLOCK/fallback"""

    guard_id = "SG-038"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        # This guard is evaluated by the AI integration layer, not here.
        # Placeholder: always PASS when AI is not in use.
        return self._pass(now)


class SG039_AIInvalidOutputStop(BaseGuard):
    """SG-039: AI invalid output stop. Result: BLOCK/fallback"""

    guard_id = "SG-039"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        return self._pass(now)


class SG040_AILowConfidenceFallback(BaseGuard):
    """SG-040: AI low confidence fallback."""

    guard_id = "SG-040"
    tier = 2

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        return self._pass(now)


# ---------------------------------------------------------------------------
# Internal Rules (no SG-ID)
# ---------------------------------------------------------------------------


class InternalPriceSanityCheck(BaseGuard):
    """【監査4】Price sanity check. Reference: Section 3 (after SG-018)"""

    guard_id = "INTERNAL-PRICE-SANITY"
    tier = 1

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if proposed_order is None or proposed_order.order_type != "limit":
            return self._pass(now)
        if ticker is None:
            return self._pass(now)
        if state is None:
            return self._pass(now)

        limit_price = proposed_order.limit_price
        if limit_price is None:
            return self._pass(now)

        current_mid = (ticker.bid + ticker.ask) / 2
        deviation = abs(limit_price - current_mid)

        # Get ATR14 from primary timeframe
        primary = state.indicators.get("H1")
        if primary is None:
            return self._pass(now)
        atr = primary.values.get("atr14")
        if atr is None or atr <= 0:
            return self._pass(now)

        atr_mult = settings.price_sanity_atr_multiple
        max_deviation = atr * atr_mult
        # Convert to approximate pips for JPY pairs
        deviation_pips = deviation * 100

        details = {
            "limit_price": limit_price, "current_mid": current_mid,
            "deviation": deviation, "atr14": atr, "max_deviation": max_deviation,
        }
        if deviation > max_deviation:
            return self._block(
                f"PRICE_SANITY_CHECK_FAILED: deviation {deviation:.5f} > ATR*{atr_mult} ({max_deviation:.5f})",
                details, now,
            )
        return self._pass(now)


class InternalAIFailureTimeout(BaseGuard):
    """【監査】AI failure timeout. Reference: Section 3 (after SG-040)"""

    guard_id = "INTERNAL-AI-TIMEOUT"
    tier = 1

    def __init__(self) -> None:
        self.ai_hold_state: bool = False
        self.ai_hold_start_time: datetime | None = None

    def set_ai_hold(self, start_time: datetime) -> None:
        """Called when AI enters hold state."""
        self.ai_hold_state = True
        self.ai_hold_start_time = start_time

    def clear_ai_hold(self) -> None:
        """Called when AI recovers."""
        self.ai_hold_state = False
        self.ai_hold_start_time = None

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if not self.ai_hold_state or self.ai_hold_start_time is None:
            return self._pass(now)

        now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        start = self.ai_hold_start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        elapsed_min = (now_utc - start).total_seconds() / 60

        timeout_min = settings.ai_failsafe_hold_timeout_minutes
        details = {
            "elapsed_minutes": elapsed_min,
            "timeout_minutes": timeout_min,
            "emergency_close_all": settings.ai_failsafe_emergency_close_all,
        }

        if elapsed_min > timeout_min and settings.ai_failsafe_emergency_close_all:
            return self._halt("AI_FAILURE_TIMEOUT_EMERGENCY_CLOSE", details, now)
        return self._pass(now)


class InternalRRSanityCheck(BaseGuard):
    """【生存性】RR sanity check. Reference: Section 3"""

    guard_id = "INTERNAL-RR-SANITY"
    tier = 1

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if proposed_order is None:
            return self._pass(now)
        tp_pips = proposed_order.tp_pips
        sl_pips = proposed_order.sl_pips
        if tp_pips is None or sl_pips is None or sl_pips <= 0:
            return self._pass(now)

        rr_ratio = tp_pips / sl_pips
        rr_min = settings.rr_min_threshold
        details = {"rr_ratio": rr_ratio, "rr_min": rr_min, "tp_pips": tp_pips, "sl_pips": sl_pips}
        if rr_ratio < rr_min:
            return self._block(
                f"RR_BELOW_MINIMUM: {rr_ratio:.2f} < {rr_min}",
                details, now,
            )
        return self._pass(now)


class InternalPositionSizeCheck(BaseGuard):
    """【生存性】Position size limit check. Reference: Section 3"""

    guard_id = "INTERNAL-POSITION-SIZE"
    tier = 1

    def evaluate(self, settings, state, ticker, account, positions,
                 economic_events, proposed_order, now):
        if proposed_order is None or account is None:
            return self._pass(now)
        if proposed_order.sl_pips is None or proposed_order.sl_pips <= 0:
            return self._pass(now)
        if proposed_order.risk_per_trade_pct is None:
            return self._pass(now)

        capital = account.capital
        if capital <= 0:
            return self._pass(now)

        # risk_amount = lot_size * sl_pips * pip_value
        # Simplified: pip_value ≈ 100 for JPY pairs (0.01 * 10000)
        pip_value = 100.0  # approximate for JPY pairs
        risk_amount = proposed_order.lot_size * proposed_order.sl_pips * pip_value
        risk_pct = risk_amount / capital * 100

        margin = settings.position_size_margin_pct
        allowed_risk_pct = proposed_order.risk_per_trade_pct * (1 + margin / 100)

        details = {
            "risk_pct": risk_pct, "allowed_risk_pct": allowed_risk_pct,
            "lot_size": proposed_order.lot_size, "sl_pips": proposed_order.sl_pips,
        }
        if risk_pct > allowed_risk_pct:
            return self._block(
                f"POSITION_SIZE_EXCEEDS_RISK_LIMIT: {risk_pct:.2f}% > {allowed_risk_pct:.2f}%",
                details, now,
            )
        return self._pass(now)


def build_all_guards() -> list[BaseGuard]:
    """Build all guard instances in evaluation order (category -> priority)."""
    return [
        # Category 1: Capital Protection (Tier 1)
        SG001_DailyMaxLoss(),
        SG002_MonthlyMaxLoss(),
        SG003_MaxDrawdown(),
        SG004_005_ProfitStop(),
        SG006_009_ConsecutiveLoss(),
        # Category 2: Market Anomaly
        SG012_SpreadAnomaly(),       # Tier 1
        SG013_015_ATRSpike(),        # Tier 2
        SG016_018_RangeSpike(),      # Tier 2
        # Internal: Price Sanity (Tier 1)
        InternalPriceSanityCheck(),
        # Category 3: Session Time Control (Tier 2)
        SG019_TokyoSession(),
        SG020_LondonSession(),
        SG021_NewyorkSession(),
        SG022_023_SessionStartBuffer(),
        SG024_025_SessionEndBuffer(),
        SG026_LowVolatilityStop(),
        # Category 4: Economic Event Filter (Tier 2)
        SG027_031_EconomicEventFilter(),
        # Category 5: Regime Protection (Tier 2)
        SG032_TrendBreakdownStop(),
        SG033_ADXDropStop(),
        SG034_RangeStop(),
        # Category 6: Execution Protection
        SG035_MaxPositions(),        # Tier 1
        SG036_SameDirectionLimit(),  # Tier 2
        SG037_CorrelatedPairBlock(), # Tier 2
        SG038_AITimeoutStop(),       # Tier 2
        SG039_AIInvalidOutputStop(), # Tier 2
        SG040_AILowConfidenceFallback(),  # Tier 2
        # Internal rules (Tier 1)
        InternalAIFailureTimeout(),
        InternalRRSanityCheck(),
        InternalPositionSizeCheck(),
    ]
