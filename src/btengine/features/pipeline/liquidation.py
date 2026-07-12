"""Liquidation feature module.

Pure transformation of a chronological
:class:`~btengine.data.schema.Liquidation` series into standardized
volume/imbalance features.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from btengine.data.schema import Liquidation
from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule, frame_to_feature_values


class LiquidationFeatures(BaseFeatureModule):
    """Computes liquidation volume and long/short imbalance features."""

    def __init__(self, *, rolling_window: int = 24) -> None:
        self._rolling_window = rolling_window

    @property
    def module_name(self) -> str:
        return "liquidation"

    def compute(self, symbol: str, records: Sequence[Liquidation]) -> list[FeatureValue]:
        """Compute liquidation features for one symbol's chronological series.

        Emits: ``long_liquidation_usd``, ``short_liquidation_usd``,
        ``total_liquidation_usd``, ``liquidation_imbalance`` (in
        ``[-1, 1]``, positive means longs liquidated more), plus rolling
        sums of each over ``rolling_window`` bars.
        """
        if not records:
            return []

        frame = pd.DataFrame(
            {
                "timestamp": [record.timestamp for record in records],
                "long_liquidation_usd": [record.long_liquidation_usd for record in records],
                "short_liquidation_usd": [record.short_liquidation_usd for record in records],
            }
        ).sort_values("timestamp").reset_index(drop=True)

        frame["total_liquidation_usd"] = frame["long_liquidation_usd"] + frame["short_liquidation_usd"]
        total_safe = frame["total_liquidation_usd"].replace(0, np.nan)
        frame["liquidation_imbalance"] = (
            frame["long_liquidation_usd"] - frame["short_liquidation_usd"]
        ) / total_safe

        long_sum_col = f"long_liquidation_usd_sum_{self._rolling_window}"
        short_sum_col = f"short_liquidation_usd_sum_{self._rolling_window}"
        total_sum_col = f"total_liquidation_usd_sum_{self._rolling_window}"
        frame[long_sum_col] = frame["long_liquidation_usd"].rolling(window=self._rolling_window).sum()
        frame[short_sum_col] = frame["short_liquidation_usd"].rolling(window=self._rolling_window).sum()
        frame[total_sum_col] = frame["total_liquidation_usd"].rolling(window=self._rolling_window).sum()

        feature_columns = [
            "long_liquidation_usd", "short_liquidation_usd", "total_liquidation_usd",
            "liquidation_imbalance", long_sum_col, short_sum_col, total_sum_col,
        ]
        return frame_to_feature_values(
            frame, symbol=symbol, module_name=self.module_name, feature_columns=feature_columns
        )
