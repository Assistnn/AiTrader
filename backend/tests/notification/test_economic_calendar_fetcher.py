"""
Tests for EconomicCalendarFetcher.
Reference: 16_実行エンジンとUI接続 Section 10
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.notification.economic_calendar_fetcher import (
    EconomicCalendarFetcher,
    EconomicEvent,
)


def _make_event(
    hours_from_now: float = 1.0,
    importance: int = 3,
    currency: str = "USD",
) -> EconomicEvent:
    return EconomicEvent(
        event_id="test-1",
        title="Test Event",
        country="US",
        importance=importance,
        event_datetime=datetime.now(timezone.utc) + timedelta(hours=hours_from_now),
        currency=currency,
    )


class TestEconomicEvent:
    def test_creation(self):
        event = _make_event()
        assert event.title == "Test Event"
        assert event.importance == 3


class TestEconomicCalendarFetcher:
    def test_init(self):
        fetcher = EconomicCalendarFetcher()
        assert fetcher.is_cache_valid is False
        assert fetcher.get_cached_events() == []

    def test_is_cache_valid_after_manual_set(self):
        fetcher = EconomicCalendarFetcher()
        fetcher._events = [_make_event()]
        fetcher._last_fetch = datetime.now(timezone.utc)
        assert fetcher.is_cache_valid is True

    def test_is_cache_expired(self):
        fetcher = EconomicCalendarFetcher()
        fetcher._last_fetch = datetime.now(timezone.utc) - timedelta(hours=24)
        assert fetcher.is_cache_valid is False

    def test_is_fetch_failed_and_expired(self):
        fetcher = EconomicCalendarFetcher()
        assert fetcher.is_fetch_failed_and_expired() is True

        fetcher._last_fetch = datetime.now(timezone.utc)
        assert fetcher.is_fetch_failed_and_expired() is False

    @pytest.mark.asyncio
    async def test_get_upcoming_events_with_cache(self):
        fetcher = EconomicCalendarFetcher()
        events = [
            _make_event(hours_from_now=0.5),
            _make_event(hours_from_now=2.0),
            _make_event(hours_from_now=48.0),  # Too far ahead
        ]
        fetcher._events = events
        fetcher._last_fetch = datetime.now(timezone.utc)

        upcoming = await fetcher.get_upcoming_events(hours_ahead=24)
        assert len(upcoming) == 2

    @pytest.mark.asyncio
    async def test_fetch_events_no_api_url(self):
        fetcher = EconomicCalendarFetcher()
        with patch("app.services.notification.economic_calendar_fetcher.settings") as mock_settings:
            mock_settings.ECONOMIC_CALENDAR_API_URL = ""
            mock_settings.ECONOMIC_CALENDAR_REFRESH_HOURS = 6
            events = await fetcher.fetch_events()
            assert events == []

    def test_parse_events_various_formats(self):
        fetcher = EconomicCalendarFetcher()

        # Test with standard format
        raw_data = [
            {
                "id": "1",
                "title": "NFP",
                "country": "US",
                "importance": 3,
                "dateUtc": "2026-01-01T12:00:00Z",
                "currency": "USD",
                "actual": "200K",
                "forecast": "180K",
                "previous": "175K",
            }
        ]
        events = fetcher._parse_events(raw_data)
        assert len(events) == 1
        assert events[0].title == "NFP"
        assert events[0].importance == 3

    def test_parse_events_string_importance(self):
        fetcher = EconomicCalendarFetcher()
        raw_data = [
            {
                "id": "2",
                "title": "CPI",
                "country": "US",
                "impact": "high",
                "dateUtc": "2026-01-01T12:00:00Z",
                "currency": "USD",
            }
        ]
        events = fetcher._parse_events(raw_data)
        assert len(events) == 1
        assert events[0].importance == 3

    def test_parse_events_nested_format(self):
        fetcher = EconomicCalendarFetcher()
        raw_data = {"events": [
            {
                "id": "3",
                "title": "GDP",
                "country": "JP",
                "importance": 2,
                "dateUtc": "2026-01-01T12:00:00Z",
                "currency": "JPY",
            }
        ]}
        events = fetcher._parse_events(raw_data)
        assert len(events) == 1

    def test_parse_events_invalid_skipped(self):
        fetcher = EconomicCalendarFetcher()
        raw_data = [
            {"id": "bad", "no_date": True},
            {
                "id": "ok",
                "title": "Good",
                "country": "US",
                "importance": 1,
                "dateUtc": "2026-01-01T12:00:00Z",
                "currency": "USD",
            },
        ]
        events = fetcher._parse_events(raw_data)
        assert len(events) == 1
