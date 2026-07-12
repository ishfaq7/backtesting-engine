"""Open Interest score provider — framework only.

Turning an :class:`~btengine.analysis.open_interest.models.OpenInterestAnalysis`
into a single score requires deciding which of its fields matter and how
much — that decision is the strategy owner's proprietary scoring logic,
not something this framework may invent. :meth:`OpenInterestScoreProvider.compute`
therefore raises ``NotImplementedError`` until the owner supplies it.
"""

from __future__ import annotations

from btengine.analysis.open_interest.models import OpenInterestAnalysis
from btengine.scoring.models import ScoreComponent
from btengine.scoring.providers.base import ScoreProvider


class OpenInterestScoreProvider(ScoreProvider[OpenInterestAnalysis]):
    """Placeholder for the open-interest-analysis-derived score."""

    def __init__(self, *, version: str = "unversioned") -> None:
        self._version = version

    @property
    def provider_name(self) -> str:
        return "open_interest"

    @property
    def provider_version(self) -> str:
        return self._version

    def compute(self, analysis: OpenInterestAnalysis) -> ScoreComponent:
        raise NotImplementedError(
            "Open Interest score computation is not implemented. This is "
            "the proprietary scoring formula the strategy owner must "
            "supply; the framework only defines where it plugs in."
        )
