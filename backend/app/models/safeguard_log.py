"""Safeguard log model. Reference: 07_データベーススキーマ Section 3-3"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SafeguardLog(Base):
    __tablename__ = "safeguard_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    pair: Mapped[str | None] = mapped_column(String(20))
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    guard_id: Mapped[str] = mapped_column(String(10), nullable=False)  # SG-001 etc
    result: Mapped[str] = mapped_column(String(10), nullable=False)  # pass/warn/block/halt
    reason: Mapped[str | None] = mapped_column(String(200))
    details_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_sgl_user_id", "user_id"),
        Index("idx_sgl_trader_id_timestamp", "trader_id", "timestamp"),
        Index("idx_sgl_result", "result"),
    )
