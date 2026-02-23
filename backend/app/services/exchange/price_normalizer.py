"""
PriceNormalizer: FX (pip) / Crypto (decimal) price unit normalization.

Reference: 06_取引所抽象化 Section 3
"""

from __future__ import annotations


class PriceNormalizer:
    """Price unit normalization. Reference: Section 3"""

    # Pip definition table. Reference: Section 3-2
    PIP_DEFINITIONS: dict[str, dict] = {
        # FX
        "USD_JPY": {"pip_size": 0.01, "pip_digits": 2, "pip_value_per_lot": 100},
        "EUR_JPY": {"pip_size": 0.01, "pip_digits": 2, "pip_value_per_lot": 100},
        "GBP_JPY": {"pip_size": 0.01, "pip_digits": 2, "pip_value_per_lot": 100},
        "AUD_JPY": {"pip_size": 0.01, "pip_digits": 2, "pip_value_per_lot": 100},
        "NZD_JPY": {"pip_size": 0.01, "pip_digits": 2, "pip_value_per_lot": 100},
        "CHF_JPY": {"pip_size": 0.01, "pip_digits": 2, "pip_value_per_lot": 100},
        "CAD_JPY": {"pip_size": 0.01, "pip_digits": 2, "pip_value_per_lot": 100},
        "EUR_USD": {"pip_size": 0.0001, "pip_digits": 4, "pip_value_per_lot": 1000},
        "GBP_USD": {"pip_size": 0.0001, "pip_digits": 4, "pip_value_per_lot": 1000},
        "AUD_USD": {"pip_size": 0.0001, "pip_digits": 4, "pip_value_per_lot": 1000},
        "NZD_USD": {"pip_size": 0.0001, "pip_digits": 4, "pip_value_per_lot": 1000},
        # Crypto (Phase 4)
        "BTC_JPY": {"pip_size": 1, "pip_digits": 0, "pip_value_per_lot": 1},
        "ETH_JPY": {"pip_size": 1, "pip_digits": 0, "pip_value_per_lot": 1},
        "XRP_JPY": {"pip_size": 0.001, "pip_digits": 3, "pip_value_per_lot": 1000},
    }

    def get_pip_definition(self, pair: str) -> dict:
        """Get pip definition for a pair. Raises KeyError for unknown pairs."""
        return self.PIP_DEFINITIONS[pair]

    def to_pips(self, price_diff: float, pair: str) -> float:
        """Convert price difference to pips. Reference: Section 3-3"""
        pip_size = self.PIP_DEFINITIONS[pair]["pip_size"]
        return price_diff / pip_size

    def from_pips(self, pips: float, pair: str) -> float:
        """Convert pips to price difference. Reference: Section 3-3"""
        pip_size = self.PIP_DEFINITIONS[pair]["pip_size"]
        return pips * pip_size

    def pip_value(self, pair: str, lot_size: float) -> float:
        """Calculate 1 pip P&L in account currency. Reference: Section 3-3"""
        base_pip_value = self.PIP_DEFINITIONS[pair]["pip_value_per_lot"]
        return base_pip_value * lot_size

    def round_price(self, price: float, pair: str) -> float:
        """Round price to exchange minimum unit. Reference: Section 3-3"""
        digits = self.PIP_DEFINITIONS[pair]["pip_digits"]
        return round(price, digits)

    def calculate_pnl(
        self, entry_price: float, exit_price: float,
        side: str, amount: float, pair: str,
    ) -> float:
        """Calculate P&L in account currency. Reference: Section 3-3"""
        price_diff = exit_price - entry_price
        if side == "SELL":
            price_diff = -price_diff
        pips = self.to_pips(price_diff, pair)
        return pips * self.pip_value(pair, amount)
