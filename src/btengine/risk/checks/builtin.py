"""The six stateless, built-in risk-input validation checks.

These validate this task's six named VALIDATION responsibilities —
input integrity only, never a risk rule. E.g. "invalid leverage" means
"a supplied position reports a structurally impossible leverage value
(negative, NaN)," never "leverage is too high for the strategy" — the
latter is the (unimplemented) LeverageValidationModule's future job,
against an owner-supplied ``RiskProfile.max_leverage``.
"""

from __future__ import annotations

import math

from btengine.risk.checks.base import RiskValidationCheck
from btengine.risk.config import _LIMIT_FIELDS
from btengine.risk.context import RiskRequest
from btengine.risk.models import RiskValidationIssue


def _is_bad_number(value: float) -> bool:
    return math.isnan(value) or math.isinf(value)


class InvalidLeverageCheck(RiskValidationCheck):
    """Flags a structurally impossible leverage value on any supplied position."""

    @property
    def check_name(self) -> str:
        return "invalid_leverage"

    def run(self, request: RiskRequest) -> list[RiskValidationIssue]:
        issues: list[RiskValidationIssue] = []
        for position in request.portfolio.positions:
            leverage = position.leverage
            if leverage is None:
                continue
            if _is_bad_number(leverage) or leverage <= 0:
                issues.append(
                    RiskValidationIssue(
                        "ERROR", "structural",
                        f"position {position.symbol} reports invalid leverage {leverage}",
                    )
                )
        return issues


class InvalidPortfolioStateCheck(RiskValidationCheck):
    """Flags structurally impossible portfolio values."""

    @property
    def check_name(self) -> str:
        return "invalid_portfolio_state"

    def run(self, request: RiskRequest) -> list[RiskValidationIssue]:
        issues: list[RiskValidationIssue] = []
        portfolio = request.portfolio
        for name, value in (("cash", portfolio.cash), ("equity", portfolio.equity)):
            if _is_bad_number(value):
                issues.append(
                    RiskValidationIssue("ERROR", "structural", f"portfolio {name} is {value}")
                )
        for position in portfolio.positions:
            if _is_bad_number(position.quantity) or _is_bad_number(position.avg_entry_price):
                issues.append(
                    RiskValidationIssue(
                        "ERROR", "structural",
                        f"position {position.symbol} has NaN/infinite quantity or entry price",
                    )
                )
            elif position.avg_entry_price < 0:
                issues.append(
                    RiskValidationIssue(
                        "ERROR", "structural",
                        f"position {position.symbol} has a negative avg_entry_price "
                        f"{position.avg_entry_price}",
                    )
                )
        return issues


class InvalidAccountBalanceCheck(RiskValidationCheck):
    """Flags a non-positive account equity — nothing can be risked from
    an empty or negative account, whatever the (unimplemented) rules say.
    """

    @property
    def check_name(self) -> str:
        return "invalid_account_balance"

    def run(self, request: RiskRequest) -> list[RiskValidationIssue]:
        equity = request.portfolio.equity
        if _is_bad_number(equity):
            return []  # already flagged by InvalidPortfolioStateCheck
        if equity <= 0:
            return [
                RiskValidationIssue(
                    "ERROR", "structural", f"account equity {equity} is not positive"
                )
            ]
        return []


class InvalidExposureCheck(RiskValidationCheck):
    """Flags structurally impossible exposure inputs (a position with no
    way to value it: NaN unrealized PnL, or market data with a
    non-positive price).
    """

    @property
    def check_name(self) -> str:
        return "invalid_exposure"

    def run(self, request: RiskRequest) -> list[RiskValidationIssue]:
        issues: list[RiskValidationIssue] = []
        for position in request.portfolio.positions:
            if _is_bad_number(position.unrealized_pnl):
                issues.append(
                    RiskValidationIssue(
                        "ERROR", "structural",
                        f"position {position.symbol} has NaN/infinite unrealized_pnl",
                    )
                )
        market_data = request.market_data
        if market_data is not None and (
            _is_bad_number(market_data.price) or market_data.price <= 0
        ):
            issues.append(
                RiskValidationIssue(
                    "ERROR", "structural",
                    f"market data for {market_data.symbol} has invalid price {market_data.price}",
                )
            )
        return issues


class MissingConfigurationCheck(RiskValidationCheck):
    """Flags an unset active risk profile, and unset limits on the active one.

    An unset profile/limit is the expected state until the strategy
    owner fills one in — flagged as ``WARNING`` (visible, but not
    blocking data-quality validation), while the fail-safe
    ``risk_approved`` semantics already guarantee nothing gets approved
    without real modules and limits.
    """

    @property
    def check_name(self) -> str:
        return "missing_configuration"

    def run(self, request: RiskRequest) -> list[RiskValidationIssue]:
        profile = request.profile
        if profile is None:
            return [
                RiskValidationIssue(
                    "WARNING", "configuration",
                    "no active risk profile is configured; every limit is unset",
                )
            ]
        unset = [name for name in _LIMIT_FIELDS if getattr(profile, name) is None]
        if unset:
            return [
                RiskValidationIssue(
                    "WARNING", "configuration",
                    f"risk profile {profile.name!r} has unset limits: {', '.join(unset)}",
                )
            ]
        return []


class StrategyVersionMismatchCheck(RiskValidationCheck):
    """Flags a strategy version that doesn't match the configured
    expectation, and any disagreement between the decision context and
    the score it should describe.
    """

    @property
    def check_name(self) -> str:
        return "strategy_version_mismatch"

    def run(self, request: RiskRequest) -> list[RiskValidationIssue]:
        issues: list[RiskValidationIssue] = []
        decision_version = request.decision_context.strategy_version
        expected = request.config.expected_strategy_version
        if expected is not None and decision_version != expected:
            issues.append(
                RiskValidationIssue(
                    "WARNING", "version",
                    f"strategy_version {decision_version!r} does not match expected {expected!r}",
                )
            )
        if decision_version != request.score.score_version:
            issues.append(
                RiskValidationIssue(
                    "WARNING", "version",
                    f"DecisionContext.strategy_version {decision_version!r} disagrees with "
                    f"StrategyScore.score_version {request.score.score_version!r}",
                )
            )
        return issues


def default_checks() -> list[RiskValidationCheck]:
    """The standard set of built-in checks, in a stable, deterministic order."""
    return [
        InvalidLeverageCheck(),
        InvalidPortfolioStateCheck(),
        InvalidAccountBalanceCheck(),
        InvalidExposureCheck(),
        MissingConfigurationCheck(),
        StrategyVersionMismatchCheck(),
    ]
