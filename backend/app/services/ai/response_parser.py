"""
ResponseParser: parse and validate AI provider responses per stage schema.

Reference: 05_AI統合 Section 3-4
"""

from __future__ import annotations

import json
import re
from typing import Any

# Stage-specific JSON schemas (required fields + allowed values)
_SCHEMAS: dict[str, dict[str, Any]] = {
    "m1": {
        "required": ["trend", "regime", "volatility", "tradeAllowed", "confidence", "reason_codes"],
        "enums": {
            "trend": ["UP", "DOWN", "NEUTRAL"],
            "regime": ["trend", "range"],
            "volatility": ["low", "normal", "high", "extreme"],
        },
        "types": {
            "tradeAllowed": bool,
            "confidence": (int, float),
            "reason_codes": list,
        },
    },
    "m2": {
        "required": ["setupValid", "setupType", "probability", "confidence", "reason_codes"],
        "enums": {
            "setupType": ["trendFollow", "pullback", "breakout", "meanReversion", "none"],
        },
        "types": {
            "setupValid": bool,
            "probability": (int, float),
            "confidence": (int, float),
            "reason_codes": list,
        },
    },
    "m3": {
        "required": ["entry", "entryType", "tpPips", "slPips", "confidence", "reason_codes"],
        "enums": {
            "entry": ["BUY", "SELL", "NO_TRADE"],
            "entryType": ["market", "limit"],
        },
        "types": {
            "tpPips": (int, float),
            "slPips": (int, float),
            "confidence": (int, float),
            "reason_codes": list,
        },
    },
    "m4": {
        "required": ["action", "confidence", "reason_codes"],
        "enums": {
            "action": ["HOLD", "CLOSE", "PARTIAL_CLOSE", "ADJUST_TP", "ADJUST_SL"],
        },
        "types": {
            "confidence": (int, float),
            "reason_codes": list,
        },
    },
}

# Regex to extract JSON from markdown code blocks
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def parse_response(stage: str, raw_text: str) -> dict[str, Any] | None:
    """Parse AI response text into validated JSON.

    Reference: 05_AI統合 Section 3-4

    Steps:
    1. Strip markdown code blocks
    2. Extract JSON object
    3. Parse JSON
    4. Validate against stage schema
    5. Validate enum values

    Returns:
        Validated dict if successful, None if parsing/validation fails.
    """
    if not raw_text or not raw_text.strip():
        return None

    # 1. Try to extract from markdown code blocks
    text = raw_text.strip()
    block_match = _JSON_BLOCK_RE.search(text)
    if block_match:
        text = block_match.group(1).strip()

    # 2. Try direct JSON parse
    parsed = _try_parse_json(text)
    if parsed is None:
        # 3. Try to find JSON object in text
        obj_match = _JSON_OBJECT_RE.search(text)
        if obj_match:
            parsed = _try_parse_json(obj_match.group())

    if parsed is None or not isinstance(parsed, dict):
        return None

    # 4. Validate schema
    schema = _SCHEMAS.get(stage)
    if schema is None:
        return parsed  # No schema defined, return as-is

    # Check required fields
    for field_name in schema.get("required", []):
        if field_name not in parsed:
            return None

    # Check types
    for field_name, expected_type in schema.get("types", {}).items():
        if field_name in parsed and not isinstance(parsed[field_name], expected_type):
            return None

    # Check enum values
    for field_name, allowed_values in schema.get("enums", {}).items():
        if field_name in parsed and parsed[field_name] not in allowed_values:
            return None

    # Clamp confidence to [0.0, 1.0]
    if "confidence" in parsed:
        parsed["confidence"] = max(0.0, min(1.0, float(parsed["confidence"])))

    return parsed


def _try_parse_json(text: str) -> dict[str, Any] | None:
    """Attempt to parse JSON, return None on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
