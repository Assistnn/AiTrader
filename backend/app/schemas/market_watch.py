"""
Market Watch API schemas.
Reference: 08_API仕様 Section 3-7
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketWatchItem(BaseModel):
    """GET /api/v1/market-watch 1要素."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    pair: str
    display_order: int = Field(alias="displayOrder")
    is_visible: bool = Field(alias="isVisible")
    created_at: datetime = Field(alias="createdAt")


class MarketWatchCreateRequest(BaseModel):
    """POST /api/v1/market-watch リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    pair: str
    display_order: int = Field(0, alias="displayOrder")
    is_visible: bool = Field(True, alias="isVisible")


class MarketWatchReorderRequest(BaseModel):
    """PUT /api/v1/market-watch/reorder リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    order: list[dict[str, int]]
