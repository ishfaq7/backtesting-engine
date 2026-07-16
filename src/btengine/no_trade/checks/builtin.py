"""The five stateless, built-in no-trade validation checks.

These cover this task's five named VALIDATION responsibilities — input
and registration integrity only, never a gating rule.
"""

from __future__ import annotations

import math

from btengine.no_trade.checks.base import NoTradeValidationCheck
from btengine.no_trade.context import NoTradeRequest
from btengine.no_trade.models import NoTradeValidationIssue


class MissingFilterInputsCheck(NoTradeValidationCheck):
    """Flags any optional input that was not supplied at all.

    ``WARNING`` only — a future filter that doesn't need the missing
    input can still evaluate; one that does need it will return
    ``CANNOT_EVALUATE``, which already keeps the gate closed.
    """

    @property
    def check_name(self) -> str:
        return "missing_filter_inputs"

    def run(self, request: NoTradeRequest, registered_filter_names) -> list[NoTradeValidationIssue]:
        issues = [
            NoTradeValidationIssue(
                "WARNING", "completeness", f"{name} analysis was not provided", name
            )
            for name, analysis in request.analyses.items()
            if analysis is None
        ]
        for name, value in (
            ("risk_assessment", request.risk_assessment),
            ("market_data", request.market_data),
            ("portfolio", request.portfolio),
        ):
            if value is None:
                issues.append(
                    NoTradeValidationIssue(
                        "WARNING", "completeness", f"{name} was not provided"
                    )
                )
        return issues


class InvalidDataCheck(NoTradeValidationCheck):
    """Structural sanity of the supplied objects — defense-in-depth
    re-validation at this final pre-trade stage, mirroring the same
    checks every prior engine applies at its own boundary.
    """

    @property
    def check_name(self) -> str:
        return "invalid_data"

    def run(self, request: NoTradeRequest, registered_filter_names) -> list[NoTradeValidationIssue]:
        issues: list[NoTradeValidationIssue] = []

        score = request.score
        if not score.symbol:
            issues.append(NoTradeValidationIssue("ERROR", "structural", "score has an empty symbol"))
        if score.as_of.tzinfo is None:
            issues.append(
                NoTradeValidationIssue(
                    "ERROR", "structural", "score has a naive (non-timezone-aware) timestamp"
                )
            )

        for name, analysis in request.analyses.items():
            if analysis is None:
                continue
            confidence = analysis.confidence_level
            if math.isnan(confidence) or math.isinf(confidence) or not (0.0 <= confidence <= 1.0):
                issues.append(
                    NoTradeValidationIssue(
                        "ERROR", "structural",
                        f"{name} analysis has an invalid confidence_level {confidence}", name,
                    )
                )

        market_data = request.market_data
        if market_data is not None and (
            math.isnan(market_data.price) or math.isinf(market_data.price) or market_data.price <= 0
        ):
            issues.append(
                NoTradeValidationIssue(
                    "ERROR", "structural",
                    f"market data for {market_data.symbol} has invalid price {market_data.price}",
                )
            )

        portfolio = request.portfolio
        if portfolio is not None and (math.isnan(portfolio.equity) or math.isinf(portfolio.equity)):
            issues.append(
                NoTradeValidationIssue(
                    "ERROR", "structural", f"portfolio equity is {portfolio.equity}"
                )
            )
        return issues


class ConflictingFiltersCheck(NoTradeValidationCheck):
    """Flags an ``enabled_filters`` entry that names no registered filter —
    the configuration and the registration disagree about which filters
    exist, so the configured intent cannot actually run.
    """

    @property
    def check_name(self) -> str:
        return "conflicting_filters"

    def run(self, request: NoTradeRequest, registered_filter_names) -> list[NoTradeValidationIssue]:
        enabled = request.config.enabled_filters
        if enabled is None:
            return []
        registered = set(registered_filter_names)
        return [
            NoTradeValidationIssue(
                "ERROR", "registration",
                f"enabled filter {name!r} is not registered with this engine", name,
            )
            for name in enabled
            if name not in registered
        ]


class DuplicateFiltersCheck(NoTradeValidationCheck):
    """Flags two registered filters sharing one ``filter_name`` — the
    name is the configuration key, so a duplicate makes enable/disable
    and parameter lookup ambiguous.
    """

    @property
    def check_name(self) -> str:
        return "duplicate_filters"

    def run(self, request: NoTradeRequest, registered_filter_names) -> list[NoTradeValidationIssue]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for name in registered_filter_names:
            if name in seen and name not in duplicates:
                duplicates.append(name)
            seen.add(name)
        return [
            NoTradeValidationIssue(
                "ERROR", "registration", f"filter {name!r} is registered more than once", name
            )
            for name in duplicates
        ]


class StrategyVersionMismatchCheck(NoTradeValidationCheck):
    """Flags a strategy version that doesn't match the configured
    expectation, and any disagreement among the versioned inputs.
    """

    @property
    def check_name(self) -> str:
        return "strategy_version_mismatch"

    def run(self, request: NoTradeRequest, registered_filter_names) -> list[NoTradeValidationIssue]:
        issues: list[NoTradeValidationIssue] = []
        decision_version = request.decision_context.strategy_version
        expected = request.config.expected_strategy_version
        if expected is not None and decision_version != expected:
            issues.append(
                NoTradeValidationIssue(
                    "WARNING", "version",
                    f"strategy_version {decision_version!r} does not match expected {expected!r}",
                )
            )
        if decision_version != request.score.score_version:
            issues.append(
                NoTradeValidationIssue(
                    "WARNING", "version",
                    f"DecisionContext.strategy_version {decision_version!r} disagrees with "
                    f"StrategyScore.score_version {request.score.score_version!r}",
                )
            )
        risk = request.risk_assessment
        if risk is not None and risk.strategy_version != decision_version:
            issues.append(
                NoTradeValidationIssue(
                    "WARNING", "version",
                    f"RiskAssessment.strategy_version {risk.strategy_version!r} disagrees with "
                    f"DecisionContext.strategy_version {decision_version!r}",
                )
            )
        return issues


def default_checks() -> list[NoTradeValidationCheck]:
    """The standard set of built-in checks, in a stable, deterministic order."""
    return [
        MissingFilterInputsCheck(),
        InvalidDataCheck(),
        ConflictingFiltersCheck(),
        DuplicateFiltersCheck(),
        StrategyVersionMismatchCheck(),
    ]
