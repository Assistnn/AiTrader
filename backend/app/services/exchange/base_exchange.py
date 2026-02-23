"""
BaseExchange abstract interface.

Reference: 06_取引所抽象化 Section 2
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.pipeline.data_types import OHLCV, Ticker
from app.services.exchange.exchange_types import (
    Balance,
    ExchangePosition,
    Order,
    OrderSide,
    OrderType,
)


class BaseExchange(ABC):
    """Exchange operations common interface. Reference: Section 2"""

    @abstractmethod
    async def get_ticker(self, pair: str) -> Ticker:
        """Get latest ticker."""
        ...

    @abstractmethod
    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        """Get OHLCV bar data."""
        ...

    @abstractmethod
    async def place_order(
        self,
        pair: str,
        side: OrderSide,
        amount: float,
        order_type: OrderType,
        price: float | None = None,
        client_order_id: str | None = None,
        tp_price: float | None = None,
        sl_price: float | None = None,
    ) -> Order:
        """Place an order."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """Get order status."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[ExchangePosition]:
        """Get open positions."""
        ...

    @abstractmethod
    async def close_position(
        self, position_id: str, amount: float | None = None
    ) -> Order:
        """Close a position (partial close when amount specified)."""
        ...

    @abstractmethod
    async def get_balance(self) -> Balance:
        """Get account balance."""
        ...

    @abstractmethod
    async def modify_order(
        self, order_id: str, price: float | None = None
    ) -> Order:
        """Modify an order (e.g. trailing stop SL adjustment)."""
        ...
