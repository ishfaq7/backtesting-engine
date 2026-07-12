"""Premium & Discount score provider — framework only.

Turning a :class:`~btengine.analysis.premium_discount.models.PremiumDiscountAnalysis`
into a single score requires deciding which of its fields matter and how
much — that decision is the strategy owner's proprietary scoring logic,
not something this framework may invent. :meth:`PremiumDiscountScoreProvider.compute`
therefore raises ``NotImplementedError`` until the owner supplies it.
"""

from __future__ import annotations

from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis
from btengine.scoring.models import ScoreComponent
from btengine.scoring.providers.base import ScoreProvider


class PremiumDiscountScoreProvider(ScoreProvider[PremiumDiscountAnalysis]):
    """Placeholder for the premium/discount-analysis-derived score."""

    def __init__(self, *, version: str = "unversioned") -> None:
        self._version = version

    @property
    def provider_name(self) -> str:
        return "premium_discount"

    @property
    def provider_version(self) -> str:
        return self._version

    def compute(self, analysis: PremiumDiscountAnalysis) -> ScoreComponent:
        raise NotImplementedError(
            "Premium & Discount score computation is not implemented. This "
            "is the proprietary scoring formula the strategy owner must "
            "supply; the framework only defines where it plugs in."
        )
