"""
AssetProfile model — per-pair pip definition and defaults.

Reference: 07_データベーススキーマ — asset_profiles (監査対応)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AssetProfile(Base):
    """Asset profile (pip definition + trading defaults per pair)."""

    __tablename__ = "asset_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    asset_type: Mapped[str] = mapped_column(String(10), nullable=False)  # fx / crypto
    pip_size: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    pip_digits: Mapped[int] = mapped_column(Integer, nullable=False)
    pip_value_per_lot: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    default_min_lot: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, server_default="0.01")
    default_max_lot: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="100.0")
    default_tp_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, server_default="1.5")
    default_sl_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, server_default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
