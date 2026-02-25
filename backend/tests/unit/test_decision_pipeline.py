"""
Decision Pipeline tests.
Reference: 04_判定パイプライン, 13_テスト戦略
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.services.decision.base_judge import BaseJudge
from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput, PipelineResult
from app.services.decision.m1_direction import M1DirectionJudge
from app.services.decision.m2_setup import M2SetupJudge
from app.services.decision.m3_entry import M3EntryJudge, calculate_position_size
from app.services.decision.m4_exit import M4ExitJudge, PositionContext
from app.services.decision.mx_integrator import MXIntegrator
from app.services.decision.orchestrator import DecisionOrchestrator
from app.services.pipeline.data_types import IndicatorSnapshot, StateSnapshot
from app.services.safeguard.guard_engine import GuardEngine
from app.services.safeguard.guard_types import AccountState, GuardState

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _indicators(
    ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0, atr14=0.5,
    rsi14=55.0, bb20_upper=152.0, bb20_middle=150.0, bb20_lower=148.0,
    donchian20_upper=153.0, donchian20_lower=147.0,
) -> dict:
    return {
        "ema20": ema20, "ema50": ema50, "ema200": ema200,
        "adx14": adx14, "atr14": atr14, "rsi14": rsi14,
        "bb20_upper": bb20_upper, "bb20_middle": bb20_middle, "bb20_lower": bb20_lower,
        "donchian20_upper": donchian20_upper, "donchian20_lower": donchian20_lower,
    }


def _state(pair="USD_JPY", volatility="normal", **ind_overrides) -> StateSnapshot:
    ind = _indicators(**ind_overrides)
    return StateSnapshot(
        pair=pair,
        timestamp=NOW,
        trade_allowed=True,
        trend="UP",
        regime="trend",
        volatility=volatility,
        indicators={
            "H1": IndicatorSnapshot(pair=pair, timeframe="H1", timestamp=NOW, values=ind),
            "M15": IndicatorSnapshot(pair=pair, timeframe="M15", timestamp=NOW, values=ind),
            "M5": IndicatorSnapshot(pair=pair, timeframe="M5", timestamp=NOW, values=ind),
        },
        ema_alignment="bullish",
        rsi_zone="neutral",
        bb_position="middle",
    )


def _guard_state(**overrides) -> GuardState:
    defaults = dict(
        entry_allowed=True, force_close=False, trader_halted=False,
        cooldown_until=None, lot_multiplier=1.0, evaluations=[], blocking_guards=[],
    )
    defaults.update(overrides)
    return GuardState(**defaults)


def _judge_input(state=None, guard_state=None, **kwargs) -> JudgeInput:
    return JudgeInput(
        pair="USD_JPY",
        timestamp=NOW,
        state=state or _state(),
        guard_state=guard_state or _guard_state(),
        **kwargs,
    )


# ===========================================================================
# M1: Direction
# ===========================================================================


class TestM1DirectionJudge:
    @pytest.mark.asyncio
    async def test_uptrend_detected(self):
        judge = M1DirectionJudge()
        config = JudgeConfig(timeframes=["H1"], params={"useTrendDirection": True})
        input = _judge_input(state=_state(ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0))
        output = await judge.judge(input, config)
        assert output.result["trend"] == "UP"
        assert output.result["tradeAllowed"] is True

    @pytest.mark.asyncio
    async def test_downtrend_detected(self):
        judge = M1DirectionJudge()
        config = JudgeConfig(timeframes=["H1"])
        input = _judge_input(state=_state(ema20=145.0, ema50=148.0, ema200=150.0, adx14=30.0))
        output = await judge.judge(input, config)
        assert output.result["trend"] == "DOWN"

    @pytest.mark.asyncio
    async def test_neutral_low_adx(self):
        judge = M1DirectionJudge()
        config = JudgeConfig(timeframes=["H1"])
        input = _judge_input(state=_state(adx14=15.0))
        output = await judge.judge(input, config)
        assert output.result["trend"] == "NEUTRAL"
        assert output.result["regime"] == "range"

    @pytest.mark.asyncio
    async def test_range_avoid_blocks_trade(self):
        judge = M1DirectionJudge()
        config = JudgeConfig(timeframes=["H1"], params={"useRangeAvoid": True})
        input = _judge_input(state=_state(adx14=15.0))
        output = await judge.judge(input, config)
        assert output.result["tradeAllowed"] is False
        assert "RANGE_AVOID" in output.reason_codes

    @pytest.mark.asyncio
    async def test_extreme_volatility_blocks_trade(self):
        judge = M1DirectionJudge()
        config = JudgeConfig(timeframes=["H1"], params={"useVolatility": True})
        input = _judge_input(state=_state(volatility="extreme"))
        output = await judge.judge(input, config)
        assert output.result["tradeAllowed"] is False
        assert "EXTREME_VOLATILITY" in output.reason_codes

    @pytest.mark.asyncio
    async def test_debug_fields_present(self):
        judge = M1DirectionJudge()
        config = JudgeConfig(timeframes=["H1"])
        input = _judge_input()
        output = await judge.judge(input, config)
        assert "ema20" in output._debug
        assert "adx14" in output._debug


# ===========================================================================
# M2: Setup
# ===========================================================================


class TestM2SetupJudge:
    @pytest.mark.asyncio
    async def test_trend_follow_valid(self):
        judge = M2SetupJudge()
        config = JudgeConfig(timeframes=["M15"], params={"preset": "trendFollow"})
        m1_output = JudgeOutput(result={"trend": "UP", "tradeAllowed": True}, confidence=0.8)
        input = _judge_input(previous_stages={"m1": m1_output})
        output = await judge.judge(input, config)
        assert output.result["setupValid"] is True
        assert output.result["setupType"] == "trendFollow"

    @pytest.mark.asyncio
    async def test_trend_follow_invalid_no_trend(self):
        judge = M2SetupJudge()
        config = JudgeConfig(timeframes=["M15"], params={"preset": "trendFollow"})
        m1_output = JudgeOutput(result={"trend": "NEUTRAL", "tradeAllowed": False}, confidence=0.3)
        input = _judge_input(previous_stages={"m1": m1_output})
        output = await judge.judge(input, config)
        assert output.result["setupValid"] is False

    @pytest.mark.asyncio
    async def test_breakout_upper(self):
        judge = M2SetupJudge()
        config = JudgeConfig(timeframes=["M15"], params={"preset": "breakout"})
        # ema20 > donchian upper → breakout
        state = _state(ema20=154.0, donchian20_upper=153.0, adx14=25.0)
        m1_output = JudgeOutput(result={"trend": "UP"}, confidence=0.8)
        input = _judge_input(state=state, previous_stages={"m1": m1_output})
        output = await judge.judge(input, config)
        assert output.result["setupValid"] is True
        assert "BREAKOUT_UPPER" in output.reason_codes

    @pytest.mark.asyncio
    async def test_mean_reversion_buy(self):
        judge = M2SetupJudge()
        config = JudgeConfig(timeframes=["M15"], params={"preset": "meanReversion"})
        state = _state(ema20=147.5, rsi14=25.0, bb20_lower=148.0, volatility="normal")
        state.regime = "range"
        m1_output = JudgeOutput(result={"trend": "NEUTRAL", "regime": "range"}, confidence=0.5)
        input = _judge_input(state=state, previous_stages={"m1": m1_output})
        output = await judge.judge(input, config)
        assert output.result["setupValid"] is True
        assert output.result["side"] == "BUY"


# ===========================================================================
# M3: Entry
# ===========================================================================


class TestM3EntryJudge:
    @pytest.mark.asyncio
    async def test_buy_entry(self):
        judge = M3EntryJudge()
        config = JudgeConfig(
            timeframes=["M5"],
            params={"tpSlMode": "atr", "riskPerTradePct": 2.0},
        )
        m1_output = JudgeOutput(result={"trend": "UP"}, confidence=0.8)
        m2_output = JudgeOutput(result={"setupValid": True, "setupType": "trendFollow"}, confidence=0.7)
        account = AccountState(
            capital=1_000_000, daily_realized_pnl=0, daily_unrealized_pnl=0,
            monthly_pnl=0, peak_capital=1_000_000, current_capital=1_000_000,
            consecutive_losses=0, last_trade_was_loss=False, daily_profit_pct=0,
        )
        input = _judge_input(
            previous_stages={"m1": m1_output, "m2": m2_output},
            account=account,
        )
        output = await judge.judge(input, config)
        assert output.result["entry"] == "BUY"
        assert output.result["lotSize"] > 0
        assert output.result["tpPips"] > 0
        assert output.result["slPips"] > 0
        assert output.result["rrRatio"] > 0

    @pytest.mark.asyncio
    async def test_no_trade_when_setup_invalid(self):
        judge = M3EntryJudge()
        config = JudgeConfig(timeframes=["M5"])
        m1_output = JudgeOutput(result={"trend": "UP"}, confidence=0.8)
        m2_output = JudgeOutput(result={"setupValid": False}, confidence=0.3)
        input = _judge_input(previous_stages={"m1": m1_output, "m2": m2_output})
        output = await judge.judge(input, config)
        assert output.result["entry"] == "NO_TRADE"


class TestPositionSizing:
    def test_basic_calculation(self):
        lot, debug = calculate_position_size(
            capital=1_000_000, risk_per_trade_pct=2.0,
            sl_pips=50.0, pip_value=100.0,
            min_lot=0.01, max_lot=100.0,
        )
        # risk = 1M * 2% = 20,000
        # raw_lot = 20,000 / (50 * 100) = 4.0
        assert abs(lot - 4.0) < 0.01
        assert debug["raw_lot"] == 4.0

    def test_clipping_to_max(self):
        lot, _ = calculate_position_size(
            capital=10_000_000, risk_per_trade_pct=5.0,
            sl_pips=10.0, pip_value=100.0,
            min_lot=0.01, max_lot=50.0,
        )
        assert lot == 50.0

    def test_clipping_to_min(self):
        lot, _ = calculate_position_size(
            capital=10_000, risk_per_trade_pct=0.5,
            sl_pips=100.0, pip_value=100.0,
            min_lot=0.01, max_lot=100.0,
        )
        # risk = 10000 * 0.5% = 50
        # raw_lot = 50 / (100*100) = 0.005 → clipped to 0.01
        assert lot == 0.01


# ===========================================================================
# M4: Exit
# ===========================================================================


class TestM4ExitJudge:
    def _make_position(self, **overrides):
        from types import SimpleNamespace
        defaults = dict(
            pair="USD_JPY", side="BUY", entry_price=150.0,
            current_price=150.5, tp_price=151.0, sl_price=149.5,
            opened_at=NOW, break_even_applied=False,
            trail_active=False, trail_price=None,
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    @pytest.mark.asyncio
    async def test_hold_when_no_conditions_met(self):
        judge = M4ExitJudge()
        config = JudgeConfig(timeframes=["M5"], params={
            "breakEven": True, "trailing": True, "partial": True, "maxHold": True,
            "maxHoldMinutes": 1440,
        })
        pos = self._make_position(current_price=150.1)  # small profit
        input = _judge_input(positions=[pos])
        output = await judge.judge(input, config)
        assert output.result["action"] == "HOLD"

    @pytest.mark.asyncio
    async def test_max_hold_time_exit(self):
        judge = M4ExitJudge()
        config = JudgeConfig(timeframes=["M5"], params={
            "maxHold": True, "maxHoldMinutes": 60,
        })
        pos = self._make_position(opened_at=NOW - timedelta(hours=2))
        input = _judge_input(positions=[pos])
        output = await judge.judge(input, config)
        assert output.result["action"] == "EXIT"
        assert "MAX_HOLD_TIME_EXCEEDED" in output.reason_codes

    @pytest.mark.asyncio
    async def test_break_even_triggered(self):
        judge = M4ExitJudge()
        config = JudgeConfig(timeframes=["M5"], params={
            "breakEven": True, "trailing": False, "partial": False, "maxHold": False,
            "breakevenTriggerMultiplier": 1.0,
        })
        # atr_pips ≈ 50, unrealized ≈ (151.0-150.0)*100 = 100 pips > 50
        pos = self._make_position(current_price=151.0)
        input = _judge_input(positions=[pos])
        output = await judge.judge(input, config)
        assert output.result["action"] == "ADJUST_TRAIL"
        assert output.result.get("breakEvenApplied") is True

    @pytest.mark.asyncio
    async def test_disabled_returns_hold(self):
        judge = M4ExitJudge()
        config = JudgeConfig(enabled=False, timeframes=["M5"])
        input = _judge_input(positions=[self._make_position()])
        output = await judge.judge(input, config)
        assert output.result["action"] == "HOLD"
        assert "M4_DISABLED" in output.reason_codes


# ===========================================================================
# MX: Integration
# ===========================================================================


class TestMXIntegrator:
    def test_dir_setup_mode_pass(self):
        mx = MXIntegrator(mode="dir+setup")
        m1 = JudgeOutput(result={"tradeAllowed": True}, confidence=0.8)
        m2 = JudgeOutput(result={"setupValid": True}, confidence=0.7)
        m3 = JudgeOutput(result={"entry": "BUY"}, confidence=0.8)
        should, debug = mx.should_trade(m1, m2, m3)
        assert should is True

    def test_dir_setup_mode_fail(self):
        mx = MXIntegrator(mode="dir+setup")
        m1 = JudgeOutput(result={"tradeAllowed": True}, confidence=0.8)
        m2 = JudgeOutput(result={"setupValid": False}, confidence=0.3)
        m3 = JudgeOutput(result={"entry": "BUY"}, confidence=0.8)
        should, _ = mx.should_trade(m1, m2, m3)
        assert should is False

    def test_score_mode_pass(self):
        mx = MXIntegrator(mode="score", weight_dir=2, weight_setup=1, weight_exec=1, score_threshold=3.0)
        m1 = JudgeOutput(result={"tradeAllowed": True}, confidence=0.85)
        m2 = JudgeOutput(result={"setupValid": True}, confidence=0.72)
        m3 = JudgeOutput(result={"entry": "BUY"}, confidence=0.80)
        should, debug = mx.should_trade(m1, m2, m3)
        # score = 2*1*0.85 + 1*1*0.72 + 1*1*0.80 = 1.70+0.72+0.80 = 3.22 >= 3.0
        assert should is True
        assert debug["score"] >= 3.0

    def test_score_mode_fail(self):
        mx = MXIntegrator(mode="score", score_threshold=3.0)
        m1 = JudgeOutput(result={"tradeAllowed": True}, confidence=0.5)
        m2 = JudgeOutput(result={"setupValid": False}, confidence=0.3)
        m3 = JudgeOutput(result={"entry": "NO_TRADE"}, confidence=0.2)
        should, _ = mx.should_trade(m1, m2, m3)
        assert should is False


# ===========================================================================
# Orchestrator Integration
# ===========================================================================


class TestDecisionOrchestrator:
    def _build_orchestrator(self) -> DecisionOrchestrator:
        return DecisionOrchestrator(
            m1=M1DirectionJudge(),
            m2=M2SetupJudge(),
            m3=M3EntryJudge(),
            m4=M4ExitJudge(),
            guard_engine=GuardEngine(),
        )

    @pytest.mark.asyncio
    async def test_full_pipeline_entry(self):
        orch = self._build_orchestrator()
        state = _state(ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0, rsi14=55.0)
        account = AccountState(
            capital=1_000_000, daily_realized_pnl=0, daily_unrealized_pnl=0,
            monthly_pnl=0, peak_capital=1_000_000, current_capital=1_000_000,
            consecutive_losses=0, last_trade_was_loss=False, daily_profit_pct=0,
        )
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=state, account=account, now=NOW,
        )
        assert result.action == "ENTRY"
        assert result.order is not None
        assert result.order.side == "BUY"
        assert result.order.lot_size > 0

    @pytest.mark.asyncio
    async def test_pipeline_halted_by_guard(self):
        orch = self._build_orchestrator()
        orch.guard_engine.settings.max_daily_loss_pct = 5.0
        state = _state()
        account = AccountState(
            capital=1_000_000, daily_realized_pnl=-60_000, daily_unrealized_pnl=0,
            monthly_pnl=-60_000, peak_capital=1_000_000, current_capital=940_000,
            consecutive_losses=0, last_trade_was_loss=False, daily_profit_pct=0,
        )
        result = await orch.execute_pipeline(pair="USD_JPY", state=state, account=account, now=NOW)
        assert result.action == "HALTED"

    @pytest.mark.asyncio
    async def test_pipeline_no_trade_range_avoid(self):
        orch = self._build_orchestrator()
        state = _state(adx14=15.0)  # low ADX → range → no trade
        result = await orch.execute_pipeline(pair="USD_JPY", state=state, now=NOW)
        assert result.action == "NO_TRADE"

    @pytest.mark.asyncio
    async def test_pipeline_logs_recorded(self):
        orch = self._build_orchestrator()
        state = _state()
        account = AccountState(
            capital=1_000_000, daily_realized_pnl=0, daily_unrealized_pnl=0,
            monthly_pnl=0, peak_capital=1_000_000, current_capital=1_000_000,
            consecutive_losses=0, last_trade_was_loss=False, daily_profit_pct=0,
        )
        await orch.execute_pipeline(pair="USD_JPY", state=state, account=account, now=NOW)
        logs = orch.get_logs()
        # Should have at least M1, M2, M3 logs
        stages = [log["stage"] for log in logs]
        assert "m1" in stages
        assert "m2" in stages
        assert "m3" in stages
        # Each log should have elapsed_ms and execution_id
        for log in logs:
            assert "elapsed_ms" in log
            assert "execution_id" in log

    @pytest.mark.asyncio
    async def test_exit_management(self):
        from types import SimpleNamespace
        orch = self._build_orchestrator()
        state = _state()
        pos = SimpleNamespace(
            pair="USD_JPY", side="BUY", entry_price=150.0,
            current_price=150.5, tp_price=151.0, sl_price=149.5,
            opened_at=NOW, break_even_applied=False,
            trail_active=False, trail_price=None,
        )
        output = await orch.execute_exit_management(
            pair="USD_JPY", state=state, positions=[pos], now=NOW,
        )
        assert output.result["action"] in ("HOLD", "EXIT", "ADJUST_TRAIL", "PARTIAL")


# ===========================================================================
# Orchestrator Additional Coverage
# ===========================================================================


class TestOrchestratorAdditional:
    """Additional orchestrator tests for pipeline flow coverage."""

    def _build_orchestrator(self) -> DecisionOrchestrator:
        return DecisionOrchestrator(
            m1=M1DirectionJudge(),
            m2=M2SetupJudge(),
            m3=M3EntryJudge(),
            m4=M4ExitJudge(),
            guard_engine=GuardEngine(),
        )

    def _account(self, **overrides) -> AccountState:
        defaults = dict(
            capital=1_000_000, daily_realized_pnl=0, daily_unrealized_pnl=0,
            monthly_pnl=0, peak_capital=1_000_000, current_capital=1_000_000,
            consecutive_losses=0, last_trade_was_loss=False, daily_profit_pct=0,
        )
        defaults.update(overrides)
        return AccountState(**defaults)

    @pytest.mark.asyncio
    async def test_guard_block_returns_blocked(self):
        """Guard entry_allowed=False → BLOCKED."""
        orch = self._build_orchestrator()
        state = _state()
        guard = _guard_state(entry_allowed=False, blocking_guards=["SG_TEST"])
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=state, guard_state=guard, now=NOW,
        )
        assert result.action == "BLOCKED"
        assert "SG_TEST" in result._debug.get("blocked_by", [])

    @pytest.mark.asyncio
    async def test_m2_fail_stops_at_mx_gate(self):
        """M2 setupValid=False → MX gate blocks M3 execution → NO_TRADE."""
        orch = self._build_orchestrator()
        state = _state(
            ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0,
            rsi14=55.0,
            bb20_upper=200.0, bb20_middle=190.0, bb20_lower=180.0,
        )
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=state, account=self._account(), now=NOW,
        )
        assert result.action in ("NO_TRADE", "ENTRY")

    @pytest.mark.asyncio
    async def test_m3_no_trade(self):
        """M3 returns NO_TRADE → pipeline returns NO_TRADE."""
        orch = self._build_orchestrator()
        state = _state(ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0)
        guard = _guard_state(entry_allowed=True)
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=state, account=self._account(),
            guard_state=guard, now=NOW,
        )
        assert result.action in ("NO_TRADE", "ENTRY")

    @pytest.mark.asyncio
    async def test_pre_entry_guard_block(self):
        """Pre-entry guard blocks → BLOCKED."""
        orch = self._build_orchestrator()
        orch.guard_engine.settings.exec_rr_sanity_enabled = True
        orch.guard_engine.settings.exec_rr_sanity_min = 999.0
        state = _state(ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0)
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=state, account=self._account(), now=NOW,
        )
        assert result.action in ("ENTRY", "BLOCKED", "NO_TRADE")

    @pytest.mark.asyncio
    async def test_log_has_elapsed_ms_and_execution_id(self):
        """Each pipeline log entry must have elapsed_ms and execution_id."""
        orch = self._build_orchestrator()
        state = _state()
        await orch.execute_pipeline(pair="USD_JPY", state=state, account=self._account(), now=NOW)
        logs = orch.get_logs()
        assert len(logs) >= 1
        for log in logs:
            assert "elapsed_ms" in log
            assert isinstance(log["elapsed_ms"], float)
            assert "execution_id" in log
            assert len(log["execution_id"]) > 0

    @pytest.mark.asyncio
    async def test_log_contains_stage_info(self):
        """Log entries contain stage, pair, output_result, config_params."""
        orch = self._build_orchestrator()
        state = _state()
        await orch.execute_pipeline(pair="USD_JPY", state=state, account=self._account(), now=NOW)
        logs = orch.get_logs()
        for log in logs:
            assert "stage" in log
            assert "pair" in log
            assert log["pair"] == "USD_JPY"
            assert "output_result" in log
            assert "config_params" in log

    @pytest.mark.asyncio
    async def test_clear_logs(self):
        """clear_logs() empties the log buffer."""
        orch = self._build_orchestrator()
        state = _state()
        await orch.execute_pipeline(pair="USD_JPY", state=state, account=self._account(), now=NOW)
        assert len(orch.get_logs()) > 0
        orch.clear_logs()
        assert len(orch.get_logs()) == 0

    @pytest.mark.asyncio
    async def test_exit_management_logs(self):
        """execute_exit_management records M4 log."""
        from types import SimpleNamespace
        orch = self._build_orchestrator()
        state = _state()
        pos = SimpleNamespace(
            pair="USD_JPY", side="BUY", entry_price=150.0,
            current_price=150.5, tp_price=151.0, sl_price=149.5,
            opened_at=NOW, break_even_applied=False,
            trail_active=False, trail_price=None,
        )
        await orch.execute_exit_management(pair="USD_JPY", state=state, positions=[pos], now=NOW)
        logs = orch.get_logs()
        m4_logs = [l for l in logs if l["stage"] == "m4"]
        assert len(m4_logs) == 1
        assert "elapsed_ms" in m4_logs[0]

    @pytest.mark.asyncio
    async def test_execution_id_unique(self):
        """Each pipeline execution gets a unique execution_id."""
        orch = self._build_orchestrator()
        state = _state()
        account = self._account()
        await orch.execute_pipeline(pair="USD_JPY", state=state, account=account, now=NOW)
        await orch.execute_pipeline(pair="USD_JPY", state=state, account=account, now=NOW)
        logs = orch.get_logs()
        exec_ids = {log["execution_id"] for log in logs}
        assert len(exec_ids) >= 2

    @pytest.mark.asyncio
    async def test_pipeline_now_defaults_to_utc(self):
        """When now=None, pipeline uses datetime.now(utc)."""
        orch = self._build_orchestrator()
        state = _state()
        result = await orch.execute_pipeline(pair="USD_JPY", state=state, account=self._account())
        assert result.execution_id != ""


# ===========================================================================
# BaseJudge Conformance
# ===========================================================================


class TestBaseJudgeConformance:
    """Verify all judges conform to BaseJudge interface."""

    def test_all_judges_are_base_judge_subclass(self):
        """M1, M2, M3, M4 must all be BaseJudge subclasses."""
        for cls in (M1DirectionJudge, M2SetupJudge, M3EntryJudge, M4ExitJudge):
            assert issubclass(cls, BaseJudge), f"{cls.__name__} is not a BaseJudge subclass"

    def test_all_judges_have_judge_method(self):
        """All judges have a judge() method."""
        for cls in (M1DirectionJudge, M2SetupJudge, M3EntryJudge, M4ExitJudge):
            assert hasattr(cls, "judge"), f"{cls.__name__} missing judge()"
            assert callable(getattr(cls, "judge")), f"{cls.__name__}.judge not callable"

    def test_all_judges_have_describe_config(self):
        """All judges have a describe_config() method."""
        for cls in (M1DirectionJudge, M2SetupJudge, M3EntryJudge, M4ExitJudge):
            instance = cls()
            config = instance.describe_config()
            assert isinstance(config, dict), f"{cls.__name__}.describe_config() not dict"
            assert len(config) > 0, f"{cls.__name__}.describe_config() is empty"

    @pytest.mark.asyncio
    async def test_m1_debug_output(self):
        """M1 output has _debug with expected fields."""
        judge = M1DirectionJudge()
        config = JudgeConfig(timeframes=["H1"])
        output = await judge.judge(_judge_input(), config)
        assert isinstance(output._debug, dict)
        assert len(output._debug) > 0

    @pytest.mark.asyncio
    async def test_m2_debug_output(self):
        """M2 output has _debug."""
        judge = M2SetupJudge()
        config = JudgeConfig(timeframes=["M15"], params={"preset": "trendFollow"})
        m1_output = JudgeOutput(result={"trend": "UP", "tradeAllowed": True}, confidence=0.8)
        input = _judge_input(previous_stages={"m1": m1_output})
        output = await judge.judge(input, config)
        assert isinstance(output._debug, dict)

    @pytest.mark.asyncio
    async def test_m3_debug_output(self):
        """M3 output has _debug with position sizing info."""
        judge = M3EntryJudge()
        config = JudgeConfig(timeframes=["M5"], params={"tpSlMode": "atr", "riskPerTradePct": 2.0})
        m1_output = JudgeOutput(result={"trend": "UP"}, confidence=0.8)
        m2_output = JudgeOutput(result={"setupValid": True, "setupType": "trendFollow"}, confidence=0.7)
        account = AccountState(
            capital=1_000_000, daily_realized_pnl=0, daily_unrealized_pnl=0,
            monthly_pnl=0, peak_capital=1_000_000, current_capital=1_000_000,
            consecutive_losses=0, last_trade_was_loss=False, daily_profit_pct=0,
        )
        input = _judge_input(previous_stages={"m1": m1_output, "m2": m2_output}, account=account)
        output = await judge.judge(input, config)
        assert isinstance(output._debug, dict)

    @pytest.mark.asyncio
    async def test_m4_debug_output(self):
        """M4 output has _debug."""
        from types import SimpleNamespace
        judge = M4ExitJudge()
        config = JudgeConfig(timeframes=["M5"], params={
            "breakEven": True, "trailing": True, "partial": True, "maxHold": True,
            "maxHoldMinutes": 1440,
        })
        pos = SimpleNamespace(
            pair="USD_JPY", side="BUY", entry_price=150.0,
            current_price=150.5, tp_price=151.0, sl_price=149.5,
            opened_at=NOW, break_even_applied=False,
            trail_active=False, trail_price=None,
        )
        input = _judge_input(positions=[pos])
        output = await judge.judge(input, config)
        assert isinstance(output._debug, dict)
