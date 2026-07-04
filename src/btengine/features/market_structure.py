"""Market structure analyzer — interface only.

Intended to classify recent price action (e.g. higher-highs/higher-lows
trend structure, ranges, breakdowns, swing points) into a feature usable by
a strategy's analysis pipeline. The classification method itself is a
market-interpretation decision, not infrastructure, so it is deliberately
left unimplemented in this architecture pass — see
``docs/RESEARCH_PLATFORM_ARCHITECTURE.md``. This module fixes the shape a
future implementation must satisfy.
"""

from __future__ import annotations

from btengine.features.base import FeatureAnalyzer, FeatureValue, HistoricalCandleSource


class MarketStructureAnalyzer(FeatureAnalyzer):
    """Computes a market-structure feature from recent candle history.

    Not implemented: :meth:`compute` raises ``NotImplementedError`` until a
    specific classification methodology is approved and supplied.
    """

    @property
    def feature_name(self) -> str:
        return "market_structure"

    def compute(self, symbol: str, history: HistoricalCandleSource) -> FeatureValue:
        raise NotImplementedError(
            "Market structure classification logic has not been implemented yet."
        )
