"""Price (OHLCV) feature module.

Pure transformation of a chronological :class:`~btengine.data.schema.Candle`
series into standardized price-derived features. No trading logic, no
signals — only descriptive statistics of price action that a downstream
strategy (not implemented here) could consume.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from btengine.data.schema import Candle
from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule, frame_to_feature_values


class PriceFeatures(BaseFeatureModule):
    """Computes return, volatility, and range features from OHLCV candles."""

    def __init__(
        self,
        *,
        sma_window: int = 20,
        ema_window: int = 20,
        atr_window: int = 14,
        volatility_window: int = 14,
    ) -> None:
        self._sma_window = sma_window
        self._ema_window = ema_window
        self._atr_window = atr_window
        self._volatility_window = volatility_window

    @property
    def module_name(self) -> str:
        return "price"

    def compute(self, symbol: str, candles: Sequence[Candle]) -> list[FeatureValue]:
        """Compute price features for one symbol's chronological candle series.

        Emits: ``return_pct``, ``log_return``, ``true_range``,
        ``atr_{atr_window}``, ``sma_{sma_window}``, ``ema_{ema_window}``,
        ``volatility_{volatility_window}``, ``high_low_range_pct``.
        """
        if not candles:
            return []

        frame = pd.DataFrame(
            {
                "timestamp": [candle.timestamp for candle in candles],
                "open": [candle.open for candle in candles],
                "high": [candle.high for candle in candles],
                "low": [candle.low for candle in candles],
                "close": [candle.close for candle in candles],
                "volume": [candle.volume for candle in candles],
            }
        ).sort_values("timestamp").reset_index(drop=True)

        previous_close = frame["close"].shift(1)
        frame["return_pct"] = frame["close"].pct_change()
        frame["log_return"] = np.log(frame["close"] / previous_close)
        frame["true_range"] = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - previous_close).abs(),
                (frame["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr_col = f"atr_{self._atr_window}"
        sma_col = f"sma_{self._sma_window}"
        ema_col = f"ema_{self._ema_window}"
        volatility_col = f"volatility_{self._volatility_window}"

        frame[atr_col] = frame["true_range"].rolling(window=self._atr_window).mean()
        frame[sma_col] = frame["close"].rolling(window=self._sma_window).mean()
        frame[ema_col] = frame["close"].ewm(span=self._ema_window, adjust=False).mean()
        frame[volatility_col] = frame["return_pct"].rolling(window=self._volatility_window).std()
        frame["high_low_range_pct"] = (frame["high"] - frame["low"]) / frame["close"]

        feature_columns = [
            "return_pct", "log_return", "true_range", atr_col, sma_col, ema_col,
            volatility_col, "high_low_range_pct",
        ]
        return frame_to_feature_values(
            frame, symbol=symbol, module_name=self.module_name, feature_columns=feature_columns
        )
