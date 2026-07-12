"""Structured errors for the Premium & Discount Analysis Engine."""

from __future__ import annotations


class PremiumDiscountAnalysisError(Exception):
    """Raised when the engine cannot produce a :class:`PremiumDiscountAnalysis`."""
