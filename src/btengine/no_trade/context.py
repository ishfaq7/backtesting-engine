"""The bundle every :class:`~btengine.no_trade.checks.base.NoTradeValidationCheck`
and :class:`~btengine.no_trade.filters.base.NoTradeFilter` receives.

The same Interface Segregation role
:class:`~btengine.risk.context.RiskRequest` plays for its own layer.
Reuses :class:`btengine.risk.models.PortfolioStateSnapshot` and
:class:`~btengine.risk.models.MarketDataSnapshot` — the risk framework
already defined exactly the decoupled portfolio/market input shapes
this task's INPUT section names, so re-defining them here would be
gratuitous duplication rather than layer isolation (both engines sit at
the same post-decision stage and receive the same caller-supplied
state).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from btengine.analysis.funding_rate.models import FundingAnalysis
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis
from btengine.decision.models import DecisionContext
from btengine.no_trade.config import NoTradeEngineConfig
from btengine.risk.models import MarketDataSnapshot, PortfolioStateSnapshot, RiskAssessment
from btengine.scoring.models import StrategyScore


@dataclass(frozen=True)
class NoTradeRequest:
    """Everything one ``evaluate()`` call needs, bundled for the pluggable
    checks and filters.

    ``reference_time`` is supplied by the caller — this engine never
    reads the wall clock itself, the same discipline every engine in
    this project follows (which is also what will let the future
    Time/Session filters run identically in a backtest).
    """

    symbol: str
    reference_time: datetime
    decision_context: DecisionContext
    score: StrategyScore
    risk_assessment: RiskAssessment | None
    funding: FundingAnalysis | None
    open_interest: OpenInterestAnalysis | None
    premium_discount: PremiumDiscountAnalysis | None
    liquidity: LiquidityAnalysis | None
    market_data: MarketDataSnapshot | None
    portfolio: PortfolioStateSnapshot | None
    config: NoTradeEngineConfig

    @property
    def analyses(self) -> dict[str, object | None]:
        """The four analyses, keyed by provider name — the same keys used
        throughout the scoring/signal-validation/decision layers.
        """
        return {
            "funding": self.funding,
            "open_interest": self.open_interest,
            "premium_discount": self.premium_discount,
            "liquidity": self.liquidity,
        }
