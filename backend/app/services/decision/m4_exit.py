"""
M4: Exit management.

Reference: 04_判定パイプライン Section 6
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.decision.base_judge import BaseJudge
from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput

if TYPE_CHECKING:
    from app.services.ai.judge_helper import AIJudgeHelper


@dataclass
class PositionContext:
    """Position context for M4 evaluation."""

    pair: str
    side: str  # "BUY" / "SELL"
    entry_price: float
    current_price: float
    tp_price: float | None
    sl_price: float | None
    unrealized_pnl_pips: float
    atr_pips: float
    opened_at: datetime
    break_even_applied: bool = False
    trail_active: bool = False
    trail_price: float | None = None


class M4ExitJudge(BaseJudge):
    """
    M4: Exit management.

    Reference: Section 6
    Timeframes: M5, M1 (configurable)
    """

    def __init__(self, ai_helper: AIJudgeHelper | None = None) -> None:
        self._ai_helper = ai_helper

    async def judge(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        if config.mode == "rule":
            return self._judge_rule(input, config)
        if config.mode == "aiAssist":
            rule_result = self._judge_rule(input, config)
            if self._ai_helper is None:
                return rule_result
            ai_result = await self._ai_helper.execute_ai_judgment(
                stage="m4", input=input, config=config, rule_result=rule_result,
            )
            if ai_result and ai_result.confidence >= config.params.get("minConfidence", 0.7):
                ai_result._debug["ai_adopted"] = True
                return ai_result
            rule_result._debug["ai_adopted"] = False
            return rule_result
        if config.mode == "aiFull":
            if self._ai_helper is None:
                return self._judge_rule(input, config)
            ai_result = await self._ai_helper.execute_ai_judgment(
                stage="m4", input=input, config=config, rule_result=None,
            )
            if ai_result:
                ai_result._debug["ai_adopted"] = True
                return ai_result
            fallback = self._judge_rule(input, config)
            fallback._debug["ai_adopted"] = False
            return fallback
        return self._judge_rule(input, config)

    def _judge_rule(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        """M4 rule mode exit management. Reference: Section 6-4"""
        if not config.enabled:
            return JudgeOutput(
                result={"action": "HOLD"},
                confidence=0.5,
                reason_codes=["M4_DISABLED"],
                _debug={},
            )

        # Extract position context from input
        position_ctx = self._extract_position_context(input, config)
        if position_ctx is None:
            return JudgeOutput(
                result={"action": "HOLD"},
                confidence=0.5,
                reason_codes=["NO_POSITION_CONTEXT"],
                _debug={},
            )

        debug: dict = {
            "unrealized_pnl_pips": position_ctx.unrealized_pnl_pips,
            "atr_pips": position_ctx.atr_pips,
            "break_even_applied": position_ctx.break_even_applied,
            "trail_active": position_ctx.trail_active,
        }
        reason_codes: list[str] = []
        params = config.params

        # --- Max hold time check (Section 6-4) ---
        if params.get("maxHold", True):
            max_hold_min = params.get("maxHoldMinutes", 1440)  # default 24h
            now = input.timestamp
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            opened = position_ctx.opened_at
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            hold_minutes = (now - opened).total_seconds() / 60
            debug["hold_minutes"] = hold_minutes
            debug["max_hold_minutes"] = max_hold_min
            if hold_minutes > max_hold_min:
                reason_codes.append("MAX_HOLD_TIME_EXCEEDED")
                return JudgeOutput(
                    result={"action": "EXIT", "reason": "MAX_HOLD_TIME"},
                    confidence=1.0,
                    reason_codes=reason_codes,
                    _debug=debug,
                )

        # --- Break-even check (Section 6-4) ---
        if params.get("breakEven", True) and not position_ctx.break_even_applied:
            be_trigger_mult = params.get("breakevenTriggerMultiplier", 1.0)
            if position_ctx.unrealized_pnl_pips >= position_ctx.atr_pips * be_trigger_mult:
                reason_codes.append("BREAK_EVEN_TRIGGERED")
                debug["be_trigger"] = position_ctx.atr_pips * be_trigger_mult
                return JudgeOutput(
                    result={
                        "action": "ADJUST_TRAIL",
                        "slAdjustPips": 1.0,  # SL to entry + 1 pip
                        "breakEvenApplied": True,
                    },
                    confidence=0.9,
                    reason_codes=reason_codes,
                    _debug=debug,
                )

        # --- Trailing stop check (Section 6-4) ---
        if params.get("trailing", True):
            trail_start_mult = params.get("trailStartMultiplier", 1.5)
            trail_mult = params.get("trailMultiplier", 1.0)
            if position_ctx.unrealized_pnl_pips >= position_ctx.atr_pips * trail_start_mult:
                trail_distance = position_ctx.atr_pips * trail_mult
                reason_codes.append("TRAILING_STOP_ACTIVE")
                debug["trail_distance_pips"] = trail_distance
                return JudgeOutput(
                    result={
                        "action": "ADJUST_TRAIL",
                        "trailMode": "ON",
                        "trailDistancePips": trail_distance,
                    },
                    confidence=0.85,
                    reason_codes=reason_codes,
                    _debug=debug,
                )

        # --- Partial take-profit check (Section 6-4) ---
        if params.get("partial", True) and position_ctx.tp_price is not None:
            partial_trigger = params.get("partialTriggerPct", 0.5)
            partial_close = params.get("partialClosePct", 0.5)
            tp_distance_pips = abs(position_ctx.tp_price - position_ctx.entry_price) * 100
            if tp_distance_pips > 0:
                progress = position_ctx.unrealized_pnl_pips / tp_distance_pips
                debug["tp_progress"] = progress
                if progress >= partial_trigger:
                    reason_codes.append("PARTIAL_TAKE_PROFIT")
                    return JudgeOutput(
                        result={
                            "action": "PARTIAL",
                            "partialPct": partial_close,
                        },
                        confidence=0.8,
                        reason_codes=reason_codes,
                        _debug=debug,
                    )

        # Default: HOLD
        reason_codes.append("HOLD_POSITION")
        return JudgeOutput(
            result={"action": "HOLD"},
            confidence=0.5,
            reason_codes=reason_codes,
            _debug=debug,
        )

    def _extract_position_context(self, input: JudgeInput, config: JudgeConfig) -> PositionContext | None:
        """Extract position context from JudgeInput."""
        if not input.positions:
            return None

        pos = input.positions[0]
        if not hasattr(pos, "entry_price"):
            return None

        # Get ATR from primary timeframe
        primary_tf = config.timeframes[0] if config.timeframes else "M5"
        primary = input.state.indicators.get(primary_tf)
        atr_pips = 30.0  # fallback
        if primary is not None:
            atr = primary.values.get("atr14")
            if atr is not None and atr > 0:
                atr_pips = atr * 100  # approximate for JPY pairs

        current_price = getattr(pos, "current_price", None) or getattr(pos, "entry_price", 0.0)
        entry_price = getattr(pos, "entry_price", 0.0)
        side = getattr(pos, "side", "BUY")

        # Calculate unrealized P&L in pips
        if side == "BUY":
            unrealized_pips = (current_price - entry_price) * 100
        else:
            unrealized_pips = (entry_price - current_price) * 100

        return PositionContext(
            pair=getattr(pos, "pair", input.pair),
            side=side,
            entry_price=entry_price,
            current_price=current_price,
            tp_price=getattr(pos, "tp_price", None),
            sl_price=getattr(pos, "sl_price", None),
            unrealized_pnl_pips=unrealized_pips,
            atr_pips=atr_pips,
            opened_at=getattr(pos, "opened_at", input.timestamp),
            break_even_applied=getattr(pos, "break_even_applied", False) or False,
            trail_active=getattr(pos, "trail_active", False) or False,
            trail_price=getattr(pos, "trail_price", None),
        )

    def describe_config(self) -> dict:
        return {
            "M4-001": {"key": "exit.enabled", "type": "boolean", "default": True},
            "M4-002": {"key": "exit.timeframes", "type": "array", "default": ["M5", "M1"]},
            "M4-003": {"key": "exit.mode", "type": "enum", "default": "rule"},
            "M4-004": {"key": "exit.rule.breakEven", "type": "boolean", "default": True},
            "M4-005": {"key": "exit.rule.trailing", "type": "boolean", "default": True},
            "M4-006": {"key": "exit.rule.partial", "type": "boolean", "default": True},
            "M4-007": {"key": "exit.rule.maxHold", "type": "boolean", "default": True},
        }
