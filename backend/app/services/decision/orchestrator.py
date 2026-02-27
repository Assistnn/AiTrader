"""
Decision Orchestrator: pipeline execution control and automatic logging.

Reference: 04_判定パイプライン Section 8
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from app.logging_config import log_with_data
from app.services.decision.base_judge import BaseJudge
from app.services.decision.decision_types import (
    JudgeConfig,
    JudgeInput,
    JudgeOutput,
    PipelineResult,
)
from app.services.decision.mx_integrator import MXIntegrator
from app.services.safeguard.guard_engine import GuardEngine
from app.services.safeguard.guard_rules import PositionInfo
from app.services.safeguard.guard_types import AccountState, GuardState, ProposedOrder


logger = logging.getLogger(__name__)


class DecisionOrchestrator:
    """
    Pipeline orchestrator.

    Reference: Section 8
    Executes M1→M2→MX→M3→Guard→Execution flow with automatic logging.
    """

    def __init__(
        self,
        m1: BaseJudge,
        m2: BaseJudge,
        m3: BaseJudge,
        m4: BaseJudge,
        guard_engine: GuardEngine,
        mx: MXIntegrator | None = None,
    ):
        self.m1 = m1
        self.m2 = m2
        self.m3 = m3
        self.m4 = m4
        self.guard_engine = guard_engine
        self.mx = mx or MXIntegrator()
        self._logs: list[dict] = []  # in-memory log buffer (DB persistence in Phase 1-8)

    async def execute_pipeline(
        self,
        pair: str,
        state: Any,
        account: AccountState | None = None,
        positions: list[PositionInfo] | None = None,
        m1_config: JudgeConfig | None = None,
        m2_config: JudgeConfig | None = None,
        m3_config: JudgeConfig | None = None,
        guard_state: GuardState | None = None,
        trader_id: int | None = None,
        user_id: int | None = None,
        now: datetime | None = None,
    ) -> PipelineResult:
        """
        Execute full pipeline: Guard → M1 → M2 → MX → M3 → Pre-entry Guard.

        Reference: Section 8-2
        """
        if now is None:
            now = datetime.now(timezone.utc)
        if positions is None:
            positions = []

        execution_id = str(uuid.uuid4())

        # 0. Guard Engine evaluation
        if guard_state is None:
            guard_state = self.guard_engine.evaluate_all(
                state=state, account=account, positions=positions, now=now,
            )

        if guard_state.trader_halted:
            log_with_data(logger, logging.INFO, "Pipeline HALTED", {
                "execution_id": execution_id, "pair": pair,
                "halted_by": guard_state.blocking_guards,
            })
            return PipelineResult(
                action="HALTED",
                execution_id=execution_id,
                guard_state=guard_state,
                _debug={"halted_by": guard_state.blocking_guards},
            )

        if not guard_state.entry_allowed:
            log_with_data(logger, logging.INFO, "Pipeline BLOCKED", {
                "execution_id": execution_id, "pair": pair,
                "blocked_by": guard_state.blocking_guards,
            })
            return PipelineResult(
                action="BLOCKED",
                execution_id=execution_id,
                guard_state=guard_state,
                _debug={"blocked_by": guard_state.blocking_guards},
            )

        # Build JudgeInput
        judge_input = JudgeInput(
            pair=pair,
            timestamp=now,
            state=state,
            guard_state=guard_state,
            positions=positions,
            account=account,
            trader_id=trader_id,
            user_id=user_id,
        )

        # 1. M1: Direction judgment
        m1_cfg = m1_config or JudgeConfig(timeframes=["D1", "H4", "H1"])
        m1_output = await self._execute_stage("m1", self.m1, judge_input, m1_cfg, execution_id)

        if not m1_output.result.get("tradeAllowed", False):
            log_with_data(logger, logging.INFO, "Pipeline NO_TRADE at M1", {
                "execution_id": execution_id, "pair": pair,
                "reason_codes": m1_output.reason_codes,
            })
            return PipelineResult(
                action="NO_TRADE",
                execution_id=execution_id,
                m1_output=m1_output,
                guard_state=guard_state,
                _debug={"m1_reason": m1_output.reason_codes},
            )

        # 2. M2: Setup judgment
        judge_input.previous_stages["m1"] = m1_output
        m2_cfg = m2_config or JudgeConfig(timeframes=["H1", "M30", "M15"],
                                           params={"preset": "trendFollow"})
        m2_output = await self._execute_stage("m2", self.m2, judge_input, m2_cfg, execution_id)

        # 3. MX integration check
        if not self.mx.should_execute_m3(m1_output, m2_output):
            log_with_data(logger, logging.INFO, "Pipeline NO_TRADE at MX gate", {
                "execution_id": execution_id, "pair": pair,
            })
            return PipelineResult(
                action="NO_TRADE",
                execution_id=execution_id,
                m1_output=m1_output,
                m2_output=m2_output,
                guard_state=guard_state,
                _debug={"mx_reason": "M2 setup not valid or MX gate failed"},
            )

        # 4. M3: Entry judgment
        judge_input.previous_stages["m2"] = m2_output
        m3_cfg = m3_config or JudgeConfig(timeframes=["M5", "M1"],
                                           params={"tpSlMode": "atr", "riskPerTradePct": 2.0})
        m3_output = await self._execute_stage("m3", self.m3, judge_input, m3_cfg, execution_id)

        entry = m3_output.result.get("entry", "NO_TRADE")
        if entry == "NO_TRADE":
            log_with_data(logger, logging.INFO, "Pipeline NO_TRADE at M3", {
                "execution_id": execution_id, "pair": pair,
                "reason_codes": m3_output.reason_codes,
            })
            return PipelineResult(
                action="NO_TRADE",
                execution_id=execution_id,
                m1_output=m1_output,
                m2_output=m2_output,
                m3_output=m3_output,
                guard_state=guard_state,
                _debug={"m3_reason": m3_output.reason_codes},
            )

        # 5. MX final decision
        should_trade, mx_debug = self.mx.should_trade(m1_output, m2_output, m3_output)
        if not should_trade:
            log_with_data(logger, logging.INFO, "Pipeline NO_TRADE at MX final", {
                "execution_id": execution_id, "pair": pair,
            })
            return PipelineResult(
                action="NO_TRADE",
                execution_id=execution_id,
                m1_output=m1_output,
                m2_output=m2_output,
                m3_output=m3_output,
                guard_state=guard_state,
                _debug={"mx_decision": mx_debug},
            )

        # 6. Build proposed order
        proposed_order = ProposedOrder(
            pair=pair,
            side=entry,
            lot_size=m3_output.result.get("lotSize", 0.0),
            order_type=m3_output.result.get("entryType", "market"),
            sl_pips=m3_output.result.get("slPips", 0.0),
            tp_pips=m3_output.result.get("tpPips", 0.0),
            risk_per_trade_pct=m3_output.result.get("riskPerTradePct", 2.0),
        )

        # 7. Pre-entry Guard check
        pre_entry_guard = self.guard_engine.evaluate_pre_entry(
            proposed_order=proposed_order,
            positions=positions,
            state=state,
            account=account,
            now=now,
        )

        if not pre_entry_guard.entry_allowed:
            log_with_data(logger, logging.INFO, "Pipeline BLOCKED pre-entry", {
                "execution_id": execution_id, "pair": pair,
                "blocked_by": pre_entry_guard.blocking_guards,
            })
            return PipelineResult(
                action="BLOCKED",
                execution_id=execution_id,
                m1_output=m1_output,
                m2_output=m2_output,
                m3_output=m3_output,
                guard_state=pre_entry_guard,
                _debug={"pre_entry_blocked_by": pre_entry_guard.blocking_guards},
            )

        log_with_data(logger, logging.INFO, "Pipeline ENTRY signal", {
            "execution_id": execution_id, "pair": pair,
            "side": entry,
            "lot_size": proposed_order.lot_size,
            "sl_pips": proposed_order.sl_pips,
            "tp_pips": proposed_order.tp_pips,
            "rr_ratio": round(proposed_order.tp_pips / proposed_order.sl_pips, 2) if proposed_order.sl_pips else 0,
        })
        return PipelineResult(
            action="ENTRY",
            execution_id=execution_id,
            order=proposed_order,
            m1_output=m1_output,
            m2_output=m2_output,
            m3_output=m3_output,
            guard_state=pre_entry_guard,
            _debug={"mx_decision": mx_debug},
        )

    async def execute_exit_management(
        self,
        pair: str,
        state: Any,
        positions: list[Any],
        m4_config: JudgeConfig | None = None,
        guard_state: GuardState | None = None,
        account: AccountState | None = None,
        trader_id: int | None = None,
        user_id: int | None = None,
        now: datetime | None = None,
    ) -> JudgeOutput:
        """
        Execute M4 exit management.

        Reference: Section 8 execute_exit_management
        """
        if now is None:
            now = datetime.now(timezone.utc)

        execution_id = str(uuid.uuid4())

        if guard_state is None:
            guard_state = GuardState(
                entry_allowed=True, force_close=False, trader_halted=False,
                cooldown_until=None, lot_multiplier=1.0,
                evaluations=[], blocking_guards=[],
            )

        judge_input = JudgeInput(
            pair=pair,
            timestamp=now,
            state=state,
            guard_state=guard_state,
            positions=positions,
            account=account,
            trader_id=trader_id,
            user_id=user_id,
        )

        m4_cfg = m4_config or JudgeConfig(
            timeframes=["M5", "M1"],
            params={"breakEven": True, "trailing": True, "partial": True, "maxHold": True},
        )
        start = time.monotonic()
        result = await self._execute_stage("m4", self.m4, judge_input, m4_cfg, execution_id)
        elapsed = (time.monotonic() - start) * 1000
        log_with_data(logger, logging.INFO, "M4 exit result", {
            "execution_id": execution_id, "pair": pair,
            "action": result.result.get("action"),
            "confidence": result.confidence,
            "elapsed_ms": round(elapsed, 2),
        })
        return result

    async def _execute_stage(
        self,
        stage: str,
        judge: BaseJudge,
        input: JudgeInput,
        config: JudgeConfig,
        execution_id: str,
    ) -> JudgeOutput:
        """
        Execute a stage and automatically log the result.

        Reference: Section 8-3 (principle B: automatic logging)
        """
        start_time = time.monotonic()
        output = await judge.judge(input, config)
        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Automatic log entry (principle B)
        log_entry = {
            "execution_id": execution_id,
            "trader_id": input.trader_id,
            "user_id": input.user_id,
            "pair": input.pair,
            "timestamp": input.timestamp.isoformat() if input.timestamp else None,
            "stage": stage,
            "mode": config.mode,
            "output_result": output.result,
            "output_confidence": output.confidence,
            "output_reason_codes": output.reason_codes,
            "output_debug": output._debug,
            "config_params": config.params,
            "elapsed_ms": round(elapsed_ms, 2),
        }
        self._logs.append(log_entry)

        # Bridge to Python logging
        result_summary = {
            k: v for k, v in output.result.items()
            if k in ("trend", "tradeAllowed", "setupValid", "entry", "action", "lotSize", "tpPips", "slPips")
        }
        log_with_data(logger, logging.INFO, "Pipeline stage completed", {
            "execution_id": execution_id,
            "pair": input.pair,
            "stage": stage,
            "mode": config.mode,
            "result": result_summary,
            "confidence": output.confidence,
            "reason_codes": output.reason_codes,
            "elapsed_ms": round(elapsed_ms, 2),
        })
        if output._debug and logger.isEnabledFor(logging.DEBUG):
            log_with_data(logger, logging.DEBUG, "Pipeline stage debug", {
                "execution_id": execution_id,
                "stage": stage,
                "debug": output._debug,
            })

        return output

    def get_logs(self) -> list[dict]:
        """Get accumulated log entries (for persistence)."""
        return self._logs

    def clear_logs(self) -> None:
        """Clear log buffer after persistence."""
        self._logs.clear()
