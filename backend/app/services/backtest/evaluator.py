"""
BacktestEvaluator: バックテスト結果の評価指標算出.
Reference: 09_バックテストシミュレーション Section 5-1, 5-2
"""

from __future__ import annotations

import math

from app.services.backtest.backtest_types import (
    BacktestMetrics,
    BacktestResult,
    BacktestTradeRecord,
    EquityPoint,
)


class BacktestEvaluator:
    """バックテスト結果から BacktestMetrics を算出."""

    def calculate(self, result: BacktestResult) -> BacktestMetrics:
        """BacktestResult から BacktestMetrics を計算."""
        trades = result.trades
        equity_curve = result.equity_curve
        config = result.config

        if not trades:
            return BacktestMetrics()

        # 損益
        total_pnl = sum(t.realized_pnl for t in trades)
        total_pnl_pct = (total_pnl / config.capital * 100) if config.capital > 0 else 0.0

        # トレード統計
        total_trades = len(trades)
        wins = [t for t in trades if t.realized_pnl > 0]
        losses = [t for t in trades if t.realized_pnl <= 0]
        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # 収益性
        total_win = sum(t.realized_pnl for t in wins)
        total_loss = abs(sum(t.realized_pnl for t in losses))
        profit_factor = (total_win / total_loss) if total_loss > 0 else float("inf") if total_win > 0 else 0.0

        avg_win = (total_win / winning_trades) if winning_trades > 0 else 0.0
        avg_loss = (total_loss / losing_trades) if losing_trades > 0 else 0.0

        avg_win_pips = (sum(t.realized_pnl_pips for t in wins) / winning_trades) if winning_trades > 0 else 0.0
        avg_loss_pips = (abs(sum(t.realized_pnl_pips for t in losses)) / losing_trades) if losing_trades > 0 else 0.0

        # RR 比
        rr_values = [t.rr_ratio for t in trades if t.rr_ratio > 0]
        avg_rr_ratio = (sum(rr_values) / len(rr_values)) if rr_values else 0.0
        rr_distribution = self._rr_distribution(trades)

        # リスク: 最大ドローダウン
        max_dd_pct, max_dd_amount = self._max_drawdown(equity_curve, config.capital)

        # シャープレシオ（年率換算）
        sharpe_ratio = self._sharpe_ratio(trades, config.capital)

        # カルマーレシオ
        calmar_ratio = 0.0
        if max_dd_pct > 0:
            calmar_ratio = total_pnl_pct / max_dd_pct

        # 時間
        durations = self._hold_durations(trades)
        avg_hold_min = (sum(durations) / len(durations)) if durations else 0.0
        max_hold_min = max(durations) if durations else 0.0

        # セーフガード統計（equity_curve の action から集計）
        guard_block_count = sum(1 for e in equity_curve if e.action == "BLOCKED")
        guard_halt_count = sum(1 for e in equity_curve if e.action == "HALTED")

        # 破綻確率推定
        ruin_prob = estimate_ruin_probability(
            win_rate=win_rate / 100.0,
            avg_rr=avg_rr_ratio,
            risk_per_trade_pct=config.risk_per_trade_pct,
        )

        return BacktestMetrics(
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_win_pips=avg_win_pips,
            avg_loss_pips=avg_loss_pips,
            avg_rr_ratio=avg_rr_ratio,
            rr_distribution=rr_distribution,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_amount=max_dd_amount,
            sharpe_ratio=sharpe_ratio,
            calmar_ratio=calmar_ratio,
            avg_hold_duration_min=avg_hold_min,
            max_hold_duration_min=max_hold_min,
            guard_block_count=guard_block_count,
            guard_halt_count=guard_halt_count,
            ruin_probability=ruin_prob,
        )

    @staticmethod
    def _max_drawdown(
        equity_curve: list[EquityPoint], initial_capital: float,
    ) -> tuple[float, float]:
        """最大ドローダウンを計算. 返り値: (pct, amount)."""
        if not equity_curve:
            return 0.0, 0.0

        peak = initial_capital
        max_dd_amount = 0.0
        for point in equity_curve:
            if point.equity > peak:
                peak = point.equity
            dd = peak - point.equity
            if dd > max_dd_amount:
                max_dd_amount = dd

        max_dd_pct = (max_dd_amount / peak * 100) if peak > 0 else 0.0
        return max_dd_pct, max_dd_amount

    @staticmethod
    def _sharpe_ratio(trades: list[BacktestTradeRecord], capital: float) -> float:
        """年率シャープレシオ（簡易計算）."""
        if len(trades) < 2:
            return 0.0
        returns = [t.realized_pnl / capital for t in trades]
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(var_r) if var_r > 0 else 0.0
        if std_r == 0:
            return 0.0
        # 年率換算: √252（日次換算）を概算で使用
        return (mean_r / std_r) * math.sqrt(252)

    @staticmethod
    def _hold_durations(trades: list[BacktestTradeRecord]) -> list[float]:
        """各トレードの保有時間（分）."""
        durations = []
        for t in trades:
            if t.entry_timestamp and t.exit_timestamp:
                delta = (t.exit_timestamp - t.entry_timestamp).total_seconds() / 60.0
                durations.append(abs(delta))
        return durations

    @staticmethod
    def _rr_distribution(trades: list[BacktestTradeRecord]) -> dict:
        """RR 分布をバケットに集計."""
        buckets = {"<0.5": 0, "0.5-1.0": 0, "1.0-1.5": 0, "1.5-2.0": 0, "2.0-3.0": 0, ">3.0": 0}
        for t in trades:
            rr = t.rr_ratio
            if rr < 0.5:
                buckets["<0.5"] += 1
            elif rr < 1.0:
                buckets["0.5-1.0"] += 1
            elif rr < 1.5:
                buckets["1.0-1.5"] += 1
            elif rr < 2.0:
                buckets["1.5-2.0"] += 1
            elif rr < 3.0:
                buckets["2.0-3.0"] += 1
            else:
                buckets[">3.0"] += 1
        return buckets


def estimate_ruin_probability(
    win_rate: float,
    avg_rr: float,
    risk_per_trade_pct: float,
) -> float:
    """破綻確率推定（Kelly基準ベース）. Reference: Section 5-2.

    edge = win_rate * avg_rr - (1 - win_rate)
    IF edge <= 0: return 1.0
    risk_of_ruin ≈ ((1 - edge) / (1 + edge)) ^ (100 / risk_per_trade_pct)
    """
    if risk_per_trade_pct <= 0:
        return 1.0

    edge = win_rate * avg_rr - (1 - win_rate)
    if edge <= 0:
        return 1.0

    ratio = (1 - edge) / (1 + edge)
    if ratio <= 0:
        return 0.0
    units = 100.0 / risk_per_trade_pct
    return ratio ** units
