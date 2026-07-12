"""The bundle every :class:`~btengine.signal_validation.checks.base.ValidationCheck` receives.

Isolating this into one small, frozen dataclass (rather than passing
five separate positional arguments to every check) is what lets a check
be added or removed independently — Interface Segregation for the
validation-check layer, the same role
:class:`~btengine.analysis.premium_discount.models.CandleObservation` or
:class:`~btengine.scoring.models.ScoreComponent` play for their own
layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from btengine.analysis.funding_rate.models import FundingAnalysis
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis
from btengine.scoring.models import StrategyScore
from btengine.signal_validation.config import SignalValidationConfig


@dataclass(frozen=True)
class ValidationContext:
    """Everything one validation run needs, bundled for the pluggable checks.

    ``reference_time`` is supplied by the caller — this engine never
    reads the wall clock itself, so it behaves identically whether
    called live or replayed against a
    :class:`~btengine.backtest.simulation_clock.SimulationClock`-driven
    backtest.
    """

    symbol: str
    reference_time: datetime
    score: StrategyScore
    funding: FundingAnalysis | None
    open_interest: OpenInterestAnalysis | None
    premium_discount: PremiumDiscountAnalysis | None
    liquidity: LiquidityAnalysis | None
    config: SignalValidationConfig

    @property
    def analyses(self) -> dict[str, object | None]:
        """The four analyses, keyed by provider name — the same keys used
        throughout :mod:`btengine.scoring` and this package.
        """
        return {
            "funding": self.funding,
            "open_interest": self.open_interest,
            "premium_discount": self.premium_discount,
            "liquidity": self.liquidity,
        }
