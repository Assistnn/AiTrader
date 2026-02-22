"""Trader model (T-001~T-012). Reference: 07_データベーススキーマ Section 3-1"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Trader(Base):
    __tablename__ = "traders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_name: Mapped[str] = mapped_column(String(40), nullable=False)  # T-001
    trade_type: Mapped[str] = mapped_column(
        String(10), default="FX", nullable=False
    )  # T-002
    symbols: Mapped[dict] = mapped_column(
        JSON, default=["USD_JPY"], nullable=False
    )  # T-003
    capital_jpy: Mapped[float] = mapped_column(
        Numeric(15, 2), default=1000000, nullable=False
    )  # T-004
    order_unit_lots: Mapped[float] = mapped_column(
        Numeric(10, 4), default=1.0, nullable=False
    )  # T-005
    strategy_text: Mapped[str | None] = mapped_column(Text, default="")  # T-006
    notify_email: Mapped[str | None] = mapped_column(String(255))  # T-007
    notify_on_entry: Mapped[bool | None] = mapped_column(Boolean, default=True)  # T-008
    notify_on_stop: Mapped[bool | None] = mapped_column(Boolean, default=True)  # T-009
    notify_on_error: Mapped[bool | None] = mapped_column(
        Boolean, default=True
    )  # T-010
    notify_on_exit: Mapped[bool | None] = mapped_column(Boolean, default=True)  # T-011
    notify_on_target: Mapped[bool | None] = mapped_column(
        Boolean, default=True
    )  # T-012
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="stopped", nullable=False
    )  # running/stopped/halted
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="traders")

    __table_args__ = (Index("idx_traders_user_id", "user_id"),)
