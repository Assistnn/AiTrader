"""
Account API schemas.
Reference: 08_API仕様 Section 3-2
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountResponse(BaseModel):
    """GET /api/v1/account レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    email: str
    display_name: str | None = Field(None, alias="displayName")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")


class AccountUpdateRequest(BaseModel):
    """PUT /api/v1/account リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    display_name: str | None = Field(None, alias="displayName")
    email: str | None = None
