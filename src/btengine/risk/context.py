"""The bundle every :class:`~btengine.risk.checks.base.RiskValidationCheck`
and :class:`~btengine.risk.modules.base.RiskModule` receives.

The same Interface Segregation role
:class:`~btengine.decision.context.DecisionRequest` plays for its own
layer. The upstream :class:`~btengine.scoring.models.StrategyScore` —
this task's other named input — is reached via
``decision_context.score`` only indirectly: ``DecisionContext`` doesn't
embed the score, so it's a separate explicit field here, both named per
this task's INPUT section.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from btengine.decision.models import DecisionContext
from btengine.risk.config import RiskEngineConfig, RiskProfile
from btengine.risk.models import MarketDataSnapshot, PortfolioStateSnapshot
from btengine.scoring.models import StrategyScore


@dataclass(frozen=True)
class RiskRequest:
    """Everything one ``assess()`` call needs, bundled for the pluggable
    checks and modules.

    ``reference_time`` is supplied by the caller — this engine never
    reads the wall clock itself, the same discipline every engine in
    this project follows.
    """

    symbol: str
    reference_time: datetime
    decision_context: DecisionContext
    score: StrategyScore
    portfolio: PortfolioStateSnapshot
    market_data: MarketDataSnapshot | None
    config: RiskEngineConfig

    @property
    def profile(self) -> RiskProfile | None:
        """The active risk profile, or ``None`` when none is configured."""
        return self.config.resolved_profile
