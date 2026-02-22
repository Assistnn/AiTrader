"""Smoke tests for project foundation."""

from app.config import Settings, TradingMode


def test_settings_default_trading_mode():
    s = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test",
        MASTER_ENCRYPTION_KEY="test",
    )
    assert s.TRADING_MODE == TradingMode.SIMULATION


def test_settings_live_mode():
    s = Settings(
        TRADING_MODE="live",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test",
        MASTER_ENCRYPTION_KEY="test",
    )
    assert s.TRADING_MODE == TradingMode.LIVE


def test_settings_case_insensitive_mode():
    s = Settings(
        TRADING_MODE="BACKTEST",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test",
        MASTER_ENCRYPTION_KEY="test",
    )
    assert s.TRADING_MODE == TradingMode.BACKTEST


def test_fastapi_app_creation():
    from app.main import app

    assert app.title == "AI Trading System"
    routes = [r.path for r in app.routes]
    assert "/health" in routes
