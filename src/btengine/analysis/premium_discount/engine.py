"""The Premium & Discount Analysis Engine.

Turns a chronological OHLC candle history into one
:class:`~btengine.analysis.premium_discount.models.PremiumDiscountAnalysis`
snapshot: an active trading range (swing high to swing low), its
midpoint, and where the current price sits within that range. Every
computation here is a plain descriptive statistic — nothing in this
module decides whether a price is a good entry, computes a score, or
emits a BUY/SELL signal.

One engine instance is scoped to one timeframe — pass
``timeframe_label="4h"`` (default ``"unspecified"``) so a caller can run
several instances, one per timeframe, for multi-timeframe analysis. The
computation is identical either way; only the label attached to the
output (and used to namespace
:meth:`~btengine.analysis.premium_discount.models.PremiumDiscountAnalysis.to_feature_map`)
differs — this engine has no opinion on how multiple timeframes' results
should be combined, since that would be a strategy decision.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from btengine.analysis.premium_discount.config import PremiumDiscountAnalysisConfig
from btengine.analysis.premium_discount.errors import PremiumDiscountAnalysisError
from btengine.analysis.premium_discount.models import CandleObservation, PremiumDiscountAnalysis, PremiumDiscountZone
from btengine.analysis.premium_discount.swings import SwingKind, detect_swings
from btengine.analysis.premium_discount.validation import (
    PremiumDiscountValidationIssue,
    PremiumDiscountValidator,
)


class PremiumDiscountAnalysisEngine:
    """Reusable, stateless engine that turns OHLC history into a :class:`PremiumDiscountAnalysis`."""

    def __init__(
        self,
        config: PremiumDiscountAnalysisConfig | None = None,
        *,
        timeframe_label: str = "unspecified",
    ) -> None:
        self._config = config or PremiumDiscountAnalysisConfig()
        self._timeframe_label = timeframe_label

    @property
    def timeframe_label(self) -> str:
        return self._timeframe_label

    def validate(
        self, candles: Sequence[CandleObservation]
    ) -> list[PremiumDiscountValidationIssue]:
        """Run data-quality checks on the raw, as-given candles."""
        return PremiumDiscountValidator(self._config).validate(candles)

    def analyze(self, symbol: str, candles: Sequence[CandleObservation]) -> PremiumDiscountAnalysis:
        """Compute a :class:`PremiumDiscountAnalysis` snapshot as of the latest candle.

        Missing/invalid candles are excluded from every computation;
        duplicate timestamps keep the last-given candle; the series is
        sorted chronologically regardless of input order. Raises
        :class:`~btengine.analysis.premium_discount.errors.PremiumDiscountAnalysisError`
        if no usable candle remains after cleaning, or if the detected
        swings don't form a usable active trading range.
        """
        cleaned = self._clean(candles)
        if not cleaned:
            raise PremiumDiscountAnalysisError(f"no usable candles to analyze for {symbol!r}")

        swings = detect_swings(cleaned, self._config)
        swing_highs = [swing.price for swing in swings if swing.kind is SwingKind.HIGH]
        swing_lows = [swing.price for swing in swings if swing.kind is SwingKind.LOW]
        if not swing_highs or not swing_lows:
            raise PremiumDiscountAnalysisError(
                f"insufficient data to establish an active trading range for {symbol!r}: "
                f"need at least one confirmed swing high and one confirmed swing low "
                f"within the lookback window"
            )

        active_high = max(swing_highs)
        active_low = min(swing_lows)
        if active_high <= active_low:
            raise PremiumDiscountAnalysisError(
                f"invalid active trading range for {symbol!r}: "
                f"active_high ({active_high}) must be greater than active_low ({active_low})"
            )

        range_size = active_high - active_low
        midpoint = active_low + range_size * self._config.midpoint_ratio

        current_price = cleaned[-1].close
        assert current_price is not None  # narrowed by _clean
        position_pct = (current_price - active_low) / range_size * 100

        zone = self._classify_zone(current_price, active_low, active_high, midpoint, range_size)
        premium_pct, discount_pct = self._zone_percentages(
            current_price, midpoint, active_high, active_low
        )

        return PremiumDiscountAnalysis(
            symbol=symbol.upper(),
            timeframe=self._timeframe_label,
            as_of=cleaned[-1].timestamp,
            active_high=active_high,
            active_low=active_low,
            range_size=range_size,
            midpoint=midpoint,
            current_price=current_price,
            current_price_position_pct=position_pct,
            zone=zone,
            premium_percentage=premium_pct,
            discount_percentage=discount_pct,
            sample_size=len(cleaned),
            confidence_level=self._confidence(len(cleaned)),
        )

    def _clean(self, candles: Sequence[CandleObservation]) -> list[CandleObservation]:
        by_timestamp: dict[datetime, CandleObservation] = {}
        for candle in candles:
            if candle.high is None or candle.low is None or candle.close is None:
                continue
            if candle.high < candle.low:
                continue
            by_timestamp[candle.timestamp] = candle  # last-given wins
        return [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]

    def _classify_zone(
        self,
        current_price: float,
        active_low: float,
        active_high: float,
        midpoint: float,
        range_size: float,
    ) -> PremiumDiscountZone:
        if current_price > active_high:
            return PremiumDiscountZone.ABOVE_RANGE
        if current_price < active_low:
            return PremiumDiscountZone.BELOW_RANGE

        band_pct = self._config.equilibrium_band_pct
        if band_pct is not None:
            half_width = range_size * band_pct / 2
            if abs(current_price - midpoint) <= half_width:
                return PremiumDiscountZone.EQUILIBRIUM
        elif current_price == midpoint:
            return PremiumDiscountZone.EQUILIBRIUM

        return PremiumDiscountZone.PREMIUM if current_price > midpoint else PremiumDiscountZone.DISCOUNT

    def _zone_percentages(
        self, current_price: float, midpoint: float, active_high: float, active_low: float
    ) -> tuple[float | None, float | None]:
        if current_price >= midpoint:
            premium_span = active_high - midpoint
            premium_pct = (current_price - midpoint) / premium_span * 100 if premium_span > 0 else None
            return premium_pct, 0.0
        discount_span = midpoint - active_low
        discount_pct = (midpoint - current_price) / discount_span * 100 if discount_span > 0 else None
        return 0.0, discount_pct

    def _confidence(self, sample_size: int) -> float:
        required = max(self._config.swing_lookback, 2 * self._config.swing_strength + 1, 1)
        return min(sample_size / required, 1.0)
