"""The read-only view a strategy plugin receives on every market event.

This is the entire surface a strategy is allowed to see: the current
(fully-closed) candle, a bounded window into history, and a snapshot of
its own portfolio state. There is no path from here to the engine's
internals, to other symbols' future data, or to anything beyond the
current simulation timestamp — lookahead is prevented structurally by
:class:`HistoryView`, not by strategy authors remembering not to cheat.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe


class ClockLike(Protocol):
    """Anything exposing the current simulation time.

    A ``Protocol`` (rather than importing
    ``btengine.backtest.simulation_clock.SimulationClock`` directly) keeps
    this module — part of the plugin-facing API — decoupled from the
    engine's concrete internals.
    """

    @property
    def now(self) -> datetime: ...


class HistoryView:
    """Bounded, read-only access to historical candles for one symbol.

    Every query is clipped to ``clock.now`` regardless of what the caller
    asks for: a strategy cannot obtain a candle from the future even if it
    tries, because there is no parameter that can push ``end`` past the
    current simulation time.
    """

    def __init__(
        self,
        repository: DataRepository,
        clock: ClockLike,
        *,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._exchange = exchange
        self._symbol = symbol
        self._timeframe = timeframe

    def get_candles(
        self, *, lookback_periods: int | None = None, start: datetime | None = None
    ) -> list[Candle]:
        """Return cached candles up to (and including) the current simulation time.

        Either ``lookback_periods`` (number of bars back from now) or an
        explicit ``start`` must be given. If ``start`` is after the current
        simulation time it is clamped to it, never extended forward.
        """
        end = self._clock.now
        if start is None:
            if lookback_periods is None:
                raise ValueError("Provide either start or lookback_periods")
            if lookback_periods <= 0:
                raise ValueError("lookback_periods must be positive")
            start = end - self._timeframe.duration * lookback_periods
        elif start > end:
            start = end

        return self._repository.read(
            Candle,
            exchange=self._exchange,
            symbol=self._symbol,
            timeframe=self._timeframe,
            start=start,
            end=end,
        )


@dataclass(frozen=True)
class PositionSnapshot:
    """An immutable, point-in-time view of one open position."""

    symbol: str
    quantity: float  # signed: positive = long, negative = short
    avg_entry_price: float
    unrealized_pnl: float


@dataclass(frozen=True)
class PortfolioSnapshot:
    """An immutable, point-in-time view of the whole account."""

    cash: float
    equity: float
    positions: Mapping[str, PositionSnapshot]


@dataclass(frozen=True)
class StrategyContext:
    """Everything a strategy plugin receives for one market event."""

    timestamp: datetime
    exchange: str
    symbol: str
    current_candle: Candle
    history: HistoryView
    portfolio: PortfolioSnapshot
