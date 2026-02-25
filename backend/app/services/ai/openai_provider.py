"""
OpenAI provider implementation.

Reference: 05_AI統合 Section 2-3
"""

from __future__ import annotations

import time

import httpx

from app.services.ai.ai_types import AIRequest, AIResponse
from app.services.ai.base_provider import BaseAIProvider


class OpenAIProvider(BaseAIProvider):
    """OpenAI API provider (GPT-4o). Reference: Section 2-3"""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = "https://api.openai.com/v1/chat/completions"

    async def call(self, request: AIRequest) -> AIResponse:
        start = time.monotonic()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": request.system_prompt},
                        {"role": "user", "content": request.user_prompt},
                    ],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                },
                timeout=request.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.monotonic() - start) * 1000
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return AIResponse(
            raw_text=choice["message"]["content"],
            parsed_json=None,
            model=data.get("model", self._model),
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            latency_ms=round(latency_ms, 2),
            provider="openai",
        )

    def provider_name(self) -> str:
        return "openai"
