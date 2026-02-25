"""
FastAPI application entry point.

Reference: 12_ディレクトリ構成.md, 08_API仕様.md
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes.auth import router as auth_router
from app.api.routes.backtests import router as backtests_router
from app.api.routes.websocket import router as websocket_router
from app.api.routes.traders import router as traders_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.pipeline_logs import router as pipeline_logs_router
from app.api.routes.config_changes import router as config_changes_router
from app.api.routes.history import router as history_router


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

app.include_router(auth_router)
app.include_router(backtests_router)
app.include_router(websocket_router)
app.include_router(traders_router)
app.include_router(dashboard_router)
app.include_router(pipeline_logs_router)
app.include_router(config_changes_router)
app.include_router(history_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "tradingMode": settings.TRADING_MODE.value}
