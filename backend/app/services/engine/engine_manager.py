"""
EngineManager: manages all trader engines as a singleton.

Reference: 16_実行エンジンとUI接続 Section 2-2
- One EngineManager per FastAPI application (lifespan)
- start_trader / stop_trader / stop_all / reload_config
- Auto-restart on crash (max ENGINE_MAX_RESTART_COUNT times)
- On HALT: force close all positions
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.services.exchange.base_exchange import BaseExchange
from app.services.exchange.exchange_factory import ExchangeFactory
from app.services.exchange.exchange_types import ExecutionResult
from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.engine.trade_execution_engine import (
    TradeExecutionEngine,
    EngineStatus,
)
from app.services.engine.config_event_bus import ConfigEventBus, ConfigChangeEvent
from app.config import settings

logger = logging.getLogger(__name__)


class EngineManager:
    """Manages all trader engines.

    Reference: 16_実行エンジンとUI接続 Section 2-2
    """

    def __init__(self) -> None:
        self._engines: dict[int, TradeExecutionEngine] = {}
        self._tasks: dict[int, asyncio.Task] = {}
        self._config_bus = ConfigEventBus()
        self._lock = asyncio.Lock()  # WARNING #5 from review: protect dict access

    @property
    def config_bus(self) -> ConfigEventBus:
        return self._config_bus

    async def startup(self, running_traders: list[dict] | None = None) -> None:
        """Start engines for all previously-running traders.

        Reference: 16書§2-2 startup()
        Called from FastAPI lifespan.
        """
        if running_traders:
            for trader_info in running_traders:
                try:
                    await self.start_trader(
                        trader_id=trader_info["id"],
                        pair=trader_info["pair"],
                        trade_type=trader_info.get("trade_type", "FX"),
                        api_key=trader_info.get("api_key", ""),
                        api_secret=trader_info.get("api_secret", ""),
                        trader_config=trader_info.get("config", {}),
                    )
                except Exception:
                    logger.exception(
                        "Failed to start engine for trader %d", trader_info["id"],
                    )
        logger.info("EngineManager startup complete. %d engines running.", len(self._engines))

    async def shutdown(self) -> None:
        """Stop all engines gracefully.

        Reference: 16書§2-2 shutdown()
        """
        logger.info("EngineManager shutting down %d engines...", len(self._engines))
        await self.stop_all()
        logger.info("EngineManager shutdown complete.")

    async def start_trader(
        self,
        trader_id: int,
        pair: str,
        trade_type: str = "FX",
        api_key: str = "",
        api_secret: str = "",
        trader_config: dict | None = None,
        user_id: int = 0,
    ) -> None:
        """Start engine for a trader.

        Reference: 16書§2-2 start_trader(), §6-1
        """
        async with self._lock:
            if trader_id in self._engines:
                logger.warning("Engine for trader %d already running", trader_id)
                return

            logger.info("Starting engine for trader %d (%s, %s)", trader_id, pair, trade_type)

            # Create exchange and data provider
            exchange = ExchangeFactory.create_exchange(
                mode=settings.TRADING_MODE.value,
                trade_type=trade_type,
                api_key=api_key,
                api_secret=api_secret,
            )
            data_provider = ExchangeFactory.create_data_provider(trade_type)

            # Create supporting components
            from app.services.engine.bar_scheduler import BarConfirmationScheduler
            from app.services.engine.market_data_feed import MarketDataFeed
            from app.services.engine.execution_engine import ExecutionEngine
            from app.services.exchange.position_sizer import PositionSizer
            from app.services.exchange.price_normalizer import PriceNormalizer

            price_normalizer = PriceNormalizer()
            position_sizer = PositionSizer(price_normalizer=price_normalizer)
            execution_engine = ExecutionEngine(
                exchange=exchange,
                position_sizer=position_sizer,
                price_normalizer=price_normalizer,
                trade_type=trade_type,
            )
            bar_scheduler = BarConfirmationScheduler()
            market_data_feed = MarketDataFeed(data_provider)

            # Load judge configs from DB (16書§7-4)
            judge_configs = await self._load_judge_configs(trader_id)

            # Create orchestrator with AI helper if API keys available
            orchestrator = self._create_orchestrator(trader_config or {})

            # Create indicator engine and state builder for pipeline state
            from app.services.pipeline.indicator_engine import IndicatorEngine
            from app.services.pipeline.state_builder import StateBuilder

            indicator_engine = IndicatorEngine()
            state_builder = StateBuilder()

            engine = TradeExecutionEngine(
                trader_id=trader_id,
                pair=pair,
                exchange=exchange,
                data_provider=data_provider,
                orchestrator=orchestrator,
                execution_engine=execution_engine,
                bar_scheduler=bar_scheduler,
                market_data_feed=market_data_feed,
                config_bus=self._config_bus,
                trader_config=trader_config,
                indicator_engine=indicator_engine,
                state_builder=state_builder,
                user_id=user_id,
                judge_configs=judge_configs,
            )

            self._engines[trader_id] = engine

            # Register live price broadcast to WebSocket (16書§8-1)
            self._register_price_broadcast(market_data_feed)

            # Warmup, start scheduler and feed, then create task
            await engine.warmup()
            await bar_scheduler.start([pair], data_provider)
            await market_data_feed.connect([pair])

            task = asyncio.create_task(
                self._run_with_restart(trader_id, engine),
                name=f"engine_{trader_id}",
            )
            self._tasks[trader_id] = task

            logger.info("Engine for trader %d started successfully", trader_id)

    async def stop_trader(
        self, trader_id: int, force_close: bool = False,
    ) -> None:
        """Stop engine for a trader.

        Reference: 16書§2-2 stop_trader(), §6-2
        """
        async with self._lock:
            task = self._tasks.pop(trader_id, None)
            engine = self._engines.pop(trader_id, None)

            if task is not None:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

            if engine is not None:
                if force_close:
                    logger.info("Force closing positions for trader %d", trader_id)
                    await engine.execution_engine.close_all_positions()

                await engine.bar_scheduler.stop()
                await engine.market_data_feed.disconnect()
                await engine.cleanup()

            logger.info("Engine for trader %d stopped", trader_id)

    async def stop_all(self) -> None:
        """Stop all engines.

        Reference: 16書§2-2 stop_all()
        """
        trader_ids = list(self._engines.keys())
        for trader_id in trader_ids:
            await self.stop_trader(trader_id)

    async def reload_config(
        self, trader_id: int, config_type: str, new_config: dict,
        stage: str | None = None,
    ) -> None:
        """Push a config change to an engine via ConfigEventBus.

        Reference: 16書§7-2
        """
        event = ConfigChangeEvent(
            trader_id=trader_id,
            config_type=config_type,
            stage=stage,
            new_config=new_config,
            timestamp=datetime.now(timezone.utc),
        )
        await self._config_bus.publish(event)

    def get_engine_status(self, trader_id: int) -> EngineStatus | None:
        """Get engine status for a trader."""
        engine = self._engines.get(trader_id)
        if engine is None:
            return None
        return engine.status

    def get_all_statuses(self) -> dict[int, EngineStatus]:
        """Get all engine statuses."""
        return {tid: e.status for tid, e in self._engines.items()}

    async def _run_with_restart(
        self, trader_id: int, engine: TradeExecutionEngine,
    ) -> None:
        """Run engine with auto-restart on crash.

        Reference: 16書§11-3
        """
        max_restarts = settings.ENGINE_MAX_RESTART_COUNT
        restart_delay = settings.ENGINE_RESTART_DELAY

        for attempt in range(max_restarts + 1):
            try:
                await engine.run()
                return  # Normal exit
            except asyncio.CancelledError:
                return  # Explicit stop
            except Exception:
                engine._status.restart_count = attempt + 1
                if attempt < max_restarts:
                    logger.warning(
                        "Engine[%d] crashed (attempt %d/%d), restarting in %.0fs",
                        trader_id, attempt + 1, max_restarts, restart_delay,
                    )
                    await asyncio.sleep(restart_delay)
                    await engine.warmup()
                else:
                    logger.error(
                        "Engine[%d] HALTED after %d failures",
                        trader_id, max_restarts + 1,
                    )
                    engine._status.state = "halted"
                    engine._status.last_error = f"Halted after {max_restarts + 1} failures"

                    # Force close all positions with retry (§12-2 監査7)
                    await self._halt_force_close(trader_id, engine)

    async def _halt_force_close(
        self, trader_id: int, engine: TradeExecutionEngine,
    ) -> None:
        """Force close all positions on HALT with retry (§12-2 監査7).

        Retries up to 3 times with 30-second intervals.
        If all retries fail, logs CRITICAL for manual intervention.
        """
        max_retries = 3
        retry_delay = 30.0

        for retry in range(max_retries):
            try:
                results = await engine.execution_engine.close_all_positions()
                all_closed = all(r.success for r in results)
                if all_closed:
                    if results:
                        logger.info(
                            "Engine[%d] HALT: %d positions force-closed",
                            trader_id, len(results),
                        )
                    return
                failed = [r for r in results if not r.success]
                logger.warning(
                    "Engine[%d] HALT close retry %d/%d: %d/%d failed",
                    trader_id, retry + 1, max_retries,
                    len(failed), len(results),
                )
            except Exception:
                logger.exception(
                    "Engine[%d] HALT close retry %d/%d failed",
                    trader_id, retry + 1, max_retries,
                )
            if retry < max_retries - 1:
                await asyncio.sleep(retry_delay)

        logger.critical(
            "Engine[%d] CRITICAL: cannot close positions after %d retries. "
            "Manual intervention required.",
            trader_id, max_retries,
        )

    async def _load_judge_configs(self, trader_id: int) -> dict[str, dict]:
        """Load JudgeConfig from DB model_stage_configs for a trader.

        Reference: 16書§7-4
        Returns dict like {"m1": {...}, "m2": {...}, "m3": {...}, "m4": {...}}
        """
        from app.db.session import async_session_factory
        from sqlalchemy import select
        from app.models.model_stage_config import ModelStageConfig

        configs: dict[str, dict] = {}
        try:
            async with async_session_factory() as session:
                q = select(ModelStageConfig).where(
                    ModelStageConfig.trader_id == trader_id,
                )
                result = await session.execute(q)
                for msc in result.scalars().all():
                    configs[msc.stage] = msc.config_json or {}
            if configs:
                logger.info(
                    "Loaded judge configs from DB for trader %d: stages=%s",
                    trader_id, list(configs.keys()),
                )
            else:
                logger.info(
                    "No judge configs in DB for trader %d, using defaults",
                    trader_id,
                )
        except Exception:
            logger.exception("Failed to load judge configs from DB for trader %d", trader_id)
        return configs

    def _register_price_broadcast(
        self,
        market_data_feed: Any,
    ) -> None:
        """Register on_tick callback to broadcast live prices via WebSocket.

        Reference: 16書§8-1 — MarketDataFeedからWebSocket pricesチャネルへの配信
        """
        from app.api.routes.websocket import get_ws_manager
        from app.services.pipeline.data_types import Ticker
        from datetime import datetime, timezone

        ws_manager = get_ws_manager()
        ws_manager.set_live_feed(True)

        async def _broadcast_tick(pair: str, ticker: Ticker) -> None:
            await ws_manager.broadcast("prices", {
                "pair": pair,
                "bid": ticker.bid,
                "ask": ticker.ask,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        market_data_feed.add_on_tick(_broadcast_tick)

    def _create_orchestrator(self, config: dict) -> DecisionOrchestrator:
        """Create a DecisionOrchestrator with AI helper if API keys available.

        Reference: 16書§7-4, 05_AI統合
        """
        from app.services.decision.orchestrator import DecisionOrchestrator
        from app.services.decision.m1_direction import M1DirectionJudge
        from app.services.decision.m2_setup import M2SetupJudge
        from app.services.decision.m3_entry import M3EntryJudge
        from app.services.decision.m4_exit import M4ExitJudge
        from app.services.safeguard.guard_engine import GuardEngine

        ai_helper = self._create_ai_helper()

        guard_engine = GuardEngine()
        return DecisionOrchestrator(
            m1=M1DirectionJudge(ai_helper=ai_helper),
            m2=M2SetupJudge(ai_helper=ai_helper),
            m3=M3EntryJudge(ai_helper=ai_helper),
            m4=M4ExitJudge(ai_helper=ai_helper),
            guard_engine=guard_engine,
        )

    def _create_ai_helper(self) -> Any:
        """Create AIJudgeHelper from environment API keys.

        Reference: 05_AI統合, 16書§7-4
        Returns AIJudgeHelper or None if no API keys configured.
        """
        from app.services.ai.provider_factory import create_provider
        from app.services.ai.judge_helper import AIJudgeHelper
        from app.services.ai.rate_limiter import AIRateLimiter
        from app.services.ai.budget_tracker import BudgetTracker

        provider_name = settings.AI_DEFAULT_PROVIDER
        api_key = ""
        if provider_name == "openai":
            api_key = settings.OPENAI_API_KEY
        elif provider_name == "gemini":
            api_key = settings.GEMINI_API_KEY
        elif provider_name == "claude":
            api_key = settings.CLAUDE_API_KEY

        if not api_key:
            logger.warning(
                "AI API key not configured for provider '%s'. "
                "AI judge modes (aiAssist/aiFull) will fall back to rule mode.",
                provider_name,
            )
            return None

        try:
            provider = create_provider(
                provider_name=provider_name,
                api_key=api_key,
                model=settings.AI_DEFAULT_MODEL,
            )
            rate_limiter = AIRateLimiter(
                per_trader_limit=settings.AI_RATE_LIMIT_PER_TRADER,
                global_limit=settings.AI_RATE_LIMIT_GLOBAL,
            )
            budget_tracker = BudgetTracker(
                daily_token_budget=settings.AI_DAILY_TOKEN_BUDGET,
                warning_pct=settings.AI_BUDGET_WARNING_PCT,
            )
            logger.info("AI helper initialized: provider=%s, model=%s", provider_name, settings.AI_DEFAULT_MODEL)
            return AIJudgeHelper(
                provider=provider,
                rate_limiter=rate_limiter,
                budget_tracker=budget_tracker,
            )
        except Exception:
            logger.exception("Failed to initialize AI helper, falling back to rule mode")
            return None
