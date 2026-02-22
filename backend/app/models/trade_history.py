"""Trade history model. Reference: 07_データベーススキーマ Section 3-2"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TradeHistory(Base):
    __tablename__ = "trade_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 8), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(15, 2))
    realized_pnl_pips: Mapped[float | None] = mapped_column(Numeric(10, 2))
    rr_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tp_pips: Mapped[float | None] = mapped_column(Numeric(10, 2))
    sl_pips: Mapped[float | None] = mapped_column(Numeric(10, 2))
    exit_reason: Mapped[str | None] = mapped_column(String(50))
    execution_id: Mapped[str | None] = mapped_column(String(36))
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    hold_duration_min: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_th_user_id", "user_id"),
        Index("idx_th_trader_id", "trader_id"),
        Index("idx_th_closed_at", "closed_at"),
        Index("idx_th_pair", "pair"),
    )
