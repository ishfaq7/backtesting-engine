"""Configuration for the Funding Rate Analysis Engine.

Every parameter here is either a generic statistical window (the same
kind of "how many bars to look back" parameter used throughout the
Feature Engineering Layer — not a trading rule) or an explicit,
unset-by-default placeholder for a rule the strategy owner has not
supplied yet. Nothing here encodes an assumption about what a funding
rate value means for a trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class FundingRateAnalysisConfig:
    """Tunable parameters for :class:`~btengine.analysis.funding_rate.engine.FundingRateAnalysisEngine`.

    ``trend_window``, ``momentum_window``, and ``volatility_window`` are
    generic lookback sizes (like an SMA/ATR period) with reasonable
    technical-analysis defaults; they do not imply any bullish/bearish
    interpretation of the result.

    ``historical_window``, ``outlier_zscore_threshold``, and
    ``expected_interval`` default to ``None`` — explicit placeholders.
    Set them once you supply the corresponding rule; until then the
    engine skips the behavior they'd control rather than guessing a
    value.
    """

    trend_window: int = 8
    momentum_window: int = 8
    volatility_window: int = 30

    # None = use the engine's entire given history rather than a fixed window.
    historical_window: int | None = None

    # TODO(owner): set this to enable outlier detection in validate().
    # None = outlier detection is skipped; no default threshold is assumed.
    outlier_zscore_threshold: float | None = None

    # TODO(owner): set this to enable timestamp-gap detection in validate().
    # None = gap detection is skipped; no default interval is assumed.
    expected_interval: timedelta | None = None

    def __post_init__(self) -> None:
        for name in ("trend_window", "momentum_window", "volatility_window"):
            value = getattr(self, name)
            if value < 2:
                raise ValueError(f"{name} must be >= 2, got {value}")
        if self.historical_window is not None and self.historical_window < 1:
            raise ValueError(f"historical_window must be >= 1, got {self.historical_window}")
        if self.outlier_zscore_threshold is not None and self.outlier_zscore_threshold <= 0:
            raise ValueError(
                f"outlier_zscore_threshold must be > 0, got {self.outlier_zscore_threshold}"
            )
        if self.expected_interval is not None and self.expected_interval <= timedelta(0):
            raise ValueError(f"expected_interval must be positive, got {self.expected_interval}")
