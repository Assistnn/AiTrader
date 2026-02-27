"""
bitbank data provider.

Reference: 02_データパイプライン Section 2-2, 16_実行エンジンとUI接続 Section 4
- Public API: Candlestick, Ticker
- Candlestick: GET /{pair}/candlestick/{candle_type}/{YYYYMMDD}
- candle_type: 1min, 5min, 15min, 30min, 1hour, 4hour, 8hour, 12hour, 1day
- Timestamps: UTC (bitbank returns UTC)
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import httpx

from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.pipeline.data_types import OHLCV, Spread, Ticker
from app.services.exchange.pair_normalizer import PairNormalizer

logger = logging.getLogger(__name__)

# Internal timeframe → bitbank candle_type mapping
TIMEFRAME_MAP: dict[str, str] = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1hour",
    "H4": "4hour",
    "D1": "1day",
}


class BitbankDataProvider(BaseDataProvider):
    """
    bitbank data provider.

    Reference: 02_データパイプライン Section 2-2, 16_実行エンジンとUI接続 Section 4
    Public REST API for OHLCV and ticker data.
    """

    PUBLIC_URL = "https://public.bitbank.cc"

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

    @staticmethod
    def to_candle_type(timeframe: str) -> str:
        """Convert internal timeframe to bitbank candle_type.

        Args:
            timeframe: Internal timeframe (M1, M5, M15, M30, H1, H4, D1)

        Returns:
            bitbank candle_type string

        Raises:
            ValueError: If timeframe is not supported
        """
        ct = TIMEFRAME_MAP.get(timeframe)
        if ct is None:
            raise ValueError(f"Unsupported timeframe for bitbank: {timeframe}")
        return ct

    @staticmethod
    def to_bitbank_pair(pair: str) -> str:
        """Convert internal pair to bitbank format (lowercase)."""
        return PairNormalizer.to_bitbank(pair)

    async def _public_get(self, path: str) -> dict:
        """Execute public GET request."""
        resp = await self._client.get(f"{self.PUBLIC_URL}{path}")
        data = resp.json()
        if data.get("success") != 1:
            code = data.get("data", {}).get("code", 0)
            raise RuntimeError(f"bitbank public API error: code={code}")
        return data

    # --- BaseDataProvider interface ---

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        """Get the latest N OHLCV bars. Reference: 16書§3-2"""
        candle_type = self.to_candle_type(timeframe)
        bb_pair = self.to_bitbank_pair(pair)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

        data = await self._public_get(
            f"/{bb_pair}/candlestick/{candle_type}/{date_str}",
        )
        candlesticks = data.get("data", {}).get("candlestick", [])

        bars: list[OHLCV] = []
        for cs in candlesticks:
            for ohlcv_item in cs.get("ohlcv", []):
                # bitbank: [open, high, low, close, volume, timestamp]
                bars.append(OHLCV(
                    timestamp=datetime.fromtimestamp(
                        int(ohlcv_item[5]) / 1000, tz=timezone.utc,
                    ),
                    open=float(ohlcv_item[0]),
                    high=float(ohlcv_item[1]),
                    low=float(ohlcv_item[2]),
                    close=float(ohlcv_item[3]),
                    volume=float(ohlcv_item[4]),
                ))

        bars.sort(key=lambda x: x.timestamp)
        return bars[-limit:] if len(bars) > limit else bars

    async def get_ticker(self, pair: str) -> Ticker:
        """Get the latest ticker. Reference: 16書§3-2"""
        bb_pair = self.to_bitbank_pair(pair)
        data = await self._public_get(f"/{bb_pair}/ticker")
        t = data["data"]
        return Ticker(
            timestamp=datetime.fromtimestamp(
                int(t["timestamp"]) / 1000, tz=timezone.utc,
            ),
            bid=float(t["buy"]),
            ask=float(t["sell"]),
            last=float(t["last"]),
            volume=float(t.get("vol", 0)),
        )

    async def get_spread(self, pair: str) -> Spread:
        """Get the latest spread."""
        ticker = await self.get_ticker(pair)
        return Spread(
            timestamp=ticker.timestamp,
            bid=ticker.bid,
            ask=ticker.ask,
            spread_raw=ticker.ask - ticker.bid,
            spread_pips=ticker.ask - ticker.bid,  # Crypto: raw spread (no pip conversion)
        )

    async def subscribe_ticks(
        self,
        pairs: list[str],
        callback: Callable[[str, Ticker], Awaitable[None]],
    ) -> None:
        """Subscribe to tick stream.

        Note: bitbank WebSocket (Socket.IO) integration is handled by
        MarketDataFeed (16書§4-3). This stores the callback for delivery.
        """
        self._subscribed_pairs = pairs
        self._tick_callbacks.append(callback)
        logger.info("BitbankDataProvider: subscribed to ticks for %s", pairs)

    async def get_historical_ohlcv(
        self, pair: str, timeframe: str, start: datetime, end: datetime,
    ) -> list[OHLCV]:
        """Get historical OHLCV for a given period.

        bitbank candlestick API returns data by date, so we iterate over each date.
        """
        candle_type = self.to_candle_type(timeframe)
        bb_pair = self.to_bitbank_pair(pair)

        all_bars: list[OHLCV] = []
        current = start.date()
        end_date = end.date()

        while current <= end_date:
            date_str = current.strftime("%Y%m%d")
            try:
                data = await self._public_get(
                    f"/{bb_pair}/candlestick/{candle_type}/{date_str}",
                )
                candlesticks = data.get("data", {}).get("candlestick", [])
                for cs in candlesticks:
                    for ohlcv_item in cs.get("ohlcv", []):
                        ts = datetime.fromtimestamp(
                            int(ohlcv_item[5]) / 1000, tz=timezone.utc,
                        )
                        if start <= ts <= end:
                            all_bars.append(OHLCV(
                                timestamp=ts,
                                open=float(ohlcv_item[0]),
                                high=float(ohlcv_item[1]),
                                low=float(ohlcv_item[2]),
                                close=float(ohlcv_item[3]),
                                volume=float(ohlcv_item[4]),
                            ))
            except RuntimeError:
                logger.warning("Failed to fetch candlestick for %s on %s", pair, date_str)
            current += timedelta(days=1)

        all_bars.sort(key=lambda x: x.timestamp)
        return all_bars

    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all streams."""
        self._tick_callbacks.clear()
        self._subscribed_pairs.clear()
        logger.info("BitbankDataProvider: unsubscribed from all ticks")
