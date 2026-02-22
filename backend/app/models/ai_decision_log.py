"""AI decision log model. Reference: 07_データベーススキーマ Section 3-3"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AiDecisionLog(Base):
    __tablename__ = "ai_decision_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36))
    stage: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt_hash: Mapped[str | None] = mapped_column(String(64))
    user_prompt: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[str | None] = mapped_column(Text)
    parsed_result: Mapped[dict | None] = mapped_column(JSON)
    parse_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Numeric(10, 2))
    adopted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_adl_user_id", "user_id"),
        Index("idx_adl_trader_id", "trader_id"),
        Index("idx_adl_timestamp", "timestamp"),
    )
