"""
UsageRecorder: record AI call usage to DB (ai_decision_logs).

Reference: 14_コスト管理 Section 2-3, 07_データベーススキーマ Section 3-3
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_decision_log import AiDecisionLog
from app.services.ai.ai_types import AIRequest, AIResponse


class UsageRecorder:
    """Record AI call details to ai_decision_logs table.

    Reference: 14_コスト管理 Section 2-3
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(
        self,
        user_id: int,
        trader_id: int,
        execution_id: str,
        stage: str,
        request: AIRequest,
        response: AIResponse,
        adopted: bool,
        fallback_reason: str | None = None,
    ) -> int:
        """Record AI call to database.

        Returns:
            Created log record ID.
        """
        prompt_hash = hashlib.sha256(
            request.system_prompt.encode("utf-8")
        ).hexdigest()

        log = AiDecisionLog(
            user_id=user_id,
            trader_id=trader_id,
            execution_id=execution_id,
            stage=stage,
            timestamp=datetime.now(timezone.utc),
            provider=response.provider,
            model=response.model,
            system_prompt_hash=prompt_hash,
            user_prompt=request.user_prompt,
            raw_response=response.raw_text,
            parsed_result=response.parsed_json,
            parse_success=response.parsed_json is not None,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
            latency_ms=response.latency_ms,
            adopted=adopted,
            fallback_reason=fallback_reason,
        )
        self._db.add(log)
        await self._db.flush()
        return log.id
