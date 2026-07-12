"""Data types for the Liquidity Analysis Engine.

The four ``*Observation`` types are this module's own minimal input
types — deliberately decoupled from the canonical
:class:`~btengine.data.schema.CanonicalRecord` subclasses (pydantic
validated, cannot represent a missing reading) so this module's own
validator can detect and report exactly those problems, and so the
engine stays reusable outside the canonical schema. Each carries its own
``exchange`` field since this engine analyzes across (and compares
between) multiple exchanges — see
:mod:`~btengine.analysis.liquidity.integration` for how they're built
from canonical records.

:class:`LiquidityAnalysis` is this module's only output type. Every
field is a descriptive statistic about liquidation activity, positioning,
and open-interest/price context — never a trade signal, a composite
score, or an entry/exit decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LiquidationObservation:
    """One liquidation reading for one exchange at one point in time."""

    timestamp: datetime
    exchange: str
    long_liquidation_usd: float | None
    short_liquidation_usd: float | None


@dataclass(frozen=True)
class RatioObservation:
    """One long/short account-ratio reading for one exchange at one point in time.

    Used uniformly for the Global Long/Short Ratio, Top Trader Account
    Ratio, and Top Trader Position Ratio inputs — all three share this
    shape (see :mod:`~btengine.data.schema.LongShortRatio`); which source
    a given series represents is determined entirely by which keyword
    argument it's passed under in
    :meth:`~btengine.analysis.liquidity.engine.LiquidityAnalysisEngine.analyze`.
    """

    timestamp: datetime
    exchange: str
    long_account_ratio: float | None
    short_account_ratio: float | None


@dataclass(frozen=True)
class OpenInterestObservation:
    """One Open Interest reading for one exchange at one point in time.

    Read-only context input for this module — deep Open Interest
    analysis (trend, momentum, volatility, spikes) is
    :mod:`btengine.analysis.open_interest`'s responsibility, not this
    module's.
    """

    timestamp: datetime
    exchange: str
    open_interest: float | None


@dataclass(frozen=True)
class PriceObservation:
    """One closing price reading for one exchange at one point in time.

    Read-only context input for this module — range/zone analysis is
    :mod:`btengine.analysis.premium_discount`'s responsibility, not this
    module's.
    """

    timestamp: datetime
    exchange: str
    close: float | None


@dataclass(frozen=True)
class LiquidityAnalysis:
    """Standardized analytical summary of market liquidity behavior.

    Every numeric field is a plain statistic; none of them are trade
    signals, composite scores, or entry/exit decisions.
    ``confidence_level`` is a *data-sufficiency* measure, not a
    trading-confidence score. ``liquidation_bias``/``top_trader_*_bias``
    describe which side of a series is currently larger — a fact about
    the data, never a bullish/bearish judgment.
    """

    symbol: str
    as_of: datetime
    sample_size: int
    confidence_level: float

    # Liquidation Events / Long / Short / Imbalance / Intensity
    long_liquidation_volume: float
    short_liquidation_volume: float
    total_liquidation_volume: float
    liquidation_event_count: int
    liquidation_bias: float | None
    liquidation_intensity: float | None
    is_abnormal_liquidation: bool | None

    # Long/Short Positioning
    long_short_ratio: float | None
    top_trader_account_bias: float | None
    top_trader_position_bias: float | None
    top_trader_bias: float | None

    # Crowded Market Conditions
    market_crowdedness: float | None

    # Market Participation (Open Interest, read-only context)
    market_participation: float | None
    current_open_interest: float | None

    # Price (read-only context)
    current_price: float | None

    # Liquidity Pressure / Shift
    liquidity_pressure: float | None
    liquidity_shift: float | None

    # Exchange Comparison
    exchange_liquidation_totals: dict[str, float] = field(default_factory=dict)

    def to_feature_map(self) -> dict[str, float]:
        """Flatten the numeric fields into a namespaced ``name -> value`` map.

        Intended for the Strategy Framework's
        :class:`~btengine.strategy.rules.primitives.RuleCondition.feature`
        lookup (see ``docs/LIQUIDITY_ANALYSIS_MODULE.md`` §Integration
        with the Strategy Framework) once a condition evaluator exists.
        ``is_abnormal_liquidation`` is represented as ``1.0``/``0.0`` when
        known; ``exchange_liquidation_totals`` is flattened into one key
        per exchange. ``None`` values are omitted (a feature that
        couldn't be computed doesn't exist yet, rather than existing with
        a placeholder value).
        """
        prefix = "liquidity_analysis"
        candidates: dict[str, float | None] = {
            f"{prefix}.long_liquidation_volume": self.long_liquidation_volume,
            f"{prefix}.short_liquidation_volume": self.short_liquidation_volume,
            f"{prefix}.total_liquidation_volume": self.total_liquidation_volume,
            f"{prefix}.liquidation_event_count": float(self.liquidation_event_count),
            f"{prefix}.liquidation_bias": self.liquidation_bias,
            f"{prefix}.liquidation_intensity": self.liquidation_intensity,
            f"{prefix}.long_short_ratio": self.long_short_ratio,
            f"{prefix}.top_trader_account_bias": self.top_trader_account_bias,
            f"{prefix}.top_trader_position_bias": self.top_trader_position_bias,
            f"{prefix}.top_trader_bias": self.top_trader_bias,
            f"{prefix}.market_crowdedness": self.market_crowdedness,
            f"{prefix}.market_participation": self.market_participation,
            f"{prefix}.current_open_interest": self.current_open_interest,
            f"{prefix}.current_price": self.current_price,
            f"{prefix}.liquidity_pressure": self.liquidity_pressure,
            f"{prefix}.liquidity_shift": self.liquidity_shift,
            f"{prefix}.confidence_level": self.confidence_level,
        }
        feature_map = {name: value for name, value in candidates.items() if value is not None}
        if self.is_abnormal_liquidation is not None:
            feature_map[f"{prefix}.is_abnormal_liquidation"] = (
                1.0 if self.is_abnormal_liquidation else 0.0
            )
        for exchange, total in self.exchange_liquidation_totals.items():
            feature_map[f"{prefix}.exchange_liquidation_total.{exchange}"] = total
        return feature_map
