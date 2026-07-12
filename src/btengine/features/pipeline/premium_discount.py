"""Premium/discount feature module — framework only.

Premium/discount (spot vs. perpetual price divergence) requires a paired
spot price series alongside the perpetual data this pipeline otherwise
consumes; the canonical schema and data layer for that pairing are not
yet defined. This module exists so the Feature Store and pipeline
orchestrator have a stable slot to register it into once that input is
available — it deliberately does not compute anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule


class PremiumDiscountFeatures(BaseFeatureModule):
    """Placeholder for spot-vs-perpetual premium/discount features."""

    @property
    def module_name(self) -> str:
        return "premium_discount"

    def compute(self, symbol: str, records: Sequence[Any]) -> list[FeatureValue]:
        raise NotImplementedError(
            "Premium/discount features require a paired spot price series "
            "not yet defined in the data layer."
        )
