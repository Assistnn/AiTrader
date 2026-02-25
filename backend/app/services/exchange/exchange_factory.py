"""
ExchangeFactory: create exchange/data provider instances based on mode and config.

Reference: 06_取引所抽象化 Section 9
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.exchange.base_exchange import BaseExchange
from app.services.exchange.mock_exchange import MockExchange
from app.services.exchange.gmo_fx_exchange import GmoFxExchange
from app.services.exchange.bitbank_exchange import BitbankExchange
from app.services.exchange.price_normalizer import PriceNormalizer
from app.services.pipeline.data_ingest import BaseDataProvider
from app.services.pipeline.bitbank_data_provider import BitbankDataProvider

if TYPE_CHECKING:
    from app.services.backtest.simulation_clock import SimulationClock


class ExchangeFactory:
    """Create exchange and data provider instances. Reference: Section 9"""

    @staticmethod
    def create_exchange(
        mode: str,
        trade_type: str,
        api_key: str = "",
        api_secret: str = "",
        capital: float = 1_000_000.0,
        clock: SimulationClock | None = None,
        price_normalizer: PriceNormalizer | None = None,
    ) -> BaseExchange:
        """Create exchange based on TRADING_MODE.

        Args:
            mode: "live", "simulation", "backtest"
            trade_type: "FX" or "Crypto"
            api_key: Exchange API key (live mode)
            api_secret: Exchange API secret (live mode)
            capital: Initial capital for simulation/backtest
            clock: SimulationClock for backtest
            price_normalizer: PriceNormalizer instance
        """
        if mode == "live":
            if trade_type == "FX":
                return GmoFxExchange(api_key, api_secret)
            else:
                return BitbankExchange(api_key, api_secret)

        elif mode in ("simulation", "backtest"):
            return MockExchange(
                initial_balance=capital,
                clock=clock,
                price_normalizer=price_normalizer,
            )

        raise ValueError(f"Unknown mode: {mode}")

    @staticmethod
    def create_data_provider(trade_type: str) -> BaseDataProvider:
        """Create data provider based on trade type.

        Args:
            trade_type: "FX" or "Crypto"

        Note: HistoricalDataProvider (for backtest) is created separately
              in BacktestEngine with a SimulationClock dependency.
        """
        if trade_type == "Crypto":
            return BitbankDataProvider()

        raise NotImplementedError(
            f"Data provider for {trade_type}: GmoFxDataProvider requires API integration"
        )
