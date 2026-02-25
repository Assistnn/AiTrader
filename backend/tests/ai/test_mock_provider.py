"""
MockAIProvider tests: test helper functionality.
Reference: 05_AI統合 Section 2-3
"""

import pytest
from app.services.ai.ai_types import AIRequest
from app.services.ai.mock_provider import MockAIProvider


@pytest.fixture
def ai_request():
    return AIRequest(
        system_prompt="You are a trading assistant.",
        user_prompt="Analyze the market.",
    )


class TestMockProviderNormal:
    async def test_returns_default_response(self, ai_request):
        provider = MockAIProvider()
        response = await provider.call(ai_request)
        assert response.provider == "mock"
        assert response.tokens_input > 0
        assert provider.call_count == 1
        assert provider.last_request is ai_request

    async def test_returns_custom_json(self, ai_request):
        custom = {"trend": "DOWN", "confidence": 0.9}
        provider = MockAIProvider(response_json=custom)
        response = await provider.call(ai_request)
        assert '"DOWN"' in response.raw_text
        assert response.parsed_json == custom

    async def test_returns_custom_text(self, ai_request):
        provider = MockAIProvider(response_text="raw text response")
        response = await provider.call(ai_request)
        assert response.raw_text == "raw text response"

    async def test_provider_name(self):
        assert MockAIProvider().provider_name() == "mock"


class TestMockProviderErrors:
    async def test_timeout_raises(self, ai_request):
        provider = MockAIProvider(should_timeout=True)
        with pytest.raises(TimeoutError):
            await provider.call(ai_request)
        assert provider.call_count == 1

    async def test_error_raises(self, ai_request):
        provider = MockAIProvider(should_error=True, error_status_code=429)
        with pytest.raises(RuntimeError, match="429"):
            await provider.call(ai_request)

    async def test_call_count_incremented_on_error(self, ai_request):
        provider = MockAIProvider(should_error=True)
        with pytest.raises(RuntimeError):
            await provider.call(ai_request)
        assert provider.call_count == 1
