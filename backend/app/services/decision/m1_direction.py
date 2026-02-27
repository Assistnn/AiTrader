"""
M1: Direction / Regime judgment.

Reference: 04_判定パイプライン Section 3
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.decision.base_judge import BaseJudge
from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput

if TYPE_CHECKING:
    from app.services.ai.judge_helper import AIJudgeHelper

logger = logging.getLogger(__name__)


class M1DirectionJudge(BaseJudge):
    """
    M1: Direction and regime judgment.

    Reference: Section 3
    Timeframes: D1, H4, H1 (configurable)
    Indicators: EMA(20/50/200), ADX(14), ATR(14), Donchian(20)
    """

    def __init__(self, ai_helper: AIJudgeHelper | None = None) -> None:
        self._ai_helper = ai_helper

    async def judge(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        if config.mode == "rule":
            return self._judge_rule(input, config)
        if config.mode == "aiAssist":
            return await self._judge_ai_assist(input, config)
        if config.mode == "aiFull":
            return await self._judge_ai_full(input, config)
        return self._judge_rule(input, config)

    async def _judge_ai_assist(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        """aiAssist: rule first, then AI confirmation. Reference: 05_AI統合 Section 4-1"""
        rule_result = self._judge_rule(input, config)
        if self._ai_helper is None:
            return rule_result
        ai_result = await self._ai_helper.execute_ai_judgment(
            stage="m1", input=input, config=config, rule_result=rule_result,
        )
        if ai_result and ai_result.confidence >= config.params.get("minConfidence", 0.7):
            ai_result._debug["ai_adopted"] = True
            logger.info("M1 AI adopted: confidence=%.2f", ai_result.confidence)
            return ai_result
        rule_result._debug["ai_adopted"] = False
        rule_result._debug["ai_fallback_reason"] = "low_confidence_or_failure"
        logger.info("M1 AI rejected, using rule result")
        return rule_result

    async def _judge_ai_full(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        """aiFull: AI only, rule fallback. Reference: 05_AI統合 Section 4-2"""
        if self._ai_helper is None:
            return self._judge_rule(input, config)
        ai_result = await self._ai_helper.execute_ai_judgment(
            stage="m1", input=input, config=config, rule_result=None,
        )
        if ai_result:
            ai_result._debug["ai_adopted"] = True
            return ai_result
        fallback = self._judge_rule(input, config)
        fallback._debug["ai_adopted"] = False
        fallback._debug["ai_fallback_reason"] = "ai_failure"
        return fallback

    def _judge_rule(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        """M1 rule mode judgment. Reference: Section 3-4"""
        state = input.state
        debug: dict = {}
        logger.debug("M1 _judge_rule: pair=%s", input.pair)

        # Get primary timeframe indicator snapshot
        primary_tf = config.timeframes[-1] if config.timeframes else "H1"
        primary = state.indicators.get(primary_tf)
        if primary is None:
            return JudgeOutput(
                result={"trend": "NEUTRAL", "regime": "range", "volatility": "normal", "tradeAllowed": False},
                confidence=0.0,
                reason_codes=["NO_PRIMARY_INDICATORS"],
                _debug={"primary_tf": primary_tf, "available_tfs": list(state.indicators.keys())},
            )

        v = primary.values

        # --- Trend direction judgment ---
        trend = "NEUTRAL"
        ema20 = v.get("ema20")
        ema50 = v.get("ema50")
        ema200 = v.get("ema200")
        adx = v.get("adx14")

        debug["ema20"] = ema20
        debug["ema50"] = ema50
        debug["ema200"] = ema200
        debug["adx14"] = adx

        if config.params.get("useTrendDirection", True) and all(
            x is not None for x in (ema20, ema50, adx)
        ):
            if ema200 is not None:
                if ema20 > ema50 > ema200 and adx >= 25:
                    trend = "UP"
                elif ema20 < ema50 < ema200 and adx >= 25:
                    trend = "DOWN"
            else:
                if ema20 > ema50 and adx >= 25:
                    trend = "UP"
                elif ema20 < ema50 and adx >= 25:
                    trend = "DOWN"

        # --- Regime judgment ---
        regime = "range"
        if adx is not None and adx >= 25:
            regime = "trend"

        # --- Volatility judgment ---
        volatility = state.volatility

        # --- trade_allowed ---
        trade_allowed = True
        reason_codes: list[str] = []

        if not config.enabled:
            trade_allowed = False
            reason_codes.append("M1_DISABLED")

        if config.params.get("useRangeAvoid", True) and regime == "range":
            trade_allowed = False
            reason_codes.append("RANGE_AVOID")

        if config.params.get("useVolatility", True) and volatility == "extreme":
            trade_allowed = False
            reason_codes.append("EXTREME_VOLATILITY")

        if trend != "NEUTRAL":
            reason_codes.append(f"TREND_{trend}")
        else:
            reason_codes.append("TREND_NEUTRAL")

        # --- Confidence calculation ---
        confidence = self._calc_confidence(trend, regime, adx, volatility)

        debug["trend"] = trend
        debug["regime"] = regime
        debug["volatility"] = volatility
        debug["trade_allowed"] = trade_allowed
        debug["primary_tf"] = primary_tf

        return JudgeOutput(
            result={
                "trend": trend,
                "regime": regime,
                "volatility": volatility,
                "tradeAllowed": trade_allowed,
            },
            confidence=confidence,
            reason_codes=reason_codes,
            _debug=debug,
        )

    def _calc_confidence(self, trend: str, regime: str, adx: float | None, volatility: str) -> float:
        """Calculate confidence based on indicator clarity."""
        conf = 0.5  # baseline

        if trend in ("UP", "DOWN"):
            conf += 0.2
        if regime == "trend":
            conf += 0.1
        if adx is not None and adx > 30:
            conf += 0.1
        if volatility == "normal":
            conf += 0.1
        elif volatility == "extreme":
            conf -= 0.2

        return max(0.0, min(1.0, conf))

    def describe_config(self) -> dict:
        return {
            "M1-001": {"key": "dir.enabled", "type": "boolean", "default": True},
            "M1-002": {"key": "dir.timeframes", "type": "array", "default": ["D1", "H4", "H1"]},
            "M1-004": {"key": "dir.useTrendDirection", "type": "boolean", "default": True},
            "M1-005": {"key": "dir.useRangeAvoid", "type": "boolean", "default": True},
            "M1-006": {"key": "dir.useVolatility", "type": "boolean", "default": True},
            "M1-007": {"key": "dir.mode", "type": "enum", "default": "rule"},
        }
