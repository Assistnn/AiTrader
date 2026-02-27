"""
PositionSyncService: periodic position synchronization.

Reference: 16_実行エンジンとUI接続 Section 9-3, 監査6
- Every ENGINE_POSITION_SYNC_INTERVAL seconds, compare exchange positions
  with locally tracked positions.
- Detect 3 types of divergence:
  1. UNKNOWN_POSITION: exchange has a position not tracked locally
  2. MISSING_POSITION: locally tracked position not on exchange
  3. AMOUNT_MISMATCH: position exists on both but amounts differ
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from app.services.exchange.base_exchange import BaseExchange
from app.services.exchange.exchange_types import ExchangePosition

logger = logging.getLogger(__name__)


class DivergenceType(Enum):
    UNKNOWN_POSITION = "UNKNOWN_POSITION"  # exchange has, local doesn't
    MISSING_POSITION = "MISSING_POSITION"  # local has, exchange doesn't
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"    # both have, amounts differ


@dataclass
class SyncDivergence:
    """A detected divergence between exchange and local state."""

    divergence_type: DivergenceType
    position_id: str
    pair: str
    exchange_amount: float | None = None
    local_amount: float | None = None
    detail: str = ""


class PositionSyncService:
    """Periodic position synchronization (§9-3, 監査6).

    Compares exchange positions with locally known positions and detects
    divergences. Does NOT modify any state — caller decides the action.
    """

    def __init__(
        self,
        exchange: BaseExchange,
        trader_id: int,
    ) -> None:
        self._exchange = exchange
        self._trader_id = trader_id
        # Locally known positions (updated by the engine on entry/exit)
        self._known_positions: dict[str, ExchangePosition] = {}

    @property
    def known_position_count(self) -> int:
        """Number of locally known positions."""
        return len(self._known_positions)

    def register_position(self, position: ExchangePosition) -> None:
        """Register a position as locally known."""
        self._known_positions[position.position_id] = position

    def unregister_position(self, position_id: str) -> None:
        """Remove a position from local tracking."""
        self._known_positions.pop(position_id, None)

    def update_known_from_exchange(self, positions: list[ExchangePosition]) -> None:
        """Bulk update known positions from exchange data.

        Called after initial sync or restart to seed the local state.
        """
        self._known_positions = {p.position_id: p for p in positions}

    async def sync(self) -> list[SyncDivergence]:
        """Compare exchange positions with locally tracked positions.

        Returns list of divergences found (empty if all consistent).
        """
        divergences: list[SyncDivergence] = []

        try:
            exchange_positions = await self._exchange.get_positions()
        except Exception:
            logger.exception(
                "PositionSync[%d] failed to get exchange positions",
                self._trader_id,
            )
            return divergences

        exchange_map = {p.position_id: p for p in exchange_positions}
        local_ids = set(self._known_positions.keys())
        exchange_ids = set(exchange_map.keys())

        # 1. UNKNOWN_POSITION: on exchange but not local
        for pid in exchange_ids - local_ids:
            pos = exchange_map[pid]
            divergences.append(SyncDivergence(
                divergence_type=DivergenceType.UNKNOWN_POSITION,
                position_id=pid,
                pair=pos.pair,
                exchange_amount=pos.amount,
                local_amount=None,
                detail=f"Exchange has position {pid} not tracked locally",
            ))
            # Auto-register to prevent repeated alerts
            self._known_positions[pid] = pos

        # 2. MISSING_POSITION: local but not on exchange
        for pid in local_ids - exchange_ids:
            local_pos = self._known_positions[pid]
            divergences.append(SyncDivergence(
                divergence_type=DivergenceType.MISSING_POSITION,
                position_id=pid,
                pair=local_pos.pair,
                exchange_amount=None,
                local_amount=local_pos.amount,
                detail=f"Local position {pid} not found on exchange",
            ))
            # Remove from local tracking
            del self._known_positions[pid]

        # 3. AMOUNT_MISMATCH: both have but amounts differ
        for pid in local_ids & exchange_ids:
            local_pos = self._known_positions[pid]
            exchange_pos = exchange_map[pid]
            if abs(local_pos.amount - exchange_pos.amount) > 1e-8:
                divergences.append(SyncDivergence(
                    divergence_type=DivergenceType.AMOUNT_MISMATCH,
                    position_id=pid,
                    pair=local_pos.pair,
                    exchange_amount=exchange_pos.amount,
                    local_amount=local_pos.amount,
                    detail=(
                        f"Amount mismatch: local={local_pos.amount} "
                        f"exchange={exchange_pos.amount}"
                    ),
                ))
                # Update local to match exchange
                self._known_positions[pid] = exchange_pos

        if divergences:
            for d in divergences:
                log_level = (
                    logging.CRITICAL
                    if d.divergence_type == DivergenceType.UNKNOWN_POSITION
                    else logging.WARNING
                )
                logger.log(
                    log_level,
                    "PositionSync[%d] %s: %s",
                    self._trader_id, d.divergence_type.value, d.detail,
                )

        return divergences
