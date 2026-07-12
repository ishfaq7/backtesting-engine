"""The bundle every :class:`~btengine.decision.checks.base.DecisionValidationCheck`
and :class:`~btengine.decision.providers.base.DecisionProvider` receives.

Not to be confused with :class:`~btengine.decision.models.DecisionContext`
(this engine's *output* object, named literally "DecisionContext" per
this task's spec) — this is the *input* bundle prepared for one
``decide()`` call, the same Interface Segregation role
:class:`~btengine.signal_validation.context.ValidationContext` plays for
its own layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from btengine.analysis.funding_rate.models import FundingAnalysis
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis
from btengine.decision.config import DecisionEngineConfig
from btengine.signal_validation.models import ValidatedStrategyState


@dataclass(frozen=True)
class DecisionRequest:
    """Everything one ``decide()`` call needs, bundled for the pluggable
    checks and providers.

    ``reference_time`` is supplied by the caller — this engine never
    reads the wall clock itself, the same discipline
    :class:`~btengine.signal_validation.engine.SignalValidationEngine`
    and every backtest-aware engine in this project follow. The
    upstream :class:`~btengine.scoring.models.StrategyScore` is reached
    via ``validated_state.score`` rather than a separate field, so there
    is exactly one source of truth and no possibility of the two
    disagreeing.
    """

    symbol: str
    reference_time: datetime
    validated_state: ValidatedStrategyState
    funding: FundingAnalysis | None
    open_interest: OpenInterestAnalysis | None
    premium_discount: PremiumDiscountAnalysis | None
    liquidity: LiquidityAnalysis | None
    config: DecisionEngineConfig
    provider_names: tuple[str, ...]

    @property
    def analyses(self) -> dict[str, object | None]:
        """The four analyses, keyed by provider name — the same keys used
        throughout :mod:`btengine.scoring` and :mod:`btengine.signal_validation`.
        """
        return {
            "funding": self.funding,
            "open_interest": self.open_interest,
            "premium_discount": self.premium_discount,
            "liquidity": self.liquidity,
        }
