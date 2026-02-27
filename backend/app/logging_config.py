"""
Centralized logging configuration.

- Console: human-readable format
- File: JSON structured logs with RotatingFileHandler (50MB x 10)
- Error file: WARNING+ only with RotatingFileHandler (20MB x 5)
- SecretMaskingFilter applied to all handlers
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from app.services.auth.log_masking import SecretMaskingFilter


class _JsonFormatter(logging.Formatter):
    """JSON structured log formatter for file output."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "data") and record.data:
            log_entry["data"] = record.data
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False, default=str)


def log_with_data(
    logger: logging.Logger,
    level: int,
    msg: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Log a message with optional structured data attached."""
    if not logger.isEnabledFor(level):
        return
    record = logger.makeRecord(
        logger.name, level, "(log_with_data)", 0, msg, (), None,
    )
    if data:
        record.data = data  # type: ignore[attr-defined]
    logger.handle(record)


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure application-wide logging."""
    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicates on reload
    root.handlers.clear()

    secret_filter = SecretMaskingFilter()

    # --- Console handler ---
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s] %(message)s")
    )
    console.addFilter(secret_filter)
    root.addHandler(console)

    # --- JSON file handler ---
    json_handler = RotatingFileHandler(
        os.path.join(log_dir, "trading.log"),
        maxBytes=50_000_000,
        backupCount=10,
        encoding="utf-8",
    )
    json_handler.setLevel(logging.DEBUG)
    json_handler.setFormatter(_JsonFormatter())
    json_handler.addFilter(secret_filter)
    root.addHandler(json_handler)

    # --- Error file handler (WARNING+) ---
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, "trading_error.log"),
        maxBytes=20_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(_JsonFormatter())
    error_handler.addFilter(secret_filter)
    root.addHandler(error_handler)

    # Suppress noisy third-party loggers
    for name in ("httpx", "httpcore", "urllib3", "asyncio", "aiosqlite"):
        logging.getLogger(name).setLevel(logging.WARNING)
