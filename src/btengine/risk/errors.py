"""Structured errors for the Risk Management Framework."""

from __future__ import annotations


class RiskEngineError(Exception):
    """Base class for every exception raised by :mod:`btengine.risk`."""


class RiskEngineConfigError(RiskEngineError):
    """A :class:`~btengine.risk.config.RiskEngineConfig` failed to load or validate."""
