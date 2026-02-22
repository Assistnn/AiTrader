"""Simulation history model (paper trading). Reference: 07_データベーススキーマ Section 3-6"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SimulationHistory(Base):
    __tablename__ = "simulation_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(15, 8))
    entry_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    exit_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(15, 2))
    exit_reason: Mapped[str | None] = mapped_column(String(50))
    execution_id: Mapped[str | None] = mapped_column(String(36))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_sh_user_id", "user_id"),)
