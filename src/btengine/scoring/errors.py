"""Structured errors for the Scoring Engine Framework."""

from __future__ import annotations


class ScoringError(Exception):
    """Base class for every exception raised by :mod:`btengine.scoring`."""


class ScoringConfigError(ScoringError):
    """A :class:`~btengine.scoring.config.ScoringEngineConfig` failed to load or validate."""
