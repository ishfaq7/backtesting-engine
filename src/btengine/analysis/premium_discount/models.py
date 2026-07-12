"""Data types for the Premium & Discount Analysis Engine.

:class:`CandleObservation` is the engine's own minimal input type —
deliberately decoupled from the canonical
:class:`~btengine.data.schema.Candle` (which is pydantic-validated and
cannot represent a missing/invalid bar) so this module's own validator
can detect and report exactly those problems, and so the engine stays
reusable outside the canonical schema.

:class:`PremiumDiscountAnalysis` is this module's only output type.
Every field is a descriptive statistic about where price sits within a
historically identified trading range — never a trade signal, a score,
or an entry/exit decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True)
class CandleObservation:
    """One OHLC bar at one point in time.

    ``high``/``low``/``close`` are ``None`` to explicitly represent a
    known-missing reading (as opposed to omitting the timestamp
    entirely, which would make a gap indistinguishable from "no candle
    was ever expected here"). Unlike the canonical
    :class:`~btengine.data.schema.Candle`, this type does not validate
    that ``high >= low`` — that is instead a data-quality problem this
    module's validator can flag.
    """

    timestamp: datetime
    high: float | None
    low: float | None
    close: float | None


class SwingKind(str, Enum):
    """Which side of a range a detected swing point represents."""

    HIGH = "HIGH"
    LOW = "LOW"


@dataclass(frozen=True)
class SwingPoint:
    """One confirmed swing high or swing low."""

    timestamp: datetime
    price: float
    kind: SwingKind


class PremiumDiscountZone(str, Enum):
    """Where the current price sits relative to the active trading range.

    A purely descriptive classification of position within a historical
    range — never a bullish/bearish judgment or a trade signal.
    """

    DISCOUNT = "DISCOUNT"
    EQUILIBRIUM = "EQUILIBRIUM"
    PREMIUM = "PREMIUM"
    ABOVE_RANGE = "ABOVE_RANGE"  # price has broken above the identified active high
    BELOW_RANGE = "BELOW_RANGE"  # price has broken below the identified active low


@dataclass(frozen=True)
class PremiumDiscountAnalysis:
    """Standardized analytical summary of a Premium & Discount range.

    ``timeframe`` identifies which candle timeframe this summarizes
    (e.g. ``"1h"``, ``"4h"``) — the engine that produced this is generic
    over any single timeframe; multi-timeframe analysis is supported by
    running one engine instance per timeframe (see
    ``docs/PREMIUM_DISCOUNT_ANALYSIS_MODULE.md`` §Multi-timeframe
    support).

    Every numeric field is a plain statistic; none of them are trade
    signals, scores, or entry/exit decisions. ``confidence_level`` is a
    *data-sufficiency* measure (how much of the configured lookback was
    actually satisfied by the given history), not a trading-confidence
    score.
    """

    symbol: str
    timeframe: str
    as_of: datetime

    active_high: float
    active_low: float
    range_size: float
    midpoint: float

    current_price: float
    current_price_position_pct: float

    zone: PremiumDiscountZone

    premium_percentage: float | None
    discount_percentage: float | None

    sample_size: int
    confidence_level: float

    def to_feature_map(self) -> dict[str, float]:
        """Flatten the numeric fields into a namespaced ``name -> value`` map.

        Intended for the Strategy Framework's
        :class:`~btengine.strategy.rules.primitives.RuleCondition.feature`
        lookup (see ``docs/PREMIUM_DISCOUNT_ANALYSIS_MODULE.md``
        §Integration with the Strategy Framework) once a condition
        evaluator exists. ``zone`` (categorical) is one-hot encoded into
        ``zone_is_<value>`` flags (``1.0``/``0.0``) so every field a
        condition might reference is numeric. ``None`` values are
        omitted (a field that couldn't be computed doesn't exist yet,
        rather than existing with a placeholder value).
        """
        prefix = f"premium_discount_analysis_{self.timeframe}"
        candidates: dict[str, float | None] = {
            f"{prefix}.active_high": self.active_high,
            f"{prefix}.active_low": self.active_low,
            f"{prefix}.range_size": self.range_size,
            f"{prefix}.midpoint": self.midpoint,
            f"{prefix}.current_price": self.current_price,
            f"{prefix}.current_price_position_pct": self.current_price_position_pct,
            f"{prefix}.premium_percentage": self.premium_percentage,
            f"{prefix}.discount_percentage": self.discount_percentage,
            f"{prefix}.confidence_level": self.confidence_level,
        }
        feature_map = {name: value for name, value in candidates.items() if value is not None}
        for zone in PremiumDiscountZone:
            feature_map[f"{prefix}.zone_is_{zone.value.lower()}"] = 1.0 if self.zone is zone else 0.0
        return feature_map
