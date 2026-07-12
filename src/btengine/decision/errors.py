"""Structured errors for the Decision Engine Framework."""

from __future__ import annotations


class DecisionEngineError(Exception):
    """Base class for every exception raised by :mod:`btengine.decision`."""


class DecisionEngineConfigError(DecisionEngineError):
    """A :class:`~btengine.decision.config.DecisionEngineConfig` failed to load or validate."""
