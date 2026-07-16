"""The No Trade Framework's orchestrator.

Runs the pluggable input/registration validation checks and every
enabled :class:`~btengine.no_trade.filters.base.NoTradeFilter`, then
rolls everything up into one
:class:`~btengine.no_trade.models.NoTradeAssessment` under strict
**fail-safe gating semantics**: ``trading_allowed`` is only ever
``True`` when validation found no errors, at least one filter actually
ran, and *every* filter that ran explicitly returned
:attr:`~btengine.no_trade.models.FilterVerdict.ALLOW`. An empty
framework, an unimplemented filter (``CANNOT_EVALUATE``), an explicit
``BLOCK``, or any validation error all keep the gate closed — and every
closed gate carries explicit ``blocked_reasons``, never a silent
refusal.

This engine never generates a trading signal — it only answers whether
the system is permitted to trade at all.
"""

from __future__ import annotations

from datetime import datetime

from btengine.analysis.funding_rate.models import FundingAnalysis
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis
from btengine.decision.models import DecisionContext
from btengine.no_trade.checks.base import NoTradeValidationCheck
from btengine.no_trade.checks.builtin import default_checks
from btengine.no_trade.config import NoTradeEngineConfig
from btengine.no_trade.context import NoTradeRequest
from btengine.no_trade.filters.base import NoTradeFilter
from btengine.no_trade.models import (
    FilterResult,
    FilterVerdict,
    NoTradeAssessment,
    NoTradeValidationIssue,
)
from btengine.risk.models import MarketDataSnapshot, PortfolioStateSnapshot, RiskAssessment
from btengine.scoring.models import StrategyScore, ValidationStatus


class NoTradeEngine:
    """Determines whether the system is permitted to trade right now."""

    def __init__(
        self,
        config: NoTradeEngineConfig,
        *,
        filters: list[NoTradeFilter] | None = None,
        checks: list[NoTradeValidationCheck] | None = None,
    ) -> None:
        self._config = config
        self._filters = list(filters) if filters is not None else []
        self._checks = list(checks) if checks is not None else default_checks()

    def evaluate(
        self,
        symbol: str,
        reference_time: datetime,
        *,
        decision_context: DecisionContext,
        score: StrategyScore,
        risk_assessment: RiskAssessment | None = None,
        funding: FundingAnalysis | None = None,
        open_interest: OpenInterestAnalysis | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        liquidity: LiquidityAnalysis | None = None,
        market_data: MarketDataSnapshot | None = None,
        portfolio: PortfolioStateSnapshot | None = None,
    ) -> NoTradeAssessment:
        """Prepare a :class:`NoTradeAssessment` for ``symbol`` as of ``reference_time``."""
        symbol = symbol.upper()
        request = NoTradeRequest(
            symbol=symbol, reference_time=reference_time, decision_context=decision_context,
            score=score, risk_assessment=risk_assessment, funding=funding,
            open_interest=open_interest, premium_discount=premium_discount, liquidity=liquidity,
            market_data=market_data, portfolio=portfolio, config=self._config,
        )
        registered_names = tuple(f.filter_name for f in self._filters)

        issues: list[NoTradeValidationIssue] = []
        for check in self._checks:
            issues += check.run(request, registered_names)
        errors = tuple(issue for issue in issues if issue.severity == "ERROR")
        warnings = tuple(issue for issue in issues if issue.severity == "WARNING")

        active_filters = self._active_filters()
        filter_results = (
            tuple(self._run_filters(request, active_filters)) if not errors else ()
        )

        blocked_reasons = self._blocked_reasons(errors, filter_results, active_filters)
        trading_allowed = not blocked_reasons

        return NoTradeAssessment(
            symbol=symbol,
            as_of=decision_context.as_of,
            strategy_version=decision_context.strategy_version,
            timestamp=reference_time,
            trading_allowed=trading_allowed,
            blocked_reasons=blocked_reasons,
            warning_messages=tuple(issue.message for issue in warnings),
            active_filters=tuple(f.filter_name for f in active_filters),
            validation_status=self._rollup_validation_status(errors, warnings),
            filter_results=filter_results,
            errors=errors,
            warnings=warnings,
            metadata={
                "registered_filters": list(registered_names),
                "engine_version": self._config.engine_version,
                "skipped_filters": [
                    name for name in registered_names
                    if name not in {f.filter_name for f in active_filters}
                ],
            },
        )

    # --- filters -------------------------------------------------------------

    def _active_filters(self) -> list[NoTradeFilter]:
        enabled = self._config.enabled_filters
        if enabled is None:
            return list(self._filters)
        enabled_set = set(enabled)
        return [f for f in self._filters if f.filter_name in enabled_set]

    def _run_filters(
        self, request: NoTradeRequest, active_filters: list[NoTradeFilter]
    ) -> list[FilterResult]:
        results: list[FilterResult] = []
        for no_trade_filter in active_filters:
            try:
                result = no_trade_filter.evaluate(request)
            except NotImplementedError:
                result = FilterResult(
                    filter_name=no_trade_filter.filter_name,
                    filter_version=no_trade_filter.filter_version,
                    verdict=FilterVerdict.CANNOT_EVALUATE,
                    reason="no-trade rule not implemented",
                )
            results.append(result)
        return results

    # --- rollups ----------------------------------------------------------------

    @staticmethod
    def _blocked_reasons(
        errors: tuple[NoTradeValidationIssue, ...],
        filter_results: tuple[FilterResult, ...],
        active_filters: list[NoTradeFilter],
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if errors:
            reasons.append(f"validation failed with {len(errors)} error(s)")
        elif not active_filters:
            reasons.append(
                "no active no-trade filters; trading is not permitted until at "
                "least one filter is registered, enabled, and implemented"
            )
        for result in filter_results:
            if result.verdict is FilterVerdict.BLOCK:
                reasons.append(f"{result.filter_name}: {result.reason}")
            elif result.verdict is FilterVerdict.CANNOT_EVALUATE:
                reasons.append(
                    f"{result.filter_name}: could not evaluate ({result.reason})"
                )
        return tuple(reasons)

    @staticmethod
    def _rollup_validation_status(
        errors: tuple[NoTradeValidationIssue, ...], warnings: tuple[NoTradeValidationIssue, ...]
    ) -> ValidationStatus:
        if errors:
            return ValidationStatus.INVALID
        if warnings:
            return ValidationStatus.WARNING
        return ValidationStatus.VALID
