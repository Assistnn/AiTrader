"""
PositionSizer: risk-based position sizing (bypass-proof).

Reference: 06_取引所抽象化 Section 4
"""

from __future__ import annotations

from app.services.exchange.exchange_types import PositionSizeResult
from app.services.exchange.price_normalizer import PriceNormalizer


class PositionSizer:
    """
    Position size calculation.

    Reference: Section 4
    Called on EVERY order path, bypass-proof (survivability design).
    """

    def __init__(self, price_normalizer: PriceNormalizer):
        self.normalizer = price_normalizer

    def calculate(
        self,
        pair: str,
        capital: float,
        risk_per_trade_pct: float,
        sl_pips: float,
        tp_pips: float,
        min_lot: float,
        max_lot: float,
    ) -> PositionSizeResult:
        """
        Calculate position size. Reference: Section 4-2

        Args:
            pair: currency pair
            capital: account balance (JPY)
            risk_per_trade_pct: risk per trade (%)
            sl_pips: stop-loss distance (pips)
            tp_pips: take-profit distance (pips)
            min_lot: exchange minimum lot
            max_lot: user/exchange max lot
        """
        # 1. Risk amount
        risk_amount = capital * (risk_per_trade_pct / 100)

        # 2. Pip value per lot
        pip_value_per_lot = self.normalizer.PIP_DEFINITIONS[pair]["pip_value_per_lot"]

        # 3. Raw lot calculation
        if sl_pips <= 0 or pip_value_per_lot <= 0:
            raw_lot = min_lot  # safety fallback
        else:
            raw_lot = risk_amount / (sl_pips * pip_value_per_lot)

        # 4. Clip to min/max
        lot_size = max(min_lot, min(raw_lot, max_lot))

        # 5. RR ratio
        rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0.0

        # 6. Actual risk after clipping
        actual_risk = lot_size * sl_pips * pip_value_per_lot
        actual_risk_pct = (actual_risk / capital * 100) if capital > 0 else 0.0

        return PositionSizeResult(
            lot_size=lot_size,
            rr_ratio=rr_ratio,
            risk_amount=actual_risk,
            risk_pct=actual_risk_pct,
            _debug={
                "capital": capital,
                "risk_per_trade_pct": risk_per_trade_pct,
                "target_risk_amount": risk_amount,
                "sl_pips": sl_pips,
                "tp_pips": tp_pips,
                "pip_value_per_lot": pip_value_per_lot,
                "raw_lot": raw_lot,
                "clipped_lot": lot_size,
                "min_lot": min_lot,
                "max_lot": max_lot,
                "rr_ratio": rr_ratio,
                "actual_risk_amount": actual_risk,
                "actual_risk_pct": actual_risk_pct,
            },
        )
