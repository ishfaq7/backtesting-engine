"""Dynamic Score Aggregation: combining independently-computed
:class:`~btengine.scoring.models.ScoreComponent` objects into one
``total_score``.

:class:`ScoreAggregator` is pluggable so a future aggregation strategy
(a nonlinear blend, an AI/ML model — see
``docs/SCORING_ENGINE_FRAMEWORK.md`` §Future Extension Points) can be
substituted into :class:`~btengine.scoring.engine.ScoringEngine` via
dependency injection without changing it.

:class:`WeightedSumAggregator` is the one concrete implementation
shipped here: a generic Σ(weight × value) / Σ(weight) combination — a
structural mathematical operation, not a trading rule, in the same
spirit as the z-score/linear-regression helpers used throughout the
analysis modules. It contributes no opinion about what weight any
component *should* have (every weight is a placeholder — see
:class:`~btengine.scoring.config.ScoreWeights`) and refuses to produce a
number when a weight or a value is missing, rather than silently
defaulting to zero or an equal share.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from btengine.scoring.config import ScoreWeights
from btengine.scoring.models import FeatureStatus, ScoreComponent


class ScoreAggregator(ABC):
    """Combines a set of named :class:`ScoreComponent` objects into one total."""

    @abstractmethod
    def aggregate(
        self, components: Mapping[str, ScoreComponent | None], weights: ScoreWeights
    ) -> float | None:
        """Return the combined score, or ``None`` if it cannot be honestly computed."""


class WeightedSumAggregator(ScoreAggregator):
    """``sum(weight_i * value_i) / sum(weight_i)`` over every given component.

    Only responsible for the arithmetic: a ``None`` entry in
    ``components`` (an unavailable input — see
    :attr:`~btengine.scoring.models.FeatureStatus`) is excluded, not
    treated as zero. Deciding *which* components are trustworthy enough
    to include is the caller's job (:class:`~btengine.scoring.engine.ScoringEngine`
    only passes components whose status is
    :attr:`~btengine.scoring.models.FeatureStatus.AVAILABLE`). Returns
    ``None`` if there are no non-``None`` components, if any of them has
    no configured weight or value, or if every configured weight is zero.
    """

    def aggregate(
        self, components: Mapping[str, ScoreComponent | None], weights: ScoreWeights
    ) -> float | None:
        available = {
            name: component
            for name, component in components.items()
            if component is not None
        }
        if not available:
            return None

        weighted_total = 0.0
        weight_total = 0.0
        for name, component in available.items():
            weight = weights.get(name)
            if weight is None or component.value is None:
                return None
            weighted_total += weight * component.value
            weight_total += weight

        if weight_total == 0:
            return None
        return weighted_total / weight_total
