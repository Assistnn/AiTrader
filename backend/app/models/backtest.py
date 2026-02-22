"""Backtest models. Reference: 07_データベーススキーマ Section 3-6"""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending/running/completed/failed
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_trades: Mapped[int | None] = mapped_column(Integer)
    win_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    profit_factor: Mapped[float | None] = mapped_column(Numeric(8, 2))
    max_drawdown_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    total_pnl: Mapped[float | None] = mapped_column(Numeric(15, 2))
    avg_rr_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_br_user_id", "user_id"),)


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    backtest_run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_runs.id"), nullable=False
    )
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(15, 8))
    entry_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    exit_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(15, 2))
    realized_pnl_pips: Mapped[float | None] = mapped_column(Numeric(10, 2))
    rr_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2))
    exit_reason: Mapped[str | None] = mapped_column(String(50))
    entry_timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    exit_timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    pipeline_log_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_bt_backtest_run_id", "backtest_run_id"),)
