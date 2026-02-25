"""
BitbankExchange tests.
Reference: 06_取引所抽象化 Section 6, Phase 4 Step 6
"""

import hmac
import hashlib

from app.services.exchange.bitbank_exchange import BitbankExchange


class TestBitbankSignature:
    def test_sign_get(self):
        ex = BitbankExchange(api_key="test_key", api_secret="test_secret")
        nonce = "1234567890"
        path = "/v1/user/assets"
        sig = ex._sign_get(nonce, path)
        # Verify it produces valid HMAC-SHA256
        expected = hmac.new(
            b"test_secret", (nonce + path).encode(), hashlib.sha256,
        ).hexdigest()
        assert sig == expected

    def test_sign_get_with_query(self):
        ex = BitbankExchange(api_key="test_key", api_secret="test_secret")
        nonce = "1234567890"
        path = "/v1/user/spot/order"
        query = "pair=btc_jpy&order_id=123"
        sig = ex._sign_get(nonce, path, query)
        expected = hmac.new(
            b"test_secret",
            (nonce + path + "?" + query).encode(),
            hashlib.sha256,
        ).hexdigest()
        assert sig == expected

    def test_sign_post(self):
        ex = BitbankExchange(api_key="test_key", api_secret="test_secret")
        nonce = "1234567890"
        body = '{"pair":"btc_jpy","amount":"0.01","side":"buy","type":"market"}'
        sig = ex._sign_post(nonce, body)
        expected = hmac.new(
            b"test_secret", (nonce + body).encode(), hashlib.sha256,
        ).hexdigest()
        assert sig == expected


class TestBitbankHeaders:
    def test_headers_contain_required_fields(self):
        ex = BitbankExchange(api_key="my_key", api_secret="my_secret")
        headers = ex._headers("GET", "/v1/user/assets")
        assert headers["ACCESS-KEY"] == "my_key"
        assert "ACCESS-NONCE" in headers
        assert "ACCESS-SIGNATURE" in headers
        assert headers["Content-Type"] == "application/json"


class TestBitbankPairConversion:
    def test_to_bitbank_pair(self):
        assert BitbankExchange._to_bitbank_pair("BTC_JPY") == "btc_jpy"
        assert BitbankExchange._to_bitbank_pair("XRP_JPY") == "xrp_jpy"


class TestBitbankRateLimiter:
    def test_rate_limiter_config(self):
        ex = BitbankExchange(api_key="k", api_secret="s")
        assert ex._rate_limiter.max_per_second == 6
        assert ex._rate_limiter.max_per_minute == 300
