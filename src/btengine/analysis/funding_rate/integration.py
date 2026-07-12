"""Adapters from upstream layers into this engine's own input type.

The engine itself only knows about :class:`~btengine.analysis.funding_rate.models.FundingRateObservation`
so it stays reusable independent of any one upstream shape. These
functions are the two supported integration points:

- :func:`observations_from_feature_values` — the normal path, consuming
  the ``funding_rate`` :class:`~btengine.features.base.FeatureValue`
  series produced by
  :class:`~btengine.features.pipeline.funding.FundingFeatures` (the
  Feature Engineering Layer).
- :func:`observations_from_funding_rates` — a direct path from the
  canonical :class:`~btengine.data.schema.FundingRate` records, for
  callers that have raw Data Layer output and no Feature Layer stage in
  between.
"""

from __future__ import annotations

from collections.abc import Sequence

from btengine.analysis.funding_rate.models import FundingRateObservation
from btengine.data.schema import FundingRate
from btengine.features.base import FeatureValue


def observations_from_feature_values(
    values: Sequence[FeatureValue],
) -> list[FundingRateObservation]:
    """Convert a ``funding_rate`` :class:`FeatureValue` series into observations.

    Callers are expected to have already filtered ``values`` down to one
    feature series (e.g. everything with ``feature_name ==
    "funding_standard.funding_rate"``) for one symbol; this function does
    not filter by name or symbol itself since it has no opinion on which
    funding source the caller wants.
    """
    observations = [
        FundingRateObservation(timestamp=value.timestamp, funding_rate=value.value)
        for value in values
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)


def observations_from_funding_rates(
    records: Sequence[FundingRate],
) -> list[FundingRateObservation]:
    """Convert canonical :class:`FundingRate` records into observations."""
    observations = [
        FundingRateObservation(timestamp=record.timestamp, funding_rate=record.funding_rate)
        for record in records
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)
