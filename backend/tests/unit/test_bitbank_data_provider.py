"""
BitbankDataProvider tests.
Reference: 02_データパイプライン Section 2-2, Phase 4 Step 7
"""

import pytest

from app.services.pipeline.bitbank_data_provider import BitbankDataProvider, TIMEFRAME_MAP


class TestTimeframeConversion:
    def test_m1_to_1min(self):
        assert BitbankDataProvider.to_candle_type("M1") == "1min"

    def test_h1_to_1hour(self):
        assert BitbankDataProvider.to_candle_type("H1") == "1hour"

    def test_d1_to_1day(self):
        assert BitbankDataProvider.to_candle_type("D1") == "1day"

    def test_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            BitbankDataProvider.to_candle_type("W1")


class TestPairConversion:
    def test_btc_jpy(self):
        assert BitbankDataProvider.to_bitbank_pair("BTC_JPY") == "btc_jpy"

    def test_xrp_jpy(self):
        assert BitbankDataProvider.to_bitbank_pair("XRP_JPY") == "xrp_jpy"


class TestTimeframeMapCompleteness:
    def test_all_required_timeframes(self):
        """Verify all 7 required timeframes from design spec are mapped."""
        required = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}
        assert required == set(TIMEFRAME_MAP.keys())
