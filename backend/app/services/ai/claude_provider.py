"""
Anthropic Claude provider implementation.

Reference: 05_AI統合 Section 2-3
"""

from __future__ import annotations

import time

import httpx

from app.services.ai.ai_types import AIRequest, AIResponse
from app.services.ai.base_provider import BaseAIProvider


class ClaudeProvider(BaseAIProvider):
    """Anthropic Claude API provider. Reference: Section 2-3"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = "https://api.anthropic.com/v1/messages"

    async def call(self, request: AIRequest) -> AIResponse:
        start = time.monotonic()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._base_url,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": request.max_tokens,
                    "system": request.system_prompt,
                    "messages": [
                        {"role": "user", "content": request.user_prompt},
                    ],
                    "temperature": request.temperature,
                },
                timeout=request.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.monotonic() - start) * 1000
        content_blocks = data.get("content", [])
        text = ""
        for block in content_blocks:
            if block.get("type") == "text":
                text += block.get("text", "")

        usage = data.get("usage", {})

        return AIResponse(
            raw_text=text,
            parsed_json=None,
            model=data.get("model", self._model),
            tokens_input=usage.get("input_tokens", 0),
            tokens_output=usage.get("output_tokens", 0),
            latency_ms=round(latency_ms, 2),
            provider="claude",
        )

    def provider_name(self) -> str:
        return "claude"
