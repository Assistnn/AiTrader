"""Historical OHLCV data model. Reference: 07_データベーススキーマ Section 3-6"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HistoricalOhlcv(Base):
    __tablename__ = "historical_ohlcv"

    id: Mapped[int] = mapped_column(primary_key=True)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(20, 8), default=0, nullable=False)
    source: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        UniqueConstraint("pair", "timeframe", "timestamp"),
        Index("idx_ho_pair_tf_ts", "pair", "timeframe", "timestamp"),
    )
