"""Structured errors for the Funding Rate Analysis Engine."""

from __future__ import annotations


class FundingRateAnalysisError(Exception):
    """Raised when the engine cannot produce a :class:`FundingAnalysis`."""
