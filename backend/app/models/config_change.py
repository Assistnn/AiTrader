"""Config change log model. Reference: 07_データベーススキーマ Section 3-3"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ConfigChange(Base):
    __tablename__ = "config_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    config_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # model_stage/safeguard/trader
    stage: Mapped[str | None] = mapped_column(String(10))  # m1/m2/m3/m4/mx/null
    config_before: Mapped[dict] = mapped_column(JSON, nullable=False)
    config_after: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_cc_user_id", "user_id"),
        Index("idx_cc_trader_id", "trader_id"),
        Index("idx_cc_changed_at", "changed_at"),
    )
