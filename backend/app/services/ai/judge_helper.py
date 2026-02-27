"""
AIJudgeHelper: common AI call flow for M1-M4 pipeline stages.

Reference: 05_AI統合 Section 4, 14_コスト管理 Section 2【監査3,4】
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.logging_config import log_with_data
from app.services.ai.ai_types import AIResponse
from app.services.ai.base_provider import BaseAIProvider
from app.services.ai.budget_tracker import BudgetStatus, BudgetTracker, UsageRecord
from app.services.ai.prompt_assembler import PromptAssembler
from app.services.ai.rate_limiter import AIRateLimiter
from app.services.ai.response_parser import parse_response
from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput

logger = logging.getLogger(__name__)


class AIJudgeHelper:
    """Common AI judgment execution flow.

    Reference: 05_AI統合 Section 4

    Flow:
    1. PromptAssembler builds prompt
    2. AIRateLimiter checks rate
    3. BudgetTracker checks budget
    4. BaseAIProvider.call() executes
    5. ResponseParser validates response
    6. BudgetTracker records usage
    7. On failure → fallback (HOLD or rule_result)
    """

    def __init__(
        self,
        provider: BaseAIProvider,
        rate_limiter: AIRateLimiter,
        budget_tracker: BudgetTracker,
        assembler: PromptAssembler | None = None,
    ) -> None:
        self._provider = provider
        self._rate_limiter = rate_limiter
        self._budget_tracker = budget_tracker
        self._assembler = assembler or PromptAssembler()

    async def execute_ai_judgment(
        self,
        stage: str,
        input: JudgeInput,
        config: JudgeConfig,
        rule_result: JudgeOutput | None = None,
    ) -> JudgeOutput | None:
        """Execute AI judgment for a pipeline stage.

        Returns:
            JudgeOutput if AI call succeeds and parses correctly.
            None if any step fails (caller should fallback).
        """
        trader_id = input.trader_id or 0

        # 1. Rate limit check
        if not self._rate_limiter.can_call(trader_id):
            logger.warning("AI rate limit exceeded for trader %d", trader_id)
            return None

        # 2. Budget check
        budget_status = self._budget_tracker.check_budget()
        if budget_status == BudgetStatus.EXCEEDED:
            logger.warning("AI budget exceeded, blocking call for trader %d", trader_id)
            return None

        # 3. Assemble prompt
        request = self._assembler.assemble(stage, input, config, rule_result)

        # 4. Call AI provider
        try:
            response: AIResponse = await self._provider.call(request)
        except TimeoutError:
            logger.warning("AI call timeout for stage %s, trader %d", stage, trader_id)
            return None
        except Exception:
            logger.exception("AI call error for stage %s, trader %d", stage, trader_id)
            return None

        # 5. Record rate limit
        self._rate_limiter.record_call(trader_id)

        # 6. Parse response
        parsed = parse_response(stage, response.raw_text)
        if parsed is None:
            logger.warning("AI response parse failed for stage %s", stage)
            # Record usage even on parse failure
            self._record_usage(trader_id, stage, response)
            return None

        response.parsed_json = parsed

        # 7. Record usage
        self._record_usage(trader_id, stage, response)

        # 8. Build JudgeOutput
        confidence = parsed.get("confidence", 0.0)
        reason_codes = parsed.get("reason_codes", [])

        log_with_data(logger, logging.INFO, "AI judgment", {
            "stage": stage,
            "trader_id": trader_id,
            "provider": self._provider.provider_name(),
            "model": response.model,
            "tokens_in": response.tokens_input,
            "tokens_out": response.tokens_output,
            "latency_ms": response.latency_ms,
            "confidence": confidence,
        })

        return JudgeOutput(
            result=parsed,
            confidence=confidence,
            reason_codes=reason_codes,
            _debug={
                "ai_provider": self._provider.provider_name(),
                "ai_model": response.model,
                "ai_tokens_input": response.tokens_input,
                "ai_tokens_output": response.tokens_output,
                "ai_latency_ms": response.latency_ms,
            },
        )

    def _record_usage(self, trader_id: int, stage: str, response: AIResponse) -> None:
        """Record usage to budget tracker."""
        # Estimate cost (GPT-4o pricing as default)
        cost = (response.tokens_input * 5 + response.tokens_output * 15) / 1_000_000

        self._budget_tracker.record_usage(UsageRecord(
            trader_id=trader_id,
            stage=stage,
            provider=response.provider,
            model=response.model,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
            estimated_cost_usd=cost,
            timestamp=datetime.now(timezone.utc),
        ))
