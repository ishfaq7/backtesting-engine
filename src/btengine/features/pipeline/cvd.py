"""Cumulative Volume Delta (CVD) feature module — framework only.

CVD requires taker buy/sell volume splits that CoinGlass's aggregated
OHLCV endpoints do not currently expose in the canonical
:class:`~btengine.data.schema.Candle` schema. This module exists so the
Feature Store and pipeline orchestrator have a stable slot to register it
into once that input is available — it deliberately does not compute
anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule


class CvdFeatures(BaseFeatureModule):
    """Placeholder for cumulative volume delta features."""

    @property
    def module_name(self) -> str:
        return "cvd"

    def compute(self, symbol: str, records: Sequence[Any]) -> list[FeatureValue]:
        raise NotImplementedError(
            "CVD features require taker buy/sell volume splits not yet "
            "exposed by the canonical data schema."
        )
