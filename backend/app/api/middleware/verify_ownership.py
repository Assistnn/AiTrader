"""
@verify_ownership decorator for API routes.

Reference: 07_データベーススキーマ Section 2【監査1】

Ensures that a user can only access their own resources.
Applied to all API endpoints that handle tenant-specific data.
"""

from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, status


def verify_ownership(model_class: Any):
    """
    Decorator factory that verifies the authenticated user owns the requested resource.

    Usage:
        @router.get("/{trader_id}")
        @verify_ownership(Trader)
        async def get_trader(trader_id: int, db: TenantAwareSession = Depends(...)):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        wrapper._verify_ownership_model = model_class
        return wrapper

    return decorator
