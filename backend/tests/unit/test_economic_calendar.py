"""
Economic calendar tests.
Reference: Phase 4 Step 17
"""

from datetime import datetime, timezone

from app.services.notification.economic_calendar import EconomicCalendar


class TestHighImpact:
    def test_importance_3_is_high(self):
        assert EconomicCalendar.is_high_impact(3) is True

    def test_importance_2_is_not_high(self):
        assert EconomicCalendar.is_high_impact(2) is False

    def test_importance_1_is_not_high(self):
        assert EconomicCalendar.is_high_impact(1) is False


class TestStopWindow:
    def test_default_30min_window(self):
        event = datetime(2026, 2, 25, 13, 30, tzinfo=timezone.utc)
        start, end = EconomicCalendar.get_stop_window(event)
        assert start == datetime(2026, 2, 25, 13, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 2, 25, 14, 0, tzinfo=timezone.utc)

    def test_custom_window(self):
        event = datetime(2026, 2, 25, 13, 30, tzinfo=timezone.utc)
        start, end = EconomicCalendar.get_stop_window(event, before_min=60, after_min=15)
        assert start == datetime(2026, 2, 25, 12, 30, tzinfo=timezone.utc)
        assert end == datetime(2026, 2, 25, 13, 45, tzinfo=timezone.utc)


class TestIsInStopWindow:
    def test_within_window(self):
        event = datetime(2026, 2, 25, 13, 30, tzinfo=timezone.utc)
        now = datetime(2026, 2, 25, 13, 15, tzinfo=timezone.utc)
        assert EconomicCalendar.is_in_stop_window(now, event) is True

    def test_outside_window(self):
        event = datetime(2026, 2, 25, 13, 30, tzinfo=timezone.utc)
        now = datetime(2026, 2, 25, 12, 0, tzinfo=timezone.utc)
        assert EconomicCalendar.is_in_stop_window(now, event) is False

    def test_at_boundary(self):
        event = datetime(2026, 2, 25, 13, 30, tzinfo=timezone.utc)
        at_start = datetime(2026, 2, 25, 13, 0, tzinfo=timezone.utc)
        assert EconomicCalendar.is_in_stop_window(at_start, event) is True
