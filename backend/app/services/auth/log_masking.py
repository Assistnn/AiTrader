"""
Log masking for secrets.

Reference: 11_セキュリティ Section 4-3

Masking rules:
  - api_key → "****" + last 4 chars
  - api_secret → "********"
  - password → "********"
  - access_token → "Bearer ****..."
"""

from __future__ import annotations

import logging
import re


# Patterns to mask in log output
_MASK_PATTERNS = [
    # JSON-style key-value pairs
    (re.compile(r'("api_key"\s*:\s*")([^"]+)(")', re.IGNORECASE), r'\1****\3'),
    (re.compile(r'("api_secret"\s*:\s*")([^"]+)(")', re.IGNORECASE), r'\1********\3'),
    (re.compile(r'("password"\s*:\s*")([^"]+)(")', re.IGNORECASE), r'\1********\3'),
    (re.compile(r'("access_token"\s*:\s*")([^"]+)(")', re.IGNORECASE), r'\1Bearer ****...\3'),
    (re.compile(r'("refresh_token"\s*:\s*")([^"]+)(")', re.IGNORECASE), r'\1****...\3'),
    # Bearer token in headers
    (re.compile(r'(Bearer\s+)(\S+)', re.IGNORECASE), r'\1****...'),
]


def mask_secrets(text: str) -> str:
    """Apply all masking patterns to a string."""
    for pattern, replacement in _MASK_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def mask_api_key(key: str) -> str:
    """Mask an API key showing only last 4 chars."""
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


class SecretMaskingFilter(logging.Filter):
    """Logging filter that masks secrets in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: mask_secrets(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_secrets(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True
