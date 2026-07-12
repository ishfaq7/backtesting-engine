"""Adapter from the canonical candle schema into this engine's own input type.

The engine itself only knows about
:class:`~btengine.analysis.premium_discount.models.CandleObservation` so
it stays reusable and so its own validator can detect missing/invalid
candles that the pydantic-validated canonical
:class:`~btengine.data.schema.Candle` cannot represent.

:func:`observations_from_candles` is the Feature Layer integration
point: it accepts exactly the ``Sequence[Candle]`` type that
:class:`~btengine.features.pipeline.price.PriceFeatures` (the Feature
Engineering Layer's price module) consumes — the same normalized,
canonical OHLC series that flows through that layer — rather than a
:class:`~btengine.features.base.FeatureValue` series, since a full OHLC
bar is not itself a single named feature value.
"""

from __future__ import annotations

from collections.abc import Sequence

from btengine.analysis.premium_discount.models import CandleObservation
from btengine.data.schema import Candle


def observations_from_candles(candles: Sequence[Candle]) -> list[CandleObservation]:
    """Convert canonical :class:`Candle` records into observations."""
    observations = [
        CandleObservation(
            timestamp=candle.timestamp, high=candle.high, low=candle.low, close=candle.close
        )
        for candle in candles
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)
