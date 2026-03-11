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
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/ai_trading"

    # --- Security (11_セキュリティ.md Section 2-1, 7) ---
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60  # 1 hour per design
    JWT_REFRESH_EXPIRE_DAYS: int = 7  # 7 days per design
    MASTER_ENCRYPTION_KEY: str = ""

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

    # --- Engine (16_実行エンジンとUI接続 Section 14) ---
    ENGINE_WARMUP_BARS: int = 200
    ENGINE_POSITION_SYNC_INTERVAL: int = 30  # seconds
    ENGINE_MAX_RESTART_COUNT: int = 3
    ENGINE_RESTART_DELAY: float = 30.0  # seconds

    # --- Retry ---
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 60.0

    # --- Circuit Breaker ---
    CB_FAILURE_THRESHOLD: int = 5
    CB_RECOVERY_TIMEOUT: float = 300.0  # seconds

    # --- Market Data ---
    BAR_POLL_DELAY: float = 5.0  # seconds after bar close
    WS_RECONNECT_MAX_DELAY: float = 60.0
    WS_DISCONNECT_ALERT_THRESHOLD: float = 300.0  # seconds

    # --- Economic Calendar ---
    ECONOMIC_CALENDAR_FETCH_INTERVAL: int = 21600  # 6 hours
    ECONOMIC_CALENDAR_REFRESH_HOURS: int = 6
    ECONOMIC_CALENDAR_API_URL: str = ""  # External API URL (empty = disabled)
    ECONOMIC_CALENDAR_FALLBACK_BLOCK: bool = True

    # --- Order ---
    ORDER_FILL_TIMEOUT: float = 10.0  # seconds
    ORDER_FILL_POLL_INTERVAL: float = 1.0

    # --- GMO Coin ---
    GMO_BASE_URL_PUBLIC: str = "https://forex-api.coin.z.com/public"
    GMO_BASE_URL_PRIVATE: str = "https://forex-api.coin.z.com/private"
    GMO_WS_URL: str = "wss://forex-api.coin.z.com/ws/public/v1"

    # --- bitbank ---
    BITBANK_BASE_URL_PUBLIC: str = "https://public.bitbank.cc"
    BITBANK_BASE_URL_PRIVATE: str = "https://api.bitbank.cc"
    BITBANK_WS_URL: str = "wss://stream.bitbank.cc/socket.io/"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_MAX_BYTES: int = 50_000_000
    LOG_BACKUP_COUNT: int = 10

    @field_validator("TRADING_MODE", mode="before")
    @classmethod
    def validate_trading_mode(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("JWT_SECRET_KEY", mode="after")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "change-me-in-production":
            raise ValueError(
                "JWT_SECRET_KEY must be changed from default in .env"
            )
        if not v:
            import os
            if os.environ.get("TRADING_MODE", "").lower() != "backtest":
                import warnings
                warnings.warn(
                    "JWT_SECRET_KEY is empty. Set it in .env for production.",
                    stacklevel=2,
                )
        return v

    @field_validator("MASTER_ENCRYPTION_KEY", mode="after")
    @classmethod
    def validate_master_key(cls, v: str) -> str:
        if v == "change-me-in-production":
            raise ValueError(
                "MASTER_ENCRYPTION_KEY must be changed from default in .env"
            )
        if not v:
            import os
            if os.environ.get("TRADING_MODE", "").lower() != "backtest":
                import warnings
                warnings.warn(
                    "MASTER_ENCRYPTION_KEY is empty. Set it in .env for production.",
                    stacklevel=2,
                )
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
