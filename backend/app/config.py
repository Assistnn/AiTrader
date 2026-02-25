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

    # --- AI Integration (05_AI統合.md, 14_コスト管理.md) ---
    AI_DEFAULT_PROVIDER: str = "openai"
    AI_DEFAULT_MODEL: str = "gpt-4o"
    AI_RATE_LIMIT_PER_TRADER: int = 10  # calls/minute per trader
    AI_RATE_LIMIT_GLOBAL: int = 30  # calls/minute global
    AI_DAILY_TOKEN_BUDGET: int = 1_000_000  # daily token limit
    AI_BUDGET_WARNING_PCT: int = 80  # warning threshold %
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""

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
