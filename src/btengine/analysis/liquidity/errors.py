"""Structured errors for the Liquidity Analysis Engine."""

from __future__ import annotations


class LiquidityAnalysisError(Exception):
    """Raised when the engine cannot produce a :class:`LiquidityAnalysis`."""
