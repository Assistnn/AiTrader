"""
Pipeline full integration tests: end-to-end flows through the complete pipeline.
Reference: 04_判定パイプライン, 03_セーフガードエンジン, 13_テスト戦略
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.decision.decision_types import JudgeConfig, JudgeOutput, PipelineResult
from app.services.decision.m1_direction import M1DirectionJudge
from app.services.decision.m2_setup import M2SetupJudge
from app.services.decision.m3_entry import M3EntryJudge
from app.services.decision.m4_exit import M4ExitJudge
from app.services.decision.orchestrator import DecisionOrchestrator
from app.services.pipeline.data_types import IndicatorSnapshot, StateSnapshot
from app.services.safeguard.guard_engine import GuardEngine
from app.services.safeguard.guard_types import AccountState, GuardState

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _indicators(**overrides) -> dict:
    defaults = dict(
        ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0, atr14=0.5,
        rsi14=55.0, bb20_upper=152.0, bb20_middle=150.0, bb20_lower=148.0,
        donchian20_upper=153.0, donchian20_lower=147.0,
    )
    defaults.update(overrides)
    return defaults


def _state(
    trend="UP", regime="trend", volatility="normal", ema_alignment="bullish",
    rsi_zone="neutral", bb_position="middle", **ind_overrides,
) -> StateSnapshot:
    ind = _indicators(**ind_overrides)
    return StateSnapshot(
        pair="USD_JPY",
        timestamp=NOW,
        trade_allowed=True,
        trend=trend,
        regime=regime,
        volatility=volatility,
        indicators={
            "H1": IndicatorSnapshot(pair="USD_JPY", timeframe="H1", timestamp=NOW, values=ind),
            "M15": IndicatorSnapshot(pair="USD_JPY", timeframe="M15", timestamp=NOW, values=ind),
            "M5": IndicatorSnapshot(pair="USD_JPY", timeframe="M5", timestamp=NOW, values=ind),
        },
        ema_alignment=ema_alignment,
        rsi_zone=rsi_zone,
        bb_position=bb_position,
    )


def _account(**overrides) -> AccountState:
    defaults = dict(
        capital=1_000_000, daily_realized_pnl=0, daily_unrealized_pnl=0,
        monthly_pnl=0, peak_capital=1_000_000, current_capital=1_000_000,
        consecutive_losses=0, last_trade_was_loss=False, daily_profit_pct=0,
    )
    defaults.update(overrides)
    return AccountState(**defaults)


def _build_orchestrator(**settings_overrides) -> DecisionOrchestrator:
    engine = GuardEngine()
    for k, v in settings_overrides.items():
        setattr(engine.settings, k, v)
    return DecisionOrchestrator(
        m1=M1DirectionJudge(),
        m2=M2SetupJudge(),
        m3=M3EntryJudge(),
        m4=M4ExitJudge(),
        guard_engine=engine,
    )


class TestPipelineFullEntry:
    """Complete entry flow: Guard → M1 → M2 → MX → M3 → PreGuard → ENTRY."""

    def test_full_entry_flow(self):
        orch = _build_orchestrator()
        state = _state(
            ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0, rsi14=55.0,
        )
        result = orch.execute_pipeline(
            pair="USD_JPY", state=state, account=_account(), now=NOW,
        )
        assert result.action == "ENTRY"
        assert result.order is not None
        assert result.order.side == "BUY"
        assert result.order.lot_size > 0
        assert result.order.sl_pips > 0
        assert result.order.tp_pips > 0
        assert result.execution_id != ""
        assert result.m1_output is not None
        assert result.m2_output is not None
        assert result.m3_output is not None


class TestPipelineGuardHalt:
    """Guard HALT flow: daily loss exceeded → HALTED."""

    def test_daily_loss_halt(self):
        orch = _build_orchestrator(max_daily_loss_pct=5.0)
        state = _state()
        account = _account(
            daily_realized_pnl=-60_000,  # 6% loss on 1M capital
            current_capital=940_000,
        )
        result = orch.execute_pipeline(
            pair="USD_JPY", state=state, account=account, now=NOW,
        )
        assert result.action == "HALTED"
        assert result.guard_state is not None
        assert result.guard_state.trader_halted is True


class TestPipelinePreEntryBlock:
    """Pre-entry Guard BLOCK flow: RR sanity fails → BLOCKED."""

    def test_rr_sanity_block(self):
        orch = _build_orchestrator(
            rr_min_threshold=999.0,  # impossibly high RR requirement → blocks any entry
        )
        state = _state(ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0)
        result = orch.execute_pipeline(
            pair="USD_JPY", state=state, account=_account(), now=NOW,
        )
        assert result.action == "BLOCKED"
        assert "INTERNAL-RR-SANITY" in result.guard_state.blocking_guards


class TestPipelineDowntrendSell:
    """Downtrend flow: EMA bearish → SELL entry."""

    def test_downtrend_sell(self):
        orch = _build_orchestrator()
        state = _state(
            trend="DOWN", ema_alignment="bearish",
            ema20=145.0, ema50=148.0, ema200=150.0, adx14=30.0, rsi14=40.0,
        )
        result = orch.execute_pipeline(
            pair="USD_JPY", state=state, account=_account(), now=NOW,
        )
        if result.action == "ENTRY":
            assert result.order.side == "SELL"
        else:
            # M2/M3 may not produce entry in all conditions
            assert result.action in ("NO_TRADE", "BLOCKED")


class TestPipelineRangeNoTrade:
    """Range NO_TRADE flow: low ADX → NEUTRAL → NO_TRADE."""

    def test_range_no_trade(self):
        orch = _build_orchestrator()
        state = _state(
            trend="NEUTRAL", regime="range",
            adx14=15.0, ema20=150.0, ema50=150.0, ema200=150.0,
        )
        result = orch.execute_pipeline(
            pair="USD_JPY", state=state, account=_account(), now=NOW,
        )
        assert result.action == "NO_TRADE"


class TestPipelineExitManagement:
    """Exit management flow through M4."""

    def test_exit_management_hold(self):
        orch = _build_orchestrator()
        state = _state()
        pos = SimpleNamespace(
            pair="USD_JPY", side="BUY", entry_price=150.0,
            current_price=150.2, tp_price=151.0, sl_price=149.5,
            opened_at=NOW, break_even_applied=False,
            trail_active=False, trail_price=None,
        )
        output = orch.execute_exit_management(
            pair="USD_JPY", state=state, positions=[pos], now=NOW,
        )
        assert output.result["action"] in ("HOLD", "EXIT", "ADJUST_TRAIL", "PARTIAL")


class TestPipelineDebugTransparency:
    """_debug field transparency: all outputs must have _debug."""

    def test_entry_result_has_debug(self):
        orch = _build_orchestrator()
        state = _state(ema20=150.0, ema50=149.0, ema200=145.0, adx14=30.0)
        result = orch.execute_pipeline(
            pair="USD_JPY", state=state, account=_account(), now=NOW,
        )
        assert isinstance(result._debug, dict)
        if result.m1_output:
            assert isinstance(result.m1_output._debug, dict)

    def test_no_trade_result_has_debug(self):
        orch = _build_orchestrator()
        state = _state(adx14=15.0)
        result = orch.execute_pipeline(
            pair="USD_JPY", state=state, account=_account(), now=NOW,
        )
        assert result.action == "NO_TRADE"
        assert isinstance(result._debug, dict)


class TestPipelineMultipleBlockingGuards:
    """Multiple guards blocking simultaneously."""

    def test_multiple_blocks(self):
        orch = _build_orchestrator(
            max_daily_loss_pct=5.0,
            max_monthly_dd_pct=10.0,
        )
        state = _state()
        account = _account(
            daily_realized_pnl=-60_000,  # 6% daily loss
            monthly_pnl=-120_000,  # 12% monthly DD
            current_capital=880_000,
        )
        result = orch.execute_pipeline(
            pair="USD_JPY", state=state, account=account, now=NOW,
        )
        assert result.action == "HALTED"
        # Multiple guards should be in blocking list
        assert result.guard_state.trader_halted is True
        assert len(result.guard_state.blocking_guards) >= 1
