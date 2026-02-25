"""
PairNormalizer tests.
Reference: 06_取引所抽象化, Phase 4 Step 5
"""

from app.services.exchange.pair_normalizer import PairNormalizer


class TestToInternal:
    def test_bitbank_to_internal(self):
        assert PairNormalizer.to_internal("btc_jpy") == "BTC_JPY"

    def test_gmo_to_internal(self):
        assert PairNormalizer.to_internal("USD_JPY") == "USD_JPY"

    def test_mixed_case(self):
        assert PairNormalizer.to_internal("Eth_Jpy") == "ETH_JPY"


class TestToBitbank:
    def test_internal_to_bitbank(self):
        assert PairNormalizer.to_bitbank("BTC_JPY") == "btc_jpy"
        assert PairNormalizer.to_bitbank("XRP_JPY") == "xrp_jpy"


class TestIsCrypto:
    def test_crypto_pairs(self):
        assert PairNormalizer.is_crypto("BTC_JPY") is True
        assert PairNormalizer.is_crypto("ETH_JPY") is True
        assert PairNormalizer.is_crypto("XRP_JPY") is True

    def test_fx_not_crypto(self):
        assert PairNormalizer.is_crypto("USD_JPY") is False

    def test_case_insensitive(self):
        assert PairNormalizer.is_crypto("btc_jpy") is True


class TestIsFx:
    def test_fx_pairs(self):
        assert PairNormalizer.is_fx("USD_JPY") is True
        assert PairNormalizer.is_fx("EUR_USD") is True

    def test_crypto_not_fx(self):
        assert PairNormalizer.is_fx("BTC_JPY") is False
