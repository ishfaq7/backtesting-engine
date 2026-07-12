"""Swing high/low detection.

Isolated from :mod:`~btengine.analysis.premium_discount.engine` so it's
independently testable, per this task's explicit "unit tests for: Swing
detection" requirement. Both implemented methods are standard technical
techniques with no proprietary interpretation:

- ``FRACTAL``: a bar is a confirmed swing high (low) if its high (low)
  is strictly greater (less) than every bar within ``swing_strength``
  bars on *both* sides. This is a no-repaint definition: once a bar has
  ``swing_strength`` bars of future context available, whether it
  qualifies never changes as still more data arrives later.
- ``EXTREMUM``: simply the single highest high and single lowest low in
  the window — no confirmation delay, always available given at least
  one candle.

Callers must pass an already-cleaned, chronologically sorted candle
sequence (no ``None`` fields, no duplicate timestamps) — this module
does not validate or clean its input; see
:mod:`~btengine.analysis.premium_discount.validation` for that.
"""

from __future__ import annotations

from collections.abc import Sequence

from btengine.analysis.premium_discount.config import PremiumDiscountAnalysisConfig, SwingDetectionMethod
from btengine.analysis.premium_discount.models import CandleObservation, SwingKind, SwingPoint


def detect_swings(
    candles: Sequence[CandleObservation], config: PremiumDiscountAnalysisConfig
) -> list[SwingPoint]:
    """Detect swing highs/lows in the last ``config.swing_lookback`` candles."""
    window = list(candles[-config.swing_lookback :])
    method = config.swing_detection_method
    if method == SwingDetectionMethod.FRACTAL:
        return _detect_fractal_swings(window, config.swing_strength)
    if method == SwingDetectionMethod.EXTREMUM:
        return _detect_extremum_swings(window)
    raise NotImplementedError(f"swing detection method {method!r} is not implemented")


def _detect_fractal_swings(window: list[CandleObservation], strength: int) -> list[SwingPoint]:
    swings: list[SwingPoint] = []
    for i in range(strength, len(window) - strength):
        candidate = window[i]
        neighborhood = window[i - strength : i] + window[i + 1 : i + strength + 1]

        if all(candidate.high > other.high for other in neighborhood):
            swings.append(SwingPoint(timestamp=candidate.timestamp, price=candidate.high, kind=SwingKind.HIGH))

        if all(candidate.low < other.low for other in neighborhood):
            swings.append(SwingPoint(timestamp=candidate.timestamp, price=candidate.low, kind=SwingKind.LOW))

    return swings


def _detect_extremum_swings(window: list[CandleObservation]) -> list[SwingPoint]:
    if not window:
        return []
    highest = max(window, key=lambda candle: candle.high)
    lowest = min(window, key=lambda candle: candle.low)
    return [
        SwingPoint(timestamp=highest.timestamp, price=highest.high, kind=SwingKind.HIGH),
        SwingPoint(timestamp=lowest.timestamp, price=lowest.low, kind=SwingKind.LOW),
    ]
