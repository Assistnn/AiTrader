"""
ResponseParser tests: stage-specific JSON validation.
Reference: 05_AI統合 Section 3-4
"""

from app.services.ai.response_parser import parse_response


class TestM1Schema:
    """M1 response parsing and validation."""

    def test_valid_m1_response(self):
        raw = '{"trend": "UP", "regime": "trend", "volatility": "normal", "tradeAllowed": true, "confidence": 0.85, "reason_codes": ["EMA_BULLISH"]}'
        result = parse_response("m1", raw)
        assert result is not None
        assert result["trend"] == "UP"
        assert result["confidence"] == 0.85

    def test_m1_invalid_trend_enum(self):
        raw = '{"trend": "SIDEWAYS", "regime": "trend", "volatility": "normal", "tradeAllowed": true, "confidence": 0.8, "reason_codes": []}'
        result = parse_response("m1", raw)
        assert result is None

    def test_m1_missing_required_field(self):
        raw = '{"trend": "UP", "regime": "trend", "confidence": 0.8, "reason_codes": []}'
        result = parse_response("m1", raw)
        assert result is None  # missing tradeAllowed, volatility


class TestM2Schema:
    def test_valid_m2_response(self):
        raw = '{"setupValid": true, "setupType": "trendFollow", "probability": 0.7, "confidence": 0.8, "reason_codes": ["SETUP_OK"]}'
        result = parse_response("m2", raw)
        assert result is not None
        assert result["setupValid"] is True

    def test_m2_invalid_setup_type(self):
        raw = '{"setupValid": true, "setupType": "momentum", "probability": 0.7, "confidence": 0.8, "reason_codes": []}'
        result = parse_response("m2", raw)
        assert result is None


class TestM3Schema:
    def test_valid_m3_response(self):
        raw = '{"entry": "BUY", "entryType": "market", "tpPips": 30.0, "slPips": 20.0, "confidence": 0.75, "reason_codes": ["ENTRY_BUY"]}'
        result = parse_response("m3", raw)
        assert result is not None
        assert result["entry"] == "BUY"

    def test_m3_invalid_entry(self):
        raw = '{"entry": "LONG", "entryType": "market", "tpPips": 30.0, "slPips": 20.0, "confidence": 0.8, "reason_codes": []}'
        result = parse_response("m3", raw)
        assert result is None


class TestM4Schema:
    def test_valid_m4_response(self):
        raw = '{"action": "HOLD", "confidence": 0.6, "reason_codes": ["HOLD_POSITION"]}'
        result = parse_response("m4", raw)
        assert result is not None
        assert result["action"] == "HOLD"


class TestMarkdownExtraction:
    """Test markdown code block extraction."""

    def test_json_in_markdown_block(self):
        raw = '```json\n{"trend": "DOWN", "regime": "range", "volatility": "high", "tradeAllowed": false, "confidence": 0.9, "reason_codes": ["BEARISH"]}\n```'
        result = parse_response("m1", raw)
        assert result is not None
        assert result["trend"] == "DOWN"

    def test_json_with_surrounding_text(self):
        raw = 'Here is my analysis:\n{"trend": "UP", "regime": "trend", "volatility": "normal", "tradeAllowed": true, "confidence": 0.7, "reason_codes": ["UP"]}\nEnd.'
        result = parse_response("m1", raw)
        assert result is not None


class TestEdgeCases:
    def test_empty_string(self):
        assert parse_response("m1", "") is None

    def test_invalid_json(self):
        assert parse_response("m1", "not json at all") is None

    def test_confidence_clamped_to_max(self):
        raw = '{"trend": "UP", "regime": "trend", "volatility": "normal", "tradeAllowed": true, "confidence": 1.5, "reason_codes": []}'
        result = parse_response("m1", raw)
        assert result is not None
        assert result["confidence"] == 1.0

    def test_confidence_clamped_to_min(self):
        raw = '{"trend": "UP", "regime": "trend", "volatility": "normal", "tradeAllowed": true, "confidence": -0.5, "reason_codes": []}'
        result = parse_response("m1", raw)
        assert result is not None
        assert result["confidence"] == 0.0

    def test_unknown_stage_returns_parsed(self):
        """Unknown stage returns parsed JSON without schema validation."""
        raw = '{"custom_field": "value"}'
        result = parse_response("unknown_stage", raw)
        assert result is not None
        assert result["custom_field"] == "value"
