"""
BacktestRecorder: バックテスト実行中の結果記録.
Reference: 09_バックテストシミュレーション Section 3-1, 3-3
"""

from datetime import datetime, timezone

from app.services.backtest.backtest_types import (
    BacktestConfig,
    BacktestResult,
    BacktestTradeRecord,
    EquityPoint,
)


class BacktestRecorder:
    """バックテスト実行中のステップ・トレード記録."""

    def __init__(self, config: BacktestConfig, initial_equity: float) -> None:
        self._config = config
        self._initial_equity = initial_equity
        self._equity = initial_equity
        self._trades: list[BacktestTradeRecord] = []
        self._equity_curve: list[EquityPoint] = []
        self._step_count = 0
        self._started_at = datetime.now(timezone.utc)

    def record_step(
        self,
        timestamp: datetime,
        bar_close: float,
        equity: float,
        action: str,
    ) -> None:
        """1足分のステップを記録."""
        self._step_count += 1
        self._equity = equity
        self._equity_curve.append(
            EquityPoint(timestamp=timestamp, equity=equity, action=action)
        )

    def record_trade(self, trade: BacktestTradeRecord) -> None:
        """トレード記録."""
        self._trades.append(trade)

    @property
    def trades(self) -> list[BacktestTradeRecord]:
        return self._trades

    @property
    def equity(self) -> float:
        return self._equity

    def finalize(self, completed_at: datetime | None = None) -> BacktestResult:
        """記録を集約して BacktestResult を返す."""
        return BacktestResult(
            config=self._config,
            trades=self._trades,
            equity_curve=self._equity_curve,
            step_count=self._step_count,
            started_at=self._started_at,
            completed_at=completed_at or datetime.now(timezone.utc),
        )
