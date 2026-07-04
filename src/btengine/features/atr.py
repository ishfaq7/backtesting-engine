"""Average True Range (ATR) analyzer — interface only.

ATR is a well-known volatility measure computable purely from OHLC candle
data. Even though its formula is public/standard, its actual calculation
is deliberately left unimplemented in this architecture-only pass — see
``docs/RESEARCH_PLATFORM_ARCHITECTURE.md`` for the rationale (analyzers
that produce a market-interpretation value are treated the same as
indicators: out of scope until explicitly requested). This module fixes
the shape a future implementation must satisfy.
"""

from __future__ import annotations

from btengine.features.base import FeatureAnalyzer, FeatureValue, HistoricalCandleSource


class ATRAnalyzer(FeatureAnalyzer):
    """Computes Average True Range from recent OHLC history.

    Not implemented: :meth:`compute` raises ``NotImplementedError`` until
    the calculation is supplied (period length, smoothing method, etc. are
    all still open parameters).
    """

    def __init__(self, *, period: int = 14) -> None:
        if period <= 0:
            raise ValueError("period must be positive")
        self._period = period

    @property
    def period(self) -> int:
        return self._period

    @property
    def feature_name(self) -> str:
        return f"atr_{self._period}"

    def compute(self, symbol: str, history: HistoricalCandleSource) -> FeatureValue:
        raise NotImplementedError("ATR calculation has not been implemented yet.")
