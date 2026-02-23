"""
Guard Engine tests.
Reference: 03_セーフガードエンジン, 13_テスト戦略
"""

from datetime import datetime, timedelta, timezone

from app.services.pipeline.data_types import (
    IndicatorSnapshot,
    StateSnapshot,
    Ticker,
)
from app.services.safeguard.guard_engine import GuardEngine
from app.services.safeguard.guard_rules import (
    EconomicEvent,
    PositionInfo,
    SG001_DailyMaxLoss,
    SG002_MonthlyMaxLoss,
    SG003_MaxDrawdown,
    SG004_005_ProfitStop,
    SG006_009_ConsecutiveLoss,
    SG012_SpreadAnomaly,
    SG013_015_ATRSpike,
    SG016_018_RangeSpike,
    SG019_TokyoSession,
    SG020_LondonSession,
    SG021_NewyorkSession,
    SG022_023_SessionStartBuffer,
    SG024_025_SessionEndBuffer,
    SG026_LowVolatilityStop,
    SG032_TrendBreakdownStop,
    SG033_ADXDropStop,
    SG034_RangeStop,
    SG035_MaxPositions,
    SG036_SameDirectionLimit,
    SG037_CorrelatedPairBlock,
    SG038_AITimeoutStop,
    SG039_AIInvalidOutputStop,
    SG040_AILowConfidenceFallback,
    InternalPriceSanityCheck,
    InternalRRSanityCheck,
    InternalPositionSizeCheck,
    InternalAIFailureTimeout,
    _is_dst_london,
    _is_dst_newyork,
)
from app.services.safeguard.guard_types import (
    AccountState,
    GuardResult,
    ProposedOrder,
    SafeguardSettings,
)

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _settings(**overrides) -> SafeguardSettings:
    return SafeguardSettings(**overrides)


def _account(**overrides) -> AccountState:
    defaults = dict(
        capital=1_000_000.0,
        daily_realized_pnl=0.0,
        daily_unrealized_pnl=0.0,
        monthly_pnl=0.0,
        peak_capital=1_000_000.0,
        current_capital=1_000_000.0,
        consecutive_losses=0,
        last_trade_was_loss=False,
        daily_profit_pct=0.0,
    )
    defaults.update(overrides)
    return AccountState(**defaults)


def _ticker(bid: float = 150.0, ask: float = 150.02) -> Ticker:
    return Ticker(timestamp=NOW, bid=bid, ask=ask, last=150.01, volume=1000.0)


def _state(**overrides) -> StateSnapshot:
    defaults = dict(
        pair="USD_JPY",
        timestamp=NOW,
        trade_allowed=True,
        trend="UP",
        regime="trend",
        volatility="normal",
        indicators={"H1": IndicatorSnapshot(
            pair="USD_JPY", timeframe="H1", timestamp=NOW,
            values={"ema20": 150.0, "ema50": 149.0, "atr14": 0.5, "adx14": 30.0, "rsi14": 55.0},
        )},
        ema_alignment="bullish",
        rsi_zone="neutral",
        bb_position="middle",
    )
    defaults.update(overrides)
    return StateSnapshot(**defaults)


# ===========================================================================
# Category 1: Capital Protection
# ===========================================================================


class TestSG001_DailyMaxLoss:
    def test_pass_when_within_limit(self):
        guard = SG001_DailyMaxLoss()
        settings = _settings(max_daily_loss_pct=10.0)
        account = _account(daily_realized_pnl=-50_000, daily_unrealized_pnl=0)
        # -5% < -10% threshold → PASS
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_halt_when_exceeded(self):
        guard = SG001_DailyMaxLoss()
        settings = _settings(max_daily_loss_pct=10.0)
        account = _account(daily_realized_pnl=-80_000, daily_unrealized_pnl=-30_000)
        # (-80000 + -30000) / 1000000 * 100 = -11% <= -10% → HALT
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.HALT

    def test_pass_when_no_account(self):
        guard = SG001_DailyMaxLoss()
        result = guard.evaluate(_settings(), None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG002_MonthlyMaxLoss:
    def test_halt_when_exceeded(self):
        guard = SG002_MonthlyMaxLoss()
        settings = _settings(max_monthly_loss_pct=20.0)
        account = _account(monthly_pnl=-250_000)
        # -25% <= -20% → HALT
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.HALT

    def test_pass_when_within_limit(self):
        guard = SG002_MonthlyMaxLoss()
        settings = _settings(max_monthly_loss_pct=20.0)
        account = _account(monthly_pnl=-100_000)
        # -10% > -20% → PASS
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG003_MaxDrawdown:
    def test_halt_when_exceeded(self):
        guard = SG003_MaxDrawdown()
        settings = _settings(max_drawdown_pct=30.0)
        account = _account(peak_capital=1_000_000, current_capital=650_000)
        # DD = 35% >= 30% → HALT
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.HALT

    def test_pass_when_within(self):
        guard = SG003_MaxDrawdown()
        settings = _settings(max_drawdown_pct=30.0)
        account = _account(peak_capital=1_000_000, current_capital=900_000)
        # DD = 10% < 30% → PASS
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG004_005_ProfitStop:
    def test_halt_when_target_reached(self):
        guard = SG004_005_ProfitStop()
        settings = _settings(stop_on_profit_enabled=True, stop_on_profit_target_pct=10.0)
        account = _account(daily_profit_pct=12.0)
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.HALT

    def test_pass_when_disabled(self):
        guard = SG004_005_ProfitStop()
        settings = _settings(stop_on_profit_enabled=False)
        account = _account(daily_profit_pct=20.0)
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG006_009_ConsecutiveLoss:
    def test_block_on_consecutive_losses(self):
        guard = SG006_009_ConsecutiveLoss()
        settings = _settings(consecutive_loss_enabled=True, consecutive_loss_max=3,
                             consecutive_loss_cooldown_min=60)
        account = _account(consecutive_losses=3)
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.BLOCK
        assert guard.cooldown_until is not None

    def test_pass_when_below_max(self):
        guard = SG006_009_ConsecutiveLoss()
        settings = _settings(consecutive_loss_enabled=True, consecutive_loss_max=3)
        account = _account(consecutive_losses=2)
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_cooldown_blocks_entry(self):
        guard = SG006_009_ConsecutiveLoss()
        settings = _settings(consecutive_loss_enabled=True, consecutive_loss_max=3,
                             consecutive_loss_cooldown_min=60)
        account = _account(consecutive_losses=3)
        # First evaluation triggers cooldown
        guard.evaluate(settings, None, None, account, [], [], None, NOW)
        # Second evaluation 30 min later should still block
        later = NOW + timedelta(minutes=30)
        account2 = _account(consecutive_losses=2)  # even if losses reduced
        result = guard.evaluate(settings, None, None, account2, [], [], None, later)
        assert result.result == GuardResult.BLOCK

    def test_cooldown_expires(self):
        guard = SG006_009_ConsecutiveLoss()
        settings = _settings(consecutive_loss_enabled=True, consecutive_loss_max=3,
                             consecutive_loss_cooldown_min=60)
        account = _account(consecutive_losses=3)
        guard.evaluate(settings, None, None, account, [], [], None, NOW)
        # 61 minutes later, cooldown should have expired
        later = NOW + timedelta(minutes=61)
        account2 = _account(consecutive_losses=0)
        result = guard.evaluate(settings, None, None, account2, [], [], None, later)
        assert result.result == GuardResult.PASS

    def test_lot_halving(self):
        guard = SG006_009_ConsecutiveLoss()
        settings = _settings(consecutive_loss_enabled=True, consecutive_loss_max=3,
                             consecutive_loss_cooldown_min=60, consecutive_loss_halve_lot=True)
        account = _account(consecutive_losses=3)
        guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert guard.lot_halved is True

    def test_pass_when_disabled(self):
        guard = SG006_009_ConsecutiveLoss()
        settings = _settings(consecutive_loss_enabled=False)
        account = _account(consecutive_losses=10)
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS


# ===========================================================================
# Category 2: Market Anomaly
# ===========================================================================


class TestSG012_SpreadAnomaly:
    def test_block_on_wide_spread(self):
        guard = SG012_SpreadAnomaly()
        settings = _settings(spread_max_multiple=2.0)
        # Seed history with normal spreads
        for _ in range(100):
            guard.record_spread(0.02)
        # Now check with wide spread
        ticker = Ticker(timestamp=NOW, bid=150.0, ask=150.10, last=150.05, volume=100)
        result = guard.evaluate(settings, None, ticker, None, [], [], None, NOW)
        assert result.result == GuardResult.BLOCK

    def test_pass_on_normal_spread(self):
        guard = SG012_SpreadAnomaly()
        settings = _settings(spread_max_multiple=2.0)
        for _ in range(100):
            guard.record_spread(0.02)
        ticker = Ticker(timestamp=NOW, bid=150.0, ask=150.02, last=150.01, volume=100)
        result = guard.evaluate(settings, None, ticker, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


# ===========================================================================
# Category 6: Execution Protection
# ===========================================================================


class TestSG035_MaxPositions:
    def test_block_when_max_reached(self):
        guard = SG035_MaxPositions()
        settings = _settings(exec_max_positions=3)
        positions = [
            PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0),
            PositionInfo(pair="EUR_USD", side="SELL", amount=1.0, entry_price=1.08),
            PositionInfo(pair="GBP_USD", side="BUY", amount=1.0, entry_price=1.27),
        ]
        result = guard.evaluate(settings, None, None, None, positions, [], None, NOW)
        assert result.result == GuardResult.BLOCK

    def test_pass_when_below_max(self):
        guard = SG035_MaxPositions()
        settings = _settings(exec_max_positions=3)
        positions = [
            PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0),
        ]
        result = guard.evaluate(settings, None, None, None, positions, [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG037_CorrelatedPairBlock:
    def test_block_correlated_pair(self):
        guard = SG037_CorrelatedPairBlock()
        settings = _settings(exec_block_correlated=True)
        positions = [PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0)]
        order = ProposedOrder(pair="EUR_JPY", side="BUY", lot_size=1.0, order_type="market")
        result = guard.evaluate(settings, None, None, None, positions, [], order, NOW)
        assert result.result == GuardResult.WARN  # Tier 2 → WARN

    def test_pass_uncorrelated_pair(self):
        guard = SG037_CorrelatedPairBlock()
        settings = _settings(exec_block_correlated=True)
        positions = [PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0)]
        order = ProposedOrder(pair="AUD_USD", side="BUY", lot_size=1.0, order_type="market")
        result = guard.evaluate(settings, None, None, None, positions, [], order, NOW)
        assert result.result == GuardResult.PASS


# ===========================================================================
# Internal Rules
# ===========================================================================


class TestInternalPriceSanityCheck:
    def test_block_when_deviation_exceeds_atr(self):
        guard = InternalPriceSanityCheck()
        settings = _settings(price_sanity_atr_multiple=3.0)
        state = _state()
        ticker = _ticker(bid=150.0, ask=150.02)
        # Limit price far from mid: 152.0 vs mid 150.01, deviation=1.99
        # ATR=0.5, max_deviation=1.5 → block
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0,
            order_type="limit", limit_price=152.0,
        )
        result = guard.evaluate(settings, state, ticker, None, [], [], order, NOW)
        assert result.result == GuardResult.BLOCK

    def test_pass_when_within_atr(self):
        guard = InternalPriceSanityCheck()
        settings = _settings(price_sanity_atr_multiple=3.0)
        state = _state()
        ticker = _ticker(bid=150.0, ask=150.02)
        # Limit price close to mid: 150.5 vs mid 150.01, deviation=0.49
        # ATR=0.5, max_deviation=1.5 → pass
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0,
            order_type="limit", limit_price=150.5,
        )
        result = guard.evaluate(settings, state, ticker, None, [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_skip_for_market_orders(self):
        guard = InternalPriceSanityCheck()
        settings = _settings()
        order = ProposedOrder(pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market")
        result = guard.evaluate(settings, None, None, None, [], [], order, NOW)
        assert result.result == GuardResult.PASS


class TestInternalRRSanityCheck:
    def test_block_low_rr(self):
        guard = InternalRRSanityCheck()
        settings = _settings(rr_min_threshold=0.8)
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market",
            tp_pips=10.0, sl_pips=20.0,  # RR = 0.5 < 0.8
        )
        result = guard.evaluate(settings, None, None, None, [], [], order, NOW)
        assert result.result == GuardResult.BLOCK

    def test_pass_good_rr(self):
        guard = InternalRRSanityCheck()
        settings = _settings(rr_min_threshold=0.8)
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market",
            tp_pips=20.0, sl_pips=10.0,  # RR = 2.0 > 0.8
        )
        result = guard.evaluate(settings, None, None, None, [], [], order, NOW)
        assert result.result == GuardResult.PASS


class TestInternalPositionSizeCheck:
    def test_block_oversized_position(self):
        guard = InternalPositionSizeCheck()
        settings = _settings(position_size_margin_pct=10.0)
        account = _account(capital=1_000_000)
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=10.0, order_type="market",
            sl_pips=50.0, risk_per_trade_pct=2.0,
            # risk = 10 * 50 * 100 = 50,000 → 5% > 2.0 * 1.1 = 2.2%
        )
        result = guard.evaluate(settings, None, None, account, [], [], order, NOW)
        assert result.result == GuardResult.BLOCK

    def test_pass_proper_size(self):
        guard = InternalPositionSizeCheck()
        settings = _settings(position_size_margin_pct=10.0)
        account = _account(capital=1_000_000)
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=0.2, order_type="market",
            sl_pips=50.0, risk_per_trade_pct=2.0,
            # risk = 0.2 * 50 * 100 = 1,000 → 0.1% < 2.2%
        )
        result = guard.evaluate(settings, None, None, account, [], [], order, NOW)
        assert result.result == GuardResult.PASS


class TestInternalAIFailureTimeout:
    def test_halt_on_timeout(self):
        guard = InternalAIFailureTimeout()
        settings = _settings(ai_failsafe_hold_timeout_minutes=30, ai_failsafe_emergency_close_all=True)
        guard.set_ai_hold(NOW - timedelta(minutes=35))
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.HALT

    def test_pass_when_not_in_hold(self):
        guard = InternalAIFailureTimeout()
        settings = _settings()
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


# ===========================================================================
# GuardEngine Integration
# ===========================================================================


class TestGuardEngine:
    def test_all_pass_when_no_issues(self):
        engine = GuardEngine()
        result = engine.evaluate_all(now=NOW)
        assert result.entry_allowed is True
        assert result.trader_halted is False
        assert result.force_close is False
        assert result.lot_multiplier == 1.0
        assert len(result.blocking_guards) == 0

    def test_halt_propagates(self):
        engine = GuardEngine(settings=_settings(max_daily_loss_pct=5.0))
        account = _account(daily_realized_pnl=-60_000, daily_unrealized_pnl=0)
        result = engine.evaluate_all(account=account, now=NOW)
        assert result.entry_allowed is False
        assert result.trader_halted is True
        assert "SG-001" in result.blocking_guards

    def test_block_propagates(self):
        engine = GuardEngine(settings=_settings(exec_max_positions=1))
        positions = [
            PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0),
        ]
        result = engine.evaluate_all(positions=positions, now=NOW)
        assert result.entry_allowed is False
        assert "SG-035" in result.blocking_guards
        assert result.trader_halted is False

    def test_all_guards_evaluated_even_after_halt(self):
        """No early termination — all guards evaluated. Reference: Section 2-3"""
        engine = GuardEngine(settings=_settings(max_daily_loss_pct=5.0, exec_max_positions=1))
        account = _account(daily_realized_pnl=-60_000)
        positions = [PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0)]
        result = engine.evaluate_all(account=account, positions=positions, now=NOW)
        # Both SG-001 (HALT) and SG-035 (BLOCK) should be in blocking_guards
        assert "SG-001" in result.blocking_guards
        assert "SG-035" in result.blocking_guards
        # All guards should have been evaluated
        assert len(result.evaluations) == len(engine.guards)

    def test_pre_entry_check(self):
        engine = GuardEngine(settings=_settings(rr_min_threshold=1.0))
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market",
            tp_pips=5.0, sl_pips=10.0,  # RR = 0.5 < 1.0
        )
        result = engine.evaluate_pre_entry(
            proposed_order=order, positions=[], now=NOW,
        )
        assert result.entry_allowed is False
        assert "INTERNAL-RR-SANITY" in result.blocking_guards

    def test_lot_multiplier_from_consecutive_loss(self):
        engine = GuardEngine(settings=_settings(
            consecutive_loss_enabled=True,
            consecutive_loss_max=3,
            consecutive_loss_cooldown_min=60,
            consecutive_loss_halve_lot=True,
        ))
        account = _account(consecutive_losses=3)
        result = engine.evaluate_all(account=account, now=NOW)
        assert result.lot_multiplier == 0.5

    def test_settings_from_config_json(self):
        config = {
            "sg.maxDailyLossPct": 5.0,
            "sg.exec.maxPositions": 2,
        }
        settings = SafeguardSettings.from_config_json(config)
        assert settings.max_daily_loss_pct == 5.0
        assert settings.exec_max_positions == 2
        # Defaults should remain
        assert settings.max_monthly_loss_pct == 20.0


# ===========================================================================
# Category 2: Market Anomaly (ATR Spike, Range Spike)
# ===========================================================================


class TestSG013_015_ATRSpike:
    def test_pass_when_disabled(self):
        guard = SG013_015_ATRSpike()
        settings = _settings(atr_spike_enabled=False)
        result = guard.evaluate(settings, _state(volatility="extreme"), None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_state(self):
        guard = SG013_015_ATRSpike()
        settings = _settings(atr_spike_enabled=True)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_primary_indicators(self):
        guard = SG013_015_ATRSpike()
        settings = _settings(atr_spike_enabled=True)
        state = _state(indicators={})
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_atr(self):
        guard = SG013_015_ATRSpike()
        settings = _settings(atr_spike_enabled=True)
        state = _state(indicators={"H1": IndicatorSnapshot(
            pair="USD_JPY", timeframe="H1", timestamp=NOW,
            values={"ema20": 150.0},  # no atr14
        )})
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_warn_on_extreme_volatility(self):
        guard = SG013_015_ATRSpike()
        settings = _settings(atr_spike_enabled=True)
        state = _state(volatility="extreme")
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.WARN  # Tier 2 → WARN
        assert "ATR_SPIKE" in result.reason

    def test_warn_on_high_volatility(self):
        guard = SG013_015_ATRSpike()
        settings = _settings(atr_spike_enabled=True)
        state = _state(volatility="high")
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.WARN
        assert "ATR_ELEVATED" in result.reason

    def test_pass_on_normal_volatility(self):
        guard = SG013_015_ATRSpike()
        settings = _settings(atr_spike_enabled=True)
        state = _state(volatility="normal")
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG016_018_RangeSpike:
    def test_pass_when_disabled(self):
        guard = SG016_018_RangeSpike()
        settings = _settings(range_spike_enabled=False)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_bars(self):
        guard = SG016_018_RangeSpike()
        settings = _settings(range_spike_enabled=True, range_spike_window_min=5, range_spike_max_pips=50.0)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_warn_on_spike(self):
        guard = SG016_018_RangeSpike()
        settings = _settings(range_spike_enabled=True, range_spike_window_min=5, range_spike_max_pips=50.0)
        # Record bars within window (range = 150.8 - 150.0 = 0.8 → 80 pips)
        guard.record_bar(150.8, 150.0, NOW - timedelta(minutes=2))
        guard.record_bar(150.5, 150.1, NOW - timedelta(minutes=1))
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.WARN  # Tier 2 → WARN
        assert "RANGE_SPIKE" in result.reason

    def test_pass_when_range_within_limit(self):
        guard = SG016_018_RangeSpike()
        settings = _settings(range_spike_enabled=True, range_spike_window_min=5, range_spike_max_pips=100.0)
        guard.record_bar(150.3, 150.0, NOW - timedelta(minutes=2))
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_window_filtering(self):
        guard = SG016_018_RangeSpike()
        settings = _settings(range_spike_enabled=True, range_spike_window_min=5, range_spike_max_pips=50.0)
        # Old bar (outside window) with extreme range
        guard.record_bar(160.0, 140.0, NOW - timedelta(minutes=10))
        # Recent bar (inside window) with small range
        guard.record_bar(150.2, 150.0, NOW - timedelta(minutes=1))
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_record_bar(self):
        guard = SG016_018_RangeSpike()
        guard.record_bar(150.5, 150.0, NOW)
        guard.record_bar(150.8, 150.2, NOW + timedelta(minutes=1))
        assert len(guard._recent_bars) == 2


# ===========================================================================
# Category 3: Session Time Control
# ===========================================================================


class TestDSTHelpers:
    def test_london_dst_summer(self):
        dt = datetime(2024, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert _is_dst_london(dt) is True

    def test_london_dst_winter(self):
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert _is_dst_london(dt) is False

    def test_london_dst_non_sunday_march31(self):
        """Cover line 406: while loop when March 31 is not Sunday (2025)"""
        # March 31, 2025 is Monday → while loop iterates to find last Sunday (March 30)
        dt = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert _is_dst_london(dt) is True

    def test_newyork_dst_summer(self):
        dt = datetime(2024, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert _is_dst_newyork(dt) is True

    def test_newyork_dst_winter(self):
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert _is_dst_newyork(dt) is False


class TestSG019_TokyoSession:
    def test_pass_when_disabled(self):
        guard = SG019_TokyoSession()
        settings = _settings(session_block_outside_tokyo=False)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_in_tokyo_session(self):
        guard = SG019_TokyoSession()
        settings = _settings(session_block_outside_tokyo=True)
        # UTC 16:00 = JST 01:00 → Tokyo session (15:00-23:59 UTC)
        now_utc = datetime(2024, 6, 15, 16, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.PASS

    def test_warn_outside_tokyo(self):
        guard = SG019_TokyoSession()
        settings = _settings(session_block_outside_tokyo=True)
        # UTC 10:00 = JST 19:00 → outside Tokyo session
        now_utc = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.WARN

    def test_boundary_hour_15_utc(self):
        guard = SG019_TokyoSession()
        settings = _settings(session_block_outside_tokyo=True)
        # UTC 15:00 → start of Tokyo session
        now_utc = datetime(2024, 6, 15, 15, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.PASS


class TestSG020_LondonSession:
    def test_pass_when_disabled(self):
        guard = SG020_LondonSession()
        settings = _settings(session_block_outside_london=False)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_in_london_summer(self):
        guard = SG020_LondonSession()
        settings = _settings(session_block_outside_london=True)
        # Summer: 07:00-15:30 UTC, test at 10:00
        now_utc = datetime(2024, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.PASS

    def test_warn_outside_london_summer(self):
        guard = SG020_LondonSession()
        settings = _settings(session_block_outside_london=True)
        # Summer: 07:00-15:30 UTC, test at 16:00 → outside
        now_utc = datetime(2024, 7, 15, 16, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.WARN

    def test_pass_in_london_winter(self):
        guard = SG020_LondonSession()
        settings = _settings(session_block_outside_london=True)
        # Winter: 08:00-16:30 UTC, test at 10:00
        now_utc = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.PASS

    def test_warn_outside_london_winter(self):
        guard = SG020_LondonSession()
        settings = _settings(session_block_outside_london=True)
        # Winter: 08:00-16:30 UTC, test at 17:00 → outside
        now_utc = datetime(2024, 1, 15, 17, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.WARN


class TestSG021_NewyorkSession:
    def test_pass_when_disabled(self):
        guard = SG021_NewyorkSession()
        settings = _settings(session_block_outside_newyork=False)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_in_ny_summer(self):
        guard = SG021_NewyorkSession()
        settings = _settings(session_block_outside_newyork=True)
        # Summer: 12:00-21:00 UTC, test at 15:00
        now_utc = datetime(2024, 7, 15, 15, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.PASS

    def test_warn_outside_ny_summer(self):
        guard = SG021_NewyorkSession()
        settings = _settings(session_block_outside_newyork=True)
        # Summer: 12:00-21:00 UTC, test at 22:00 → outside
        now_utc = datetime(2024, 7, 15, 22, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.WARN

    def test_pass_in_ny_winter(self):
        guard = SG021_NewyorkSession()
        settings = _settings(session_block_outside_newyork=True)
        # Winter: 13:00-22:00 UTC, test at 15:00
        now_utc = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.PASS

    def test_warn_outside_ny_winter(self):
        guard = SG021_NewyorkSession()
        settings = _settings(session_block_outside_newyork=True)
        # Winter: 13:00-22:00 UTC, test at 12:00 → outside
        now_utc = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = guard.evaluate(settings, None, None, None, [], [], None, now_utc)
        assert result.result == GuardResult.WARN


class TestSG022_023_SessionStartBuffer:
    def test_pass_when_disabled(self):
        guard = SG022_023_SessionStartBuffer()
        settings = _settings(session_start_buffer_enabled=False)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_enabled(self):
        guard = SG022_023_SessionStartBuffer()
        settings = _settings(session_start_buffer_enabled=True)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS  # placeholder


class TestSG024_025_SessionEndBuffer:
    def test_pass_when_disabled(self):
        guard = SG024_025_SessionEndBuffer()
        settings = _settings(session_end_buffer_enabled=False)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_enabled(self):
        guard = SG024_025_SessionEndBuffer()
        settings = _settings(session_end_buffer_enabled=True)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS  # placeholder


class TestSG026_LowVolatilityStop:
    def test_pass_when_disabled(self):
        guard = SG026_LowVolatilityStop()
        settings = _settings(low_vol_stop_enabled=False)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_state(self):
        guard = SG026_LowVolatilityStop()
        settings = _settings(low_vol_stop_enabled=True)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_warn_on_low_volatility(self):
        guard = SG026_LowVolatilityStop()
        settings = _settings(low_vol_stop_enabled=True)
        state = _state(volatility="low")
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.WARN
        assert "LOW_VOLATILITY" in result.reason

    def test_pass_on_normal_volatility(self):
        guard = SG026_LowVolatilityStop()
        settings = _settings(low_vol_stop_enabled=True)
        state = _state(volatility="normal")
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


# ===========================================================================
# Category 5: Regime Protection
# ===========================================================================


class TestSG032_TrendBreakdownStop:
    def test_pass_when_disabled(self):
        guard = SG032_TrendBreakdownStop()
        settings = _settings(regime_break_stop_enabled=False)
        state = _state(trend="NEUTRAL")
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_warn_on_consecutive_neutral(self):
        guard = SG032_TrendBreakdownStop()
        settings = _settings(regime_break_stop_enabled=True, regime_break_stop_count=3)
        for _ in range(3):
            state = _state(trend="NEUTRAL")
            result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.WARN
        assert "TREND_BREAKDOWN" in result.reason

    def test_pass_below_threshold(self):
        guard = SG032_TrendBreakdownStop()
        settings = _settings(regime_break_stop_enabled=True, regime_break_stop_count=3)
        for _ in range(2):
            state = _state(trend="NEUTRAL")
            result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_reset_on_trend(self):
        guard = SG032_TrendBreakdownStop()
        settings = _settings(regime_break_stop_enabled=True, regime_break_stop_count=3)
        # 2 x NEUTRAL
        for _ in range(2):
            guard.evaluate(settings, _state(trend="NEUTRAL"), None, None, [], [], None, NOW)
        # 1 x UP → resets counter
        guard.evaluate(settings, _state(trend="UP"), None, None, [], [], None, NOW)
        # 1 x NEUTRAL → counter=1, below threshold
        result = guard.evaluate(settings, _state(trend="NEUTRAL"), None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_record_trend_via_state(self):
        guard = SG032_TrendBreakdownStop()
        guard.record_trend("NEUTRAL")
        guard.record_trend("NEUTRAL")
        assert guard._neutral_count == 2
        guard.record_trend("UP")
        assert guard._neutral_count == 0


class TestSG033_ADXDropStop:
    def test_pass_when_disabled(self):
        guard = SG033_ADXDropStop()
        settings = _settings(regime_adx_drop_stop_enabled=False)
        result = guard.evaluate(settings, _state(), None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_state(self):
        guard = SG033_ADXDropStop()
        settings = _settings(regime_adx_drop_stop_enabled=True)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_h1_indicators(self):
        guard = SG033_ADXDropStop()
        settings = _settings(regime_adx_drop_stop_enabled=True)
        state = _state(indicators={})
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_adx(self):
        guard = SG033_ADXDropStop()
        settings = _settings(regime_adx_drop_stop_enabled=True)
        state = _state(indicators={"H1": IndicatorSnapshot(
            pair="USD_JPY", timeframe="H1", timestamp=NOW,
            values={"ema20": 150.0},  # no adx14
        )})
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_warn_on_low_adx(self):
        guard = SG033_ADXDropStop()
        settings = _settings(regime_adx_drop_stop_enabled=True, regime_adx_drop_threshold=20.0)
        state = _state(indicators={"H1": IndicatorSnapshot(
            pair="USD_JPY", timeframe="H1", timestamp=NOW,
            values={"adx14": 15.0},
        )})
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.WARN
        assert "ADX_DROP" in result.reason

    def test_pass_on_high_adx(self):
        guard = SG033_ADXDropStop()
        settings = _settings(regime_adx_drop_stop_enabled=True, regime_adx_drop_threshold=20.0)
        state = _state(indicators={"H1": IndicatorSnapshot(
            pair="USD_JPY", timeframe="H1", timestamp=NOW,
            values={"adx14": 25.0},
        )})
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG034_RangeStop:
    def test_pass_when_disabled(self):
        guard = SG034_RangeStop()
        settings = _settings(regime_range_stop_enabled=False)
        result = guard.evaluate(settings, _state(), None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_when_no_state(self):
        guard = SG034_RangeStop()
        settings = _settings(regime_range_stop_enabled=True)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_warn_on_range_regime(self):
        guard = SG034_RangeStop()
        settings = _settings(regime_range_stop_enabled=True)
        state = _state(regime="range")
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.WARN
        assert "RANGE_TREND_STOP" in result.reason

    def test_pass_on_trend_regime(self):
        guard = SG034_RangeStop()
        settings = _settings(regime_range_stop_enabled=True)
        state = _state(regime="trend")
        result = guard.evaluate(settings, state, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


# ===========================================================================
# Category 6: Execution Protection (additional)
# ===========================================================================


class TestSG036_SameDirectionLimit:
    def test_pass_when_no_order(self):
        guard = SG036_SameDirectionLimit()
        settings = _settings(exec_max_same_direction=2)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_warn_on_max_same_direction(self):
        guard = SG036_SameDirectionLimit()
        settings = _settings(exec_max_same_direction=2)
        positions = [
            PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0),
            PositionInfo(pair="EUR_JPY", side="BUY", amount=1.0, entry_price=160.0),
        ]
        order = ProposedOrder(pair="GBP_JPY", side="BUY", lot_size=1.0, order_type="market")
        result = guard.evaluate(settings, None, None, None, positions, [], order, NOW)
        assert result.result == GuardResult.WARN  # Tier 2 → WARN

    def test_pass_different_direction(self):
        guard = SG036_SameDirectionLimit()
        settings = _settings(exec_max_same_direction=2)
        positions = [
            PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0),
            PositionInfo(pair="EUR_JPY", side="BUY", amount=1.0, entry_price=160.0),
        ]
        order = ProposedOrder(pair="GBP_JPY", side="SELL", lot_size=1.0, order_type="market")
        result = guard.evaluate(settings, None, None, None, positions, [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_pass_below_limit(self):
        guard = SG036_SameDirectionLimit()
        settings = _settings(exec_max_same_direction=3)
        positions = [
            PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0),
        ]
        order = ProposedOrder(pair="GBP_JPY", side="BUY", lot_size=1.0, order_type="market")
        result = guard.evaluate(settings, None, None, None, positions, [], order, NOW)
        assert result.result == GuardResult.PASS


class TestSG038_AITimeoutStop:
    def test_always_pass(self):
        guard = SG038_AITimeoutStop()
        result = guard.evaluate(_settings(), None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG039_AIInvalidOutputStop:
    def test_always_pass(self):
        guard = SG039_AIInvalidOutputStop()
        result = guard.evaluate(_settings(), None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestSG040_AILowConfidenceFallback:
    def test_always_pass(self):
        guard = SG040_AILowConfidenceFallback()
        result = guard.evaluate(_settings(), None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


# ===========================================================================
# GuardEngine Additional Coverage
# ===========================================================================


class TestGuardEngineAdditionalCoverage:
    def test_evaluate_all_without_now(self):
        """Cover guard_engine.py line 64: now=None defaults to datetime.now(utc)"""
        engine = GuardEngine()
        result = engine.evaluate_all()
        assert result.entry_allowed is True
        assert len(result.evaluations) == len(engine.guards)

    def test_get_consecutive_loss_guard_when_missing(self):
        """Cover guard_engine.py line 116: return None when SG006 not in guards"""
        engine = GuardEngine()
        engine.guards = []  # remove all guards
        assert engine.get_consecutive_loss_guard() is None

    def test_aggregate_with_naive_cooldown(self):
        """Cover guard_engine.py line 155: naive datetime cooldown_until"""
        engine = GuardEngine(settings=_settings(
            consecutive_loss_enabled=True,
            consecutive_loss_max=3,
            consecutive_loss_cooldown_min=60,
        ))
        # Manually set a naive cooldown_until on the consecutive loss guard
        cl_guard = engine.get_consecutive_loss_guard()
        cl_guard._cooldown_until = datetime(2024, 6, 15, 13, 0, 0)  # naive
        # Evaluate with now < cooldown → entry_allowed=False
        result = engine.evaluate_all(now=NOW)
        assert result.entry_allowed is False
        assert result.cooldown_until is not None


# ===========================================================================
# Edge case coverage tests
# ===========================================================================


class TestCapitalProtectionEdgeCases:
    """Cover remaining edge cases in Category 1 guards."""

    def test_sg001_pass_zero_capital(self):
        """SG001: capital <= 0 → PASS (line 132)"""
        guard = SG001_DailyMaxLoss()
        account = _account(capital=0.0)
        result = guard.evaluate(_settings(), None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_sg002_pass_zero_capital(self):
        """SG002: capital <= 0 → PASS (line 155)"""
        guard = SG002_MonthlyMaxLoss()
        account = _account(capital=0.0)
        result = guard.evaluate(_settings(), None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_sg003_pass_zero_peak(self):
        """SG003: peak <= 0 → PASS (line 177)"""
        guard = SG003_MaxDrawdown()
        account = _account(peak_capital=0.0)
        result = guard.evaluate(_settings(), None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_sg004_005_pass_no_account(self):
        """SG004/005: account is None → PASS (line 197)"""
        guard = SG004_005_ProfitStop()
        settings = _settings(stop_on_profit_enabled=True, stop_on_profit_target_pct=10.0)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_sg004_005_pass_below_target(self):
        """SG004/005: profit below target → PASS (line 203)"""
        guard = SG004_005_ProfitStop()
        settings = _settings(stop_on_profit_enabled=True, stop_on_profit_target_pct=10.0)
        account = _account(daily_profit_pct=5.0)
        result = guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_sg006_009_reset_on_win(self):
        """SG006-009: reset_on_win() (lines 226-227)"""
        guard = SG006_009_ConsecutiveLoss()
        settings = _settings(
            consecutive_loss_enabled=True, consecutive_loss_max=3,
            consecutive_loss_cooldown_min=60, consecutive_loss_halve_lot=True,
        )
        account = _account(consecutive_losses=3)
        guard.evaluate(settings, None, None, account, [], [], None, NOW)
        assert guard.cooldown_until is not None
        assert guard.lot_halved is True
        guard.reset_on_win()
        assert guard.cooldown_until is None
        assert guard.lot_halved is False

    def test_sg006_009_naive_cooldown(self):
        """SG006-009: naive datetime cooldown_until (line 240)"""
        guard = SG006_009_ConsecutiveLoss()
        settings = _settings(
            consecutive_loss_enabled=True, consecutive_loss_max=3,
            consecutive_loss_cooldown_min=60,
        )
        account = _account(consecutive_losses=3)
        # Force naive datetime to trigger line 240
        naive_now = datetime(2024, 6, 15, 12, 0, 0)
        guard.evaluate(settings, None, None, account, [], [], None, naive_now)
        # Set cooldown to naive datetime manually
        guard._cooldown_until = datetime(2024, 6, 15, 13, 0, 0)
        # Evaluate again during cooldown
        later = datetime(2024, 6, 15, 12, 30, 0)
        account2 = _account(consecutive_losses=0)
        result = guard.evaluate(settings, None, None, account2, [], [], None, later)
        assert result.result == GuardResult.BLOCK


class TestSpreadAnomalyEdgeCases:
    def test_negative_spread_clamped_to_zero(self):
        """SG012: negative spread → 0 (line 293)"""
        guard = SG012_SpreadAnomaly()
        for _ in range(5):
            guard.record_spread(0.02)
        # ask < bid → negative spread
        ticker = Ticker(timestamp=NOW, bid=150.05, ask=150.00, last=150.02, volume=100)
        result = guard.evaluate(_settings(), None, ticker, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_single_spread_sample(self):
        """SG012: len < 2 → PASS (line 297)"""
        guard = SG012_SpreadAnomaly()
        # First evaluation with no history
        ticker = Ticker(timestamp=NOW, bid=150.0, ask=150.10, last=150.05, volume=100)
        result = guard.evaluate(_settings(), None, ticker, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_avg_spread_zero(self):
        """SG012: avg_spread <= 0 → PASS (line 301)"""
        guard = SG012_SpreadAnomaly()
        for _ in range(5):
            guard.record_spread(0.0)
        ticker = Ticker(timestamp=NOW, bid=150.0, ask=150.0, last=150.0, volume=100)
        result = guard.evaluate(_settings(), None, ticker, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS


class TestEconomicEventEdgeCases:
    def test_all_scope_matching_currency(self):
        """SG027-031: scope=ALL, matching currency (lines 613-617)"""
        from app.services.safeguard.guard_rules import SG027_031_EconomicEventFilter
        guard = SG027_031_EconomicEventFilter()
        settings = _settings(
            econ_stop_enabled=True, econ_stop_min_importance=2,
            econ_stop_before_min=30, econ_stop_after_min=15,
            econ_stop_currency_scope="ALL",
        )
        events = [EconomicEvent(
            event_datetime=NOW + timedelta(minutes=10),
            name="BOJ Rate Decision", currency="JPY", importance=3,
        )]
        state = _state(pair="USD_JPY")
        result = guard.evaluate(settings, state, None, None, [], events, None, NOW)
        assert result.result == GuardResult.WARN

    def test_all_scope_non_matching_currency(self):
        """SG027-031: scope=ALL, non-matching currency → PASS"""
        from app.services.safeguard.guard_rules import SG027_031_EconomicEventFilter
        guard = SG027_031_EconomicEventFilter()
        settings = _settings(
            econ_stop_enabled=True, econ_stop_min_importance=2,
            econ_stop_before_min=30, econ_stop_after_min=15,
            econ_stop_currency_scope="ALL",
        )
        events = [EconomicEvent(
            event_datetime=NOW + timedelta(minutes=10),
            name="ECB Meeting", currency="EUR", importance=3,
        )]
        state = _state(pair="USD_JPY")  # EUR not in USD_JPY currencies
        result = guard.evaluate(settings, state, None, None, [], events, None, NOW)
        assert result.result == GuardResult.PASS

    def test_usd_only_non_usd_event(self):
        """SG027-031: scope=USD_ONLY, non-USD event → PASS (line 615)"""
        from app.services.safeguard.guard_rules import SG027_031_EconomicEventFilter
        guard = SG027_031_EconomicEventFilter()
        settings = _settings(
            econ_stop_enabled=True, econ_stop_min_importance=2,
            econ_stop_before_min=30, econ_stop_after_min=15,
            econ_stop_currency_scope="USD_ONLY",
        )
        events = [EconomicEvent(
            event_datetime=NOW + timedelta(minutes=10),
            name="BOJ", currency="JPY", importance=3,
        )]
        result = guard.evaluate(settings, None, None, None, [], events, None, NOW)
        assert result.result == GuardResult.PASS

    def test_naive_event_datetime(self):
        """SG027-031: naive event datetime (line 621)"""
        from app.services.safeguard.guard_rules import SG027_031_EconomicEventFilter
        guard = SG027_031_EconomicEventFilter()
        settings = _settings(
            econ_stop_enabled=True, econ_stop_min_importance=2,
            econ_stop_before_min=30, econ_stop_after_min=15,
            econ_stop_currency_scope="USD_ONLY",
        )
        # Naive datetime (no tzinfo)
        events = [EconomicEvent(
            event_datetime=datetime(2024, 6, 15, 12, 10, 0),  # no tzinfo
            name="NFP", currency="USD", importance=3,
        )]
        result = guard.evaluate(settings, None, None, None, [], events, None, NOW)
        assert result.result == GuardResult.WARN

    def test_low_importance_skipped(self):
        """SG027-031: importance below threshold → PASS (line 613)"""
        from app.services.safeguard.guard_rules import SG027_031_EconomicEventFilter
        guard = SG027_031_EconomicEventFilter()
        settings = _settings(
            econ_stop_enabled=True, econ_stop_min_importance=3,
            econ_stop_before_min=30, econ_stop_after_min=15,
        )
        events = [EconomicEvent(
            event_datetime=NOW + timedelta(minutes=10),
            name="Minor Report", currency="USD", importance=1,
        )]
        result = guard.evaluate(settings, None, None, None, [], events, None, NOW)
        assert result.result == GuardResult.PASS

    def test_pair_from_proposed_order(self):
        """SG027-031: pair derived from proposed_order (line 599-600)"""
        from app.services.safeguard.guard_rules import SG027_031_EconomicEventFilter
        guard = SG027_031_EconomicEventFilter()
        settings = _settings(
            econ_stop_enabled=True, econ_stop_min_importance=2,
            econ_stop_before_min=30, econ_stop_after_min=15,
            econ_stop_currency_scope="ALL",
        )
        events = [EconomicEvent(
            event_datetime=NOW + timedelta(minutes=10),
            name="NFP", currency="USD", importance=3,
        )]
        order = ProposedOrder(pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market")
        result = guard.evaluate(settings, None, None, None, [], events, order, NOW)
        assert result.result == GuardResult.WARN


class TestInternalRulesEdgeCases:
    def test_price_sanity_no_proposed_order(self):
        """InternalPriceSanity: no order → PASS (line 835)"""
        guard = InternalPriceSanityCheck()
        result = guard.evaluate(_settings(), _state(), _ticker(), None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_price_sanity_no_ticker(self):
        """InternalPriceSanity: no ticker → PASS (line 838)"""
        guard = InternalPriceSanityCheck()
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0,
            order_type="limit", limit_price=150.0,
        )
        result = guard.evaluate(_settings(), _state(), None, None, [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_price_sanity_no_state(self):
        """InternalPriceSanity: no state → PASS (line 840)"""
        guard = InternalPriceSanityCheck()
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0,
            order_type="limit", limit_price=150.0,
        )
        result = guard.evaluate(_settings(), None, _ticker(), None, [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_price_sanity_no_limit_price(self):
        """InternalPriceSanity: limit_price is None → PASS (line 844)"""
        guard = InternalPriceSanityCheck()
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0,
            order_type="limit",  # limit_price=None by default
        )
        result = guard.evaluate(_settings(), _state(), _ticker(), None, [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_price_sanity_no_h1_indicators(self):
        """InternalPriceSanity: no H1 indicators → PASS (line 852)"""
        guard = InternalPriceSanityCheck()
        state = _state(indicators={})
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0,
            order_type="limit", limit_price=150.0,
        )
        result = guard.evaluate(_settings(), state, _ticker(), None, [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_price_sanity_no_atr_in_indicators(self):
        """InternalPriceSanity: atr14 missing or zero → PASS (line 855)"""
        guard = InternalPriceSanityCheck()
        state = _state(indicators={"H1": IndicatorSnapshot(
            pair="USD_JPY", timeframe="H1", timestamp=NOW,
            values={"ema20": 150.0},  # no atr14
        )})
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0,
            order_type="limit", limit_price=150.0,
        )
        result = guard.evaluate(_settings(), state, _ticker(), None, [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_ai_failure_clear_hold(self):
        """InternalAIFailureTimeout: clear_ai_hold() (lines 891-892)"""
        guard = InternalAIFailureTimeout()
        guard.set_ai_hold(NOW)
        assert guard.ai_hold_state is True
        guard.clear_ai_hold()
        assert guard.ai_hold_state is False
        assert guard.ai_hold_start_time is None

    def test_ai_failure_naive_start(self):
        """InternalAIFailureTimeout: naive start datetime (line 902)"""
        guard = InternalAIFailureTimeout()
        settings = _settings(ai_failsafe_hold_timeout_minutes=30, ai_failsafe_emergency_close_all=True)
        # Set ai_hold with naive datetime
        guard.ai_hold_state = True
        guard.ai_hold_start_time = datetime(2024, 6, 15, 11, 0, 0)  # naive
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.HALT

    def test_ai_failure_within_timeout(self):
        """InternalAIFailureTimeout: within timeout → PASS (line 914)"""
        guard = InternalAIFailureTimeout()
        settings = _settings(ai_failsafe_hold_timeout_minutes=30, ai_failsafe_emergency_close_all=True)
        guard.set_ai_hold(NOW - timedelta(minutes=10))  # only 10 min
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_rr_sanity_no_sl(self):
        """InternalRR: sl_pips None or 0 → PASS (line 930)"""
        guard = InternalRRSanityCheck()
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market",
            tp_pips=20.0, sl_pips=0.0,
        )
        result = guard.evaluate(_settings(), None, None, None, [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_position_size_no_sl(self):
        """InternalPositionSize: no sl_pips → PASS (lines 954)"""
        guard = InternalPositionSizeCheck()
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market",
            sl_pips=None, risk_per_trade_pct=2.0,
        )
        result = guard.evaluate(_settings(), None, None, _account(), [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_position_size_no_risk_pct(self):
        """InternalPositionSize: no risk_per_trade_pct → PASS (line 956)"""
        guard = InternalPositionSizeCheck()
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market",
            sl_pips=10.0,  # risk_per_trade_pct=None by default
        )
        result = guard.evaluate(_settings(), None, None, _account(), [], [], order, NOW)
        assert result.result == GuardResult.PASS

    def test_position_size_zero_capital(self):
        """InternalPositionSize: capital <= 0 → PASS (line 960)"""
        guard = InternalPositionSizeCheck()
        account = _account(capital=0.0)
        order = ProposedOrder(
            pair="USD_JPY", side="BUY", lot_size=1.0, order_type="market",
            sl_pips=10.0, risk_per_trade_pct=2.0,
        )
        result = guard.evaluate(_settings(), None, None, account, [], [], order, NOW)
        assert result.result == GuardResult.PASS


class TestSG037CorrelatedEdgeCases:
    def test_no_order(self):
        """SG037: no proposed_order → PASS"""
        guard = SG037_CorrelatedPairBlock()
        settings = _settings(exec_block_correlated=True)
        result = guard.evaluate(settings, None, None, None, [], [], None, NOW)
        assert result.result == GuardResult.PASS

    def test_disabled(self):
        """SG037: exec_block_correlated=False → PASS (line 764)"""
        guard = SG037_CorrelatedPairBlock()
        settings = _settings(exec_block_correlated=False)
        order = ProposedOrder(pair="EUR_JPY", side="BUY", lot_size=1.0, order_type="market")
        positions = [PositionInfo(pair="USD_JPY", side="BUY", amount=1.0, entry_price=150.0)]
        result = guard.evaluate(settings, None, None, None, positions, [], order, NOW)
        assert result.result == GuardResult.PASS


class TestEconomicEventFilter:
    def test_warn_on_upcoming_event(self):
        engine = GuardEngine(settings=_settings(
            econ_stop_enabled=True,
            econ_stop_min_importance=3,
            econ_stop_before_min=30,
            econ_stop_after_min=15,
            econ_stop_currency_scope="USD_ONLY",
        ))
        events = [
            EconomicEvent(
                event_datetime=NOW + timedelta(minutes=20),
                name="NFP",
                currency="USD",
                importance=3,
            ),
        ]
        state = _state()
        result = engine.evaluate_all(state=state, economic_events=events, now=NOW)
        # SG-031 should have fired (WARN for Tier 2)
        econ_evals = [e for e in result.evaluations if e.guard_id == "SG-031"]
        assert len(econ_evals) == 1
        assert econ_evals[0].result == GuardResult.WARN

    def test_pass_when_no_events(self):
        engine = GuardEngine(settings=_settings(econ_stop_enabled=True))
        result = engine.evaluate_all(now=NOW)
        econ_evals = [e for e in result.evaluations if e.guard_id == "SG-031"]
        assert econ_evals[0].result == GuardResult.PASS

    def test_pass_when_disabled(self):
        engine = GuardEngine(settings=_settings(econ_stop_enabled=False))
        events = [
            EconomicEvent(
                event_datetime=NOW + timedelta(minutes=5),
                name="CPI", currency="USD", importance=3,
            ),
        ]
        result = engine.evaluate_all(economic_events=events, now=NOW)
        econ_evals = [e for e in result.evaluations if e.guard_id == "SG-031"]
        assert econ_evals[0].result == GuardResult.PASS
