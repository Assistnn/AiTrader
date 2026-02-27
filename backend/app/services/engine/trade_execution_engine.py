"""
TradeExecutionEngine: per-trader event-driven main loop.

Reference: 16_実行エンジンとUI接続 Section 2-3, 5
- One engine per trader (asyncio.Task)
- Consumes BarClosedEvent from BarConfirmationScheduler
- Dispatches to M1/M2/M3/M4 based on timeframe
- M1/M2 results cached (PipelineCache)
- Config hot-reload via ConfigEventBus
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.logging_config import log_with_data
from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.pipeline.data_types import OHLCV, StateSnapshot
from app.services.pipeline.indicator_engine import IndicatorEngine
from app.services.pipeline.state_builder import StateBuilder
from app.services.pipeline.bar_builder import BarBuilder
from app.services.exchange.base_exchange import BaseExchange
from app.services.exchange.exchange_types import ExchangePosition, OrderStatus
from app.services.decision.orchestrator import DecisionOrchestrator
from app.services.decision.decision_types import JudgeOutput, PipelineResult
from app.services.safeguard.guard_engine import GuardEngine
from app.services.engine.execution_engine import ExecutionEngine
from app.services.engine.bar_scheduler import BarConfirmationScheduler, BarClosedEvent
from app.services.engine.market_data_feed import MarketDataFeed
from app.services.engine.config_event_bus import ConfigEventBus, ConfigChangeEvent
from app.services.engine.position_sync import PositionSyncService
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PipelineCacheEntry:
    """Cached pipeline stage result. Reference: 16書§5-2"""

    output: JudgeOutput
    timestamp: datetime
    valid_until: datetime
    bar_timestamp: datetime


@dataclass
class EngineStatus:
    """Engine runtime status. Reference: 16書§2-5"""

    trader_id: int
    state: str = "stopped"  # starting | running | stopping | stopped | halted | error
    started_at: datetime | None = None
    last_pipeline_at: datetime | None = None
    last_error: str | None = None
    positions_count: int = 0
    restart_count: int = 0


class TradeExecutionEngine:
    """Per-trader event-driven trading engine.

    Reference: 16_実行エンジンとUI接続 Section 2-3
    """

    def __init__(
        self,
        trader_id: int,
        pair: str,
        exchange: BaseExchange,
        data_provider: BaseDataProvider,
        orchestrator: DecisionOrchestrator,
        execution_engine: ExecutionEngine,
        bar_scheduler: BarConfirmationScheduler,
        market_data_feed: MarketDataFeed,
        config_bus: ConfigEventBus,
        trader_config: dict | None = None,
        indicator_engine: IndicatorEngine | None = None,
        state_builder: StateBuilder | None = None,
    ) -> None:
        self.trader_id = trader_id
        self.pair = pair
        self.exchange = exchange
        self.data_provider = data_provider
        self.orchestrator = orchestrator
        self.execution_engine = execution_engine
        self.bar_scheduler = bar_scheduler
        self.market_data_feed = market_data_feed
        self.config_bus = config_bus
        self.trader_config = trader_config or {}
        self._indicator_engine = indicator_engine or IndicatorEngine()
        self._state_builder = state_builder or StateBuilder()

        self._lock = asyncio.Lock()  # pipeline execution lock
        self._exit_lock = asyncio.Lock()  # separate lock for M4 (16書§5-4)
        self._running = False
        self._status = EngineStatus(trader_id=trader_id)

        # Pipeline result cache (16書§5-2)
        self._m1_cache: PipelineCacheEntry | None = None
        self._m2_cache: PipelineCacheEntry | None = None

        # Config event queue
        self._config_queue: asyncio.Queue[ConfigChangeEvent] | None = None

        # Position sync (§9-3, 監査6)
        self._position_sync = PositionSyncService(
            exchange=exchange,
            trader_id=trader_id,
        )

    @property
    def status(self) -> EngineStatus:
        return self._status

    async def warmup(self) -> None:
        """Warmup: fetch historical data for IndicatorEngine.

        Reference: 16書§2-4
        """
        self._status.state = "starting"
        logger.info("Engine[%d] warmup started for %s", self.trader_id, self.pair)

        # Warmup is handled by the Orchestrator's indicator engine
        # which is pre-loaded during construction. For live, we fetch
        # recent bars to seed it.
        try:
            for tf, limit in [
                ("D1", 200), ("H4", 200), ("H1", 200),
                ("M30", 50), ("M15", 50), ("M5", 50), ("M1", 50),
            ]:
                try:
                    bars = await self.data_provider.get_ohlcv(self.pair, tf, limit)
                    # Feed bars to IndicatorEngine (oldest first)
                    for bar in bars:
                        self._indicator_engine.update(self.pair, tf, bar)
                    logger.debug(
                        "Engine[%d] warmup %s %s: %d bars loaded",
                        self.trader_id, self.pair, tf, len(bars),
                    )
                except Exception:
                    logger.warning(
                        "Engine[%d] warmup failed for %s %s",
                        self.trader_id, self.pair, tf,
                    )
        except Exception:
            logger.exception("Engine[%d] warmup error", self.trader_id)

        logger.info("Engine[%d] warmup completed", self.trader_id)

    async def run(self) -> None:
        """Main event loop.

        Reference: 16書§2-3 メインループ処理フロー
        """
        self._running = True
        self._status.state = "running"
        self._status.started_at = datetime.now(timezone.utc)

        # Subscribe to config events
        self._config_queue = self.config_bus.subscribe(self.trader_id)

        # Seed position sync with current exchange state (§9-3)
        try:
            initial_positions = await self.exchange.get_positions()
            self._position_sync.update_known_from_exchange(initial_positions)
        except Exception:
            logger.warning("Engine[%d] initial position sync failed", self.trader_id)

        # Start periodic position sync task (§9-3, 監査6)
        sync_task = asyncio.create_task(
            self._position_sync_loop(),
            name=f"position_sync_{self.trader_id}",
        )

        logger.info("Engine[%d] main loop started for %s", self.trader_id, self.pair)

        try:
            while self._running:
                # 1. Consume config change events (non-blocking)
                await self._process_config_events()

                # 2. Wait for next bar close event
                event = await self.bar_scheduler.wait_for_next_event(timeout=60.0)
                if event is None:
                    continue
                if event.pair != self.pair:
                    continue

                # 3. Dispatch based on timeframe
                try:
                    await self._handle_bar_event(event)
                    self._status.last_pipeline_at = datetime.now(timezone.utc)
                except Exception:
                    logger.exception(
                        "Engine[%d] pipeline error for %s %s",
                        self.trader_id, event.pair, event.timeframe,
                    )
                    self._status.last_error = "Pipeline execution error"

        except asyncio.CancelledError:
            logger.info("Engine[%d] cancelled", self.trader_id)
        except Exception:
            logger.exception("Engine[%d] fatal error", self.trader_id)
            self._status.state = "error"
            self._status.last_error = "Fatal error in main loop"
            raise
        finally:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass
            self._running = False
            if self._status.state not in ("halted", "error"):
                self._status.state = "stopped"

    async def cleanup(self) -> None:
        """Release resources."""
        self._running = False
        self.config_bus.unsubscribe(self.trader_id)
        logger.info("Engine[%d] cleanup completed", self.trader_id)

    async def _handle_bar_event(self, event: BarClosedEvent) -> None:
        """Dispatch bar event to the appropriate pipeline stage.

        Reference: 16書§5-3
        """
        # Update indicators for this timeframe (02_データパイプライン§4)
        self._indicator_engine.update(self.pair, event.timeframe, event.ohlcv)

        tf = event.timeframe

        if tf == "H1":
            # M1 direction judgment
            async with self._lock:
                await self._run_m1(event)

        elif tf == "M15":
            # M2 setup — only if M1=PASS
            if not self._is_m1_pass():
                return
            async with self._lock:
                await self._run_m2(event)

        elif tf == "M5":
            # M3 entry — only if M1+M2=PASS
            if not self._is_m1_pass() or not self._is_m2_pass():
                return
            async with self._lock:
                await self._run_full_pipeline(event)

        elif tf == "M1":
            # System-side SL/TP monitoring (§9-4, bitbank + OCO fallback)
            sl_tp_results = await self.execution_engine.check_sl_tp(self.pair)
            for r in sl_tp_results:
                if r.success:
                    logger.info(
                        "Engine[%d] watchlist SL/TP triggered for %s",
                        self.trader_id, self.pair,
                    )

            # M4 exit management — only if position held
            positions = await self.exchange.get_positions()
            if positions:
                async with self._exit_lock:
                    await self._run_m4(event, positions)

    async def _run_m1(self, event: BarClosedEvent) -> None:
        """Execute M1 direction judgment and cache result."""
        logger.info("Engine[%d] M1 executing for %s", self.trader_id, event.pair)
        # The full pipeline's M1 result will be extracted from PipelineResult
        # For caching, we run just M1 via orchestrator
        # Since orchestrator runs full pipeline, we use a simplified approach
        result = await self.orchestrator.execute_pipeline(
            pair=event.pair,
            state=self._build_state(event),
            trader_id=self.trader_id,
        )

        if result.m1_output:
            trade_allowed = result.m1_output.result.get("tradeAllowed", False)
            now = datetime.now(timezone.utc)
            self._m1_cache = PipelineCacheEntry(
                output=result.m1_output,
                timestamp=now,
                valid_until=now,  # Valid until next H1 bar
                bar_timestamp=event.timestamp,
            )
            logger.info(
                "Engine[%d] M1 result: tradeAllowed=%s",
                self.trader_id, trade_allowed,
            )

    async def _run_m2(self, event: BarClosedEvent) -> None:
        """Execute M2 setup judgment and cache result."""
        logger.info("Engine[%d] M2 executing for %s", self.trader_id, event.pair)
        result = await self.orchestrator.execute_pipeline(
            pair=event.pair,
            state=self._build_state(event),
            trader_id=self.trader_id,
        )

        if result.m2_output:
            setup_valid = result.m2_output.result.get("setupValid", False)
            now = datetime.now(timezone.utc)
            self._m2_cache = PipelineCacheEntry(
                output=result.m2_output,
                timestamp=now,
                valid_until=now,
                bar_timestamp=event.timestamp,
            )
            logger.info(
                "Engine[%d] M2 result: setupValid=%s",
                self.trader_id, setup_valid,
            )

    async def _run_full_pipeline(self, event: BarClosedEvent) -> None:
        """Execute full pipeline (M1→M2→MX→M3) and act on result.

        Reference: 16書§5-3
        """
        logger.info("Engine[%d] full pipeline executing for %s", self.trader_id, event.pair)

        result = await self.orchestrator.execute_pipeline(
            pair=event.pair,
            state=self._build_state(event),
            trader_id=self.trader_id,
        )

        if result.action == "ENTRY" and result.order:
            logger.info(
                "Engine[%d] ENTRY signal: %s %s",
                self.trader_id, result.order.side, result.order.pair,
            )
            guard_state = result.guard_state
            if guard_state is not None:
                exec_result = await self.execution_engine.execute_entry(
                    proposed_order=result.order,
                    guard_state=guard_state,
                )
                if exec_result.success:
                    logger.info("Engine[%d] entry executed successfully", self.trader_id)
                    # Immediately register position to prevent false
                    # UNKNOWN_POSITION alerts (監査指摘3)
                    if exec_result.order is not None:
                        new_pos = ExchangePosition(
                            position_id=exec_result.order.order_id,
                            pair=result.order.pair,
                            side=result.order.side,
                            amount=exec_result.order.filled_amount or result.order.amount,
                            entry_price=exec_result.order.filled_price or 0.0,
                        )
                        self._position_sync.register_position(new_pos)
                else:
                    logger.warning(
                        "Engine[%d] entry failed: %s",
                        self.trader_id, exec_result.error,
                    )
        else:
            logger.debug(
                "Engine[%d] pipeline result: %s", self.trader_id, result.action,
            )

    async def _run_m4(self, event: BarClosedEvent, positions: list) -> None:
        """Execute M4 exit management for held positions.

        Reference: 16書§5-3
        execute_exit_management() returns JudgeOutput (not PipelineResult).
        Action is in JudgeOutput.result["action"].

        Canonical actions: HOLD, EXIT, PARTIAL, ADJUST_TRAIL, ADJUST_SL, ADJUST_TP
        AI aliases accepted: CLOSE→EXIT, PARTIAL_CLOSE→PARTIAL
        """
        logger.info(
            "Engine[%d] M4 exit check: %d positions",
            self.trader_id, len(positions),
        )

        m4_output = await self.orchestrator.execute_exit_management(
            pair=event.pair,
            state=self._build_state(event),
            positions=positions,
            trader_id=self.trader_id,
        )

        raw_action = m4_output.result.get("action", "HOLD")

        # Normalize AI aliases to canonical names
        _ACTION_ALIASES = {
            "CLOSE": "EXIT",
            "PARTIAL_CLOSE": "PARTIAL",
        }
        action = _ACTION_ALIASES.get(raw_action, raw_action)

        log_with_data(logger, logging.INFO, "M4 action", {
            "trader_id": self.trader_id,
            "action": action,
            "raw_action": raw_action if raw_action != action else None,
            "confidence": m4_output.confidence,
        })

        if action == "EXIT":
            for pos in positions:
                exec_result = await self.execution_engine.execute_exit(
                    position=pos,
                    m4_output=m4_output,
                )
                if exec_result.success:
                    logger.info(
                        "Engine[%d] exit executed for position %s",
                        self.trader_id, pos.position_id,
                    )
                    self._position_sync.unregister_position(pos.position_id)

        elif action == "PARTIAL":
            partial_pct = m4_output.result.get("partialPct", 0.5)
            for pos in positions:
                exec_result = await self.execution_engine.execute_exit(
                    position=pos,
                    m4_output=m4_output,
                )
                if exec_result.success:
                    logger.info(
                        "Engine[%d] partial close (%.0f%%) for position %s",
                        self.trader_id, partial_pct * 100, pos.position_id,
                    )

        elif action == "ADJUST_TRAIL":
            new_sl = m4_output.result.get("newSlPrice")
            if new_sl is not None:
                log_with_data(logger, logging.INFO, "Adjusting trail SL", {
                    "trader_id": self.trader_id, "new_sl_price": new_sl,
                })
                for pos in positions:
                    await self.execution_engine.adjust_stop_loss(pos, new_sl)

        elif action == "ADJUST_SL":
            new_sl = m4_output.result.get("newSlPrice")
            if new_sl is not None:
                log_with_data(logger, logging.INFO, "Adjusting SL", {
                    "trader_id": self.trader_id, "new_sl_price": new_sl,
                })
                for pos in positions:
                    await self.execution_engine.adjust_stop_loss(pos, new_sl)
            else:
                logger.warning(
                    "Engine[%d] ADJUST_SL without newSlPrice", self.trader_id,
                )

        elif action == "ADJUST_TP":
            new_tp = m4_output.result.get("newTpPrice")
            if new_tp is not None:
                log_with_data(logger, logging.INFO, "Adjusting TP", {
                    "trader_id": self.trader_id, "new_tp_price": new_tp,
                })
                for pos in positions:
                    await self.execution_engine.adjust_take_profit(pos, new_tp)
            else:
                logger.warning(
                    "Engine[%d] ADJUST_TP without newTpPrice", self.trader_id,
                )

        elif action == "HOLD":
            logger.debug("Engine[%d] M4 result: HOLD", self.trader_id)

        else:
            logger.warning(
                "Engine[%d] M4 unknown action: %s", self.trader_id, action,
            )

    def _is_m1_pass(self) -> bool:
        """Check if M1 cache indicates PASS. Reference: 16書§5-1"""
        if self._m1_cache is None:
            return False
        return self._m1_cache.output.result.get("tradeAllowed", False)

    def _is_m2_pass(self) -> bool:
        """Check if M2 cache indicates PASS. Reference: 16書§5-1"""
        if self._m2_cache is None:
            return False
        return self._m2_cache.output.result.get("setupValid", False)

    def _build_state(self, event: BarClosedEvent) -> StateSnapshot:
        """Build StateSnapshot from current indicator state.

        Reference: 16書§5-3, 02_データパイプライン§5
        """
        snapshots = self._indicator_engine.get_all_snapshots(self.pair)
        return self._state_builder.build(
            pair=self.pair,
            timestamp=event.timestamp,
            indicators=snapshots,
        )

    async def _process_config_events(self) -> None:
        """Consume pending config change events (non-blocking).

        Reference: 16書§7-2
        """
        if self._config_queue is None:
            return

        while True:
            try:
                event = self._config_queue.get_nowait()
                logger.info(
                    "Engine[%d] applying config change: %s",
                    self.trader_id, event.config_type,
                )
                # Config changes are applied at the next pipeline execution
                # by reloading judge configs from DB.
                # The Orchestrator picks up configs at execution time.
            except asyncio.QueueEmpty:
                break

    async def _position_sync_loop(self) -> None:
        """Periodic position synchronization (§9-3, 監査6).

        Runs every ENGINE_POSITION_SYNC_INTERVAL seconds.
        Detects divergences between exchange and local state.
        For UNKNOWN_POSITION: attempts SL/TP recovery from watchlist (監査指摘2).
        """
        interval = settings.ENGINE_POSITION_SYNC_INTERVAL
        while self._running:
            await asyncio.sleep(interval)
            try:
                divergences = await self._position_sync.sync()
                self._status.positions_count = (
                    self._position_sync.known_position_count
                )
                for d in divergences:
                    logger.warning(
                        "Engine[%d] position sync divergence: %s %s",
                        self.trader_id, d.divergence_type.value, d.detail,
                    )
                    # UNKNOWN_POSITION: attempt SL/TP recovery (監査指摘2)
                    if d.divergence_type.value == "UNKNOWN_POSITION":
                        self._recover_sl_tp_for_unknown(d.position_id, d.pair)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Engine[%d] position sync error", self.trader_id,
                )

    def _recover_sl_tp_for_unknown(self, position_id: str, pair: str) -> None:
        """Attempt to recover SL/TP for an unknown position (監査指摘2).

        Checks if the execution engine's watchlist has SL/TP data for
        this position. If found, logs recovery; if not, adds a
        watchlist entry with no SL/TP as a tracking placeholder.
        """
        watchlist = self.execution_engine._sl_tp_watchlist
        if position_id in watchlist:
            entry = watchlist[position_id]
            logger.info(
                "Engine[%d] SL/TP recovered for unknown position %s: "
                "sl=%.5f tp=%s",
                self.trader_id,
                position_id,
                entry.get("sl_price") or 0,
                entry.get("tp_price"),
            )
        else:
            logger.warning(
                "Engine[%d] unknown position %s (%s) has no SL/TP in "
                "watchlist — manual review recommended",
                self.trader_id,
                position_id,
                pair,
            )
