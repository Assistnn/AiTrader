"""
M3: Entry / execution judgment.

Reference: 04_判定パイプライン Section 5
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.decision.base_judge import BaseJudge
from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput

if TYPE_CHECKING:
    from app.services.ai.judge_helper import AIJudgeHelper


def calculate_position_size(
    capital: float,
    risk_per_trade_pct: float,
    sl_pips: float,
    pip_value: float,
    min_lot: float,
    max_lot: float,
) -> tuple[float, dict]:
    """
    Position sizing calculation (bypass-proof).

    Reference: Section 5-5
    This function is ALWAYS called for every order, regardless of mode.
    """
    risk_amount = capital * (risk_per_trade_pct / 100)
    if sl_pips <= 0 or pip_value <= 0:
        return min_lot, {"error": "invalid sl_pips or pip_value", "fallback": True}

    raw_lot = risk_amount / (sl_pips * pip_value)
    lot_size = max(min_lot, min(raw_lot, max_lot))

    _debug = {
        "capital": capital,
        "risk_pct": risk_per_trade_pct,
        "risk_amount": risk_amount,
        "sl_pips": sl_pips,
        "pip_value": pip_value,
        "raw_lot": raw_lot,
        "clipped_lot": lot_size,
        "min_lot": min_lot,
        "max_lot": max_lot,
    }
    return lot_size, _debug


class M3EntryJudge(BaseJudge):
    """
    M3: Entry / execution judgment.

    Reference: Section 5
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
                stage="m3", input=input, config=config, rule_result=rule_result,
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
                stage="m3", input=input, config=config, rule_result=None,
            )
            if ai_result:
                ai_result._debug["ai_adopted"] = True
                return ai_result
            fallback = self._judge_rule(input, config)
            fallback._debug["ai_adopted"] = False
            return fallback
        return self._judge_rule(input, config)

    def _judge_rule(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        """M3 rule mode judgment. Reference: Section 5-3, 5-4"""
        m1_result = input.previous_stages.get("m1", {})
        m2_result = input.previous_stages.get("m2", {})
        if isinstance(m1_result, JudgeOutput):
            m1_result = m1_result.result
        if isinstance(m2_result, JudgeOutput):
            m2_result = m2_result.result

        trend = m1_result.get("trend", "NEUTRAL")
        setup_valid = m2_result.get("setupValid", False)
        setup_type = m2_result.get("setupType", "trendFollow")
        reason_codes: list[str] = []
        debug: dict = {"trend": trend, "setup_valid": setup_valid, "setup_type": setup_type}

        if not setup_valid:
            return JudgeOutput(
                result={"entry": "NO_TRADE", "entryType": "market", "lotSize": 0.0,
                        "tpPips": 0.0, "slPips": 0.0, "rrRatio": 0.0},
                confidence=0.0,
                reason_codes=["SETUP_NOT_VALID"],
                _debug=debug,
            )

        # Determine entry side
        if setup_type == "meanReversion":
            side = m2_result.get("side", "NONE")
            entry = side if side in ("BUY", "SELL") else "NO_TRADE"
        elif trend == "UP":
            entry = "BUY"
        elif trend == "DOWN":
            entry = "SELL"
        else:
            entry = "NO_TRADE"

        if entry == "NO_TRADE":
            return JudgeOutput(
                result={"entry": "NO_TRADE", "entryType": "market", "lotSize": 0.0,
                        "tpPips": 0.0, "slPips": 0.0, "rrRatio": 0.0},
                confidence=0.0,
                reason_codes=["NO_DIRECTION"],
                _debug=debug,
            )

        # --- TP/SL calculation (Reference: Section 5-4) ---
        primary_tf = config.timeframes[0] if config.timeframes else "M5"
        primary = input.state.indicators.get(primary_tf)
        atr = None
        if primary is not None:
            atr = primary.values.get("atr14")

        tp_sl_mode = config.params.get("tpSlMode", "atr")
        entry_type = config.params.get("orderType", "market")

        if tp_sl_mode == "atr" and atr is not None and atr > 0:
            tp_mult = config.params.get("tpMultiplier", 1.5)
            sl_mult = config.params.get("slMultiplier", 1.0)
            # Convert ATR to approximate pips (100 for JPY pairs)
            atr_pips = atr * 100
            tp_pips = atr_pips * tp_mult
            sl_pips = atr_pips * sl_mult
            reason_codes.append("TP_SL_ATR_MODE")
        else:
            # Fixed pips fallback
            tp_pips = config.params.get("tpFixedPips", 30.0)
            sl_pips = config.params.get("slFixedPips", 20.0)
            reason_codes.append("TP_SL_FIXED_MODE")

        rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0.0

        # --- Position sizing (Reference: Section 5-5) ---
        risk_pct = config.params.get("riskPerTradePct", 2.0)
        capital = input.account.capital if input.account else 1_000_000.0
        pip_value = config.params.get("pipValue", 100.0)  # approximate JPY pairs
        min_lot = config.params.get("minLot", 0.01)
        max_lot = config.params.get("maxLot", 100.0)

        lot_size, sizing_debug = calculate_position_size(
            capital=capital,
            risk_per_trade_pct=risk_pct,
            sl_pips=sl_pips,
            pip_value=pip_value,
            min_lot=min_lot,
            max_lot=max_lot,
        )

        # Apply lot multiplier from guard state (e.g. 0.5 for consecutive loss halving)
        lot_multiplier = input.guard_state.lot_multiplier if input.guard_state else 1.0
        lot_size *= lot_multiplier
        lot_size = max(min_lot, lot_size)

        debug["atr14"] = atr
        debug["tp_sl_mode"] = tp_sl_mode
        debug["tp_pips"] = tp_pips
        debug["sl_pips"] = sl_pips
        debug["rr_ratio"] = rr_ratio
        debug["lot_size"] = lot_size
        debug["lot_multiplier"] = lot_multiplier
        debug["sizing"] = sizing_debug

        reason_codes.append(f"ENTRY_{entry}")
        confidence = 0.7  # base confidence for rule mode

        return JudgeOutput(
            result={
                "entry": entry,
                "entryType": entry_type,
                "lotSize": lot_size,
                "tpPips": tp_pips,
                "slPips": sl_pips,
                "rrRatio": rr_ratio,
                "riskPerTradePct": risk_pct,
            },
            confidence=confidence,
            reason_codes=reason_codes,
            _debug=debug,
        )

    def describe_config(self) -> dict:
        return {
            "M3-001": {"key": "exec.enabled", "type": "boolean", "default": True},
            "M3-002": {"key": "exec.timeframes", "type": "array", "default": ["M5", "M1"]},
            "M3-003": {"key": "exec.orderType", "type": "enum", "default": "market"},
            "M3-004": {"key": "exec.tpSlMode", "type": "enum", "default": "atr"},
            "M3-005": {"key": "exec.riskPerTradePct", "type": "number", "default": 2},
        }
