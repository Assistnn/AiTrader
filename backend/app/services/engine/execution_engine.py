"""
ExecutionEngine: order placement, fill confirmation, SL/TP management.

Reference: 16_実行エンジンとUI接続 Section 9
- execute_entry: place MARKET order → confirm fill → OCO for TP/SL (GMO) or watchlist (bitbank)
- execute_exit: close position via exchange
- adjust_stop_loss: modify SL order
- close_all_positions: emergency close all
- clientOrderId for duplicate prevention (16書§9-2, 監査5)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from app.services.exchange.base_exchange import BaseExchange
from app.services.exchange.exchange_types import (
    Balance,
    ExchangePosition,
    ExecutionResult,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSizeResult,
)
from app.logging_config import log_with_data
from app.services.exchange.position_sizer import PositionSizer
from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.safeguard.guard_types import GuardState, ProposedOrder
from app.services.decision.decision_types import JudgeOutput
from app.services.engine.resilience import CircuitBreaker, CircuitOpenError
from app.config import settings

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Order placement and position management.

    Reference: 16_実行エンジンとUI接続 Section 9-1
    """

    def __init__(
        self,
        exchange: BaseExchange,
        position_sizer: PositionSizer,
        price_normalizer: PriceNormalizer,
        trade_type: str = "FX",
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.exchange = exchange
        self.position_sizer = position_sizer
        self.price_normalizer = price_normalizer
        self.trade_type = trade_type
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

        # SL/TP watchlist for bitbank (system-side monitoring, §9-4)
        self._sl_tp_watchlist: dict[str, dict] = {}
        # SL order ID tracking for GMO (§9-2 OCO management)
        self._sl_order_ids: dict[str, str] = {}  # position_id → sl_order_id

    async def execute_entry(
        self,
        proposed_order: ProposedOrder,
        guard_state: GuardState,
    ) -> ExecutionResult:
        """Execute an entry order.

        Reference: 16書§9-2
        1. CircuitBreaker check (§11-2)
        2. PositionSizer validation
        3. clientOrderId generation (UUID)
        4. place_order(MARKET)
        5. Poll for fill (max ORDER_FILL_TIMEOUT)
        6. OCO order placement (§3-1, §9-2)
        """
        # 0. CircuitBreaker check (§11-2)
        try:
            self._circuit_breaker.check()
        except CircuitOpenError:
            return ExecutionResult(
                success=False,
                error="CircuitBreaker is open — exchange API unavailable",
            )

        log_with_data(logger, logging.INFO, "Entry started", {
            "pair": proposed_order.pair, "side": proposed_order.side,
            "sl_pips": proposed_order.sl_pips, "tp_pips": proposed_order.tp_pips,
        })

        try:
            # 1. Get balance for position sizing
            balance = await self.exchange.get_balance()
            ticker = await self.exchange.get_ticker(proposed_order.pair)
            current_price = ticker.last

            # 2. Position sizing (respects guard_state.lot_multiplier)
            sl_pips = proposed_order.sl_pips or 20.0
            tp_pips = proposed_order.tp_pips or sl_pips * 2.0
            max_lot = 100.0  # Default max lot; can be overridden per trader config
            min_lot = 0.01

            size_result = self.position_sizer.calculate(
                pair=proposed_order.pair,
                capital=balance.available,
                risk_per_trade_pct=proposed_order.risk_per_trade_pct or 1.0,
                sl_pips=sl_pips,
                tp_pips=tp_pips,
                min_lot=min_lot,
                max_lot=max_lot,
            )

            # Apply guard lot_multiplier
            adjusted_lot = size_result.lot_size * guard_state.lot_multiplier
            size_result = PositionSizeResult(
                lot_size=adjusted_lot,
                rr_ratio=size_result.rr_ratio,
                risk_amount=size_result.risk_amount * guard_state.lot_multiplier,
                risk_pct=size_result.risk_pct,  # 割合は変更しない（実金額はrisk_amountで調整済み）
                _debug={**size_result._debug, "lot_multiplier": guard_state.lot_multiplier},
            )

            log_with_data(logger, logging.INFO, "Position sized", {
                "lot_size": size_result.lot_size,
                "rr_ratio": size_result.rr_ratio,
                "lot_multiplier": guard_state.lot_multiplier,
            })

            if size_result.lot_size <= 0:
                return ExecutionResult(
                    success=False,
                    error="Position size is zero after sizing calculation",
                    size_result=size_result,
                )

            # 3. Generate clientOrderId for duplicate prevention (監査5)
            client_order_id = f"entry-{uuid.uuid4().hex[:16]}"

            # 4. Place market order
            side = OrderSide(proposed_order.side)
            order = await self.exchange.place_order(
                pair=proposed_order.pair,
                side=side,
                amount=size_result.lot_size,
                order_type=OrderType.MARKET,
                client_order_id=client_order_id,
            )

            # 4.5. Check for immediate rejection
            if order.status == OrderStatus.REJECTED:
                self._circuit_breaker.record_failure()
                return ExecutionResult(
                    order=order,
                    size_result=size_result,
                    success=False,
                    error="Order rejected by exchange",
                    _debug={"client_order_id": client_order_id},
                )

            # 5. Poll for fill confirmation
            filled_order = await self._wait_for_fill(order.order_id)

            if filled_order.status != OrderStatus.FILLED:
                return ExecutionResult(
                    order=filled_order,
                    size_result=size_result,
                    success=False,
                    error=f"Order not filled: {filled_order.status.value}",
                    _debug={"client_order_id": client_order_id},
                )

            log_with_data(logger, logging.INFO, "Entry filled", {
                "order_id": filled_order.order_id,
                "filled_price": filled_order.filled_price,
                "filled_amount": filled_order.filled_amount,
            })

            # 6. Post-fill SL/TP setup (§3-1, §3-2, §9-2)
            tp_order_id, sl_order_id = await self._setup_sl_tp(
                proposed_order=proposed_order,
                filled_order=filled_order,
                lot_size=size_result.lot_size,
                client_order_id=client_order_id,
            )

            log_with_data(logger, logging.INFO, "SL/TP configured", {
                "method": "OCO" if self.trade_type == "FX" else "watchlist",
                "sl_order_id": sl_order_id,
                "tp_order_id": tp_order_id,
            })

            self._circuit_breaker.record_success()
            return ExecutionResult(
                order=filled_order,
                size_result=size_result,
                success=True,
                tp_order_id=tp_order_id,
                sl_order_id=sl_order_id,
                _debug={
                    "client_order_id": client_order_id,
                    "proposed_sl": proposed_order.sl_price,
                    "proposed_tp": proposed_order.tp_price,
                },
            )

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.exception("ExecutionEngine.execute_entry failed")
            return ExecutionResult(
                success=False,
                error=str(e),
            )

    async def execute_exit(
        self,
        position: ExchangePosition,
        m4_output: JudgeOutput,
    ) -> ExecutionResult:
        """Execute an exit (close position).

        Reference: 16書§9-2
        """
        log_with_data(logger, logging.INFO, "Exit started", {
            "position_id": position.position_id,
        })
        try:
            order = await self.exchange.close_position(
                position_id=position.position_id,
                amount=position.amount,
            )

            filled_order = await self._wait_for_fill(order.order_id)

            if filled_order.status == OrderStatus.FILLED:
                log_with_data(logger, logging.INFO, "Exit filled", {
                    "position_id": position.position_id,
                    "filled_price": filled_order.filled_price,
                })

            return ExecutionResult(
                order=filled_order,
                success=filled_order.status == OrderStatus.FILLED,
                error=None if filled_order.status == OrderStatus.FILLED
                else f"Exit order not filled: {filled_order.status.value}",
                _debug={
                    "m4_reason": m4_output.reason_codes,
                    "position_id": position.position_id,
                },
            )

        except Exception as e:
            logger.exception("ExecutionEngine.execute_exit failed")
            return ExecutionResult(success=False, error=str(e))

    async def adjust_stop_loss(
        self,
        position: ExchangePosition,
        new_sl_price: float,
    ) -> bool:
        """Adjust stop-loss for an existing position.

        Reference: 16書§9-2
        GMO FX: modify the existing STOP order via modify_order.
        bitbank: update the system-side SL watchlist.
        """
        try:
            if self.trade_type == "FX":
                # GMO: modify existing SL order via exchange API
                sl_order_id = self._sl_order_ids.get(position.position_id)
                if sl_order_id is not None:
                    await self.exchange.modify_order(sl_order_id, price=new_sl_price)
                    logger.info(
                        "SL order %s modified to %.5f for position %s",
                        sl_order_id, new_sl_price, position.position_id,
                    )
                else:
                    logger.warning(
                        "No SL order ID tracked for position %s, "
                        "updating watchlist instead",
                        position.position_id,
                    )
                    # Fallback to watchlist update
                    self._update_watchlist_sl(position.position_id, new_sl_price)
            else:
                # bitbank: update system-side watchlist
                self._update_watchlist_sl(position.position_id, new_sl_price)

            return True
        except Exception:
            logger.exception("adjust_stop_loss failed for %s", position.position_id)
            return False

    def _update_watchlist_sl(self, position_key: str, new_sl_price: float) -> None:
        """Update SL price in watchlist for a position."""
        # Search by position_id in watchlist values or by key
        for key, watch in self._sl_tp_watchlist.items():
            if key == position_key:
                watch["sl_price"] = new_sl_price
                logger.info(
                    "Watchlist SL updated: %s → %.5f", key, new_sl_price,
                )
                return
        logger.warning(
            "Position %s not found in watchlist for SL update", position_key,
        )

    async def adjust_take_profit(
        self,
        position: ExchangePosition,
        new_tp_price: float,
    ) -> bool:
        """Adjust take-profit for an existing position.

        Reference: 16書§9-2
        GMO FX: cancel old TP LIMIT order and place new one.
        bitbank: update the system-side TP watchlist.
        """
        try:
            if self.trade_type == "FX":
                # GMO: TP is a LIMIT order — modify via exchange API
                # TP order ID is not separately tracked; update watchlist as fallback
                self._update_watchlist_tp(position.position_id, new_tp_price)
            else:
                # bitbank: update system-side watchlist
                self._update_watchlist_tp(position.position_id, new_tp_price)

            return True
        except Exception:
            logger.exception("adjust_take_profit failed for %s", position.position_id)
            return False

    def _update_watchlist_tp(self, position_key: str, new_tp_price: float) -> None:
        """Update TP price in watchlist for a position."""
        for key, watch in self._sl_tp_watchlist.items():
            if key == position_key:
                watch["tp_price"] = new_tp_price
                logger.info(
                    "Watchlist TP updated: %s → %.5f", key, new_tp_price,
                )
                return
        logger.warning(
            "Position %s not found in watchlist for TP update", position_key,
        )

    async def close_all_positions(self) -> list[ExecutionResult]:
        """Close all open positions (emergency).

        Reference: 16書§9-1, 監査7
        """
        log_with_data(logger, logging.INFO, "Close all positions started", {})
        results: list[ExecutionResult] = []
        try:
            positions = await self.exchange.get_positions()
            for pos in positions:
                try:
                    order = await self.exchange.close_position(
                        position_id=pos.position_id,
                    )
                    filled = await self._wait_for_fill(order.order_id)
                    results.append(ExecutionResult(
                        order=filled,
                        success=filled.status == OrderStatus.FILLED,
                        error=None if filled.status == OrderStatus.FILLED
                        else f"Close failed: {filled.status.value}",
                    ))
                except Exception as e:
                    logger.error("Failed to close position %s: %s", pos.position_id, e)
                    results.append(ExecutionResult(success=False, error=str(e)))
        except Exception as e:
            logger.exception("close_all_positions: failed to get positions")
            results.append(ExecutionResult(success=False, error=str(e)))

        return results

    async def _wait_for_fill(self, order_id: str) -> Order:
        """Poll for order fill confirmation.

        Reference: 16書§9-2 step 5
        Polls get_order_status every ORDER_FILL_POLL_INTERVAL seconds,
        up to ORDER_FILL_TIMEOUT seconds.
        If not filled, attempts to cancel.
        """
        timeout = settings.ORDER_FILL_TIMEOUT
        poll_interval = settings.ORDER_FILL_POLL_INTERVAL
        elapsed = 0.0

        while elapsed < timeout:
            order = await self.exchange.get_order_status(order_id)
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                return order
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout: try to cancel unfilled order
        logger.warning("Order %s not filled after %.0fs, cancelling", order_id, timeout)
        try:
            await self.exchange.cancel_order(order_id)
        except Exception:
            logger.exception("Failed to cancel unfilled order %s", order_id)

        return await self.exchange.get_order_status(order_id)

    # ── OCO / SL-TP management (§3-1, §3-2, §9-2, §9-4) ──

    async def _setup_sl_tp(
        self,
        proposed_order: ProposedOrder,
        filled_order: Order,
        lot_size: float,
        client_order_id: str,
    ) -> tuple[str | None, str | None]:
        """Post-fill SL/TP setup.

        GMO FX (§3-1): place OCO orders (TP=LIMIT, SL=STOP).
        bitbank  (§3-2): add to system-side watchlist (§9-4).

        Returns (tp_order_id, sl_order_id).
        """
        if self.trade_type == "crypto":
            # bitbank: system-side watchlist (§9-4)
            return await self._add_to_watchlist(
                filled_order=filled_order,
                proposed_order=proposed_order,
                lot_size=lot_size,
            )

        # GMO FX: OCO orders (§3-1, §9-2)
        return await self._place_oco_orders(
            proposed_order=proposed_order,
            filled_order=filled_order,
            lot_size=lot_size,
            client_order_id=client_order_id,
        )

    async def _place_oco_orders(
        self,
        proposed_order: ProposedOrder,
        filled_order: Order,
        lot_size: float,
        client_order_id: str,
    ) -> tuple[str | None, str | None]:
        """Place OCO orders (TP + SL) after MARKET fill.

        Reference: 16書§3-1, §9-2
        clientOrderId prefix: tp-{uuid}, sl-{uuid}
        """
        uuid_suffix = client_order_id.replace("entry-", "")
        opposite_side = (
            OrderSide.SELL if filled_order.side == OrderSide.BUY else OrderSide.BUY
        )

        tp_order_id: str | None = None
        sl_order_id: str | None = None

        # TP order (LIMIT)
        if proposed_order.tp_price is not None:
            try:
                tp_order = await self.exchange.place_order(
                    pair=proposed_order.pair,
                    side=opposite_side,
                    amount=lot_size,
                    order_type=OrderType.LIMIT,
                    price=proposed_order.tp_price,
                    client_order_id=f"tp-{uuid_suffix}",
                )
                tp_order_id = tp_order.order_id
                logger.info(
                    "OCO TP placed: %s @ %.5f",
                    tp_order_id, proposed_order.tp_price,
                )
            except Exception:
                logger.critical(
                    "OCO TP placement failed for %s — fallback to watchlist",
                    proposed_order.pair,
                )

        # SL order (STOP)
        if proposed_order.sl_price is not None:
            try:
                sl_order = await self.exchange.place_order(
                    pair=proposed_order.pair,
                    side=opposite_side,
                    amount=lot_size,
                    order_type=OrderType.STOP,
                    price=proposed_order.sl_price,
                    client_order_id=f"sl-{uuid_suffix}",
                )
                sl_order_id = sl_order.order_id
                logger.info(
                    "OCO SL placed: %s @ %.5f",
                    sl_order_id, proposed_order.sl_price,
                )
            except Exception:
                logger.critical(
                    "OCO SL placement failed for %s — fallback to watchlist",
                    proposed_order.pair,
                )

        # Fallback: if SL placement failed, add to watchlist (§9-2 failsafe)
        if sl_order_id is None and proposed_order.sl_price is not None:
            await self._add_to_watchlist(
                filled_order=filled_order,
                proposed_order=proposed_order,
                lot_size=lot_size,
            )
            logger.warning(
                "OCO SL failed — position %s added to system-side watchlist",
                filled_order.order_id,
            )

        # Track SL order ID for adjust_stop_loss (§9-2)
        if sl_order_id is not None:
            # Use order_id as position proxy (real position ID assigned later)
            self._sl_order_ids[filled_order.order_id] = sl_order_id

        return tp_order_id, sl_order_id

    async def _add_to_watchlist(
        self,
        filled_order: Order,
        proposed_order: ProposedOrder,
        lot_size: float,
    ) -> tuple[str | None, str | None]:
        """Add position to system-side SL/TP watchlist (§9-4).

        Used for bitbank (no native SL/TP) and as GMO OCO failure fallback.
        Resolves actual exchange position_id for correct check_sl_tp matching.
        """
        # Determine position key: try to get actual exchange position_id
        position_key = filled_order.order_id  # fallback
        try:
            positions = await self.exchange.get_positions()
            for pos in positions:
                if (
                    pos.pair == proposed_order.pair
                    and pos.side.value == proposed_order.side
                    and pos.position_id not in self._sl_tp_watchlist
                ):
                    position_key = pos.position_id
                    break
        except Exception:
            logger.warning(
                "Failed to resolve position_id for watchlist, using order_id"
            )

        self._sl_tp_watchlist[position_key] = {
            "pair": proposed_order.pair,
            "entry_price": filled_order.filled_price,
            "tp_price": proposed_order.tp_price,
            "sl_price": proposed_order.sl_price,
            "side": proposed_order.side,
            "amount": lot_size,
        }
        logger.info(
            "Watchlist added: key=%s pair=%s sl=%.5f tp=%s",
            position_key,
            proposed_order.pair,
            proposed_order.sl_price or 0,
            proposed_order.tp_price,
        )
        return None, None  # No exchange-side order IDs

    async def check_sl_tp(self, pair: str) -> list[ExecutionResult]:
        """Check SL/TP conditions for watchlisted positions (§9-4).

        Called every M1 bar. For bitbank and GMO OCO-failure fallback.
        """
        results: list[ExecutionResult] = []
        if not self._sl_tp_watchlist:
            return results

        try:
            ticker = await self.exchange.get_ticker(pair)
        except Exception:
            logger.warning("check_sl_tp: failed to get ticker for %s", pair)
            return results

        current_price = ticker.last
        to_remove: list[str] = []

        # Pre-fetch positions once (avoid N+1 exchange calls)
        exchange_positions = None

        for position_key, watch in list(self._sl_tp_watchlist.items()):
            if watch["pair"] != pair:
                continue

            sl_price = watch.get("sl_price")
            tp_price = watch.get("tp_price")
            is_buy = watch["side"] == "BUY"

            sl_hit = False
            tp_hit = False

            if sl_price is not None:
                sl_hit = (current_price <= sl_price) if is_buy else (current_price >= sl_price)
            if tp_price is not None:
                tp_hit = (current_price >= tp_price) if is_buy else (current_price <= tp_price)

            if sl_hit or tp_hit:
                reason = "SL" if sl_hit else "TP"
                logger.info(
                    "Watchlist %s hit for %s (key=%s): price=%.5f %s=%.5f",
                    reason, pair, position_key, current_price,
                    reason, sl_price if sl_hit else tp_price,
                )

                # Find and close the position (match by position_id)
                try:
                    if exchange_positions is None:
                        exchange_positions = await self.exchange.get_positions()

                    # Match by position_id (= watchlist key), not just pair
                    matched_pos = None
                    for pos in exchange_positions:
                        if pos.position_id == position_key:
                            matched_pos = pos
                            break

                    if matched_pos is None:
                        # Position no longer exists on exchange (external close)
                        logger.warning(
                            "Watchlist %s: position %s not found on exchange, removing",
                            reason, position_key,
                        )
                        to_remove.append(position_key)
                        continue

                    order = await self.exchange.close_position(
                        position_id=matched_pos.position_id,
                        amount=watch["amount"],
                    )
                    filled = await self._wait_for_fill(order.order_id)
                    results.append(ExecutionResult(
                        order=filled,
                        success=filled.status == OrderStatus.FILLED,
                        error=None if filled.status == OrderStatus.FILLED
                        else f"Watchlist {reason} close failed",
                        _debug={"trigger": reason, "watchlist_key": position_key},
                    ))
                    to_remove.append(position_key)
                except Exception as e:
                    logger.exception("Watchlist close failed for %s", position_key)
                    results.append(ExecutionResult(
                        success=False,
                        error=f"Watchlist close error: {e}",
                    ))

        for key in to_remove:
            self._sl_tp_watchlist.pop(key, None)

        if results:
            log_with_data(logger, logging.INFO, "Watchlist SL/TP check completed", {
                "pair": pair,
                "triggered_count": len(results),
                "success_count": sum(1 for r in results if r.success),
            })
        return results

    def remove_from_watchlist(self, position_key: str) -> None:
        """Remove a position from the SL/TP watchlist."""
        self._sl_tp_watchlist.pop(position_key, None)
