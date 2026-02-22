"""
TenantAwareSession - automatic user_id filtering for all queries.

Reference: 07_データベーススキーマ Section 2-1【監査1】

All database queries go through this session wrapper to ensure
tenant isolation. Queries on models with a user_id column are
automatically filtered by the authenticated user's ID.
"""

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


class TenantAwareSession:
    """Wraps AsyncSession to auto-inject user_id filters."""

    def __init__(self, session: AsyncSession, user_id: int):
        self._session = session
        self.user_id = user_id

    def query(self, model: type[T]) -> Select:
        """Build a select with automatic user_id filter."""
        stmt = select(model)
        if hasattr(model, "user_id"):
            stmt = stmt.where(model.user_id == self.user_id)
        return stmt

    async def execute(self, stmt):
        return await self._session.execute(stmt)

    def add(self, instance):
        if hasattr(instance, "user_id"):
            instance.user_id = self.user_id
        self._session.add(instance)

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()

    async def refresh(self, instance):
        await self._session.refresh(instance)

    async def delete(self, instance):
        if hasattr(instance, "user_id") and instance.user_id != self.user_id:
            raise PermissionError(
                f"Cannot delete resource owned by user {instance.user_id}"
            )
        await self._session.delete(instance)

    async def flush(self):
        await self._session.flush()
