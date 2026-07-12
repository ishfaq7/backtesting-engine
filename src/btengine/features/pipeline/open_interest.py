"""Open interest feature module.

Pure transformation of a chronological
:class:`~btengine.data.schema.OpenInterest` series into standardized
trend/dispersion features.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from btengine.data.schema import OpenInterest
from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule, frame_to_feature_values


class OpenInterestFeatures(BaseFeatureModule):
    """Computes open-interest trend and dispersion features."""

    def __init__(
        self,
        *,
        sma_window: int = 20,
        roc_window: int = 14,
        zscore_window: int = 30,
    ) -> None:
        self._sma_window = sma_window
        self._roc_window = roc_window
        self._zscore_window = zscore_window

    @property
    def module_name(self) -> str:
        return "open_interest"

    def compute(self, symbol: str, records: Sequence[OpenInterest]) -> list[FeatureValue]:
        """Compute open-interest features for one symbol's chronological series.

        Emits: ``open_interest``, ``oi_change_pct``, ``oi_sma_{sma_window}``,
        ``oi_roc_{roc_window}``, ``oi_zscore_{zscore_window}``.
        """
        if not records:
            return []

        frame = pd.DataFrame(
            {
                "timestamp": [record.timestamp for record in records],
                "open_interest": [record.open_interest for record in records],
            }
        ).sort_values("timestamp").reset_index(drop=True)

        frame["oi_change_pct"] = frame["open_interest"].pct_change()

        sma_col = f"oi_sma_{self._sma_window}"
        frame[sma_col] = frame["open_interest"].rolling(window=self._sma_window).mean()

        roc_col = f"oi_roc_{self._roc_window}"
        frame[roc_col] = frame["open_interest"].pct_change(periods=self._roc_window)

        zscore_col = f"oi_zscore_{self._zscore_window}"
        rolling_mean = frame["open_interest"].rolling(window=self._zscore_window).mean()
        rolling_std = frame["open_interest"].rolling(window=self._zscore_window).std()
        frame[zscore_col] = (frame["open_interest"] - rolling_mean) / rolling_std

        feature_columns = ["open_interest", "oi_change_pct", sma_col, roc_col, zscore_col]
        return frame_to_feature_values(
            frame, symbol=symbol, module_name=self.module_name, feature_columns=feature_columns
        )
