"""
BaseAIProvider abstract base class.

Reference: 05_AI統合 Section 2-3
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.ai.ai_types import AIRequest, AIResponse


class BaseAIProvider(ABC):
    """Base class for all AI providers. Reference: Section 2-3"""

    @abstractmethod
    async def call(self, request: AIRequest) -> AIResponse:
        """Execute AI call and return response."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name (e.g. 'openai', 'gemini', 'claude')."""
        ...
