"""
PromptValidator: sanitize user strategy text and detect injection attempts.

Reference: 05_AI統合 Section 3-3【監査3】
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_STRATEGY_LENGTH = 2000

# Injection patterns (Japanese + English)
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"指示を無視", re.IGNORECASE),
    re.compile(r"ignore\s+(previous|above|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"JSON\s*フォーマットを無視", re.IGNORECASE),
    re.compile(r"forget\s+(your\s+)?instructions?", re.IGNORECASE),
    re.compile(r"new\s+instructions?", re.IGNORECASE),
    re.compile(r"\boverride\b", re.IGNORECASE),
    re.compile(r"全力[（(]?買[)）]?|全力[（(]?売[)）]?", re.IGNORECASE),
    re.compile(r"ロット.*最大", re.IGNORECASE),
    re.compile(r"SL.*なし|ストップロス.*無効", re.IGNORECASE),
    re.compile(r"stop\s*loss.*(?:disable|remove|none)", re.IGNORECASE),
    re.compile(r"max(?:imum)?\s*lot", re.IGNORECASE),
]

# Control characters to strip (U+0000 - U+001F except common whitespace)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class ValidationResult:
    """Prompt validation result."""

    sanitized_text: str
    is_safe: bool
    detected_patterns: list[str] = field(default_factory=list)
    was_truncated: bool = False


def validate_strategy_text(text: str) -> ValidationResult:
    """Validate and sanitize user strategy text.

    Reference: 05_AI統合 Section 3-3【監査3】

    - Strips control characters
    - Truncates to MAX_STRATEGY_LENGTH
    - Detects and removes injection patterns
    - Returns sanitized text + detection results
    """
    if not text:
        return ValidationResult(sanitized_text="", is_safe=True)

    # 1. Strip control characters
    cleaned = _CONTROL_CHAR_RE.sub("", text)

    # 2. Truncate
    was_truncated = len(cleaned) > MAX_STRATEGY_LENGTH
    if was_truncated:
        cleaned = cleaned[:MAX_STRATEGY_LENGTH]

    # 3. Detect injection patterns
    detected: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            detected.append(match.group())

    # 4. Remove detected patterns from text
    sanitized = cleaned
    if detected:
        for pattern in _INJECTION_PATTERNS:
            sanitized = pattern.sub("", sanitized)
        # Clean up extra whitespace from removals
        sanitized = re.sub(r"\s{2,}", " ", sanitized).strip()

    return ValidationResult(
        sanitized_text=sanitized,
        is_safe=len(detected) == 0,
        detected_patterns=detected,
        was_truncated=was_truncated,
    )
