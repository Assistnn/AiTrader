"""
Exchange layer shared types.

Reference: 06_取引所抽象化 Section 2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class Order:
    """Order representation. Reference: Section 2"""

    order_id: str
    client_order_id: str  # duplicate order prevention
    pair: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: float | None  # for LIMIT/STOP
    status: OrderStatus
    filled_amount: float = 0.0
    filled_price: float | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExchangePosition:
    """Exchange position representation. Reference: Section 2"""

    position_id: str
    pair: str
    side: OrderSide
    amount: float
    entry_price: float
    unrealized_pnl: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Balance:
    """Account balance. Reference: Section 2"""

    total: float
    available: float
    margin_used: float = 0.0
    unrealized_pnl: float = 0.0
    currency: str = "JPY"


@dataclass
class PositionSizeResult:
    """Position sizing result. Reference: Section 4-2"""

    lot_size: float
    rr_ratio: float
    risk_amount: float  # actual risk (JPY)
    risk_pct: float  # actual risk %
    _debug: dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Execution result from ExecutionEngine."""

    order: Order | None = None
    size_result: PositionSizeResult | None = None
    success: bool = True
    error: str | None = None
    tp_order_id: str | None = None  # OCO TP order ID (§9-2)
    sl_order_id: str | None = None  # OCO SL order ID (§9-2)
    _debug: dict = field(default_factory=dict)
