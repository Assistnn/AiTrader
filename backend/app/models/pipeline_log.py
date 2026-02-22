"""Pipeline log model. Reference: 07_データベーススキーマ Section 3-3"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    stage: Mapped[str] = mapped_column(String(10), nullable=False)  # m1/m2/m3/m4/guard
    mode: Mapped[str | None] = mapped_column(String(10))  # rule/aiAssist/aiFull
    input_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)  # _debug included
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    elapsed_ms: Mapped[float | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_pl_user_id", "user_id"),
        Index("idx_pl_execution_id", "execution_id"),
        Index("idx_pl_trader_id_timestamp", "trader_id", "timestamp"),
        Index("idx_pl_stage", "stage"),
    )
