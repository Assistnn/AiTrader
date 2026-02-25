"""
M1 AI mode tests: aiAssist and aiFull mode behavior.
Reference: 04_判定パイプライン Section 3, 05_AI統合 Section 4
"""

from datetime import datetime, timezone

from app.services.ai.budget_tracker import BudgetTracker
from app.services.ai.judge_helper import AIJudgeHelper
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.rate_limiter import AIRateLimiter
from app.services.decision.decision_types import JudgeConfig, JudgeInput
from app.services.decision.m1_direction import M1DirectionJudge
from app.services.pipeline.data_types import IndicatorSnapshot, StateSnapshot
from app.services.safeguard.guard_types import GuardState

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _guard_state() -> GuardState:
    return GuardState(
        entry_allowed=True, force_close=False, trader_halted=False,
        cooldown_until=None, lot_multiplier=1.0,
        evaluations=[], blocking_guards=[],
    )


def _state(trend="UP", adx14=30.0) -> StateSnapshot:
    values = {"ema20": 150.0, "ema50": 149.0, "ema200": 145.0, "adx14": adx14, "atr14": 0.5, "rsi14": 55.0}
    return StateSnapshot(
        pair="USD_JPY", timestamp=NOW, trade_allowed=True,
        trend=trend, regime="trend", volatility="normal",
        indicators={
            "D1": IndicatorSnapshot(pair="USD_JPY", timeframe="D1", timestamp=NOW, values=values),
            "H4": IndicatorSnapshot(pair="USD_JPY", timeframe="H4", timestamp=NOW, values=values),
            "H1": IndicatorSnapshot(pair="USD_JPY", timeframe="H1", timestamp=NOW, values=values),
        },
        ema_alignment="bullish", rsi_zone="neutral", bb_position="middle",
    )


def _input() -> JudgeInput:
    return JudgeInput(
        pair="USD_JPY", timestamp=NOW, state=_state(),
        guard_state=_guard_state(), positions=[], account=None, trader_id=1,
    )


def _m1_ai_response() -> dict:
    return {
        "trend": "DOWN", "regime": "range", "volatility": "high",
        "tradeAllowed": False, "confidence": 0.9,
        "reason_codes": ["AI_BEARISH_DIVERGENCE"],
    }


def _helper(response_json=None, should_timeout=False) -> AIJudgeHelper:
    provider = MockAIProvider(
        response_json=response_json or _m1_ai_response(),
        latency_ms=0,
        should_timeout=should_timeout,
    )
    return AIJudgeHelper(
        provider=provider,
        rate_limiter=AIRateLimiter(),
        budget_tracker=BudgetTracker(),
    )


class TestAiAssistMode:
    """aiAssist: rule first → AI confirm → confidence check."""

    async def test_high_confidence_ai_adopted(self):
        """AI result with high confidence is adopted over rule result."""
        helper = _helper()
        judge = M1DirectionJudge(ai_helper=helper)
        config = JudgeConfig(mode="aiAssist", timeframes=["D1", "H4", "H1"],
                             params={"minConfidence": 0.7})
        output = await judge.judge(_input(), config)
        # AI says DOWN with 0.9 confidence > 0.7 threshold
        assert output.result.get("trend") == "DOWN"
        assert output._debug.get("ai_adopted") is True

    async def test_low_confidence_falls_back_to_rule(self):
        """AI result with low confidence → fallback to rule."""
        low_conf = _m1_ai_response()
        low_conf["confidence"] = 0.3
        helper = _helper(response_json=low_conf)
        judge = M1DirectionJudge(ai_helper=helper)
        config = JudgeConfig(mode="aiAssist", timeframes=["D1", "H4", "H1"],
                             params={"minConfidence": 0.7})
        output = await judge.judge(_input(), config)
        # Should fallback to rule result (UP trend from state)
        assert output.result.get("trend") == "UP"
        assert output._debug.get("ai_adopted") is False


class TestAiFullMode:
    """aiFull: AI only → failure fallback to rule."""

    async def test_ai_success_adopted(self):
        helper = _helper()
        judge = M1DirectionJudge(ai_helper=helper)
        config = JudgeConfig(mode="aiFull", timeframes=["D1", "H4", "H1"])
        output = await judge.judge(_input(), config)
        assert output.result.get("trend") == "DOWN"
        assert output._debug.get("ai_adopted") is True

    async def test_ai_failure_falls_back_to_rule(self):
        """AI timeout → fallback to rule mode."""
        helper = _helper(should_timeout=True)
        judge = M1DirectionJudge(ai_helper=helper)
        config = JudgeConfig(mode="aiFull", timeframes=["D1", "H4", "H1"])
        output = await judge.judge(_input(), config)
        # Should fallback to rule (UP trend)
        assert output.result.get("trend") == "UP"
        assert output._debug.get("ai_adopted") is False


class TestRuleModeUnchanged:
    """Rule mode still works without ai_helper."""

    async def test_rule_mode_no_helper(self):
        judge = M1DirectionJudge()  # no ai_helper
        config = JudgeConfig(mode="rule", timeframes=["D1", "H4", "H1"])
        output = await judge.judge(_input(), config)
        assert output.result.get("trend") == "UP"
        assert output.result.get("tradeAllowed") is True
