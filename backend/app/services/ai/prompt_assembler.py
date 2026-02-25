"""
PromptAssembler: build 4-layer prompts for AI pipeline stages.

Reference: 05_AI統合 Section 3-1
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from app.services.ai.ai_types import AIRequest
from app.services.ai.prompt_templates import STAGE_PROMPTS
from app.services.ai.prompt_validator import validate_strategy_text
from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput


class PromptAssembler:
    """Assemble 4-layer prompts for AI judgment stages.

    Reference: 05_AI統合 Section 3-1

    Layer 1: System prompt (stage-specific template)
    Layer 2: User strategy text (sanitized, max 2000 chars)
    Layer 3: Structured context (JSON: indicators, state, positions)
    Layer 4: Rule mode result (aiAssist only, appended to user prompt)
    """

    def assemble(
        self,
        stage: str,
        input: JudgeInput,
        config: JudgeConfig,
        rule_result: JudgeOutput | None = None,
    ) -> AIRequest:
        """Build an AIRequest for the given stage.

        Args:
            stage: Pipeline stage ('m1', 'm2', 'm3', 'm4').
            input: Judge input with market data.
            config: Judge config with mode and params.
            rule_result: Rule mode result (for aiAssist Layer 4).

        Returns:
            AIRequest ready to send to provider.
        """
        # Layer 1: System prompt
        system_prompt = STAGE_PROMPTS.get(stage, STAGE_PROMPTS["m1"])

        # Layer 2: User strategy text (sanitized)
        strategy_text = config.params.get("strategyText", "")
        if strategy_text:
            validation = validate_strategy_text(strategy_text)
            strategy_text = validation.sanitized_text

        # Layer 3: Structured context
        context = self._build_context(stage, input)

        # Layer 4: Rule result (aiAssist only)
        rule_section = ""
        if rule_result is not None and config.mode == "aiAssist":
            rule_section = self._format_rule_result(rule_result)

        # Assemble user prompt
        parts: list[str] = []
        if strategy_text:
            parts.append(f"[Strategy]\n{strategy_text}")
        parts.append(f"[Market Data]\n{context}")
        if rule_section:
            parts.append(f"[Rule Engine Result]\n{rule_section}")

        user_prompt = "\n\n".join(parts)

        return AIRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=config.params.get("temperature", 0.1),
            max_tokens=config.params.get("maxTokens", 300),
            timeout_seconds=config.params.get("timeoutSeconds", 5.0),
        )

    def _build_context(self, stage: str, input: JudgeInput) -> str:
        """Build structured JSON context from JudgeInput."""
        ctx: dict[str, Any] = {
            "pair": input.pair,
            "timestamp": input.timestamp.isoformat() if input.timestamp else None,
        }

        # Add indicator data from state
        if input.state and hasattr(input.state, "indicators"):
            indicators_summary: dict[str, Any] = {}
            for tf, snapshot in input.state.indicators.items():
                indicators_summary[tf] = snapshot.values if hasattr(snapshot, "values") else {}
            ctx["indicators"] = indicators_summary

        if input.state:
            ctx["trend"] = getattr(input.state, "trend", None)
            ctx["regime"] = getattr(input.state, "regime", None)
            ctx["volatility"] = getattr(input.state, "volatility", None)

        # Add previous stage results
        if input.previous_stages:
            prev: dict[str, Any] = {}
            for k, v in input.previous_stages.items():
                if hasattr(v, "result"):
                    prev[k] = v.result
            if prev:
                ctx["previous_stages"] = prev

        # Add position info for M4
        if stage == "m4" and input.positions:
            ctx["positions_count"] = len(input.positions)

        # Add account state
        if input.account:
            ctx["account"] = {
                "equity": getattr(input.account, "equity", None),
                "margin_usage_pct": getattr(input.account, "margin_usage_pct", None),
            }

        return json.dumps(ctx, ensure_ascii=False, default=str)

    def _format_rule_result(self, result: JudgeOutput) -> str:
        """Format rule mode result for Layer 4."""
        data = {
            "result": result.result,
            "confidence": result.confidence,
            "reason_codes": result.reason_codes,
        }
        return json.dumps(data, ensure_ascii=False)
