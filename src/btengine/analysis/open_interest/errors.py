"""Structured errors for the Open Interest Analysis Engine."""

from __future__ import annotations


class OpenInterestAnalysisError(Exception):
    """Raised when the engine cannot produce an :class:`OpenInterestAnalysis`."""
