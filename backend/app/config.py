"""
Application configuration using Pydantic BaseSettings.

Reference: 12_ディレクトリ構成.md, 11_セキュリティ.md Section 7, 09_バックテストシミュレーション.md
"""

from enum import Enum
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class TradingMode(str, Enum):
    LIVE = "live"
    SIMULATION = "simulation"
    BACKTEST = "backtest"


class Settings(BaseSettings):
    # --- Application ---
    APP_NAME: str = "AI Trading System"
    DEBUG: bool = False

    # --- Trading Mode (09_バックテストシミュレーション.md) ---
    # live: 本番取引
    # simulation: ペーパートレード（本番価格 + MockExchange）
    # backtest: バックテスト（HistoricalData + MockExchange）
    TRADING_MODE: TradingMode = TradingMode.SIMULATION

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_trading"

    # --- Security (11_セキュリティ.md Section 2-1, 7) ---
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60  # 1 hour per design
    JWT_REFRESH_EXPIRE_DAYS: int = 7  # 7 days per design
    MASTER_ENCRYPTION_KEY: str = "change-me-in-production"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    @field_validator("TRADING_MODE", mode="before")
    @classmethod
    def validate_trading_mode(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower()
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
