"""Liquidity score provider — framework only.

Turning a :class:`~btengine.analysis.liquidity.models.LiquidityAnalysis`
into a single score requires deciding which of its fields matter and how
much — that decision is the strategy owner's proprietary scoring logic,
not something this framework may invent. :meth:`LiquidityScoreProvider.compute`
therefore raises ``NotImplementedError`` until the owner supplies it.
"""

from __future__ import annotations

from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.scoring.models import ScoreComponent
from btengine.scoring.providers.base import ScoreProvider


class LiquidityScoreProvider(ScoreProvider[LiquidityAnalysis]):
    """Placeholder for the liquidity-analysis-derived score."""

    def __init__(self, *, version: str = "unversioned") -> None:
        self._version = version

    @property
    def provider_name(self) -> str:
        return "liquidity"

    @property
    def provider_version(self) -> str:
        return self._version

    def compute(self, analysis: LiquidityAnalysis) -> ScoreComponent:
        raise NotImplementedError(
            "Liquidity score computation is not implemented. This is the "
            "proprietary scoring formula the strategy owner must supply; "
            "the framework only defines where it plugs in."
        )
