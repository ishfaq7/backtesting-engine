"""Long/short account ratio feature module.

Handles the global, top-trader-account, and top-trader-position ratio
endpoints, since all three map to the same canonical
:class:`~btengine.data.schema.LongShortRatio` shape and differ only in
which CoinGlass endpoint supplied the series — distinguished here by
``source_label`` so one class serves all three instead of three
near-duplicate classes.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from btengine.data.schema import LongShortRatio
from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule, frame_to_feature_values


class LongShortRatioFeatures(BaseFeatureModule):
    """Computes long/short ratio trend and dispersion features."""

    def __init__(
        self,
        *,
        source_label: str = "global",
        sma_window: int = 14,
        zscore_window: int = 30,
    ) -> None:
        self._source_label = source_label
        self._sma_window = sma_window
        self._zscore_window = zscore_window

    @property
    def module_name(self) -> str:
        return f"long_short_ratio_{self._source_label}"

    def compute(self, symbol: str, records: Sequence[LongShortRatio]) -> list[FeatureValue]:
        """Compute long/short ratio features for one symbol's chronological series.

        Emits: ``long_account_ratio``, ``short_account_ratio``,
        ``long_short_ratio``, ``long_short_ratio_change``,
        ``long_short_ratio_sma_{sma_window}``,
        ``long_short_ratio_zscore_{zscore_window}``.
        """
        if not records:
            return []

        frame = pd.DataFrame(
            {
                "timestamp": [record.timestamp for record in records],
                "long_account_ratio": [record.long_account_ratio for record in records],
                "short_account_ratio": [record.short_account_ratio for record in records],
                "long_short_ratio": [record.long_short_ratio for record in records],
            }
        ).sort_values("timestamp").reset_index(drop=True)

        frame["long_short_ratio_change"] = frame["long_short_ratio"].diff()

        sma_col = f"long_short_ratio_sma_{self._sma_window}"
        frame[sma_col] = frame["long_short_ratio"].rolling(window=self._sma_window).mean()

        zscore_col = f"long_short_ratio_zscore_{self._zscore_window}"
        rolling_mean = frame["long_short_ratio"].rolling(window=self._zscore_window).mean()
        rolling_std = frame["long_short_ratio"].rolling(window=self._zscore_window).std()
        frame[zscore_col] = (frame["long_short_ratio"] - rolling_mean) / rolling_std

        feature_columns = [
            "long_account_ratio", "short_account_ratio", "long_short_ratio",
            "long_short_ratio_change", sma_col, zscore_col,
        ]
        return frame_to_feature_values(
            frame, symbol=symbol, module_name=self.module_name, feature_columns=feature_columns
        )
