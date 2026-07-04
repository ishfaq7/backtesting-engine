"""Cumulative Volume Delta (CVD) analyzer — interface only, provider-independent.

CVD is normally computed from buy/sell-tagged (taker) volume, not plain
aggregate volume. The canonical :class:`~btengine.data.schema.Candle` only
carries total ``volume`` — it has no buy/sell split — so a correct CVD
implementation needs either a taker buy/sell volume data source (CoinGlass
exposes one on the Startup plan: see "Additional data likely needed later"
in ``docs/COINGLASS_INTEGRATION.md``) or trade-level tick data neither of
which this pass wires in. This analyzer is therefore "provider-independent"
in the sense that its *interface* takes only generic candle history (no
CoinGlass-specific type), but its calculation is deliberately left
unimplemented until that data dependency is resolved — see
``docs/RESEARCH_PLATFORM_ARCHITECTURE.md``.
"""

from __future__ import annotations

from btengine.features.base import FeatureAnalyzer, FeatureValue, HistoricalCandleSource


class CVDAnalyzer(FeatureAnalyzer):
    """Computes Cumulative Volume Delta from historical volume data.

    Not implemented: :meth:`compute` raises ``NotImplementedError``. See
    the module docstring for the data-availability gap this needs to
    resolve first.
    """

    @property
    def feature_name(self) -> str:
        return "cvd"

    def compute(self, symbol: str, history: HistoricalCandleSource) -> FeatureValue:
        raise NotImplementedError(
            "CVD calculation has not been implemented yet (requires taker "
            "buy/sell volume data, not yet wired into the data layer)."
        )
