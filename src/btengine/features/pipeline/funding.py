"""Funding rate feature module.

Handles both the standard funding-rate endpoint and the OI-weighted
variant, since both map to the same canonical
:class:`~btengine.data.schema.FundingRate` shape and differ only in which
CoinGlass endpoint supplied the series — distinguished here by
``source_label`` so one class serves both instead of two near-duplicate
classes.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from btengine.data.schema import FundingRate
from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule, frame_to_feature_values


class FundingFeatures(BaseFeatureModule):
    """Computes funding-rate trend and dispersion features."""

    def __init__(
        self,
        *,
        source_label: str = "standard",
        sma_window: int = 8,
        zscore_window: int = 30,
    ) -> None:
        self._source_label = source_label
        self._sma_window = sma_window
        self._zscore_window = zscore_window

    @property
    def module_name(self) -> str:
        return f"funding_{self._source_label}"

    def compute(self, symbol: str, records: Sequence[FundingRate]) -> list[FeatureValue]:
        """Compute funding features for one symbol's chronological series.

        Emits: ``funding_rate``, ``funding_rate_change``,
        ``funding_rate_sma_{sma_window}``, ``funding_rate_zscore_{zscore_window}``.
        """
        if not records:
            return []

        frame = pd.DataFrame(
            {
                "timestamp": [record.timestamp for record in records],
                "funding_rate": [record.funding_rate for record in records],
            }
        ).sort_values("timestamp").reset_index(drop=True)

        frame["funding_rate_change"] = frame["funding_rate"].diff()

        sma_col = f"funding_rate_sma_{self._sma_window}"
        frame[sma_col] = frame["funding_rate"].rolling(window=self._sma_window).mean()

        zscore_col = f"funding_rate_zscore_{self._zscore_window}"
        rolling_mean = frame["funding_rate"].rolling(window=self._zscore_window).mean()
        rolling_std = frame["funding_rate"].rolling(window=self._zscore_window).std()
        frame[zscore_col] = (frame["funding_rate"] - rolling_mean) / rolling_std

        feature_columns = ["funding_rate", "funding_rate_change", sma_col, zscore_col]
        return frame_to_feature_values(
            frame, symbol=symbol, module_name=self.module_name, feature_columns=feature_columns
        )
