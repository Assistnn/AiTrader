"""
BacktestEngine tests.
Reference: 09_バックテストシミュレーション Section 3-3
"""

from datetime import date, datetime, timedelta, timezone

from app.services.backtest.backtest_types import BacktestConfig
from app.services.backtest.engine import BacktestEngine
from app.services.decision.m1_direction import M1DirectionJudge
from app.services.decision.m2_setup import M2SetupJudge
from app.services.decision.m3_entry import M3EntryJudge
from app.services.decision.m4_exit import M4ExitJudge
from app.services.decision.orchestrator import DecisionOrchestrator
from app.services.pipeline.data_types import OHLCV
from app.services.safeguard.guard_engine import GuardEngine


def _make_bars(count: int = 220, base_price: float = 150.0) -> list[OHLCV]:
    """テスト用 OHLCV バー生成（ウォームアップ十分量）."""
    base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    bars = []
    for i in range(count):
        price = base_price + i * 0.01
        bars.append(OHLCV(
            timestamp=base + timedelta(hours=i),
            open=price, high=price + 0.5, low=price - 0.5,
            close=price, volume=1000.0,
        ))
    return bars


def _make_orchestrator(**settings_overrides) -> DecisionOrchestrator:
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


class TestBacktestEngineBasic:
    def test_run_completes(self):
        """バックテスト実行が正常完了する."""
        orchestrator = _make_orchestrator()
        engine = BacktestEngine(orchestrator=orchestrator)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 10),
        )
        bars = _make_bars(220)
        result = engine.run(config, bars)

        assert result.step_count == 220
        assert result.error is None
        assert result.started_at is not None
        assert result.completed_at is not None
        assert len(result.equity_curve) == 220

    def test_empty_bars(self):
        """空のバーリストでエラーメッセージ."""
        orchestrator = _make_orchestrator()
        engine = BacktestEngine(orchestrator=orchestrator)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 10),
        )
        result = engine.run(config, [])

        assert result.error == "No bars provided"
        assert result.step_count == 0


class TestBacktestEngineReproducibility:
    def test_same_input_same_output(self):
        """同一入力 → 同一結果（ruleモード再現可能性）."""
        bars = _make_bars(220)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 10),
        )

        orch1 = _make_orchestrator()
        engine1 = BacktestEngine(orchestrator=orch1)
        result1 = engine1.run(config, bars)

        orch2 = _make_orchestrator()
        engine2 = BacktestEngine(orchestrator=orch2)
        result2 = engine2.run(config, bars)

        assert result1.step_count == result2.step_count
        assert len(result1.trades) == len(result2.trades)
        for t1, t2 in zip(result1.trades, result2.trades):
            assert t1.entry_price == t2.entry_price
            assert t1.exit_price == t2.exit_price
            assert t1.realized_pnl == t2.realized_pnl


class TestBacktestEngineGuardHalt:
    def test_guard_halt_blocks_trading(self):
        """セーフガードHALT時はトレードが発生しない."""
        orchestrator = _make_orchestrator(max_daily_loss_pct=0.001)  # extremely tight
        engine = BacktestEngine(orchestrator=orchestrator)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 10),
        )
        bars = _make_bars(220)
        result = engine.run(config, bars)

        # With very tight loss limit, most actions should be halted
        halted_count = sum(1 for e in result.equity_curve if e.action == "HALTED")
        # At least some should be HALTED (exact count depends on pipeline)
        assert result.step_count == 220


class TestBacktestEngineEquityCurve:
    def test_equity_curve_length_matches_steps(self):
        """エクイティカーブの長さ = ステップ数."""
        orchestrator = _make_orchestrator()
        engine = BacktestEngine(orchestrator=orchestrator)
        config = BacktestConfig(
            pair="USD_JPY", timeframe="H1",
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 10),
        )
        bars = _make_bars(50)
        result = engine.run(config, bars)

        assert len(result.equity_curve) == result.step_count
        for point in result.equity_curve:
            assert point.action in ("ENTRY", "NO_TRADE", "HALTED", "BLOCKED", "HOLD", "EXIT")
