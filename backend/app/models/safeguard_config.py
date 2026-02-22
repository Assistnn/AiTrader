"""Safeguard config (SG-001~SG-040). Reference: 07_データベーススキーマ Section 3-1"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SafeguardConfig(Base):
    __tablename__ = "safeguard_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("trader_id"),
        Index("idx_sgc_user_id", "user_id"),
        Index("idx_sgc_trader_id", "trader_id"),
    )
