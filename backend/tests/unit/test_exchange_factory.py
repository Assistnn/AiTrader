"""
ExchangeFactory tests.
Reference: 06_取引所抽象化 Section 9, Phase 4 Step 8
"""

import pytest

from app.services.exchange.exchange_factory import ExchangeFactory
from app.services.exchange.gmo_fx_exchange import GmoFxExchange
from app.services.exchange.bitbank_exchange import BitbankExchange
from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.pipeline.bitbank_data_provider import BitbankDataProvider


class TestCreateExchange:
    def test_live_fx(self):
        ex = ExchangeFactory.create_exchange("live", "FX", "key", "secret")
        assert isinstance(ex, GmoFxExchange)

    def test_live_crypto(self):
        ex = ExchangeFactory.create_exchange("live", "Crypto", "key", "secret")
        assert isinstance(ex, BitbankExchange)

    def test_simulation(self):
        ex = ExchangeFactory.create_exchange("simulation", "FX", capital=500_000)
        assert isinstance(ex, MockExchange)
        assert ex.balance_total == 500_000

    def test_backtest(self):
        ex = ExchangeFactory.create_exchange("backtest", "Crypto", capital=2_000_000)
        assert isinstance(ex, MockExchange)
        assert ex.balance_total == 2_000_000

    def test_backtest_with_normalizer(self):
        n = PriceNormalizer()
        ex = ExchangeFactory.create_exchange(
            "backtest", "Crypto", capital=1_000_000, price_normalizer=n,
        )
        assert isinstance(ex, MockExchange)
        assert ex._normalizer is n

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown mode"):
            ExchangeFactory.create_exchange("invalid", "FX")


class TestCreateDataProvider:
    def test_crypto_provider(self):
        dp = ExchangeFactory.create_data_provider("Crypto")
        assert isinstance(dp, BitbankDataProvider)
