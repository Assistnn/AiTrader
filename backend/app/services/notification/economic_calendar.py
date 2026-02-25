"""
Economic calendar service.

Reference: 03_セーフガードエンジン (SG-026 経済指標停止)
Manages economic event data for safeguard integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class UpcomingEvent:
    """Upcoming economic event."""
    event_name: str
    currency: str
    importance: int  # 1-3
    event_datetime: datetime


class EconomicCalendar:
    """Economic event management."""

    @staticmethod
    def is_high_impact(importance: int) -> bool:
        """Check if event is high-impact (importance >= 3)."""
        return importance >= 3

    @staticmethod
    def get_stop_window(event_dt: datetime, before_min: int = 30, after_min: int = 30) -> tuple[datetime, datetime]:
        """Get the trading stop window around an event.

        Args:
            event_dt: Event datetime (UTC)
            before_min: Minutes before event to stop
            after_min: Minutes after event to resume

        Returns:
            (stop_start, stop_end) in UTC
        """
        return (
            event_dt - timedelta(minutes=before_min),
            event_dt + timedelta(minutes=after_min),
        )

    @staticmethod
    def is_in_stop_window(
        now: datetime,
        event_dt: datetime,
        before_min: int = 30,
        after_min: int = 30,
    ) -> bool:
        """Check if current time is within event stop window."""
        start, end = EconomicCalendar.get_stop_window(event_dt, before_min, after_min)
        return start <= now <= end
