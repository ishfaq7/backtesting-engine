"""Market structure feature module — framework only.

Market structure (swing highs/lows, break-of-structure, trend regime)
is a proprietary analytical technique whose exact definition belongs to
the strategy owner, not this generic pipeline layer. This module exists
so the Feature Store and pipeline orchestrator have a stable slot to
register it into once that definition is supplied — it deliberately does
not compute anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from btengine.data.schema import Candle
from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule


class MarketStructureFeatures(BaseFeatureModule):
    """Placeholder for market-structure (swing/trend) features."""

    @property
    def module_name(self) -> str:
        return "market_structure"

    def compute(self, symbol: str, candles: Sequence[Candle]) -> list[FeatureValue]:
        raise NotImplementedError(
            "Market structure features are not yet defined; this module is a "
            "framework placeholder pending the strategy owner's specification."
        )
