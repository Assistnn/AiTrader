"""
Email sender service (stub).

Reference: 08_API仕様 Section 3-9
Actual SMTP integration will be implemented when SMTP credentials are configured.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EmailMessage:
    """Email message."""
    to: str
    subject: str
    body_html: str


class EmailSender:
    """Send emails via SMTP (stub)."""

    def __init__(self, host: str = "", port: int = 587, user: str = "", password: str = ""):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    async def send(self, message: EmailMessage) -> bool:
        """Send an email. Returns True on success."""
        if not self.host:
            # Stub: log instead of sending
            return False
        raise NotImplementedError("EmailSender.send: requires SMTP integration")

    async def send_test(self, to: str) -> bool:
        """Send a test email."""
        return await self.send(EmailMessage(
            to=to,
            subject="AI Trading System - Test Email",
            body_html="<p>This is a test email from AI Trading System.</p>",
        ))
