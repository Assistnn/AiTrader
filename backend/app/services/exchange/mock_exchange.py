"""
MockExchange: test/simulation/backtest virtual exchange.

Reference: 06_取引所抽象化 Section 7
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.backtest.simulation_clock import SimulationClock

from app.services.pipeline.data_types import OHLCV, Ticker
from app.services.exchange.base_exchange import BaseExchange
from app.services.exchange.exchange_types import (
    Balance,
    ExchangePosition,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)


class MockExchange(BaseExchange):
    """
    Test / simulation / backtest virtual exchange.

    Reference: Section 7
    """

    def __init__(
        self,
        initial_balance: float = 1_000_000.0,
        clock: SimulationClock | None = None,
    ):
        self.balance_total = initial_balance
        self.balance_available = initial_balance
        self.positions: list[ExchangePosition] = []
        self.orders: list[Order] = []
        self.current_prices: dict[str, Ticker] = {}
        self.trade_history: list[dict] = []
        self._clock = clock

        # Simulation settings
        self.slippage_pips: float = 0.0
        self.spread_pips: float = 0.5

    def _get_now(self) -> datetime:
        """現在時刻を返す. clock設定時はシミュレーション時刻を使用."""
        if self._clock is not None:
            return self._clock.now()
        return datetime.now(timezone.utc)

    def set_price(self, pair: str, bid: float, ask: float) -> None:
        """Set current price for simulation."""
        self.current_prices[pair] = Ticker(
            timestamp=self._get_now(),
            bid=bid, ask=ask,
            last=(bid + ask) / 2,
            volume=0.0,
        )

    async def get_ticker(self, pair: str) -> Ticker:
        if pair in self.current_prices:
            return self.current_prices[pair]
        # Default price
        return Ticker(
            timestamp=self._get_now(),
            bid=100.0, ask=100.02, last=100.01, volume=0.0,
        )

    async def get_ohlcv(self, pair: str, timeframe: str, limit: int) -> list[OHLCV]:
        return []  # MockExchange doesn't provide historical data

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
        """Place a virtual order (immediate fill for MARKET). Reference: Section 7-2"""
        now = self._get_now()
        order_id = str(uuid.uuid4())
        coid = client_order_id or str(uuid.uuid4())

        ticker = self.current_prices.get(pair)
        if ticker is None:
            return Order(
                order_id=order_id, client_order_id=coid, pair=pair,
                side=side, order_type=order_type, amount=amount,
                price=price, status=OrderStatus.REJECTED,
                created_at=now, updated_at=now,
            )

        if order_type == OrderType.MARKET:
            # Immediate fill with slippage
            fill_price = self._apply_slippage(
                ticker.ask if side == OrderSide.BUY else ticker.bid,
                side, pair,
            )

            order = Order(
                order_id=order_id, client_order_id=coid, pair=pair,
                side=side, order_type=order_type, amount=amount,
                price=None, status=OrderStatus.FILLED,
                filled_amount=amount, filled_price=fill_price,
                created_at=now, updated_at=now,
            )
            self.orders.append(order)

            # Create position
            pos = ExchangePosition(
                position_id=str(uuid.uuid4()),
                pair=pair, side=side,
                amount=amount, entry_price=fill_price,
                created_at=now,
            )
            self.positions.append(pos)

            self.trade_history.append({
                "type": "entry", "order_id": order_id,
                "pair": pair, "side": side.value,
                "amount": amount, "price": fill_price,
                "timestamp": now.isoformat(),
            })
            return order

        # LIMIT/STOP orders stored as pending
        order = Order(
            order_id=order_id, client_order_id=coid, pair=pair,
            side=side, order_type=order_type, amount=amount,
            price=price, status=OrderStatus.PENDING,
            created_at=now, updated_at=now,
        )
        self.orders.append(order)
        return order

    async def cancel_order(self, order_id: str) -> bool:
        for order in self.orders:
            if order.order_id == order_id and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                order.updated_at = self._get_now()
                return True
        return False

    async def get_order_status(self, order_id: str) -> Order:
        for order in self.orders:
            if order.order_id == order_id:
                return order
        raise ValueError(f"Order not found: {order_id}")

    async def get_positions(self) -> list[ExchangePosition]:
        return list(self.positions)

    async def close_position(
        self, position_id: str, amount: float | None = None,
    ) -> Order:
        """Close position (partial when amount specified). Reference: Section 7-2"""
        now = self._get_now()

        pos = None
        for p in self.positions:
            if p.position_id == position_id:
                pos = p
                break
        if pos is None:
            raise ValueError(f"Position not found: {position_id}")

        close_amount = amount if amount is not None else pos.amount
        close_amount = min(close_amount, pos.amount)

        # Get exit price
        ticker = self.current_prices.get(pos.pair)
        if ticker is None:
            raise ValueError(f"No price for {pos.pair}")

        exit_side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY
        exit_price = ticker.bid if exit_side == OrderSide.SELL else ticker.ask

        order_id = str(uuid.uuid4())
        order = Order(
            order_id=order_id, client_order_id=str(uuid.uuid4()),
            pair=pos.pair, side=exit_side, order_type=OrderType.MARKET,
            amount=close_amount, price=None,
            status=OrderStatus.FILLED,
            filled_amount=close_amount, filled_price=exit_price,
            created_at=now, updated_at=now,
        )

        # Update or remove position
        if close_amount >= pos.amount:
            self.positions.remove(pos)
        else:
            pos.amount -= close_amount

        self.trade_history.append({
            "type": "exit", "order_id": order_id,
            "pair": pos.pair, "side": exit_side.value,
            "amount": close_amount, "price": exit_price,
            "entry_price": pos.entry_price,
            "timestamp": now.isoformat(),
        })

        return order

    async def get_balance(self) -> Balance:
        unrealized = sum(p.unrealized_pnl for p in self.positions)
        return Balance(
            total=self.balance_total + unrealized,
            available=self.balance_available,
            unrealized_pnl=unrealized,
            currency="JPY",
        )

    async def modify_order(self, order_id: str, price: float | None = None) -> Order:
        for order in self.orders:
            if order.order_id == order_id and order.status == OrderStatus.PENDING:
                if price is not None:
                    order.price = price
                order.updated_at = self._get_now()
                return order
        raise ValueError(f"Order not found or not modifiable: {order_id}")

    def _apply_slippage(self, base_price: float, side: OrderSide, pair: str) -> float:
        """Apply slippage to price."""
        if self.slippage_pips == 0:
            return base_price
        # Approximate: 0.01 per pip for JPY pairs
        slip = self.slippage_pips * 0.01
        if side == OrderSide.BUY:
            return base_price + slip  # worse for buyer
        return base_price - slip  # worse for seller
