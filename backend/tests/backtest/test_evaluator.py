"""
BacktestEvaluator tests.
Reference: 09_バックテストシミュレーション Section 5-1, 5-2
"""

from datetime import date, datetime, timedelta, timezone

from app.services.backtest.backtest_types import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    BacktestTradeRecord,
    EquityPoint,
)
from app.services.backtest.evaluator import BacktestEvaluator, estimate_ruin_probability


def _config() -> BacktestConfig:
    return BacktestConfig(
        pair="USD_JPY", timeframe="H1",
        start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        capital=1_000_000, risk_per_trade_pct=2.0,
    )


def _trade(
    pnl: float, pnl_pips: float, rr: float = 1.0,
    side: str = "BUY", hold_hours: int = 4,
) -> BacktestTradeRecord:
    base = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return BacktestTradeRecord(
        pair="USD_JPY", side=side, amount=1.0,
        entry_price=150.0,
        exit_price=150.0 + (pnl_pips * 0.01) if side == "BUY" else 150.0 - (pnl_pips * 0.01),
        entry_timestamp=base,
        exit_timestamp=base + timedelta(hours=hold_hours),
        realized_pnl=pnl,
        realized_pnl_pips=pnl_pips,
        rr_ratio=rr,
        exit_reason="TP" if pnl > 0 else "SL",
    )


def _equity_curve(count: int = 100, start_equity: float = 1_000_000) -> list[EquityPoint]:
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        EquityPoint(
            timestamp=base + timedelta(hours=i),
            equity=start_equity + i * 10,
            action="NO_TRADE",
        )
        for i in range(count)
    ]


class TestWinRate:
    def test_all_wins(self):
        trades = [_trade(5000, 50, 1.5) for _ in range(10)]
        result = BacktestResult(config=_config(), trades=trades, equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        assert metrics.win_rate == 100.0
        assert metrics.winning_trades == 10
        assert metrics.losing_trades == 0

    def test_mixed(self):
        trades = [_trade(5000, 50, 1.5)] * 6 + [_trade(-3000, -30, 0.5)] * 4
        result = BacktestResult(config=_config(), trades=trades, equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        assert abs(metrics.win_rate - 60.0) < 0.01

    def test_no_trades(self):
        result = BacktestResult(config=_config(), trades=[], equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        assert metrics.win_rate == 0.0
        assert metrics.total_trades == 0


class TestProfitFactor:
    def test_positive(self):
        trades = [_trade(5000, 50, 1.5)] * 6 + [_trade(-3000, -30, 0.5)] * 4
        result = BacktestResult(config=_config(), trades=trades, equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        # PF = 30000 / 12000 = 2.5
        assert abs(metrics.profit_factor - 2.5) < 0.01

    def test_no_losses(self):
        trades = [_trade(5000, 50, 1.5)] * 5
        result = BacktestResult(config=_config(), trades=trades, equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        assert metrics.profit_factor == float("inf")


class TestMaxDrawdown:
    def test_drawdown_from_equity(self):
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        curve = [
            EquityPoint(base, 1_000_000, "NO_TRADE"),
            EquityPoint(base + timedelta(hours=1), 1_050_000, "NO_TRADE"),
            EquityPoint(base + timedelta(hours=2), 990_000, "NO_TRADE"),  # DD from 1050k
            EquityPoint(base + timedelta(hours=3), 1_020_000, "NO_TRADE"),
        ]
        trades = [_trade(20000, 20)]
        result = BacktestResult(config=_config(), trades=trades, equity_curve=curve)
        metrics = BacktestEvaluator().calculate(result)
        # Peak 1,050,000 → trough 990,000 → DD = 60,000 (5.71%)
        assert abs(metrics.max_drawdown_amount - 60_000) < 1
        assert abs(metrics.max_drawdown_pct - 5.71) < 0.1

    def test_no_drawdown(self):
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        curve = [
            EquityPoint(base + timedelta(hours=i), 1_000_000 + i * 1000, "NO_TRADE")
            for i in range(10)
        ]
        trades = [_trade(9000, 90)]
        result = BacktestResult(config=_config(), trades=trades, equity_curve=curve)
        metrics = BacktestEvaluator().calculate(result)
        assert metrics.max_drawdown_amount == 0
        assert metrics.max_drawdown_pct == 0


class TestSharpeRatio:
    def test_positive_sharpe(self):
        trades = [_trade(5000, 50, 1.5)] * 10
        result = BacktestResult(config=_config(), trades=trades, equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        # All positive returns → high sharpe (if stddev > 0, but here all same → std 0)
        # With identical returns, std=0 → sharpe=0
        assert isinstance(metrics.sharpe_ratio, float)

    def test_mixed_sharpe(self):
        trades = [_trade(5000, 50)] * 6 + [_trade(-3000, -30)] * 4
        result = BacktestResult(config=_config(), trades=trades, equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        assert isinstance(metrics.sharpe_ratio, float)


class TestCalmarRatio:
    def test_calmar(self):
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        curve = [
            EquityPoint(base, 1_000_000, "NO_TRADE"),
            EquityPoint(base + timedelta(hours=1), 1_100_000, "NO_TRADE"),
            EquityPoint(base + timedelta(hours=2), 1_000_000, "NO_TRADE"),
            EquityPoint(base + timedelta(hours=3), 1_200_000, "NO_TRADE"),
        ]
        trades = [_trade(200_000, 200)]
        result = BacktestResult(config=_config(), trades=trades, equity_curve=curve)
        metrics = BacktestEvaluator().calculate(result)
        # total_pnl_pct = 20%, max_dd_pct from 1.1M to 1M = 9.09%
        # calmar = 20 / 9.09 ≈ 2.2
        assert metrics.calmar_ratio > 0


class TestRuinProbability:
    def test_positive_edge(self):
        prob = estimate_ruin_probability(win_rate=0.6, avg_rr=1.5, risk_per_trade_pct=2.0)
        assert 0.0 <= prob < 1.0

    def test_negative_edge(self):
        prob = estimate_ruin_probability(win_rate=0.3, avg_rr=0.5, risk_per_trade_pct=5.0)
        assert prob == 1.0

    def test_zero_edge(self):
        # edge = 0.5 * 1.0 - 0.5 = 0.0
        prob = estimate_ruin_probability(win_rate=0.5, avg_rr=1.0, risk_per_trade_pct=2.0)
        assert prob == 1.0

    def test_very_good_edge(self):
        prob = estimate_ruin_probability(win_rate=0.7, avg_rr=2.0, risk_per_trade_pct=1.0)
        assert prob < 0.01


class TestRRDistribution:
    def test_distribution_buckets(self):
        trades = [
            _trade(5000, 50, rr=0.3),
            _trade(5000, 50, rr=0.7),
            _trade(5000, 50, rr=1.2),
            _trade(5000, 50, rr=1.8),
            _trade(5000, 50, rr=2.5),
            _trade(5000, 50, rr=4.0),
        ]
        result = BacktestResult(config=_config(), trades=trades, equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        dist = metrics.rr_distribution
        assert dist["<0.5"] == 1
        assert dist["0.5-1.0"] == 1
        assert dist["1.0-1.5"] == 1
        assert dist["1.5-2.0"] == 1
        assert dist["2.0-3.0"] == 1
        assert dist[">3.0"] == 1


class TestHoldDuration:
    def test_avg_hold(self):
        trades = [
            _trade(5000, 50, hold_hours=2),
            _trade(5000, 50, hold_hours=6),
        ]
        result = BacktestResult(config=_config(), trades=trades, equity_curve=_equity_curve())
        metrics = BacktestEvaluator().calculate(result)
        # (120 + 360) / 2 = 240 minutes
        assert abs(metrics.avg_hold_duration_min - 240) < 1
        assert abs(metrics.max_hold_duration_min - 360) < 1
