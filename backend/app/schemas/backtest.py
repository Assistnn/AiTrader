"""
Backtest API schemas (Pydantic).
Reference: 08_API仕様 Section 3-11

命名規則: lowerCamelCase（APIレスポンス向け）
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class BacktestCreateRequest(BaseModel):
    """POST /api/v1/backtests リクエスト."""

    model_config = ConfigDict(populate_by_name=True)

    trader_id: int = Field(alias="traderId")
    pair: str
    timeframe: str
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    use_current_config: bool = Field(default=True, alias="useCurrentConfig")


class BacktestCreateResponse(BaseModel):
    """POST /api/v1/backtests レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    backtest_id: int = Field(alias="backtestId")
    status: str


class BacktestMetricsResponse(BaseModel):
    """メトリクスの部分スキーマ."""

    model_config = ConfigDict(populate_by_name=True)

    total_pnl: float | None = Field(None, alias="totalPnl")
    total_pnl_pct: float | None = Field(None, alias="totalPnlPct")
    total_trades: int | None = Field(None, alias="totalTrades")
    win_rate: float | None = Field(None, alias="winRate")
    profit_factor: float | None = Field(None, alias="profitFactor")
    max_drawdown_pct: float | None = Field(None, alias="maxDrawdownPct")
    sharpe_ratio: float | None = Field(None, alias="sharpeRatio")
    avg_rr_ratio: float | None = Field(None, alias="avgRrRatio")
    ruin_probability: float | None = Field(None, alias="ruinProbability")


class BacktestDetailResponse(BaseModel):
    """GET /api/v1/backtests/{id} レスポンス."""

    model_config = ConfigDict(populate_by_name=True)

    backtest_id: int = Field(alias="backtestId")
    trader_id: int = Field(alias="traderId")
    status: str
    pair: str
    timeframe: str
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    config_snapshot: dict | None = Field(None, alias="configSnapshot")
    metrics: BacktestMetricsResponse | None = None
    started_at: datetime | None = Field(None, alias="startedAt")
    completed_at: datetime | None = Field(None, alias="completedAt")
    error_message: str | None = Field(None, alias="errorMessage")
    created_at: datetime = Field(alias="createdAt")


class BacktestListItem(BaseModel):
    """GET /api/v1/backtests 一覧の1要素."""

    model_config = ConfigDict(populate_by_name=True)

    backtest_id: int = Field(alias="backtestId")
    trader_id: int = Field(alias="traderId")
    status: str
    pair: str
    timeframe: str
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    total_trades: int | None = Field(None, alias="totalTrades")
    win_rate: float | None = Field(None, alias="winRate")
    total_pnl: float | None = Field(None, alias="totalPnl")
    created_at: datetime = Field(alias="createdAt")


class BacktestTradeResponse(BaseModel):
    """GET /api/v1/backtests/{id}/trades の1要素."""

    model_config = ConfigDict(populate_by_name=True)

    trade_id: int = Field(alias="tradeId")
    pair: str
    side: str
    amount: float | None = None
    entry_price: float | None = Field(None, alias="entryPrice")
    exit_price: float | None = Field(None, alias="exitPrice")
    realized_pnl: float | None = Field(None, alias="realizedPnl")
    realized_pnl_pips: float | None = Field(None, alias="realizedPnlPips")
    rr_ratio: float | None = Field(None, alias="rrRatio")
    exit_reason: str | None = Field(None, alias="exitReason")
    entry_timestamp: datetime | None = Field(None, alias="entryTimestamp")
    exit_timestamp: datetime | None = Field(None, alias="exitTimestamp")
