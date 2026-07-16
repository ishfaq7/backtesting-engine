"""Structured errors for the No Trade Framework."""

from __future__ import annotations


class NoTradeEngineError(Exception):
    """Base class for every exception raised by :mod:`btengine.no_trade`."""


class NoTradeEngineConfigError(NoTradeEngineError):
    """A :class:`~btengine.no_trade.config.NoTradeEngineConfig` failed to load or validate."""
