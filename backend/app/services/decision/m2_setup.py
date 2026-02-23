"""
M2: Setup judgment.

Reference: 04_判定パイプライン Section 4
"""

from __future__ import annotations

from app.services.decision.base_judge import BaseJudge
from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput


class M2SetupJudge(BaseJudge):
    """
    M2: Setup judgment (trend follow / pullback / breakout / mean reversion).

    Reference: Section 4
    Timeframes: H1, M30, M15 (configurable)
    Indicators: EMA(20/50), RSI(14), Bollinger(20,2), ATR(14), Swing
    """

    def judge(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        if config.mode == "rule":
            return self._judge_rule(input, config)
        return self._judge_rule(input, config)

    def _judge_rule(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        """M2 rule mode judgment. Reference: Section 4-4"""
        preset = config.params.get("preset", "trendFollow")
        m1_result = input.previous_stages.get("m1", {})
        if isinstance(m1_result, JudgeOutput):
            m1_result = m1_result.result

        trend = m1_result.get("trend", "NEUTRAL")
        regime = m1_result.get("regime", "range")

        # Get primary timeframe indicators
        primary_tf = config.timeframes[-1] if config.timeframes else "M15"
        primary = input.state.indicators.get(primary_tf)
        if primary is None:
            return JudgeOutput(
                result={"setupValid": False, "setupType": preset, "probability": 0.0},
                confidence=0.0,
                reason_codes=["NO_INDICATORS"],
                _debug={"primary_tf": primary_tf},
            )

        v = primary.values
        debug = {"preset": preset, "trend": trend, "regime": regime, "primary_tf": primary_tf}

        if preset == "trendFollow":
            return self._eval_trend_follow(v, trend, debug, config)
        elif preset == "pullback":
            return self._eval_pullback(v, trend, debug, config)
        elif preset == "breakout":
            return self._eval_breakout(v, debug, config)
        elif preset == "meanReversion":
            return self._eval_mean_reversion(v, regime, input.state.volatility, debug, config)
        else:
            return self._eval_trend_follow(v, trend, debug, config)

    def _eval_trend_follow(self, v: dict, trend: str, debug: dict, config: JudgeConfig) -> JudgeOutput:
        """trendFollow preset. Reference: Section 4-4"""
        ema20 = v.get("ema20")
        ema50 = v.get("ema50")
        rsi = v.get("rsi14")
        adx = v.get("adx14")
        reason_codes: list[str] = []
        setup_valid = True

        debug["ema20"] = ema20
        debug["ema50"] = ema50
        debug["rsi14"] = rsi
        debug["adx14"] = adx

        if trend not in ("UP", "DOWN"):
            setup_valid = False
            reason_codes.append("NO_TREND")

        if ema20 is not None and ema50 is not None:
            if trend == "UP" and ema20 <= ema50:
                setup_valid = False
                reason_codes.append("EMA_MISALIGNED")
            elif trend == "DOWN" and ema20 >= ema50:
                setup_valid = False
                reason_codes.append("EMA_MISALIGNED")
        else:
            setup_valid = False
            reason_codes.append("EMA_MISSING")

        if rsi is not None:
            if not (40 <= rsi <= 70):
                setup_valid = False
                reason_codes.append("RSI_OUT_OF_RANGE")
        else:
            reason_codes.append("RSI_MISSING")

        if adx is not None and adx < 20:
            setup_valid = False
            reason_codes.append("ADX_TOO_LOW")

        if setup_valid:
            reason_codes.append("TREND_FOLLOW_SETUP_VALID")

        confidence = 0.7 if setup_valid else 0.3
        probability = 0.65 if setup_valid else 0.3

        return JudgeOutput(
            result={"setupValid": setup_valid, "setupType": "trendFollow", "probability": probability},
            confidence=confidence,
            reason_codes=reason_codes,
            _debug=debug,
        )

    def _eval_pullback(self, v: dict, trend: str, debug: dict, config: JudgeConfig) -> JudgeOutput:
        """pullback preset. Reference: Section 4-4"""
        ema50 = v.get("ema50")
        rsi = v.get("rsi14")
        atr = v.get("atr14")
        bb_lower = v.get("bb20_lower")
        bb_middle = v.get("bb20_middle")
        reason_codes: list[str] = []
        setup_valid = True

        debug["ema50"] = ema50
        debug["rsi14"] = rsi
        debug["atr14"] = atr

        if trend == "NEUTRAL":
            setup_valid = False
            reason_codes.append("NO_TREND")

        if ema50 is not None and atr is not None:
            # Price near EMA50 (within ATR*0.5)
            ema20 = v.get("ema20")
            if ema20 is not None:
                distance = abs(ema20 - ema50)
                if distance > atr * 0.5:
                    setup_valid = False
                    reason_codes.append("NOT_NEAR_EMA50")
        else:
            setup_valid = False
            reason_codes.append("EMA50_OR_ATR_MISSING")

        if rsi is not None:
            if trend == "UP" and not (30 <= rsi <= 50):
                setup_valid = False
                reason_codes.append("RSI_NOT_PULLBACK_UP")
            elif trend == "DOWN" and not (50 <= rsi <= 70):
                setup_valid = False
                reason_codes.append("RSI_NOT_PULLBACK_DOWN")

        if setup_valid:
            reason_codes.append("PULLBACK_SETUP_VALID")

        confidence = 0.65 if setup_valid else 0.25
        return JudgeOutput(
            result={"setupValid": setup_valid, "setupType": "pullback", "probability": 0.6 if setup_valid else 0.2},
            confidence=confidence,
            reason_codes=reason_codes,
            _debug=debug,
        )

    def _eval_breakout(self, v: dict, debug: dict, config: JudgeConfig) -> JudgeOutput:
        """breakout preset. Reference: Section 4-4"""
        donchian_upper = v.get("donchian20_upper")
        donchian_lower = v.get("donchian20_lower")
        adx = v.get("adx14")
        ema20 = v.get("ema20")  # proxy for current price
        reason_codes: list[str] = []
        setup_valid = False

        debug["donchian20_upper"] = donchian_upper
        debug["donchian20_lower"] = donchian_lower
        debug["adx14"] = adx

        if donchian_upper is not None and donchian_lower is not None and ema20 is not None:
            if ema20 >= donchian_upper:
                setup_valid = True
                reason_codes.append("BREAKOUT_UPPER")
            elif ema20 <= donchian_lower:
                setup_valid = True
                reason_codes.append("BREAKOUT_LOWER")
            else:
                reason_codes.append("NO_BREAKOUT")
        else:
            reason_codes.append("DONCHIAN_MISSING")

        if adx is not None and adx < 15:
            setup_valid = False
            reason_codes.append("ADX_TOO_LOW_BREAKOUT")

        confidence = 0.6 if setup_valid else 0.2
        return JudgeOutput(
            result={"setupValid": setup_valid, "setupType": "breakout", "probability": 0.55 if setup_valid else 0.2},
            confidence=confidence,
            reason_codes=reason_codes,
            _debug=debug,
        )

    def _eval_mean_reversion(self, v: dict, regime: str, volatility: str,
                              debug: dict, config: JudgeConfig) -> JudgeOutput:
        """meanReversion preset. Reference: Section 4-4"""
        rsi = v.get("rsi14")
        bb_upper = v.get("bb20_upper")
        bb_lower = v.get("bb20_lower")
        ema20 = v.get("ema20")  # proxy for current price
        reason_codes: list[str] = []
        setup_valid = False
        side = "NONE"

        debug["rsi14"] = rsi
        debug["bb20_upper"] = bb_upper
        debug["bb20_lower"] = bb_lower

        if regime != "range":
            reason_codes.append("NOT_RANGE_REGIME")
            return JudgeOutput(
                result={"setupValid": False, "setupType": "meanReversion", "probability": 0.0, "side": "NONE"},
                confidence=0.2, reason_codes=reason_codes, _debug=debug,
            )

        if rsi is not None and bb_lower is not None and bb_upper is not None and ema20 is not None:
            if rsi < 30 and ema20 <= bb_lower:
                setup_valid = True
                side = "BUY"
                reason_codes.append("MEAN_REVERSION_BUY")
            elif rsi > 70 and ema20 >= bb_upper:
                setup_valid = True
                side = "SELL"
                reason_codes.append("MEAN_REVERSION_SELL")
            else:
                reason_codes.append("NO_MEAN_REVERSION_SIGNAL")
        else:
            reason_codes.append("INDICATORS_MISSING")

        if volatility in ("high", "extreme"):
            setup_valid = False
            reason_codes.append("VOLATILITY_TOO_HIGH")

        confidence = 0.6 if setup_valid else 0.2
        return JudgeOutput(
            result={"setupValid": setup_valid, "setupType": "meanReversion",
                    "probability": 0.55 if setup_valid else 0.15, "side": side},
            confidence=confidence,
            reason_codes=reason_codes,
            _debug=debug,
        )

    def describe_config(self) -> dict:
        return {
            "M2-001": {"key": "setup.enabled", "type": "boolean", "default": True},
            "M2-002": {"key": "setup.timeframes", "type": "array", "default": ["H1", "M30", "M15"]},
            "M2-003": {"key": "setup.preset", "type": "enum", "default": "trendFollow",
                       "options": ["trendFollow", "pullback", "breakout", "meanReversion"]},
            "M2-006": {"key": "setup.mode", "type": "enum", "default": "rule"},
            "M2-007": {"key": "setup.minProbability", "type": "number", "default": 60},
        }
