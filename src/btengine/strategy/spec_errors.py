"""Errors for the Strategy Specification Framework."""

from __future__ import annotations


class StrategySpecError(Exception):
    """Base class for every exception raised loading or validating a
    :class:`~btengine.strategy.spec.StrategySpec`."""


class SpecLoadError(StrategySpecError):
    """A spec file was missing, malformed, or failed schema validation."""
