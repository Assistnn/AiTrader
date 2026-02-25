"""
Google Gemini provider implementation.

Reference: 05_AI統合 Section 2-3
"""

from __future__ import annotations

import time

import httpx

from app.services.ai.ai_types import AIRequest, AIResponse
from app.services.ai.base_provider import BaseAIProvider


class GeminiProvider(BaseAIProvider):
    """Google Gemini API provider. Reference: Section 2-3"""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self._api_key = api_key
        self._model = model

    async def call(self, request: AIRequest) -> AIResponse:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._api_key}"
        )
        start = time.monotonic()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": request.system_prompt}]},
                    "contents": [{"parts": [{"text": request.user_prompt}]}],
                    "generationConfig": {
                        "temperature": request.temperature,
                        "maxOutputTokens": request.max_tokens,
                    },
                },
                timeout=request.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.monotonic() - start) * 1000
        candidates = data.get("candidates", [{}])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = parts[0].get("text", "") if parts else ""

        usage = data.get("usageMetadata", {})

        return AIResponse(
            raw_text=text,
            parsed_json=None,
            model=self._model,
            tokens_input=usage.get("promptTokenCount", 0),
            tokens_output=usage.get("candidatesTokenCount", 0),
            latency_ms=round(latency_ms, 2),
            provider="gemini",
        )

    def provider_name(self) -> str:
        return "gemini"
