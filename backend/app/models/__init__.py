"""SQLAlchemy models. All models must be imported here for Alembic discovery."""

from app.models.ai_decision_log import AiDecisionLog
from app.models.ai_model_config import AiModelConfig
from app.models.backtest import BacktestRun, BacktestTrade
from app.models.chart_config import ChartConfig
from app.models.config_change import ConfigChange
from app.models.economic_event import EconomicEvent
from app.models.exchange_config import ExchangeConfig
from app.models.historical_ohlcv import HistoricalOhlcv
from app.models.market_watch_config import MarketWatchConfig
from app.models.model_stage_config import ModelStageConfig
from app.models.notification import DailyNotificationConfig, NotificationEmail
from app.models.pipeline_log import PipelineLog
from app.models.position import Position
from app.models.safeguard_config import SafeguardConfig
from app.models.safeguard_log import SafeguardLog
from app.models.simulation_history import SimulationHistory
from app.models.system_default_prompt import SystemDefaultPrompt
from app.models.trade_history import TradeHistory
from app.models.trader import Trader
from app.models.user import User

__all__ = [
    "User",
    "Trader",
    "ModelStageConfig",
    "SafeguardConfig",
    "Position",
    "TradeHistory",
    "PipelineLog",
    "SafeguardLog",
    "AiDecisionLog",
    "ConfigChange",
    "ExchangeConfig",
    "AiModelConfig",
    "SystemDefaultPrompt",
    "NotificationEmail",
    "DailyNotificationConfig",
    "MarketWatchConfig",
    "ChartConfig",
    "HistoricalOhlcv",
    "BacktestRun",
    "BacktestTrade",
    "SimulationHistory",
    "EconomicEvent",
]
