"""
BaseDataProvider ABC and DataProvider integration.

Reference: 02_データパイプライン Section 2-3
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime

from app.services.pipeline.data_types import OHLCV, Spread, Ticker


class BaseDataProvider(ABC):
    """Abstract data source interface. Reference: Section 2-3"""

    @abstractmethod
    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        """Get the latest N OHLCV bars."""

    @abstractmethod
    async def get_ticker(self, pair: str) -> Ticker:
        """Get the latest ticker."""

    @abstractmethod
    async def get_spread(self, pair: str) -> Spread:
        """Get the latest spread."""

    @abstractmethod
    async def subscribe_ticks(
        self,
        pairs: list[str],
        callback: Callable[[str, Ticker], Awaitable[None]],
    ) -> None:
        """Subscribe to tick stream (WebSocket)."""

    @abstractmethod
    async def get_historical_ohlcv(
        self, pair: str, timeframe: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        """Get historical OHLCV for a given period."""

    @abstractmethod
    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all streams."""
