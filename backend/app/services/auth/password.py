"""
Password hashing with bcrypt.

Reference: 11_セキュリティ Section 2-2
- Hash: bcrypt (cost factor=12)
- Policy: min 8 chars, alphanumeric mix (Phase 1 simple rules)
"""

from __future__ import annotations

import bcrypt

_COST_FACTOR = 12


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (cost=12)."""
    salt = bcrypt.gensalt(rounds=_COST_FACTOR)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength (Phase 1 simple rules).

    Returns:
        (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    has_alpha = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_alpha and has_digit):
        return False, "Password must contain both letters and numbers"
    return True, ""
