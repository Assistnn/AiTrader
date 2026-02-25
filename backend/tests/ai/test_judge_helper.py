"""
AIJudgeHelper tests: common AI call flow with failsafe.
Reference: 05_AI統合 Section 4, 14_コスト管理 Section 2【監査3,4】
"""

import json
from datetime import datetime, timezone

import pytest
from app.services.ai.budget_tracker import BudgetTracker, UsageRecord
from app.services.ai.judge_helper import AIJudgeHelper
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.rate_limiter import AIRateLimiter
from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput
from app.services.pipeline.data_types import IndicatorSnapshot, StateSnapshot
from app.services.safeguard.guard_types import GuardState

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _guard_state() -> GuardState:
    return GuardState(
        entry_allowed=True, force_close=False, trader_halted=False,
        cooldown_until=None, lot_multiplier=1.0,
        evaluations=[], blocking_guards=[],
    )


def _state() -> StateSnapshot:
    values = {"ema20": 150.0, "atr14": 0.5, "rsi14": 55.0}
    return StateSnapshot(
        pair="USD_JPY", timestamp=NOW, trade_allowed=True,
        trend="UP", regime="trend", volatility="normal",
        indicators={
            "H1": IndicatorSnapshot(pair="USD_JPY", timeframe="H1", timestamp=NOW, values=values),
            "M5": IndicatorSnapshot(pair="USD_JPY", timeframe="M5", timestamp=NOW, values=values),
        },
        ema_alignment="bullish", rsi_zone="neutral", bb_position="middle",
    )


def _input(trader_id: int = 1) -> JudgeInput:
    return JudgeInput(
        pair="USD_JPY", timestamp=NOW, state=_state(),
        guard_state=_guard_state(), positions=[], account=None,
        trader_id=trader_id,
    )


def _m1_response() -> dict:
    return {
        "trend": "UP", "regime": "trend", "volatility": "normal",
        "tradeAllowed": True, "confidence": 0.85,
        "reason_codes": ["AI_EMA_BULLISH"],
    }


class TestSuccessFlow:
    """Normal AI call success path."""

    async def test_returns_judge_output_on_success(self):
        provider = MockAIProvider(response_json=_m1_response(), latency_ms=0)
        helper = AIJudgeHelper(
            provider=provider,
            rate_limiter=AIRateLimiter(),
            budget_tracker=BudgetTracker(),
        )
        config = JudgeConfig(timeframes=["D1", "H4"])
        output = await helper.execute_ai_judgment("m1", _input(), config)
        assert output is not None
        assert output.confidence == 0.85
        assert "AI_EMA_BULLISH" in output.reason_codes
        assert output._debug["ai_provider"] == "mock"

    async def test_records_usage_on_success(self):
        provider = MockAIProvider(response_json=_m1_response(), latency_ms=0)
        tracker = BudgetTracker()
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=AIRateLimiter(), budget_tracker=tracker,
        )
        await helper.execute_ai_judgment("m1", _input(), JudgeConfig())
        usage = tracker.get_daily_usage()
        assert usage.total_calls == 1
        assert usage.total_tokens > 0


class TestRateLimitBlock:
    """Rate limiter blocks AI call【監査4】."""

    async def test_returns_none_when_rate_limited(self):
        provider = MockAIProvider(response_json=_m1_response(), latency_ms=0)
        limiter = AIRateLimiter(per_trader_per_minute=1, global_per_minute=100)
        limiter.record_call(trader_id=1)  # exhaust limit
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=limiter, budget_tracker=BudgetTracker(),
        )
        output = await helper.execute_ai_judgment("m1", _input(trader_id=1), JudgeConfig())
        assert output is None
        assert provider.call_count == 0  # Provider never called


class TestBudgetExceeded:
    """Budget exceeded blocks AI call【監査4】."""

    async def test_returns_none_when_budget_exceeded(self):
        provider = MockAIProvider(response_json=_m1_response(), latency_ms=0)
        tracker = BudgetTracker(daily_token_limit=100)
        # Exhaust budget
        tracker.record_usage(UsageRecord(
            trader_id=1, stage="m1", provider="mock", model="mock",
            tokens_input=50, tokens_output=60,
            estimated_cost_usd=0.01,
            timestamp=datetime.now(timezone.utc),
        ))
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=AIRateLimiter(), budget_tracker=tracker,
        )
        output = await helper.execute_ai_judgment("m1", _input(), JudgeConfig())
        assert output is None
        assert provider.call_count == 0


class TestProviderFailure:
    """AI provider failure → returns None (caller falls back)【監査4】."""

    async def test_timeout_returns_none(self):
        provider = MockAIProvider(should_timeout=True)
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=AIRateLimiter(), budget_tracker=BudgetTracker(),
        )
        output = await helper.execute_ai_judgment("m1", _input(), JudgeConfig())
        assert output is None

    async def test_error_returns_none(self):
        provider = MockAIProvider(should_error=True)
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=AIRateLimiter(), budget_tracker=BudgetTracker(),
        )
        output = await helper.execute_ai_judgment("m1", _input(), JudgeConfig())
        assert output is None


class TestParseFailure:
    """Invalid AI response → returns None."""

    async def test_invalid_json_returns_none(self):
        provider = MockAIProvider(response_text="not valid json", latency_ms=0)
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=AIRateLimiter(), budget_tracker=BudgetTracker(),
        )
        output = await helper.execute_ai_judgment("m1", _input(), JudgeConfig())
        assert output is None
        # Usage should still be recorded even on parse failure
        usage = helper._budget_tracker.get_daily_usage()
        assert usage.total_calls == 1

    async def test_schema_violation_returns_none(self):
        """Response JSON is valid but doesn't match M1 schema."""
        bad_response = {"invalid_field": "value"}
        provider = MockAIProvider(response_json=bad_response, latency_ms=0)
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=AIRateLimiter(), budget_tracker=BudgetTracker(),
        )
        output = await helper.execute_ai_judgment("m1", _input(), JudgeConfig())
        assert output is None
