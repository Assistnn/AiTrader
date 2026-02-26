"""
FastAPI application entry point.

Reference: 12_ディレクトリ構成.md, 08_API仕様.md
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes.auth import router as auth_router
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
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
