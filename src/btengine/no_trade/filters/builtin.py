"""The eight named, framework-only no-trade filters.

One class per responsibility this task's RESPONSIBILITIES section names
as buildable today. Every ``evaluate()`` raises ``NotImplementedError``
— what market condition, risk state, strategy state, portfolio state,
data-quality bar, time window, session, or exchange state should block
trading is the strategy owner's proprietary rule, which this framework
must not invent. Each class documents what its future implementation
will read.

The two "Future" responsibilities — the News/Event Filter and the AI
Validation Filter — are deliberately *not* stubbed: their required
inputs (a news/economic-calendar feed; a concrete AI model integration)
don't exist in this codebase yet, so a stub would be scaffolding with
nothing to plug into. See ``docs/NO_TRADE_FRAMEWORK.md`` §Future
Extension Points for how each lands as one more
:class:`~btengine.no_trade.filters.base.NoTradeFilter` when its inputs
exist.
"""

from __future__ import annotations

from btengine.no_trade.context import NoTradeRequest
from btengine.no_trade.filters.base import NoTradeFilter
from btengine.no_trade.models import FilterResult


class _FrameworkOnlyNoTradeFilter(NoTradeFilter):
    """Shared plumbing for the eight not-yet-implemented filters.

    Only the name/description differ between them; the "not implemented"
    behavior is identical and deliberately centralized so no stub can
    accidentally diverge into inventing a rule.
    """

    _NAME: str = ""
    _CONCERN: str = ""

    def __init__(self, *, version: str = "unversioned") -> None:
        self._version = version

    @property
    def filter_name(self) -> str:
        return self._NAME

    @property
    def filter_version(self) -> str:
        return self._version

    def evaluate(self, request: NoTradeRequest) -> FilterResult:
        raise NotImplementedError(
            f"{self._CONCERN} is not implemented. This is a proprietary "
            f"no-trade rule the strategy owner must supply; the framework "
            f"only defines where it plugs in."
        )


class MarketConditionFilter(_FrameworkOnlyNoTradeFilter):
    """Future: will read the four analyses (funding/OI/premium-discount/
    liquidity) against owner-supplied market-condition rules."""

    _NAME = "market_condition_filter"
    _CONCERN = "Market condition filtering"


class RiskFilter(_FrameworkOnlyNoTradeFilter):
    """Future: will read ``NoTradeRequest.risk_assessment`` (e.g. block
    when risk was not approved) against owner-supplied rules."""

    _NAME = "risk_filter"
    _CONCERN = "Risk filtering"


class StrategyFilter(_FrameworkOnlyNoTradeFilter):
    """Future: will read ``NoTradeRequest.score``/``decision_context``
    against owner-supplied strategy-state rules."""

    _NAME = "strategy_filter"
    _CONCERN = "Strategy filtering"


class PortfolioFilter(_FrameworkOnlyNoTradeFilter):
    """Future: will read ``NoTradeRequest.portfolio`` against
    owner-supplied portfolio-state rules."""

    _NAME = "portfolio_filter"
    _CONCERN = "Portfolio filtering"


class DataQualityFilter(_FrameworkOnlyNoTradeFilter):
    """Future: will read upstream validation statuses (score, decision,
    risk) against an owner-supplied data-quality bar."""

    _NAME = "data_quality_filter"
    _CONCERN = "Data quality filtering"


class TimeFilter(_FrameworkOnlyNoTradeFilter):
    """Future: will read ``NoTradeRequest.reference_time`` against
    owner-supplied time windows (from ``config.filter_parameters``)."""

    _NAME = "time_filter"
    _CONCERN = "Time filtering"


class SessionFilter(_FrameworkOnlyNoTradeFilter):
    """Future: will read ``NoTradeRequest.reference_time`` against
    owner-supplied trading-session definitions. Complements the existing
    declarative ``btengine.strategy.rules.session_filters.SessionFilters``
    RuleSet (spec layer), which likewise has no content yet."""

    _NAME = "session_filter"
    _CONCERN = "Session filtering"


class ExchangeFilter(_FrameworkOnlyNoTradeFilter):
    """Future: will read exchange identity/state (e.g. from
    ``NoTradeRequest.market_data``) against an owner-supplied allowlist
    in ``config.filter_parameters``."""

    _NAME = "exchange_filter"
    _CONCERN = "Exchange filtering"


def default_filters(*, version: str = "unversioned") -> list[NoTradeFilter]:
    """All eight named framework-only filters, in a stable, deterministic order."""
    return [
        MarketConditionFilter(version=version),
        RiskFilter(version=version),
        StrategyFilter(version=version),
        PortfolioFilter(version=version),
        DataQualityFilter(version=version),
        TimeFilter(version=version),
        SessionFilter(version=version),
        ExchangeFilter(version=version),
    ]
