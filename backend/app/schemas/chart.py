"""
Chart API schemas.
Reference: 08_API仕様 Section 3-8
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OhlcvItem(BaseModel):
    """GET /api/v1/charts/ohlcv 1要素."""

    model_config = ConfigDict(populate_by_name=True)

    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: float


class IndicatorDataResponse(BaseModel):
    """GET /api/v1/charts/indicators レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    values: list[float | None]


class MarkerItem(BaseModel):
    """GET /api/v1/charts/markers 1要素."""

    model_config = ConfigDict(populate_by_name=True)

    timestamp: datetime
    type: str
    side: str | None = None
    price: float | None = None
    label: str | None = None


class ChartConfigResponse(BaseModel):
    """GET /api/v1/charts/config レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    pair: str
    timeframe: str
    indicators: list[Any] | None = None
    chart_type: str | None = Field(None, alias="chartType")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ChartConfigUpdateRequest(BaseModel):
    """PUT /api/v1/charts/config リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    pair: str
    timeframe: str | None = None
    indicators: list[Any] | None = None
    chart_type: str | None = Field(None, alias="chartType")
