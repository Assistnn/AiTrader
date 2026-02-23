"""
Tenant isolation tests.
Reference: 07_データベーススキーマ Section 2-1, 08_API仕様 Section 2-2【監査1】

Verifies:
- TenantAwareSession auto-filters queries by user_id
- TenantAwareSession auto-sets user_id on add
- TenantAwareSession blocks deletion of other user's resources
- verify_trader_ownership returns 403/404 correctly
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.tenant_aware import TenantAwareSession
from app.api.middleware.verify_ownership import verify_trader_ownership
from app.models.trader import Trader
from app.models.user import User


# ===========================================================================
# TenantAwareSession
# ===========================================================================


class TestTenantAwareSession:
    @pytest.mark.asyncio
    async def test_query_auto_filters_user_id(self, db_session: AsyncSession):
        """query() adds WHERE user_id = X automatically."""
        # Create two users and their traders
        user1 = User(email="user1@test.com", password_hash="h1", display_name="User1")
        user2 = User(email="user2@test.com", password_hash="h2", display_name="User2")
        db_session.add_all([user1, user2])
        await db_session.flush()

        t1 = Trader(user_id=user1.id, trader_name="Trader1", trade_type="FX")
        t2 = Trader(user_id=user2.id, trader_name="Trader2", trade_type="FX")
        db_session.add_all([t1, t2])
        await db_session.flush()

        # TenantAwareSession for user1
        tenant1 = TenantAwareSession(db_session, user_id=user1.id)
        stmt = tenant1.query(Trader)
        result = await tenant1.execute(stmt)
        traders = result.scalars().all()
        assert len(traders) == 1
        assert traders[0].trader_name == "Trader1"

    @pytest.mark.asyncio
    async def test_add_auto_sets_user_id(self, db_session: AsyncSession):
        """add() auto-sets user_id on models that have it."""
        user = User(email="user3@test.com", password_hash="h3", display_name="User3")
        db_session.add(user)
        await db_session.flush()

        tenant = TenantAwareSession(db_session, user_id=user.id)
        new_trader = Trader(trader_name="AutoSetTrader", trade_type="FX")
        tenant.add(new_trader)
        await db_session.flush()

        assert new_trader.user_id == user.id

    @pytest.mark.asyncio
    async def test_delete_other_user_raises_permission_error(self, db_session: AsyncSession):
        """Deleting another user's resource raises PermissionError."""
        user1 = User(email="user4@test.com", password_hash="h4", display_name="User4")
        user2 = User(email="user5@test.com", password_hash="h5", display_name="User5")
        db_session.add_all([user1, user2])
        await db_session.flush()

        t_other = Trader(user_id=user2.id, trader_name="OtherTrader", trade_type="FX")
        db_session.add(t_other)
        await db_session.flush()

        tenant1 = TenantAwareSession(db_session, user_id=user1.id)
        with pytest.raises(PermissionError, match="Cannot delete resource"):
            await tenant1.delete(t_other)

    @pytest.mark.asyncio
    async def test_delete_own_resource_succeeds(self, db_session: AsyncSession):
        """Deleting own resource succeeds."""
        user = User(email="user6@test.com", password_hash="h6", display_name="User6")
        db_session.add(user)
        await db_session.flush()

        t_own = Trader(user_id=user.id, trader_name="OwnTrader", trade_type="FX")
        db_session.add(t_own)
        await db_session.flush()

        tenant = TenantAwareSession(db_session, user_id=user.id)
        await tenant.delete(t_own)
        # No exception raised

    @pytest.mark.asyncio
    async def test_model_without_user_id_not_affected(self, db_session: AsyncSession):
        """Models without user_id are not filtered or modified."""
        user = User(email="user7@test.com", password_hash="h7", display_name="User7")
        db_session.add(user)
        await db_session.flush()

        tenant = TenantAwareSession(db_session, user_id=user.id)
        # User model itself does not have user_id
        stmt = tenant.query(User)
        result = await tenant.execute(stmt)
        users = result.scalars().all()
        # Should return all users (no filter applied)
        assert len(users) >= 1


# ===========================================================================
# verify_trader_ownership
# ===========================================================================


class TestVerifyOwnership:
    @pytest.mark.asyncio
    async def test_other_user_returns_403(self, db_session: AsyncSession):
        """Accessing another user's trader raises 403."""
        from fastapi import HTTPException

        user1 = User(email="owner1@test.com", password_hash="h8", display_name="Owner1")
        user2 = User(email="owner2@test.com", password_hash="h9", display_name="Owner2")
        db_session.add_all([user1, user2])
        await db_session.flush()

        t = Trader(user_id=user1.id, trader_name="OwnerTrader", trade_type="FX")
        db_session.add(t)
        await db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await verify_trader_ownership(t.id, user2.id, db_session)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_nonexistent_id_returns_404(self, db_session: AsyncSession):
        """Non-existent trader_id raises 404."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_trader_ownership(99999, 1, db_session)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_correct_user_returns_trader(self, db_session: AsyncSession):
        """Correct user gets the Trader object."""
        user = User(email="valid@test.com", password_hash="h10", display_name="Valid")
        db_session.add(user)
        await db_session.flush()

        t = Trader(user_id=user.id, trader_name="ValidTrader", trade_type="FX")
        db_session.add(t)
        await db_session.flush()

        result = await verify_trader_ownership(t.id, user.id, db_session)
        assert result.id == t.id
        assert result.trader_name == "ValidTrader"
