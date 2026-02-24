"""
BacktestEngine: バックテスト実行エンジン.
設計書 Section 3-3 の7ステップを1足ごとに実行する.

Reference: 09_バックテストシミュレーション Section 3-3
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.backtest.backtest_recorder import BacktestRecorder
from app.services.backtest.backtest_types import (
    BacktestConfig,
    BacktestResult,
    BacktestTradeRecord,
)
from app.services.backtest.simulation_clock import SimulationClock
from app.services.decision.orchestrator import DecisionOrchestrator
from app.services.exchange.exchange_types import OrderSide, OrderType
from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.pipeline.data_types import OHLCV, IndicatorSnapshot, StateSnapshot
from app.services.pipeline.indicator_engine import IndicatorEngine
from app.services.pipeline.state_builder import StateBuilder
from app.services.safeguard.guard_types import AccountState


class BacktestEngine:
    """バックテスト実行エンジン. Reference: Section 3-3.

    本番と同一のパイプラインを1足ずつ実行し、結果を記録する。
    """

    def __init__(
        self,
        orchestrator: DecisionOrchestrator,
        indicator_engine: IndicatorEngine | None = None,
        state_builder: StateBuilder | None = None,
        normalizer: PriceNormalizer | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.indicator_engine = indicator_engine or IndicatorEngine()
        self.state_builder = state_builder or StateBuilder()
        self.normalizer = normalizer or PriceNormalizer()

    def run(self, config: BacktestConfig, bars: list[OHLCV]) -> BacktestResult:
        """バックテスト実行（同期）.

        bars は start_date〜end_date の OHLCV リスト（時系列昇順）。
        Look-ahead Bias は呼出元で bars を事前取得する構造で防止。
        """
        if not bars:
            return BacktestResult(config=config, error="No bars provided")

        # SimulationClock
        start_dt = datetime.combine(config.start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(config.end_date, datetime.max.time(), tzinfo=timezone.utc)
        clock = SimulationClock(start_dt, end_dt)

        # MockExchange with clock
        mock_exchange = MockExchange(
            initial_balance=config.capital,
            clock=clock,
        )
        mock_exchange.slippage_pips = config.slippage_pips

        # Recorder
        recorder = BacktestRecorder(config, initial_equity=config.capital)

        # Track open positions for exit management
        open_positions: list[dict] = []  # simplified position tracking

        for bar in bars:
            # Step 1: clock advance
            bar_ts = bar.timestamp
            if bar_ts.tzinfo is None:
                bar_ts = bar_ts.replace(tzinfo=timezone.utc)
            clock.advance_to(bar_ts)

            # Step 2: indicator update
            snapshot = self.indicator_engine.update(config.pair, config.timeframe, bar)

            # Step 3: state build
            all_snapshots = self.indicator_engine.get_all_snapshots(config.pair)
            if not all_snapshots:
                all_snapshots = {config.timeframe: snapshot}
            state = self.state_builder.build(
                pair=config.pair,
                timestamp=bar_ts,
                indicators=all_snapshots,
            )

            # Step 4: MockExchange price update
            spread = 0.02 if "JPY" in config.pair else 0.0002
            mock_exchange.set_price(config.pair, bid=bar.close, ask=bar.close + spread)

            # Step 5: Exit management for open positions
            action = "NO_TRADE"
            self._process_exits(
                mock_exchange, open_positions, bar, config, recorder, clock,
            )

            # Step 6: New entry evaluation (if no open positions for simplicity)
            if not open_positions:
                account = self._build_account(config, mock_exchange, recorder)
                result = self.orchestrator.execute_pipeline(
                    pair=config.pair,
                    state=state,
                    account=account,
                    now=clock.now(),
                )
                action = result.action

                if result.action == "ENTRY" and result.order is not None:
                    self._execute_entry(
                        mock_exchange, result, open_positions, bar, config,
                    )

            # Step 7: Record step
            equity = config.capital + sum(p.get("unrealized_pnl", 0) for p in open_positions)
            equity += sum(t.realized_pnl for t in recorder.trades)
            recorder.record_step(
                timestamp=bar_ts,
                bar_close=bar.close,
                equity=equity,
                action=action,
            )

        # Close remaining positions at last bar
        if open_positions and bars:
            last_bar = bars[-1]
            for pos in list(open_positions):
                self._force_close(
                    mock_exchange, pos, last_bar, config, recorder, clock, "TIMEOUT",
                )
            open_positions.clear()

        return recorder.finalize()

    def _process_exits(
        self,
        exchange: MockExchange,
        positions: list[dict],
        bar: OHLCV,
        config: BacktestConfig,
        recorder: BacktestRecorder,
        clock: SimulationClock,
    ) -> None:
        """SL/TP チェックによる退出処理."""
        for pos in list(positions):
            hit = self._check_sl_tp(pos, bar, config)
            if hit is not None:
                exit_reason, exit_price = hit
                self._record_exit(
                    pos, exit_price, bar.timestamp, exit_reason, config, recorder,
                )
                positions.remove(pos)

    def _check_sl_tp(
        self, pos: dict, bar: OHLCV, config: BacktestConfig,
    ) -> tuple[str, float] | None:
        """SL/TP ヒット判定. 返り値: (exit_reason, exit_price) or None."""
        sl = pos.get("sl_price")
        tp = pos.get("tp_price")

        if pos["side"] == "BUY":
            if sl is not None and bar.low <= sl:
                return ("SL", sl)
            if tp is not None and bar.high >= tp:
                return ("TP", tp)
        else:  # SELL
            if sl is not None and bar.high >= sl:
                return ("SL", sl)
            if tp is not None and bar.low <= tp:
                return ("TP", tp)
        return None

    def _execute_entry(
        self,
        exchange: MockExchange,
        result: Any,
        positions: list[dict],
        bar: OHLCV,
        config: BacktestConfig,
    ) -> None:
        """エントリー実行."""
        order = result.order
        entry_price = bar.close
        spread = 0.02 if "JPY" in config.pair else 0.0002
        if order.side == "BUY":
            entry_price = bar.close + spread  # ask
        entry_price += self._slippage(order.side, config)

        sl_price = None
        tp_price = None
        pip_size = 0.01 if "JPY" in config.pair else 0.0001
        if order.sl_pips:
            if order.side == "BUY":
                sl_price = entry_price - order.sl_pips * pip_size
            else:
                sl_price = entry_price + order.sl_pips * pip_size
        if order.tp_pips:
            if order.side == "BUY":
                tp_price = entry_price + order.tp_pips * pip_size
            else:
                tp_price = entry_price - order.tp_pips * pip_size

        positions.append({
            "pair": config.pair,
            "side": order.side,
            "amount": order.lot_size,
            "entry_price": entry_price,
            "entry_timestamp": bar.timestamp,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "unrealized_pnl": 0.0,
        })

    def _force_close(
        self,
        exchange: MockExchange,
        pos: dict,
        bar: OHLCV,
        config: BacktestConfig,
        recorder: BacktestRecorder,
        clock: SimulationClock,
        reason: str,
    ) -> None:
        """ポジション強制クローズ."""
        exit_price = bar.close
        self._record_exit(pos, exit_price, bar.timestamp, reason, config, recorder)

    def _record_exit(
        self,
        pos: dict,
        exit_price: float,
        exit_timestamp: datetime,
        exit_reason: str,
        config: BacktestConfig,
        recorder: BacktestRecorder,
    ) -> None:
        """退出を記録."""
        pip_size = 0.01 if "JPY" in config.pair else 0.0001
        pip_value = 100.0 if "JPY" in config.pair else 10.0  # per lot

        if pos["side"] == "BUY":
            pnl_pips = (exit_price - pos["entry_price"]) / pip_size
        else:
            pnl_pips = (pos["entry_price"] - exit_price) / pip_size

        pnl = pnl_pips * pip_value * pos["amount"]

        entry_ts = pos["entry_timestamp"]
        if isinstance(entry_ts, datetime) and entry_ts.tzinfo is None:
            entry_ts = entry_ts.replace(tzinfo=timezone.utc)
        exit_ts = exit_timestamp
        if isinstance(exit_ts, datetime) and exit_ts.tzinfo is None:
            exit_ts = exit_ts.replace(tzinfo=timezone.utc)

        sl_distance = 0.0
        if pos.get("sl_price"):
            sl_distance = abs(pos["entry_price"] - pos["sl_price"]) / pip_size
        rr = abs(pnl_pips / sl_distance) if sl_distance > 0 else 0.0

        recorder.record_trade(BacktestTradeRecord(
            pair=pos["pair"],
            side=pos["side"],
            amount=pos["amount"],
            entry_price=pos["entry_price"],
            exit_price=exit_price,
            entry_timestamp=entry_ts,
            exit_timestamp=exit_ts,
            realized_pnl=pnl,
            realized_pnl_pips=pnl_pips,
            rr_ratio=rr,
            exit_reason=exit_reason,
        ))

    def _build_account(
        self,
        config: BacktestConfig,
        exchange: MockExchange,
        recorder: BacktestRecorder,
    ) -> AccountState:
        """現在の AccountState を構築."""
        realized = sum(t.realized_pnl for t in recorder.trades)
        current = config.capital + realized
        return AccountState(
            capital=config.capital,
            daily_realized_pnl=realized,
            daily_unrealized_pnl=0.0,
            monthly_pnl=realized,
            peak_capital=max(config.capital, current),
            current_capital=current,
            consecutive_losses=0,
            last_trade_was_loss=False,
            daily_profit_pct=(realized / config.capital) * 100 if config.capital > 0 else 0,
        )

    def _slippage(self, side: str, config: BacktestConfig) -> float:
        """スリッページ計算."""
        pip_size = 0.01 if "JPY" in config.pair else 0.0001
        slip = config.slippage_pips * pip_size
        return slip if side == "BUY" else -slip
