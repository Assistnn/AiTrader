"""
Mock AI provider for testing.

Reference: 05_AI統合 Section 2-3
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.services.ai.ai_types import AIRequest, AIResponse
from app.services.ai.base_provider import BaseAIProvider


class MockAIProvider(BaseAIProvider):
    """Mock provider for testing. Returns configurable fixed responses."""

    def __init__(
        self,
        response_json: dict[str, Any] | None = None,
        response_text: str | None = None,
        latency_ms: float = 50.0,
        tokens_input: int = 500,
        tokens_output: int = 200,
        model: str = "mock-model",
        should_timeout: bool = False,
        should_error: bool = False,
        error_status_code: int = 500,
    ) -> None:
        self._response_json = response_json
        self._response_text = response_text
        self._latency_ms = latency_ms
        self._tokens_input = tokens_input
        self._tokens_output = tokens_output
        self._model = model
        self._should_timeout = should_timeout
        self._should_error = should_error
        self._error_status_code = error_status_code
        self.call_count = 0
        self.last_request: AIRequest | None = None

    async def call(self, request: AIRequest) -> AIResponse:
        self.call_count += 1
        self.last_request = request

        if self._should_timeout:
            raise TimeoutError("Mock timeout")

        if self._should_error:
            raise RuntimeError(f"Mock error: HTTP {self._error_status_code}")

        # Simulate latency
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000)

        if self._response_text is not None:
            raw_text = self._response_text
        elif self._response_json is not None:
            raw_text = json.dumps(self._response_json)
        else:
            raw_text = json.dumps({
                "trend": "UP", "regime": "trend", "volatility": "normal",
                "tradeAllowed": True, "confidence": 0.8,
                "reason_codes": ["MOCK_RESPONSE"],
            })

        return AIResponse(
            raw_text=raw_text,
            parsed_json=self._response_json,
            model=self._model,
            tokens_input=self._tokens_input,
            tokens_output=self._tokens_output,
            latency_ms=self._latency_ms,
            provider="mock",
        )

    def provider_name(self) -> str:
        return "mock"
