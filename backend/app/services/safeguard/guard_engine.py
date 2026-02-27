"""
Guard Engine: evaluates all safeguard rules and returns aggregated GuardState.

Reference: 03_セーフガードエンジン Section 2-3, 8

Design principles:
- No early termination: all guards are evaluated even after HALT (Section 2-3)
- All evaluations logged to safeguard_logs (audit trail)
- GuardState is consumed by Decision Orchestrator
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.logging_config import log_with_data
from app.services.pipeline.data_types import StateSnapshot, Ticker
from app.services.safeguard.guard_rules import (
    BaseGuard,
    EconomicEvent,
    PositionInfo,
    SG006_009_ConsecutiveLoss,
    build_all_guards,
)
from app.services.safeguard.guard_types import (
    AccountState,
    GuardEvaluation,
    GuardResult,
    GuardState,
    ProposedOrder,
    SafeguardSettings,
)


logger = logging.getLogger(__name__)


class GuardEngine:
    """
    Safeguard engine.

    Reference: 03_セーフガードエンジン Section 8

    Evaluates all 40+ guards and returns aggregated GuardState.
    No early termination — all guards are evaluated for complete audit trail.
    """

    def __init__(self, settings: SafeguardSettings | None = None):
        self.settings = settings or SafeguardSettings()
        self.guards: list[BaseGuard] = build_all_guards()

    def evaluate_all(
        self,
        state: StateSnapshot | None = None,
        ticker: Ticker | None = None,
        account: AccountState | None = None,
        positions: list[PositionInfo] | None = None,
        economic_events: list[EconomicEvent] | None = None,
        proposed_order: ProposedOrder | None = None,
        now: datetime | None = None,
    ) -> GuardState:
        """
        Evaluate all guards and return aggregated GuardState.

        Reference: Section 2-3 evaluation flow
        """
        if now is None:
            now = datetime.now(timezone.utc)
        if positions is None:
            positions = []
        if economic_events is None:
            economic_events = []

        evaluations: list[GuardEvaluation] = []

        # Evaluate all guards — no early termination (Section 2-3)
        for guard in self.guards:
            evaluation = guard.evaluate(
                settings=self.settings,
                state=state,
                ticker=ticker,
                account=account,
                positions=positions,
                economic_events=economic_events,
                proposed_order=proposed_order,
                now=now,
            )
            if evaluation.result in (GuardResult.BLOCK, GuardResult.HALT):
                log_with_data(logger, logging.WARNING, "Guard triggered", {
                    "guard_id": evaluation.guard_id,
                    "result": evaluation.result.value,
                    "reason": evaluation.reason,
                })
            evaluations.append(evaluation)

        guard_state = self._aggregate(evaluations, now)
        log_with_data(logger, logging.INFO, "Guard evaluation", {
            "guard_count": len(evaluations),
            "entry_allowed": guard_state.entry_allowed,
            "trader_halted": guard_state.trader_halted,
            "blocking_guards": guard_state.blocking_guards,
            "lot_multiplier": guard_state.lot_multiplier,
        })
        return guard_state

    def evaluate_pre_entry(
        self,
        proposed_order: ProposedOrder,
        positions: list[PositionInfo],
        state: StateSnapshot | None = None,
        ticker: Ticker | None = None,
        account: AccountState | None = None,
        now: datetime | None = None,
    ) -> GuardState:
        """
        Pre-entry check (position limits, RR sanity, etc.).

        Reference: Section 8 evaluate_pre_entry
        """
        result = self.evaluate_all(
            state=state,
            ticker=ticker,
            account=account,
            positions=positions,
            proposed_order=proposed_order,
            now=now,
        )
        if not result.entry_allowed:
            log_with_data(logger, logging.INFO, "Pre-entry guard blocked", {
                "blocking_guards": result.blocking_guards,
                "pair": proposed_order.pair,
                "side": proposed_order.side,
            })
        return result

    def get_consecutive_loss_guard(self) -> SG006_009_ConsecutiveLoss | None:
        """Get the consecutive loss guard for external state management."""
        for guard in self.guards:
            if isinstance(guard, SG006_009_ConsecutiveLoss):
                return guard
        return None

    def _aggregate(self, evaluations: list[GuardEvaluation], now: datetime) -> GuardState:
        """
        Aggregate evaluation results into GuardState.

        Reference: Section 2-2 aggregation logic
        """
        trader_halted = any(e.result == GuardResult.HALT for e in evaluations)
        blocking_guards = [
            e.guard_id for e in evaluations
            if e.result in (GuardResult.BLOCK, GuardResult.HALT)
        ]
        force_close = any(
            e.result == GuardResult.HALT and "EMERGENCY_CLOSE" in e.reason
            for e in evaluations
        )

        # Determine cooldown from consecutive loss guard
        cooldown_until = None
        consecutive_loss_guard = self.get_consecutive_loss_guard()
        if consecutive_loss_guard is not None:
            cooldown_until = consecutive_loss_guard.cooldown_until

        # Determine lot multiplier
        lot_multiplier = 1.0
        if consecutive_loss_guard is not None and consecutive_loss_guard.lot_halved:
            lot_multiplier = 0.5

        # entry_allowed: no BLOCK/HALT, not halted, no active cooldown
        entry_allowed = (
            len(blocking_guards) == 0
            and not trader_halted
        )

        # Check cooldown
        if cooldown_until is not None:
            cd = cooldown_until
            if cd.tzinfo is None:
                cd = cd.replace(tzinfo=timezone.utc)
            now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            if now_utc < cd:
                entry_allowed = False

        return GuardState(
            entry_allowed=entry_allowed,
            force_close=force_close,
            trader_halted=trader_halted,
            cooldown_until=cooldown_until,
            lot_multiplier=lot_multiplier,
            evaluations=evaluations,
            blocking_guards=blocking_guards,
        )
