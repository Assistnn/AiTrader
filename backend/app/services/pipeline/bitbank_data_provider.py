"""
bitbank data provider (stub).

Reference: 02_データパイプライン Section 2-2
- Public API: Candlestick, Ticker
- Candlestick: GET /{pair}/candlestick/{candle_type}/{YYYYMMDD}
- candle_type: 1min, 5min, 15min, 30min, 1hour, 4hour, 8hour, 12hour, 1day
- Timestamps: UTC (bitbank returns UTC)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.pipeline.data_types import OHLCV, Spread, Ticker
from app.services.exchange.pair_normalizer import PairNormalizer


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

    Reference: 02_データパイプライン Section 2-2
    Public REST API for OHLCV and ticker data.
    """

    PUBLIC_URL = "https://public.bitbank.cc"

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

    # --- BaseDataProvider interface (stubs for Phase 4) ---

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        raise NotImplementedError("BitbankDataProvider.get_ohlcv: requires API integration")

    async def get_ticker(self, pair: str) -> Ticker:
        raise NotImplementedError("BitbankDataProvider.get_ticker: requires API integration")

    async def get_spread(self, pair: str) -> Spread:
        raise NotImplementedError("BitbankDataProvider.get_spread: requires API integration")

    async def subscribe_ticks(
        self,
        pairs: list[str],
        callback: Callable[[str, Ticker], Awaitable[None]],
    ) -> None:
        raise NotImplementedError("BitbankDataProvider.subscribe_ticks: requires API integration")

    async def get_historical_ohlcv(
        self, pair: str, timeframe: str, start: datetime, end: datetime,
    ) -> list[OHLCV]:
        raise NotImplementedError(
            "BitbankDataProvider.get_historical_ohlcv: requires API integration"
        )

    async def unsubscribe_all(self) -> None:
        raise NotImplementedError("BitbankDataProvider.unsubscribe_all: requires API integration")
