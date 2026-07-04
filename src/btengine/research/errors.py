"""Structured errors for the quantitative research tooling package."""

from __future__ import annotations


class ResearchError(Exception):
    """Base class for every exception raised by ``btengine.research``."""


class ValidationConfigError(ResearchError):
    """A walk-forward/Monte Carlo/batch run was configured invalidly."""
