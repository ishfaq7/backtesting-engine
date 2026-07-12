"""Configuration for the Liquidity Analysis Engine.

Every parameter here is either a generic statistical window (like an
SMA/ATR period elsewhere in this codebase — not a trading rule), a
structural choice about how multi-exchange data is combined, or an
explicit, unset-by-default placeholder for a rule the strategy owner has
not supplied yet. Nothing here encodes an assumption about what a
liquidation, a positioning ratio, or an open-interest reading means for
a trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum


class AggregationMethod(str, Enum):
    """How multiple exchanges' readings at the same timestamp are combined
    into one aggregate value.

    ``SUM`` is the natural choice for volume-like metrics (liquidation
    USD volume: the market-wide total is the sum of every exchange's
    volume). ``MEAN`` is more natural for ratio-like metrics (averaging
    several exchanges' long/short ratios). This engine applies whichever
    method is configured uniformly to every series it aggregates — it
    does not silently pick a different method per metric, since that
    would be an unstated assumption; if you want ``SUM`` for liquidations
    and ``MEAN`` for ratios, run two engines (or two ``analyze()`` calls)
    with different configs.
    """

    SUM = "SUM"
    MEAN = "MEAN"


@dataclass(frozen=True)
class LiquidityAnalysisConfig:
    """Tunable parameters for :class:`~btengine.analysis.liquidity.engine.LiquidityAnalysisEngine`.

    ``analysis_window`` and ``spike_window`` are generic lookback sizes.
    ``exchange_selection`` and ``aggregation_method`` control which
    exchanges are considered and how their readings combine — structural
    choices, not trading rules.

    ``outlier_zscore_threshold``, ``spike_zscore_threshold``, and
    ``expected_interval`` default to ``None`` — explicit placeholders.
    Set them once you supply the corresponding rule; until then the
    engine skips the behavior they'd control (or leaves the corresponding
    output field unset) rather than guessing a value.
    """

    analysis_window: int = 30
    spike_window: int = 30

    # None = consider every exchange present in the given data.
    exchange_selection: tuple[str, ...] | None = None

    aggregation_method: AggregationMethod = AggregationMethod.SUM

    # TODO(owner): set this to enable outlier detection in validate().
    # None = outlier detection is skipped; no default threshold is assumed.
    outlier_zscore_threshold: float | None = None

    # TODO(owner): set this to enable is_abnormal_liquidation classification
    # in analyze(). None = liquidation_intensity is still computed (when
    # enough data exists) but is_abnormal_liquidation stays None rather
    # than being classified against an invented cutoff.
    spike_zscore_threshold: float | None = None

    # TODO(owner): set this to enable timestamp-gap detection in validate().
    # None = gap detection is skipped; no default interval is assumed.
    expected_interval: timedelta | None = None

    def __post_init__(self) -> None:
        if self.analysis_window < 2:
            raise ValueError(f"analysis_window must be >= 2, got {self.analysis_window}")
        if self.spike_window < 2:
            raise ValueError(f"spike_window must be >= 2, got {self.spike_window}")
        if self.exchange_selection is not None:
            if len(self.exchange_selection) == 0:
                raise ValueError("exchange_selection must not be empty when provided")
            if any(not exchange.strip() for exchange in self.exchange_selection):
                raise ValueError("exchange_selection must not contain blank entries")
        if self.outlier_zscore_threshold is not None and self.outlier_zscore_threshold <= 0:
            raise ValueError(
                f"outlier_zscore_threshold must be > 0, got {self.outlier_zscore_threshold}"
            )
        if self.spike_zscore_threshold is not None and self.spike_zscore_threshold <= 0:
            raise ValueError(
                f"spike_zscore_threshold must be > 0, got {self.spike_zscore_threshold}"
            )
        if self.expected_interval is not None and self.expected_interval <= timedelta(0):
            raise ValueError(f"expected_interval must be positive, got {self.expected_interval}")
