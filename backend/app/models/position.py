"""Position model. Reference: 07_データベーススキーマ Section 3-2"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    exchange_position_id: Mapped[str | None] = mapped_column(String(100))
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY / SELL
    amount: Mapped[float] = mapped_column(Numeric(15, 8), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    current_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(15, 2))
    tp_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    sl_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    break_even_applied: Mapped[bool | None] = mapped_column(Boolean, default=False)
    trail_active: Mapped[bool | None] = mapped_column(Boolean, default=False)
    trail_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    sl_order_id: Mapped[str | None] = mapped_column(String(100))
    tp_order_id: Mapped[str | None] = mapped_column(String(100))
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_positions_user_id", "user_id"),
        Index("idx_positions_trader_id", "trader_id"),
        Index("idx_positions_pair", "pair"),
    )
