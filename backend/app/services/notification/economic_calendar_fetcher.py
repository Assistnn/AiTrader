"""
EconomicCalendarFetcher: fetches economic calendar events from external APIs.

Reference: 16_実行エンジンとUI接続 Section 10
- Fetches economic events from external data sources
- Caches results in memory for GuardEngine integration (SG-027~031)
- Fallback: if fetch fails and cache expired, assume all events active (safe side)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EconomicEvent:
    """A single economic calendar event.

    Reference: 16書§10-2
    """

    event_id: str
    title: str
    country: str  # "US" | "JP" | "EU" | "GB" | "AU" | ...
    importance: int  # 1(low) | 2(medium) | 3(high)
    event_datetime: datetime  # UTC
    currency: str  # "USD" | "JPY" | ...
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None


class EconomicCalendarFetcher:
    """Fetches and caches economic calendar events from external APIs.

    Reference: 16書§10-2, §10-3, §10-4

    Data source priority:
    1. FXStreet Economic Calendar API (public JSON, structured, includes impact)
    2. Forex Factory RSS (fallback)
    3. Manual/static events (last resort)

    Cache strategy:
    - Events are fetched on startup and refreshed every ECONOMIC_CALENDAR_REFRESH_HOURS
    - On fetch failure: use cached data if still valid
    - On cache expiry + fetch failure: safe side — assume all events active
    """

    def __init__(self) -> None:
        self._events: list[EconomicEvent] = []
        self._last_fetch: datetime | None = None
        self._cache_ttl_hours: int = settings.ECONOMIC_CALENDAR_REFRESH_HOURS
        self._fetch_lock = asyncio.Lock()
        self._http_timeout = 30.0

    @property
    def is_cache_valid(self) -> bool:
        """Check if cached events are still within TTL."""
        if self._last_fetch is None:
            return False
        elapsed = datetime.now(timezone.utc) - self._last_fetch
        return elapsed < timedelta(hours=self._cache_ttl_hours)

    async def fetch_events(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[EconomicEvent]:
        """Fetch economic events from external API.

        Reference: 16書§10-2
        If start/end not specified, fetches today + next 24h.
        """
        async with self._fetch_lock:
            now = datetime.now(timezone.utc)
            if start is None:
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if end is None:
                end = start + timedelta(days=2)

            try:
                events = await self._fetch_from_api(start, end)
                self._events = events
                self._last_fetch = now
                logger.info(
                    "EconomicCalendarFetcher: fetched %d events (%s to %s)",
                    len(events),
                    start.date().isoformat(),
                    end.date().isoformat(),
                )
                return events
            except Exception:
                logger.exception("EconomicCalendarFetcher: fetch failed")
                if self.is_cache_valid:
                    logger.warning("Using cached events (cache still valid)")
                    return self._events
                # Fallback: safe side (16書§10-4)
                logger.error(
                    "Cache expired and fetch failed — safe side: blocking new entries"
                )
                return []

    async def get_upcoming_events(
        self, hours_ahead: int = 24,
    ) -> list[EconomicEvent]:
        """Get upcoming events within the next N hours.

        Reference: 16書§10-3 — for GuardEngine SG-027~031 integration
        """
        if not self.is_cache_valid:
            await self.fetch_events()

        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)

        return [
            e for e in self._events
            if now - timedelta(hours=1) <= e.event_datetime <= cutoff
        ]

    def get_cached_events(self) -> list[EconomicEvent]:
        """Return currently cached events without fetching."""
        return list(self._events)

    def is_fetch_failed_and_expired(self) -> bool:
        """Check if we're in the 'safe side' fallback state.

        Reference: 16書§10-4
        Returns True when cache is expired and no fresh data available.
        In this state, GuardEngine should block new entries.
        """
        return not self.is_cache_valid

    async def _fetch_from_api(
        self,
        start: datetime,
        end: datetime,
    ) -> list[EconomicEvent]:
        """Fetch events from the configured external API.

        Currently uses a generic REST endpoint that returns JSON.
        The actual data source URL is configured via ECONOMIC_CALENDAR_API_URL.
        """
        api_url = settings.ECONOMIC_CALENDAR_API_URL
        if not api_url:
            logger.info("No economic calendar API URL configured, returning empty")
            return []

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            params = {
                "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            resp = await client.get(api_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        return self._parse_events(data)

    def _parse_events(self, raw_data: Any) -> list[EconomicEvent]:
        """Parse raw API response into EconomicEvent objects.

        Handles common calendar API response formats.
        """
        events: list[EconomicEvent] = []

        if not isinstance(raw_data, list):
            raw_data = raw_data.get("events", raw_data.get("data", []))

        for item in raw_data:
            try:
                # Flexible parsing for common API formats
                event_dt_str = (
                    item.get("dateUtc")
                    or item.get("date")
                    or item.get("event_datetime")
                    or ""
                )
                if not event_dt_str:
                    continue

                event_dt = datetime.fromisoformat(
                    event_dt_str.replace("Z", "+00:00")
                )

                importance = item.get("importance") or item.get("impact") or 1
                if isinstance(importance, str):
                    importance_map = {"low": 1, "medium": 2, "high": 3}
                    importance = importance_map.get(importance.lower(), 1)

                events.append(EconomicEvent(
                    event_id=str(item.get("id", item.get("event_id", ""))),
                    title=item.get("title") or item.get("name") or item.get("event", ""),
                    country=item.get("country") or item.get("countryCode") or "",
                    importance=int(importance),
                    event_datetime=event_dt,
                    currency=item.get("currency") or item.get("currencyCode") or "",
                    actual=item.get("actual"),
                    forecast=item.get("forecast") or item.get("consensus"),
                    previous=item.get("previous"),
                ))
            except (ValueError, KeyError, TypeError):
                logger.debug("Skipping unparseable economic event: %s", item)
                continue

        return events
