"""
Tests for PositionSyncService (§9-3, 監査6).
"""

import pytest

from app.services.engine.position_sync import (
    PositionSyncService,
    DivergenceType,
)
from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.exchange_types import ExchangePosition, OrderSide


def _make_position(
    position_id: str = "pos-1",
    pair: str = "USD_JPY",
    side: OrderSide = OrderSide.BUY,
    amount: float = 1.0,
    entry_price: float = 150.0,
) -> ExchangePosition:
    return ExchangePosition(
        position_id=position_id,
        pair=pair,
        side=side,
        amount=amount,
        entry_price=entry_price,
    )


class TestPositionSyncService:
    @pytest.mark.asyncio
    async def test_no_divergence(self):
        """No divergence when exchange and local match."""
        exchange = MockExchange()
        pos = _make_position()
        exchange.positions = [pos]

        sync = PositionSyncService(exchange=exchange, trader_id=1)
        sync.register_position(pos)

        divergences = await sync.sync()
        assert len(divergences) == 0

    @pytest.mark.asyncio
    async def test_unknown_position(self):
        """Detect position on exchange but not tracked locally."""
        exchange = MockExchange()
        pos = _make_position(position_id="unknown-1")
        exchange.positions = [pos]

        sync = PositionSyncService(exchange=exchange, trader_id=1)
        # Don't register locally

        divergences = await sync.sync()
        assert len(divergences) == 1
        assert divergences[0].divergence_type == DivergenceType.UNKNOWN_POSITION
        assert divergences[0].position_id == "unknown-1"

    @pytest.mark.asyncio
    async def test_missing_position(self):
        """Detect locally tracked position not on exchange."""
        exchange = MockExchange()
        exchange.positions = []  # Exchange has nothing

        sync = PositionSyncService(exchange=exchange, trader_id=1)
        sync.register_position(_make_position(position_id="local-1"))

        divergences = await sync.sync()
        assert len(divergences) == 1
        assert divergences[0].divergence_type == DivergenceType.MISSING_POSITION
        assert divergences[0].position_id == "local-1"

    @pytest.mark.asyncio
    async def test_amount_mismatch(self):
        """Detect amount difference between exchange and local."""
        exchange = MockExchange()
        exchange_pos = _make_position(position_id="pos-1", amount=2.0)
        exchange.positions = [exchange_pos]

        sync = PositionSyncService(exchange=exchange, trader_id=1)
        local_pos = _make_position(position_id="pos-1", amount=1.0)
        sync.register_position(local_pos)

        divergences = await sync.sync()
        assert len(divergences) == 1
        assert divergences[0].divergence_type == DivergenceType.AMOUNT_MISMATCH
        assert divergences[0].exchange_amount == 2.0
        assert divergences[0].local_amount == 1.0

    @pytest.mark.asyncio
    async def test_update_known_from_exchange(self):
        """Bulk update seeds local state, subsequent sync shows no divergence."""
        exchange = MockExchange()
        pos1 = _make_position(position_id="pos-1")
        pos2 = _make_position(position_id="pos-2")
        exchange.positions = [pos1, pos2]

        sync = PositionSyncService(exchange=exchange, trader_id=1)
        sync.update_known_from_exchange([pos1, pos2])

        divergences = await sync.sync()
        assert len(divergences) == 0

    @pytest.mark.asyncio
    async def test_multiple_divergences(self):
        """Detect multiple divergences in one sync."""
        exchange = MockExchange()
        exchange.positions = [
            _make_position(position_id="exchange-only"),
            _make_position(position_id="both", amount=3.0),
        ]

        sync = PositionSyncService(exchange=exchange, trader_id=1)
        sync.register_position(_make_position(position_id="local-only"))
        sync.register_position(_make_position(position_id="both", amount=1.0))

        divergences = await sync.sync()
        types = {d.divergence_type for d in divergences}
        assert DivergenceType.UNKNOWN_POSITION in types
        assert DivergenceType.MISSING_POSITION in types
        assert DivergenceType.AMOUNT_MISMATCH in types

    @pytest.mark.asyncio
    async def test_register_unregister(self):
        """Register and unregister work correctly."""
        exchange = MockExchange()
        exchange.positions = []

        sync = PositionSyncService(exchange=exchange, trader_id=1)
        pos = _make_position(position_id="pos-1")
        sync.register_position(pos)

        assert "pos-1" in sync._known_positions

        sync.unregister_position("pos-1")
        assert "pos-1" not in sync._known_positions
