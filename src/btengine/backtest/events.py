"""Event types exchanged between the engine's components.

The engine is event-driven end to end: components never call each other's
internals directly for the market-data-to-signal path — they communicate
only through these immutable event objects, pushed through
:class:`~btengine.backtest.event_loop.EventLoop`. This module defines the
data (what happened), never behavior (what to do about it) — that belongs
to the handlers in :mod:`~btengine.backtest.engine`.

``SignalEvent`` is the one type a strategy plugin returns, so it is
intentionally minimal and free of any strategy-specific vocabulary: a
symbol, a direction, and an optional size. The engine has no opinion on
*why* a signal was produced.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from btengine.data.schema import Candle


@dataclass(frozen=True)
class Event:
    """Base type for everything that flows through the event loop."""

    timestamp: datetime


@dataclass(frozen=True)
class MarketEvent(Event):
    """A new, fully-closed candle is available for processing."""

    candle: Candle

    @classmethod
    def from_candle(cls, candle: Candle) -> "MarketEvent":
        return cls(timestamp=candle.timestamp, candle=candle)

    @property
    def exchange(self) -> str:
        return self.candle.exchange

    @property
    def symbol(self) -> str:
        return self.candle.symbol


class SignalAction(str, Enum):
    """The only vocabulary a strategy plugin may use to express intent."""

    ENTER_LONG = "ENTER_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    EXIT = "EXIT"


@dataclass(frozen=True)
class SignalEvent(Event):
    """A strategy's requested action for one symbol, returned from ``on_market_event``."""

    symbol: str
    action: SignalAction
    quantity: float | None = None  # required for ENTER_*; ignored for EXIT
    metadata: Mapping[str, Any] = field(default_factory=dict)


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class OrderEvent(Event):
    """A validated, engine-generated order, queued for execution on the next bar."""

    symbol: str
    side: OrderSide
    quantity: float


@dataclass(frozen=True)
class FillEvent(Event):
    """The simulated execution result of an :class:`OrderEvent`."""

    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    fee: float
