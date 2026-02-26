"""
Common API response helpers.
Reference: 08_API仕様 Section 2-3, 2-4
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel


def _serialize(obj: Any) -> Any:
    """Serialize Pydantic models or lists to JSON-safe dicts."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(by_alias=True, mode="json")
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    return obj


def ok(data: Any) -> dict:
    """Standard success response: {"status": "ok", "data": ...}"""
    return {"status": "ok", "data": _serialize(data)}


def paginated(
    items: list,
    page: int,
    per_page: int,
    total: int,
) -> dict:
    """Paginated success response with pagination metadata."""
    return {
        "status": "ok",
        "data": _serialize(items),
        "pagination": {
            "page": page,
            "perPage": per_page,
            "totalItems": total,
            "totalPages": math.ceil(total / per_page) if per_page > 0 else 0,
        },
    }
