"""The Feature Store's contract: persist and query engineered feature values.

Separate from :class:`btengine.data.repository.DataRepository` (which
stores raw canonical market data) because it's a distinct concern — this
stores *derived* values a :class:`~btengine.features.base.FeatureAnalyzer`
computed, keyed by symbol, feature name, and time, so expensive feature
computations don't need to be repeated across research runs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from btengine.features.base import FeatureValue


class FeatureStore(ABC):
    """Abstract contract for persisting and querying computed features."""

    @abstractmethod
    def write(self, values: Sequence[FeatureValue]) -> None:
        """Persist ``values``, merging with anything already stored for the
        same (symbol, feature_name), deduplicated by timestamp.
        """

    @abstractmethod
    def read(
        self, *, symbol: str, feature_name: str, start: datetime, end: datetime
    ) -> list[FeatureValue]:
        """Return stored values for ``symbol``/``feature_name`` in ``[start, end]``."""
