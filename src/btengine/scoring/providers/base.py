"""The Score Provider contract: "Independent Score Providers."

Each provider turns exactly one analyzer's standardized output
(:class:`~btengine.analysis.funding_rate.models.FundingAnalysis`,
:class:`~btengine.analysis.open_interest.models.OpenInterestAnalysis`,
:class:`~btengine.analysis.premium_discount.models.PremiumDiscountAnalysis`,
or :class:`~btengine.analysis.liquidity.models.LiquidityAnalysis`) into
one :class:`~btengine.scoring.models.ScoreComponent` — nothing more. A
provider never sees another provider's output, never aggregates, never
decides a total score; that separation is what makes each one
independently testable, independently replaceable (dependency
injection, per :class:`~btengine.scoring.engine.ScoringEngine`'s
constructor), and independently versioned.

Every concrete provider shipped in :mod:`btengine.scoring.providers`
raises ``NotImplementedError`` from :meth:`compute` — this task is
explicit that the actual scoring formula (what makes a funding reading
"good" or "bad," what weight a factor deserves) is the strategy owner's
proprietary content, not something this framework may invent. See each
concrete provider's docstring.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from btengine.scoring.models import ScoreComponent

TAnalysis = TypeVar("TAnalysis")


class ScoreProvider(ABC, Generic[TAnalysis]):
    """Turns one analyzer's output into one :class:`ScoreComponent`."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """A stable, unique name for this provider (e.g. ``"funding"``).

        Used as the key the :class:`~btengine.scoring.engine.ScoringEngine`
        looks up this provider's configured weight/priority under (see
        :class:`~btengine.scoring.config.ScoreWeights`/``ScorePriorities``).
        """

    @property
    @abstractmethod
    def provider_version(self) -> str:
        """Identifies which revision of this provider's (not-yet-written)
        scoring formula produced a given :class:`ScoreComponent` — the
        same versioning discipline the Feature Store's
        ``FeatureValue.version`` already established, checked for
        consistency by
        :class:`~btengine.scoring.validation.StrategyScoreValidator`'s
        "version mismatch" check.
        """

    @abstractmethod
    def compute(self, analysis: TAnalysis) -> ScoreComponent:
        """Compute this provider's :class:`ScoreComponent` for ``analysis``."""
