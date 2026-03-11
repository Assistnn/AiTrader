"""
GMO Coin FX data provider.

Reference: 02_データパイプライン Section 2-2, 16_実行エンジンとUI接続 Section 4
- Public API: KLines (OHLCV), Ticker
- KLines: GET /v1/klines?symbol={pair}&interval={tf}&date={YYYYMMDD}
- Ticker: GET /v1/ticker?symbol={pair}
- Timestamps: UTC
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import httpx

from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.pipeline.data_types import OHLCV, Spread, Ticker

logger = logging.getLogger(__name__)

# Internal timeframe → GMO interval mapping
_TIMEFRAME_MAP: dict[str, str] = {
    "M1": "1min",
    "M5": "5min",
    "M10": "10min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1hour",
    "H4": "4hour",
    "H8": "8hour",
    "D1": "1day",
}


class GmoFxDataProvider(BaseDataProvider):
    """
    GMO Coin FX data provider.

    Reference: 02_データパイプライン Section 2-2, 16_実行エンジンとUI接続 Section 4
    Public REST API for OHLCV and ticker data.
    """

    PUBLIC_URL = "https://forex-api.coin.z.com/public"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        self._tick_callbacks: list[Callable[[str, Ticker], Awaitable[None]]] = []
        self._subscribed_pairs: list[str] = []

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _public_get(self, path: str, params: dict | None = None) -> dict:
        """Execute public GET request."""
        resp = await self._client.get(f"{self.PUBLIC_URL}{path}", params=params)
        data = resp.json()
        if data.get("status") != 0:
            messages = data.get("messages", [{"message_string": "Unknown error"}])
            msg = messages[0].get("message_string", "Unknown error") if messages else "Unknown error"
            raise RuntimeError(f"GMO public API error: {msg}")
        return data

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        """Get the latest N OHLCV bars. Reference: 16書§3-1"""
        interval = _TIMEFRAME_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"Unsupported timeframe for GMO: {timeframe}")

        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        data = await self._public_get(
            "/v1/klines",
            params={"symbol": pair, "priceType": "BID", "interval": interval, "date": date_str},
        )
        bars_raw = data.get("data", [])

        bars: list[OHLCV] = []
        for b in bars_raw:
            bars.append(OHLCV(
                timestamp=datetime.fromtimestamp(
                    int(b["openTime"]) / 1000, tz=timezone.utc,
                ),
                open=float(b["open"]),
                high=float(b["high"]),
                low=float(b["low"]),
                close=float(b["close"]),
                volume=float(b.get("volume", 0)),
            ))

        bars.sort(key=lambda x: x.timestamp)
        return bars[-limit:] if len(bars) > limit else bars

    async def get_ticker(self, pair: str) -> Ticker:
        """Get the latest ticker. Reference: 16書§3-1"""
        data = await self._public_get("/v1/ticker")
        items = data.get("data", [])
        item = next((i for i in items if i.get("symbol") == pair), items[0] if items else None)
        if item is None:
            raise RuntimeError(f"Ticker not found for {pair}")
        bid = float(item["bid"])
        ask = float(item["ask"])
        return Ticker(
            timestamp=datetime.now(timezone.utc),
            bid=bid,
            ask=ask,
            last=float(item.get("last", (bid + ask) / 2)),
            volume=float(item.get("volume", 0)),
        )

    async def get_spread(self, pair: str) -> Spread:
        """Get the latest spread."""
        ticker = await self.get_ticker(pair)
        return Spread(
            timestamp=ticker.timestamp,
            bid=ticker.bid,
            ask=ticker.ask,
            spread_raw=ticker.ask - ticker.bid,
            spread_pips=(ticker.ask - ticker.bid) * (100 if "JPY" in pair else 10000),
        )

    async def subscribe_ticks(
        self,
        pairs: list[str],
        callback: Callable[[str, Ticker], Awaitable[None]],
    ) -> None:
        """Subscribe to tick stream.

        Note: GMO Coin WebSocket integration is handled by MarketDataFeed (16書§4-3).
        This stores the callback for use when MarketDataFeed delivers ticks.
        """
        self._subscribed_pairs = pairs
        self._tick_callbacks.append(callback)
        logger.info("GmoFxDataProvider: subscribed to ticks for %s", pairs)

    async def get_historical_ohlcv(
        self, pair: str, timeframe: str, start: datetime, end: datetime,
    ) -> list[OHLCV]:
        """Get historical OHLCV for a given period.

        GMO klines API returns data by date, so we iterate over each date in range.
        """
        interval = _TIMEFRAME_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"Unsupported timeframe for GMO: {timeframe}")

        all_bars: list[OHLCV] = []
        current = start.date()
        end_date = end.date()

        while current <= end_date:
            date_str = current.strftime("%Y%m%d")
            try:
                data = await self._public_get(
                    "/v1/klines",
                    params={"symbol": pair, "priceType": "BID", "interval": interval, "date": date_str},
                )
                bars_raw = data.get("data", [])
                for b in bars_raw:
                    ts = datetime.fromtimestamp(
                        int(b["openTime"]) / 1000, tz=timezone.utc,
                    )
                    if start <= ts <= end:
                        all_bars.append(OHLCV(
                            timestamp=ts,
                            open=float(b["open"]),
                            high=float(b["high"]),
                            low=float(b["low"]),
                            close=float(b["close"]),
                            volume=float(b.get("volume", 0)),
                        ))
            except RuntimeError:
                logger.warning("Failed to fetch klines for %s on %s", pair, date_str)
            current += timedelta(days=1)

        all_bars.sort(key=lambda x: x.timestamp)
        return all_bars

    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all streams."""
        self._tick_callbacks.clear()
        self._subscribed_pairs.clear()
        logger.info("GmoFxDataProvider: unsubscribed from all ticks")
