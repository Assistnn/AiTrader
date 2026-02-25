"""
Orchestrator async tests: pipeline execution with AI mode integration.
Reference: 04_判定パイプライン Section 8
"""

from datetime import datetime, timezone

from app.services.ai.budget_tracker import BudgetTracker
from app.services.ai.judge_helper import AIJudgeHelper
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.rate_limiter import AIRateLimiter
from app.services.decision.decision_types import JudgeConfig
from app.services.decision.m1_direction import M1DirectionJudge
from app.services.decision.m2_setup import M2SetupJudge
from app.services.decision.m3_entry import M3EntryJudge
from app.services.decision.m4_exit import M4ExitJudge
from app.services.decision.orchestrator import DecisionOrchestrator
from app.services.pipeline.data_types import IndicatorSnapshot, StateSnapshot
from app.services.safeguard.guard_engine import GuardEngine
from app.services.safeguard.guard_types import AccountState

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _state(trend="UP") -> StateSnapshot:
    values = {"ema20": 150.0, "ema50": 149.0, "ema200": 145.0, "adx14": 30.0, "atr14": 0.5, "rsi14": 55.0}
    return StateSnapshot(
        pair="USD_JPY", timestamp=NOW, trade_allowed=True,
        trend=trend, regime="trend", volatility="normal",
        indicators={
            tf: IndicatorSnapshot(pair="USD_JPY", timeframe=tf, timestamp=NOW, values=values)
            for tf in ["D1", "H4", "H1", "M15", "M5"]
        },
        ema_alignment="bullish", rsi_zone="neutral", bb_position="middle",
    )


def _account() -> AccountState:
    return AccountState(
        capital=1_000_000, daily_realized_pnl=0, daily_unrealized_pnl=0,
        monthly_pnl=0, peak_capital=1_000_000, current_capital=1_000_000,
        consecutive_losses=0, last_trade_was_loss=False, daily_profit_pct=0,
    )


class TestAsyncPipelineExecution:
    """Verify execute_pipeline works as async coroutine."""

    async def test_pipeline_entry_async(self):
        orch = DecisionOrchestrator(
            m1=M1DirectionJudge(), m2=M2SetupJudge(),
            m3=M3EntryJudge(), m4=M4ExitJudge(),
            guard_engine=GuardEngine(),
        )
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=_state(), account=_account(), now=NOW,
        )
        assert result.action == "ENTRY"
        assert result.order is not None

    async def test_pipeline_no_trade_async(self):
        orch = DecisionOrchestrator(
            m1=M1DirectionJudge(), m2=M2SetupJudge(),
            m3=M3EntryJudge(), m4=M4ExitJudge(),
            guard_engine=GuardEngine(),
        )
        # Low ADX + flat EMAs → M1 judges NEUTRAL → NO_TRADE
        values = {"ema20": 150.0, "ema50": 150.0, "ema200": 150.0, "adx14": 15.0, "atr14": 0.5, "rsi14": 50.0}
        state = StateSnapshot(
            pair="USD_JPY", timestamp=NOW, trade_allowed=True,
            trend="NEUTRAL", regime="range", volatility="normal",
            indicators={
                tf: IndicatorSnapshot(pair="USD_JPY", timeframe=tf, timestamp=NOW, values=values)
                for tf in ["D1", "H4", "H1", "M15", "M5"]
            },
            ema_alignment="mixed", rsi_zone="neutral", bb_position="middle",
        )
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=state, account=_account(), now=NOW,
        )
        assert result.action == "NO_TRADE"


class TestAiAssistPipeline:
    """Pipeline execution with aiAssist mode judges."""

    async def test_aiassist_pipeline(self):
        """Full pipeline with AI-assisted M1 judge."""
        ai_m1_response = {
            "trend": "UP", "regime": "trend", "volatility": "normal",
            "tradeAllowed": True, "confidence": 0.9,
            "reason_codes": ["AI_CONFIRMED"],
        }
        provider = MockAIProvider(response_json=ai_m1_response, latency_ms=0)
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=AIRateLimiter(), budget_tracker=BudgetTracker(),
        )
        orch = DecisionOrchestrator(
            m1=M1DirectionJudge(ai_helper=helper),
            m2=M2SetupJudge(),
            m3=M3EntryJudge(),
            m4=M4ExitJudge(),
            guard_engine=GuardEngine(),
        )
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=_state(), account=_account(), now=NOW,
            m1_config=JudgeConfig(mode="aiAssist", timeframes=["D1", "H4", "H1"],
                                  params={"minConfidence": 0.7}),
        )
        # AI result should be adopted (UP with 0.9 confidence)
        assert result.action in ("ENTRY", "NO_TRADE")  # Depends on M2/M3


class TestAiFailureFallback:
    """AI failure in pipeline → graceful fallback to rule mode."""

    async def test_ai_timeout_still_completes(self):
        """If AI times out, pipeline continues with rule mode fallback."""
        provider = MockAIProvider(should_timeout=True)
        helper = AIJudgeHelper(
            provider=provider, rate_limiter=AIRateLimiter(), budget_tracker=BudgetTracker(),
        )
        orch = DecisionOrchestrator(
            m1=M1DirectionJudge(ai_helper=helper),
            m2=M2SetupJudge(),
            m3=M3EntryJudge(),
            m4=M4ExitJudge(),
            guard_engine=GuardEngine(),
        )
        result = await orch.execute_pipeline(
            pair="USD_JPY", state=_state(), account=_account(), now=NOW,
            m1_config=JudgeConfig(mode="aiFull", timeframes=["D1", "H4", "H1"]),
        )
        # Should complete (rule fallback)
        assert result.action in ("ENTRY", "NO_TRADE", "BLOCKED")
