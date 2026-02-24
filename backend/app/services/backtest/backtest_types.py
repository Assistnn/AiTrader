"""
Backtest data types.
Reference: 09_バックテストシミュレーション Section 3-3, 5-1, 5-2
"""

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class BacktestConfig:
    """バックテスト設定."""

    pair: str
    timeframe: str
    start_date: date
    end_date: date
    capital: float = 1_000_000.0
    slippage_pips: float = 0.5
    risk_per_trade_pct: float = 2.0

    # 判断パイプライン設定（TraderConfig 相当）
    safeguard_overrides: dict = field(default_factory=dict)
    judge_overrides: dict = field(default_factory=dict)


@dataclass
class BacktestTradeRecord:
    """バックテスト内の個別トレード記録."""

    pair: str
    side: str  # "BUY" | "SELL"
    amount: float
    entry_price: float
    exit_price: float
    entry_timestamp: datetime
    exit_timestamp: datetime
    realized_pnl: float
    realized_pnl_pips: float
    rr_ratio: float
    exit_reason: str  # "TP" | "SL" | "TRAIL" | "EXIT_SIGNAL" | "TIMEOUT"
    pipeline_log_json: dict = field(default_factory=dict)


@dataclass
class EquityPoint:
    """エクイティカーブ上の1点."""

    timestamp: datetime
    equity: float
    action: str  # "HOLD" | "ENTRY" | "EXIT" | "NO_TRADE" | "HALTED" | "BLOCKED"


@dataclass
class BacktestMetrics:
    """バックテスト評価指標. Reference: Section 5-1."""

    # 損益
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0

    # トレード統計
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # 収益性
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_win_pips: float = 0.0
    avg_loss_pips: float = 0.0

    # RR比
    avg_rr_ratio: float = 0.0
    rr_distribution: dict = field(default_factory=dict)

    # リスク
    max_drawdown_pct: float = 0.0
    max_drawdown_amount: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # 時間
    avg_hold_duration_min: float = 0.0
    max_hold_duration_min: float = 0.0

    # セーフガード
    guard_block_count: int = 0
    guard_halt_count: int = 0
    rr_block_count: int = 0
    size_block_count: int = 0

    # 【生存性】破綻確率推定
    ruin_probability: float = 0.0


@dataclass
class BacktestResult:
    """バックテスト実行結果."""

    config: BacktestConfig
    trades: list[BacktestTradeRecord] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)
    step_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
