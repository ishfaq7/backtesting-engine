"""Data types for the Open Interest Analysis Engine.

:class:`OpenInterestObservation` is the engine's own minimal input type —
deliberately decoupled from both the canonical
:class:`~btengine.data.schema.OpenInterest` (provider/exchange-specific)
and the Feature Layer's generic
:class:`~btengine.features.base.FeatureValue` (symbol/feature-name/version
namespaced) — so this engine stays reusable outside either of those
shapes, and equally applicable whether the underlying series is one
exchange's Open Interest or a cross-exchange aggregate.
:mod:`~btengine.analysis.open_interest.integration` adapts both of those
into this type.

:class:`OpenInterestAnalysis` is this module's only output type. Every
field is a descriptive statistic about the Open Interest series itself
(direction, dispersion, historical range, whether the latest change was
statistically unusual, how much data backed the result) — never a trade
signal, a score, or a bullish/bearish judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True)
class OpenInterestObservation:
    """One Open Interest reading at one point in time.

    ``open_interest`` is ``None`` to explicitly represent a known-missing
    reading (as opposed to omitting the timestamp entirely, which would
    make a gap indistinguishable from "no data was ever expected here").
    """

    timestamp: datetime
    open_interest: float | None


class OiDirection(str, Enum):
    """The sign of a computed trend/momentum value — a mathematical fact
    about the series, not a trading interpretation of it.
    """

    RISING = "RISING"
    FALLING = "FALLING"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"  # insufficient data to compute


@dataclass(frozen=True)
class OpenInterestAnalysis:
    """Standardized analytical summary of an Open Interest history.

    ``source`` identifies which Open Interest series this summarizes
    (e.g. ``"aggregated"`` for the cross-exchange total, or an exchange
    name for an exchange-specific series) — the engine that produced this
    is generic over both.

    Every numeric field is a plain statistic; none of them are trade
    signals, scores, or bullish/bearish calls. ``is_abnormal_spike`` is a
    statistical-outlier flag on the *latest change*, gated behind an
    explicit, unset-by-default configuration threshold — it is never
    computed from an assumed default. ``confidence_level`` is a
    *data-sufficiency* measure (how much of the configured lookback
    windows were actually satisfied by the given history), not a
    trading-confidence score.
    """

    symbol: str
    source: str
    as_of: datetime

    current_oi: float
    previous_oi: float | None
    oi_change: float | None
    oi_change_pct: float | None

    oi_trend: OiDirection
    oi_trend_value: float | None

    oi_momentum: OiDirection
    oi_momentum_value: float | None

    oi_volatility: float | None

    is_abnormal_spike: bool | None
    spike_magnitude: float | None

    historical_average: float | None
    historical_maximum: float | None
    historical_minimum: float | None

    sample_size: int
    confidence_level: float

    def to_feature_map(self) -> dict[str, float]:
        """Flatten the numeric fields into a namespaced ``name -> value`` map.

        Intended for the Strategy Framework's
        :class:`~btengine.strategy.rules.primitives.RuleCondition.feature`
        lookup (see ``docs/OPEN_INTEREST_ANALYSIS_MODULE.md`` §Integration
        with the Strategy Framework) once a condition evaluator exists.
        Only numeric fields are included (``is_abnormal_spike`` is a
        boolean flag, represented as ``1.0``/``0.0`` when known); ``None``
        values are omitted (a feature that couldn't be computed doesn't
        exist yet, rather than existing with a placeholder value).
        """
        prefix = f"open_interest_analysis_{self.source}"
        candidates: dict[str, float | None] = {
            f"{prefix}.current_oi": self.current_oi,
            f"{prefix}.previous_oi": self.previous_oi,
            f"{prefix}.oi_change": self.oi_change,
            f"{prefix}.oi_change_pct": self.oi_change_pct,
            f"{prefix}.oi_trend_value": self.oi_trend_value,
            f"{prefix}.oi_momentum_value": self.oi_momentum_value,
            f"{prefix}.oi_volatility": self.oi_volatility,
            f"{prefix}.spike_magnitude": self.spike_magnitude,
            f"{prefix}.historical_average": self.historical_average,
            f"{prefix}.historical_maximum": self.historical_maximum,
            f"{prefix}.historical_minimum": self.historical_minimum,
            f"{prefix}.confidence_level": self.confidence_level,
        }
        if self.is_abnormal_spike is not None:
            candidates[f"{prefix}.is_abnormal_spike"] = 1.0 if self.is_abnormal_spike else 0.0
        return {name: value for name, value in candidates.items() if value is not None}
