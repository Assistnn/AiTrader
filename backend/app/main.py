"""
FastAPI application entry point.

Reference: 12_ディレクトリ構成.md, 08_API仕様.md
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import logging

from app.config import settings
from app.api.routes.auth import limiter, router as auth_router

logger = logging.getLogger(__name__)
from app.api.routes.account import router as account_router
from app.api.routes.backtests import router as backtests_router
from app.api.routes.charts import router as charts_router
from app.api.routes.config_changes import router as config_changes_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.history import router as history_router
from app.api.routes.market_watch import router as market_watch_router
from app.api.routes.model_stages import router as model_stages_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.pipeline_logs import router as pipeline_logs_router
from app.api.routes.safeguards import router as safeguards_router
from app.api.routes.settings import router as settings_router
from app.api.routes.traders import router as traders_router
from app.api.routes.websocket import router as websocket_router


# --- Error code mapping (08_API仕様 Section 5) ---

_STATUS_CODE_MAP = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_ERROR",
    502: "EXTERNAL_ERROR",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — Reference: 16書§2-2
    import logging
    from app.logging_config import setup_logging
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    _logger = logging.getLogger(__name__)
    _logger.info(
        "Application starting",
        extra={"data": {"trading_mode": settings.TRADING_MODE.value, "log_level": settings.LOG_LEVEL}},
    )

    from app.services.engine.engine_manager import EngineManager

    engine_manager = EngineManager()
    app.state.engine_manager = engine_manager

    # Load previously-running traders from DB
    from app.db.session import async_session_factory
    from sqlalchemy import select
    from app.models.trader import Trader
    from app.models.exchange_config import ExchangeConfig
    from app.services.auth.key_vault import KeyVault
    from app.config import settings as app_settings

    running_traders: list[dict] = []
    try:
        async with async_session_factory() as session:
            q = select(Trader).where(Trader.status == "running")
            result = await session.execute(q)
            traders = result.scalars().all()

            if traders:
                vault = KeyVault(app_settings.MASTER_ENCRYPTION_KEY)
                user_ids = {t.user_id for t in traders}
                # Batch fetch exchange configs for all relevant users
                ec_q = select(ExchangeConfig).where(
                    ExchangeConfig.user_id.in_(user_ids),
                    ExchangeConfig.is_active == True,
                )
                ec_result = await session.execute(ec_q)
                ec_map: dict[tuple[int, str], ExchangeConfig] = {}
                for ec in ec_result.scalars().all():
                    ec_map[(ec.user_id, ec.exchange_type)] = ec

                for t in traders:
                    try:
                        exchange_type = "gmo_fx" if t.trade_type == "FX" else "bitbank"
                        ec = ec_map.get((t.user_id, exchange_type))
                        api_key = vault.decrypt(ec.api_key_encrypted) if ec else ""
                        api_secret = vault.decrypt(ec.api_secret_encrypted) if ec else ""
                        pair = t.symbols[0] if t.symbols else "USD_JPY"
                        running_traders.append({
                            "id": t.id,
                            "pair": pair,
                            "trade_type": t.trade_type,
                            "api_key": api_key,
                            "api_secret": api_secret,
                            "user_id": t.user_id,
                            "config": {},
                        })
                    except Exception:
                        _logger.exception(
                            "Failed to load trader %d (user_id=%d): key decryption or config error",
                            t.id, t.user_id,
                        )
            else:
                _logger.info("No running traders found in DB")
    except Exception:
        _logger.critical(
            "CRITICAL: Failed to load running traders from DB on startup. "
            "Engines will start without auto-restore.",
            exc_info=True,
        )

    await engine_manager.startup(running_traders if running_traders else None)

    yield

    # Shutdown — Reference: 16書§2-2
    await engine_manager.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

# --- Rate limiting (11_セキュリティ §8) ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS (11_セキュリティ §9) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- Error handlers (08_API仕様 Section 2-3) ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Standard error response format."""
    code = _STATUS_CODE_MAP.get(exc.status_code, "INTERNAL_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": {
                "code": code,
                "message": exc.detail,
            },
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
            },
        },
    )


# --- Router registration (08_API仕様 Section 3 全セクション) ---

app.include_router(auth_router)
app.include_router(account_router)
app.include_router(dashboard_router)
app.include_router(traders_router)
app.include_router(model_stages_router)
app.include_router(safeguards_router)
app.include_router(market_watch_router)
app.include_router(charts_router)
app.include_router(notifications_router)
app.include_router(history_router)
app.include_router(backtests_router)
app.include_router(pipeline_logs_router)
app.include_router(config_changes_router)
app.include_router(settings_router)
app.include_router(websocket_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "tradingMode": settings.TRADING_MODE.value}
