"""The Feature Engineering Layer's shared contract.

A "feature" is any named, engineered value derived from historical market
data (a technical measure, a market-structure classification, a
cross-timeframe statistic, ...). This layer sits alongside — not inside —
the Core Backtesting Engine and the Strategy plugin boundary: it exists so
generic, reusable computations (the kind any strategy or research notebook
might want) have one home, separate from any strategy's proprietary
analyzers (which remain in the strategy plugin per
``docs/STRATEGY_AND_DATA_LAYER.md``).

This module defines the contract only. Concrete analyzers
(:mod:`market_structure`, :mod:`atr`, :mod:`cvd`) are intentionally left
unimplemented in this pass — see
``docs/RESEARCH_PLATFORM_ARCHITECTURE.md`` for why.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from btengine.data.schema import Candle


class HistoricalCandleSource(Protocol):
    """Anything a feature analyzer can pull bounded historical candles from.

    Satisfied structurally (no inheritance needed) by both
    :class:`btengine.strategy.context.HistoryView` and
    :class:`~btengine.features.multi_timeframe.MultiTimeframeView`, so this
    layer never has to import the engine's concrete context types.
    """

    def get_candles(
        self, *, lookback_periods: int | None = None, start: datetime | None = None
    ) -> list[Candle]: ...


@dataclass(frozen=True)
class FeatureValue:
    """One computed feature value for one symbol at one point in time."""

    symbol: str
    feature_name: str
    timestamp: datetime
    value: float


class FeatureAnalyzer(ABC):
    """A single, independently-computable named feature.

    Mirrors the role of a strategy plugin's ``MarketAnalyzer`` (see
    ``docs/STRATEGY_AND_DATA_LAYER.md`` §2) but for generic, provider-
    independent technical computations reusable across any strategy —
    not proprietary analysis.
    """

    @property
    @abstractmethod
    def feature_name(self) -> str:
        """A stable, unique name for this feature (used as its Feature Store key)."""

    @abstractmethod
    def compute(self, symbol: str, history: HistoricalCandleSource) -> FeatureValue:
        """Compute this feature's current value from bounded historical data.

        ``history`` never exposes data beyond the caller's current
        simulation time (see ``HistoryView``'s lookahead-prevention), so
        any analyzer implementing this is automatically lookahead-safe.
        """
