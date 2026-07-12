"""Configuration for the Premium & Discount Analysis Engine.

Every parameter here is either a generic, structurally-required setting
(a swing detection method that must be one of the implemented options; a
midpoint ratio that must fall within the range itself) or an explicit,
unset-by-default placeholder for a rule the strategy owner has not
supplied yet. Nothing here encodes an assumption about what a Premium or
Discount zone means for a trade — in particular, ``equilibrium_band_pct``
(how wide the "equilibrium" zone around the midpoint should be) is a
genuine trading-style choice with no universal default, so it defaults to
``None`` rather than an invented width.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum


class SwingDetectionMethod(str, Enum):
    """How swing highs/lows are identified within the lookback window.

    Both are standard, well-known technical techniques — not proprietary
    trading rules. Additional methods can be added later (each is an
    isolated branch in :func:`~btengine.analysis.premium_discount.swings.detect_swings`)
    without changing this engine's public interface.
    """

    FRACTAL = "FRACTAL"  # n-bar local extremum, confirmed by bars on both sides
    EXTREMUM = "EXTREMUM"  # the single highest high / lowest low in the window


@dataclass(frozen=True)
class PremiumDiscountAnalysisConfig:
    """Tunable parameters for :class:`~btengine.analysis.premium_discount.engine.PremiumDiscountAnalysisEngine`.

    ``swing_lookback`` and ``swing_strength`` are generic lookback sizes,
    like an SMA/ATR period elsewhere in this codebase, not trading rules.
    ``midpoint_ratio`` is a structural parameter (where the midpoint sits
    between the active low and high) rather than a business threshold —
    it defaults to the conventional 50%, but is fully adjustable.

    ``equilibrium_band_pct``, ``outlier_zscore_threshold``, and
    ``expected_interval`` default to ``None`` — explicit placeholders.
    Set them once you supply the corresponding rule; until then the
    engine skips the behavior they'd control (or leaves the equilibrium
    zone effectively a single point at the midpoint) rather than
    guessing a value.
    """

    swing_detection_method: SwingDetectionMethod = SwingDetectionMethod.FRACTAL
    swing_lookback: int = 50
    swing_strength: int = 2
    midpoint_ratio: float = 0.5

    # TODO(owner): set this (as a fraction of the range width, e.g. 0.05
    # for a band spanning 47.5%-52.5%) to enable a real EQUILIBRIUM zone.
    # None = no band is assumed; only a price exactly at the midpoint
    # classifies as EQUILIBRIUM.
    equilibrium_band_pct: float | None = None

    # TODO(owner): set this to enable outlier detection in validate().
    # None = outlier detection is skipped; no default threshold is assumed.
    outlier_zscore_threshold: float | None = None

    # TODO(owner): set this to enable timestamp-gap detection in validate().
    # None = gap detection is skipped; no default interval is assumed.
    expected_interval: timedelta | None = None

    def __post_init__(self) -> None:
        if self.swing_lookback < 1:
            raise ValueError(f"swing_lookback must be >= 1, got {self.swing_lookback}")
        if self.swing_strength < 1:
            raise ValueError(f"swing_strength must be >= 1, got {self.swing_strength}")
        if (
            self.swing_detection_method is SwingDetectionMethod.FRACTAL
            and self.swing_lookback < 2 * self.swing_strength + 1
        ):
            raise ValueError(
                "swing_lookback must be >= 2 * swing_strength + 1 for FRACTAL detection "
                f"(got swing_lookback={self.swing_lookback}, swing_strength={self.swing_strength})"
            )
        if not 0.0 <= self.midpoint_ratio <= 1.0:
            raise ValueError(f"midpoint_ratio must be between 0 and 1, got {self.midpoint_ratio}")
        if self.equilibrium_band_pct is not None and not 0.0 < self.equilibrium_band_pct <= 1.0:
            raise ValueError(
                f"equilibrium_band_pct must be between 0 (exclusive) and 1, "
                f"got {self.equilibrium_band_pct}"
            )
        if self.outlier_zscore_threshold is not None and self.outlier_zscore_threshold <= 0:
            raise ValueError(
                f"outlier_zscore_threshold must be > 0, got {self.outlier_zscore_threshold}"
            )
        if self.expected_interval is not None and self.expected_interval <= timedelta(0):
            raise ValueError(f"expected_interval must be positive, got {self.expected_interval}")
