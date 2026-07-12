"""Adapters from upstream layers into this engine's own input type.

The engine itself only knows about
:class:`~btengine.analysis.open_interest.models.OpenInterestObservation`
so it stays reusable independent of any one upstream shape, and equally
usable for an exchange-specific series or an aggregated one. These
functions are the two supported integration points:

- :func:`observations_from_feature_values` — the normal path, consuming
  the ``open_interest`` :class:`~btengine.features.base.FeatureValue`
  series produced by
  :class:`~btengine.features.pipeline.open_interest.OpenInterestFeatures`
  (the Feature Engineering Layer).
- :func:`observations_from_open_interest_records` — a direct path from
  the canonical :class:`~btengine.data.schema.OpenInterest` records, for
  callers that have raw Data Layer output and no Feature Layer stage in
  between.
"""

from __future__ import annotations

from collections.abc import Sequence

from btengine.analysis.open_interest.models import OpenInterestObservation
from btengine.data.schema import OpenInterest
from btengine.features.base import FeatureValue


def observations_from_feature_values(
    values: Sequence[FeatureValue],
) -> list[OpenInterestObservation]:
    """Convert an ``open_interest`` :class:`FeatureValue` series into observations.

    Callers are expected to have already filtered ``values`` down to one
    feature series (e.g. everything with ``feature_name ==
    "open_interest.open_interest"``) for one symbol and one Open Interest
    source (exchange-specific or aggregated); this function does not
    filter by name or symbol itself since it has no opinion on which
    source the caller wants.
    """
    observations = [
        OpenInterestObservation(timestamp=value.timestamp, open_interest=value.value)
        for value in values
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)


def observations_from_open_interest_records(
    records: Sequence[OpenInterest],
) -> list[OpenInterestObservation]:
    """Convert canonical :class:`OpenInterest` records into observations."""
    observations = [
        OpenInterestObservation(timestamp=record.timestamp, open_interest=record.open_interest)
        for record in records
    ]
    return sorted(observations, key=lambda observation: observation.timestamp)
