"""Tests for trader schema validation (trade_type / symbols consistency)."""

import pytest
from pydantic import ValidationError

from app.schemas.trader import TraderCreateRequest, TraderUpdateRequest


class TestTraderCreateValidation:
    """TraderCreateRequest のバリデーションテスト."""

    def test_fx_with_valid_symbols(self):
        req = TraderCreateRequest(
            traderName="Test FX",
            tradeType="FX",
            symbols=["USD_JPY", "EUR_JPY"],
            capitalJpy=1_000_000,
            orderUnitLots=1,
        )
        assert req.trade_type == "FX"
        assert req.symbols == ["USD_JPY", "EUR_JPY"]

    def test_crypto_with_valid_symbols(self):
        req = TraderCreateRequest(
            traderName="Test Crypto",
            tradeType="Crypto",
            symbols=["BTC_JPY", "ETH_JPY"],
            capitalJpy=500_000,
            orderUnitLots=0.01,
        )
        assert req.trade_type == "Crypto"
        assert req.symbols == ["BTC_JPY", "ETH_JPY"]

    def test_fx_lowercase_normalized(self):
        """'fx' (小文字) は 'FX' に正規化される."""
        req = TraderCreateRequest(
            traderName="Test",
            tradeType="fx",
            symbols=["USD_JPY"],
            capitalJpy=1_000_000,
            orderUnitLots=1,
        )
        assert req.trade_type == "FX"

    def test_crypto_lowercase_normalized(self):
        """'crypto' (小文字) は 'Crypto' に正規化される."""
        req = TraderCreateRequest(
            traderName="Test",
            tradeType="crypto",
            symbols=["BTC_JPY"],
            capitalJpy=500_000,
            orderUnitLots=0.01,
        )
        assert req.trade_type == "Crypto"

    def test_fx_with_crypto_symbol_rejected(self):
        """FX トレーダーに BTC_JPY を含めるとエラー."""
        with pytest.raises(ValidationError, match="Invalid symbols for FX"):
            TraderCreateRequest(
                traderName="Bad",
                tradeType="FX",
                symbols=["USD_JPY", "BTC_JPY"],
                capitalJpy=1_000_000,
                orderUnitLots=1,
            )

    def test_crypto_with_fx_symbol_rejected(self):
        """Crypto トレーダーに USD_JPY を含めるとエラー."""
        with pytest.raises(ValidationError, match="Invalid symbols for Crypto"):
            TraderCreateRequest(
                traderName="Bad",
                tradeType="Crypto",
                symbols=["USD_JPY"],
                capitalJpy=500_000,
                orderUnitLots=0.01,
            )

    def test_empty_symbols_rejected(self):
        """symbols が空リストの場合エラー."""
        with pytest.raises(ValidationError, match="at least one pair"):
            TraderCreateRequest(
                traderName="Bad",
                tradeType="FX",
                symbols=[],
                capitalJpy=1_000_000,
                orderUnitLots=1,
            )

    def test_all_fx_pairs_accepted(self):
        """全11 FX ペアが受理される."""
        all_fx = [
            "USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY",
            "CHF_JPY", "CAD_JPY", "EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD",
        ]
        req = TraderCreateRequest(
            traderName="All FX",
            tradeType="FX",
            symbols=all_fx,
            capitalJpy=10_000_000,
            orderUnitLots=10,
        )
        assert len(req.symbols) == 11

    def test_all_crypto_pairs_accepted(self):
        """全6 Crypto ペアが受理される."""
        all_crypto = [
            "BTC_JPY", "ETH_JPY", "XRP_JPY",
            "LTC_JPY", "BCH_JPY", "MONA_JPY",
        ]
        req = TraderCreateRequest(
            traderName="All Crypto",
            tradeType="Crypto",
            symbols=all_crypto,
            capitalJpy=1_000_000,
            orderUnitLots=0.01,
        )
        assert len(req.symbols) == 6


class TestTraderUpdateValidation:
    """TraderUpdateRequest のバリデーションテスト."""

    def test_trade_type_only_no_error(self):
        """trade_type のみ変更（symbols 未指定）はエラーにならない."""
        req = TraderUpdateRequest(tradeType="Crypto")
        assert req.trade_type == "Crypto"

    def test_symbols_only_no_error(self):
        """symbols のみ変更（trade_type 未指定）はエラーにならない."""
        req = TraderUpdateRequest(symbols=["USD_JPY"])
        assert req.symbols == ["USD_JPY"]

    def test_both_valid_no_error(self):
        """trade_type + symbols 両方指定で整合性がある場合は OK."""
        req = TraderUpdateRequest(
            tradeType="Crypto",
            symbols=["BTC_JPY"],
        )
        assert req.trade_type == "Crypto"
        assert req.symbols == ["BTC_JPY"]

    def test_both_invalid_rejected(self):
        """trade_type + symbols 両方指定で不整合の場合はエラー."""
        with pytest.raises(ValidationError, match="Invalid symbols for FX"):
            TraderUpdateRequest(
                tradeType="FX",
                symbols=["BTC_JPY"],
            )

    def test_update_trade_type_normalized(self):
        """'fx' は 'FX' に正規化."""
        req = TraderUpdateRequest(tradeType="fx")
        assert req.trade_type == "FX"
