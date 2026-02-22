"""Economic event model. Reference: 07_データベーススキーマ Section 3-7"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EconomicEvent(Base):
    __tablename__ = "economic_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-3
    event_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_value: Mapped[str | None] = mapped_column(String(50))
    forecast_value: Mapped[str | None] = mapped_column(String(50))
    previous_value: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(50))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_ee_datetime", "event_datetime"),
        Index("idx_ee_currency", "currency"),
    )
