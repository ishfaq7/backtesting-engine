"""Data types for the Funding Rate Analysis Engine.

:class:`FundingRateObservation` is the engine's own minimal input type —
deliberately decoupled from both the canonical
:class:`~btengine.data.schema.FundingRate` (provider/exchange-specific)
and the Feature Layer's generic
:class:`~btengine.features.base.FeatureValue` (symbol/feature-name/version
namespaced) — so this engine stays reusable outside either of those
shapes. :mod:`~btengine.analysis.funding_rate.integration` adapts both of
those into this type.

:class:`FundingAnalysis` is this module's only output type. Every field
is a descriptive statistic about the funding rate series itself
(direction, dispersion, historical range, how much data backed the
result) — never a trade signal, a score, or a bullish/bearish judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True)
class FundingRateObservation:
    """One funding rate reading at one point in time.

    ``funding_rate`` is ``None`` to explicitly represent a known-missing
    reading (as opposed to omitting the timestamp entirely, which would
    make a gap indistinguishable from "no data was ever expected here").
    """

    timestamp: datetime
    funding_rate: float | None


class FundingDirection(str, Enum):
    """The sign of a computed trend/momentum value — a mathematical fact
    about the series, not a trading interpretation of it.
    """

    RISING = "RISING"
    FALLING = "FALLING"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"  # insufficient data to compute


@dataclass(frozen=True)
class FundingAnalysis:
    """Standardized analytical summary of a funding rate history.

    Every numeric field is a plain statistic; none of them are trade
    signals, scores, or bullish/bearish calls. ``confidence_level`` is a
    *data-sufficiency* measure (how much of the configured lookback
    windows were actually satisfied by the given history), not a
    trading-confidence score.
    """

    symbol: str
    as_of: datetime

    current_funding: float
    previous_funding: float | None
    funding_change: float | None
    funding_change_pct: float | None

    funding_trend: FundingDirection
    funding_trend_value: float | None

    funding_momentum: FundingDirection
    funding_momentum_value: float | None

    funding_volatility: float | None

    historical_average: float | None
    historical_maximum: float | None
    historical_minimum: float | None

    sample_size: int
    confidence_level: float

    def to_feature_map(self) -> dict[str, float]:
        """Flatten the numeric fields into a namespaced ``name -> value`` map.

        Intended for the Strategy Framework's
        :class:`~btengine.strategy.rules.primitives.RuleCondition.feature`
        lookup (see ``docs/FUNDING_RATE_ANALYSIS_MODULE.md`` §Integration
        with the Strategy Framework) once a condition evaluator exists.
        Only numeric fields are included; ``None`` values are omitted
        (a feature that couldn't be computed doesn't exist yet, rather
        than existing with a placeholder value).
        """
        candidates = {
            "funding_rate_analysis.current_funding": self.current_funding,
            "funding_rate_analysis.previous_funding": self.previous_funding,
            "funding_rate_analysis.funding_change": self.funding_change,
            "funding_rate_analysis.funding_change_pct": self.funding_change_pct,
            "funding_rate_analysis.funding_trend_value": self.funding_trend_value,
            "funding_rate_analysis.funding_momentum_value": self.funding_momentum_value,
            "funding_rate_analysis.funding_volatility": self.funding_volatility,
            "funding_rate_analysis.historical_average": self.historical_average,
            "funding_rate_analysis.historical_maximum": self.historical_maximum,
            "funding_rate_analysis.historical_minimum": self.historical_minimum,
            "funding_rate_analysis.confidence_level": self.confidence_level,
        }
        return {name: value for name, value in candidates.items() if value is not None}
