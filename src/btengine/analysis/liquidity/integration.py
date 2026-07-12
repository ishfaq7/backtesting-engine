"""Adapters from the canonical data schema into this engine's own input types.

The engine itself only knows about this module's own ``*Observation``
types (:mod:`~btengine.analysis.liquidity.models`) so it stays reusable,
and so its own validator can detect missing/invalid readings that the
pydantic-validated canonical schema cannot represent. Each function here
accepts exactly the record type that flows into (or alongside) the
corresponding Feature Engineering Layer module, per this task's
"Integration with Feature Layer" requirement:

- :func:`liquidation_observations_from_records` — the same
  ``Sequence[Liquidation]`` that
  :class:`~btengine.features.pipeline.liquidation.LiquidationFeatures`
  consumes.
- :func:`ratio_observations_from_records` — the same
  ``Sequence[LongShortRatio]`` that
  :class:`~btengine.features.pipeline.long_short_ratio.LongShortRatioFeatures`
  consumes; used identically for the Global, Top Trader Account, and Top
  Trader Position ratio inputs (they share one canonical shape).
- :func:`open_interest_observations_from_records` — the same
  ``Sequence[OpenInterest]`` that
  :class:`~btengine.features.pipeline.open_interest.OpenInterestFeatures`
  consumes (read-only context here).
- :func:`price_observations_from_candles` — the same ``Sequence[Candle]``
  that :class:`~btengine.features.pipeline.price.PriceFeatures` consumes
  (read-only context here).

None of these filter by exchange or symbol — that's the caller's
responsibility (e.g. pass only the records for the symbol you want
analyzed); :class:`~btengine.analysis.liquidity.config.LiquidityAnalysisConfig.exchange_selection`
then narrows which exchanges are considered.
"""

from __future__ import annotations

from collections.abc import Sequence

from btengine.analysis.liquidity.models import (
    LiquidationObservation,
    OpenInterestObservation,
    PriceObservation,
    RatioObservation,
)
from btengine.data.schema import Candle, Liquidation, LongShortRatio, OpenInterest


def liquidation_observations_from_records(
    records: Sequence[Liquidation],
) -> list[LiquidationObservation]:
    """Convert canonical :class:`Liquidation` records into observations."""
    observations = [
        LiquidationObservation(
            timestamp=record.timestamp,
            exchange=record.exchange,
            long_liquidation_usd=record.long_liquidation_usd,
            short_liquidation_usd=record.short_liquidation_usd,
        )
        for record in records
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)


def ratio_observations_from_records(records: Sequence[LongShortRatio]) -> list[RatioObservation]:
    """Convert canonical :class:`LongShortRatio` records into observations."""
    observations = [
        RatioObservation(
            timestamp=record.timestamp,
            exchange=record.exchange,
            long_account_ratio=record.long_account_ratio,
            short_account_ratio=record.short_account_ratio,
        )
        for record in records
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)


def open_interest_observations_from_records(
    records: Sequence[OpenInterest],
) -> list[OpenInterestObservation]:
    """Convert canonical :class:`OpenInterest` records into observations."""
    observations = [
        OpenInterestObservation(
            timestamp=record.timestamp, exchange=record.exchange, open_interest=record.open_interest
        )
        for record in records
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)


def price_observations_from_candles(candles: Sequence[Candle]) -> list[PriceObservation]:
    """Convert canonical :class:`Candle` records into (close-price) observations."""
    observations = [
        PriceObservation(timestamp=candle.timestamp, exchange=candle.exchange, close=candle.close)
        for candle in candles
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)
