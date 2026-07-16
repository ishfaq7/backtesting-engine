"""The nine named, framework-only risk modules.

One class per responsibility this task's RESPONSIBILITIES section
names as buildable today. Every ``evaluate()`` raises
``NotImplementedError`` — how a position is sized, how much leverage is
acceptable, where a drawdown limit bites, etc., are the strategy
owner's proprietary risk rules, which this framework must not invent.
Each class documents which :class:`~btengine.risk.config.RiskProfile`
limit its future implementation will evaluate against.

The two "(future)" responsibilities — Correlation Risk and Volatility
Risk — are deliberately *not* stubbed here: their required inputs
(cross-asset correlation matrices; an agreed volatility measure beyond
the optional ``MarketDataSnapshot.volatility`` hook) don't exist in
this codebase yet, so a stub would be scaffolding with nothing to plug
into. See ``docs/RISK_MANAGEMENT_FRAMEWORK.md`` §Future Extension
Points for how each lands as one more :class:`~btengine.risk.modules.base.RiskModule`
when its inputs exist.
"""

from __future__ import annotations

from btengine.risk.context import RiskRequest
from btengine.risk.models import RiskModuleResult
from btengine.risk.modules.base import RiskModule


class _FrameworkOnlyRiskModule(RiskModule):
    """Shared plumbing for the nine not-yet-implemented modules.

    Only the name/description differ between them; the "not implemented"
    behavior is identical and deliberately centralized so no stub can
    accidentally diverge into inventing logic.
    """

    _NAME: str = ""
    _CONCERN: str = ""

    def __init__(self, *, version: str = "unversioned") -> None:
        self._version = version

    @property
    def module_name(self) -> str:
        return self._NAME

    @property
    def module_version(self) -> str:
        return self._version

    def evaluate(self, request: RiskRequest) -> RiskModuleResult:
        raise NotImplementedError(
            f"{self._CONCERN} is not implemented. This is a proprietary risk "
            f"rule the strategy owner must supply; the framework only defines "
            f"where it plugs in."
        )


class PositionSizingModule(_FrameworkOnlyRiskModule):
    """Future: computes ``RiskAssessment.position_size``. Will evaluate
    against ``RiskProfile.max_risk_per_trade_pct`` and the owner's sizing formula."""

    _NAME = "position_sizing"
    _CONCERN = "Position sizing"


class LeverageValidationModule(_FrameworkOnlyRiskModule):
    """Future: computes ``RiskAssessment.leverage_allowed``. Will evaluate
    against ``RiskProfile.max_leverage``."""

    _NAME = "leverage_validation"
    _CONCERN = "Leverage validation"


class MaxRiskValidationModule(_FrameworkOnlyRiskModule):
    """Future: computes ``RiskAssessment.max_risk_allowed``. Will evaluate
    against ``RiskProfile.max_risk_per_trade_pct``."""

    _NAME = "max_risk_validation"
    _CONCERN = "Maximum risk validation"


class DailyDrawdownProtectionModule(_FrameworkOnlyRiskModule):
    """Future: will evaluate ``PortfolioStateSnapshot.daily_realized_pnl``
    against ``RiskProfile.max_daily_drawdown_pct``."""

    _NAME = "daily_drawdown_protection"
    _CONCERN = "Daily drawdown protection"


class TotalDrawdownProtectionModule(_FrameworkOnlyRiskModule):
    """Future: will evaluate equity vs. ``PortfolioStateSnapshot.peak_equity``
    against ``RiskProfile.max_total_drawdown_pct``."""

    _NAME = "total_drawdown_protection"
    _CONCERN = "Total drawdown protection"


class ExposureManagementModule(_FrameworkOnlyRiskModule):
    """Future: computes ``RiskAssessment.exposure_status``. Will evaluate
    open-position notional against ``RiskProfile.max_exposure_pct``."""

    _NAME = "exposure_management"
    _CONCERN = "Exposure management"


class CapitalAllocationModule(_FrameworkOnlyRiskModule):
    """Future: will evaluate per-symbol capital allocation against
    ``RiskProfile.max_capital_allocation_pct``."""

    _NAME = "capital_allocation"
    _CONCERN = "Capital allocation"


class MarginValidationModule(_FrameworkOnlyRiskModule):
    """Future: will evaluate ``PortfolioStateSnapshot.margin_used``
    against ``RiskProfile.max_margin_utilization_pct``."""

    _NAME = "margin_validation"
    _CONCERN = "Margin validation"


class PortfolioRiskModule(_FrameworkOnlyRiskModule):
    """Future: computes ``RiskAssessment.portfolio_risk``. Will evaluate
    aggregate portfolio risk against ``RiskProfile.max_portfolio_risk_pct``."""

    _NAME = "portfolio_risk"
    _CONCERN = "Portfolio risk"


def default_modules(*, version: str = "unversioned") -> list[RiskModule]:
    """All nine named framework-only modules, in a stable, deterministic order."""
    return [
        PositionSizingModule(version=version),
        LeverageValidationModule(version=version),
        MaxRiskValidationModule(version=version),
        DailyDrawdownProtectionModule(version=version),
        TotalDrawdownProtectionModule(version=version),
        ExposureManagementModule(version=version),
        CapitalAllocationModule(version=version),
        MarginValidationModule(version=version),
        PortfolioRiskModule(version=version),
    ]
