"""Structured error hierarchy for the Core Backtesting Engine.

Kept separate from ``btengine.data.errors`` since the data layer and the
engine are independent bounded contexts — the engine never needs to know
about CoinGlass-specific failure modes, only its own.
"""

from __future__ import annotations

from typing import Any


class BacktestEngineError(Exception):
    """Base class for every exception raised by ``btengine.backtest``."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class EngineConfigurationError(BacktestEngineError):
    """A backtest run was configured with missing or invalid parameters."""


class ClockError(BacktestEngineError):
    """The simulation clock was asked to move in an invalid way (e.g. backwards)."""


class UnknownEventError(BacktestEngineError):
    """The event loop was asked to dispatch an event type it does not recognize."""
