"""
AI provider factory.

Reference: 05_AI統合 Section 2-3
"""

from __future__ import annotations

from app.services.ai.base_provider import BaseAIProvider
from app.services.ai.claude_provider import ClaudeProvider
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.openai_provider import OpenAIProvider


def create_provider(
    provider_name: str,
    api_key: str = "",
    model: str = "",
) -> BaseAIProvider:
    """Create an AI provider by name.

    Args:
        provider_name: One of 'openai', 'gemini', 'claude', 'mock'.
        api_key: API key for the provider.
        model: Model override (uses provider default if empty).

    Returns:
        BaseAIProvider instance.

    Raises:
        ValueError: If provider_name is unknown.
    """
    if provider_name == "openai":
        return OpenAIProvider(api_key=api_key, model=model or "gpt-4o")
    if provider_name == "gemini":
        return GeminiProvider(api_key=api_key, model=model or "gemini-1.5-flash")
    if provider_name == "claude":
        return ClaudeProvider(api_key=api_key, model=model or "claude-sonnet-4-20250514")
    if provider_name == "mock":
        return MockAIProvider(model=model or "mock-model")
    raise ValueError(f"Unknown AI provider: {provider_name}")
