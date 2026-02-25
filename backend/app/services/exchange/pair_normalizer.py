"""
PairNormalizer: currency pair name normalization between exchanges and internal format.

Reference: 06_取引所抽象化 Section 6
Internal format: "BTC_JPY" (uppercase, underscore-separated)
bitbank format: "btc_jpy" (lowercase, underscore-separated)
GMO FX format: "USD_JPY" (already matches internal)
"""

from __future__ import annotations


class PairNormalizer:
    """Normalize currency pair names between exchange-specific and internal formats."""

    # Crypto pairs (bitbank)
    CRYPTO_PAIRS: set[str] = {
        "BTC_JPY", "ETH_JPY", "XRP_JPY",
        "LTC_JPY", "BCH_JPY", "MONA_JPY",
    }

    # FX pairs (GMO Coin)
    FX_PAIRS: set[str] = {
        "USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY",
        "NZD_JPY", "CHF_JPY", "CAD_JPY",
        "EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD",
    }

    @staticmethod
    def to_internal(exchange_pair: str) -> str:
        """Convert exchange-specific pair name to internal format.

        bitbank "btc_jpy" → "BTC_JPY"
        GMO "USD_JPY" → "USD_JPY" (no change)
        """
        return exchange_pair.upper()

    @staticmethod
    def to_bitbank(internal_pair: str) -> str:
        """Convert internal pair name to bitbank format.

        "BTC_JPY" → "btc_jpy"
        """
        return internal_pair.lower()

    @staticmethod
    def to_gmo(internal_pair: str) -> str:
        """Convert internal pair name to GMO Coin format.

        "USD_JPY" → "USD_JPY" (no change for GMO)
        """
        return internal_pair

    @classmethod
    def is_crypto(cls, pair: str) -> bool:
        """Check if the pair is a crypto pair."""
        return pair.upper() in cls.CRYPTO_PAIRS

    @classmethod
    def is_fx(cls, pair: str) -> bool:
        """Check if the pair is an FX pair."""
        return pair.upper() in cls.FX_PAIRS
