"""
AI provider shared types.

Reference: 05_AI統合 Section 2-1, 2-2
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AIRequest:
    """AI provider request. Reference: Section 2-1"""

    system_prompt: str
    user_prompt: str
    temperature: float = 0.1
    max_tokens: int = 300
    timeout_seconds: float = 5.0


@dataclass
class AIResponse:
    """AI provider response. Reference: Section 2-2"""

    raw_text: str
    parsed_json: dict | None
    model: str
    tokens_input: int
    tokens_output: int
    latency_ms: float
    provider: str = ""
