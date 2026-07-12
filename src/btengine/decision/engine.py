"""The Decision Engine Framework: prepares a standardized
:class:`~btengine.decision.models.DecisionContext` from a
:class:`~btengine.signal_validation.models.ValidatedStrategyState` and
its four upstream analyses.

This is explicitly a framework, not a strategy: it validates its
inputs, orders and runs whatever
:class:`~btengine.decision.providers.base.DecisionProvider` instances
it was given, and rolls the result up into a readiness diagnosis —
never a BUY/SELL/ENTER/EXIT decision. With zero providers configured
(the expected state until proprietary decision logic exists), every
call resolves to :attr:`~btengine.decision.models.DecisionStatus.PENDING`
with ``execution_ready=False``.
"""

from __future__ import annotations

from datetime import datetime

from btengine.analysis.funding_rate.models import FundingAnalysis
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis
from btengine.decision.checks.base import DecisionValidationCheck
from btengine.decision.checks.builtin import default_checks
from btengine.decision.config import DecisionEngineConfig, order_provider_names_by_priority
from btengine.decision.context import DecisionRequest
from btengine.decision.models import DecisionContext, DecisionOutcome, DecisionStatus, DecisionValidationIssue
from btengine.decision.providers.base import DecisionProvider
from btengine.scoring.models import ValidationStatus
from btengine.signal_validation.models import ValidatedStrategyState

_NON_PENDING_STATUSES = {DecisionStatus.EVALUATED}


class DecisionEngine:
    """Prepares a :class:`DecisionContext` from a :class:`ValidatedStrategyState`."""

    def __init__(
        self,
        config: DecisionEngineConfig,
        *,
        providers: list[DecisionProvider] | None = None,
        checks: list[DecisionValidationCheck] | None = None,
    ) -> None:
        self._config = config
        self._providers = list(providers) if providers is not None else []
        self._checks = list(checks) if checks is not None else default_checks()
        self._processed: set[tuple[str, datetime, str]] = set()

    def decide(
        self,
        symbol: str,
        reference_time: datetime,
        *,
        validated_state: ValidatedStrategyState,
        funding: FundingAnalysis | None = None,
        open_interest: OpenInterestAnalysis | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        liquidity: LiquidityAnalysis | None = None,
    ) -> DecisionContext:
        """Prepare a :class:`DecisionContext` for ``symbol`` as of ``reference_time``.

        The upstream :class:`~btengine.scoring.models.StrategyScore` is
        read via ``validated_state.score`` — not a separate parameter —
        so there is exactly one source of truth. ``reference_time`` is
        supplied by the caller and never read from the wall clock.
        """
        symbol = symbol.upper()
        request = DecisionRequest(
            symbol=symbol, reference_time=reference_time, validated_state=validated_state,
            funding=funding, open_interest=open_interest, premium_discount=premium_discount,
            liquidity=liquidity, config=self._config,
            provider_names=tuple(provider.provider_name for provider in self._providers),
        )

        issues: list[DecisionValidationIssue] = []
        for check in self._checks:
            issues += check.run(request)
        issues += self._check_duplicate_processing(request)
        self._record_processed(request)

        errors = tuple(issue for issue in issues if issue.severity == "ERROR")
        warnings = tuple(issue for issue in issues if issue.severity == "WARNING")
        validation_status = self._rollup_validation_status(errors, warnings)

        upstream_invalid = self._config.require_validation_passed and not validated_state.validation_passed

        if errors or upstream_invalid:
            decision_status = DecisionStatus.NOT_READY
            outcomes: tuple[DecisionOutcome, ...] = ()
            reason = self._not_ready_reason(errors, upstream_invalid)
        else:
            outcomes = tuple(self._run_providers(request))
            if any(outcome.status in _NON_PENDING_STATUSES for outcome in outcomes):
                decision_status = DecisionStatus.EVALUATED
                reason = "one or more decision providers produced an outcome"
            elif outcomes:
                decision_status = DecisionStatus.PENDING
                reason = "decision providers ran but produced no substantive outcome yet"
            else:
                decision_status = DecisionStatus.PENDING
                reason = "no decision providers configured; awaiting proprietary decision logic"

        execution_ready = decision_status is DecisionStatus.EVALUATED and not errors

        return DecisionContext(
            symbol=symbol,
            as_of=validated_state.as_of,
            strategy_version=validated_state.strategy_version,
            timestamp=reference_time,
            decision_status=decision_status,
            decision_reason=reason,
            validation_status=validation_status,
            execution_ready=execution_ready,
            provider_outcomes=outcomes,
            validation_errors=errors,
            validation_warnings=warnings,
            metadata={
                "registered_providers": list(request.provider_names),
                "engine_version": self._config.engine_version,
            },
        )

    # --- providers -------------------------------------------------------------

    def _run_providers(self, request: DecisionRequest) -> list[DecisionOutcome]:
        by_name = {provider.provider_name: provider for provider in self._providers}
        ordered_names = order_provider_names_by_priority(
            list(by_name), self._config.provider_priorities
        )
        outcomes: list[DecisionOutcome] = []
        for name in ordered_names:
            provider = by_name[name]
            try:
                outcome = provider.decide(request)
            except NotImplementedError:
                outcome = DecisionOutcome(
                    provider_name=name, provider_version=provider.provider_version,
                    status=DecisionStatus.PENDING, reason="decision logic not implemented",
                )
            outcomes.append(outcome)
        return outcomes

    # --- stateful check ----------------------------------------------------------

    def _check_duplicate_processing(self, request: DecisionRequest) -> list[DecisionValidationIssue]:
        key = (
            request.symbol,
            request.validated_state.as_of,
            request.validated_state.strategy_version,
        )
        if key in self._processed:
            return [
                DecisionValidationIssue(
                    "WARNING", "duplicate",
                    f"duplicate processing for {request.symbol} at {request.validated_state.as_of} "
                    f"(version {request.validated_state.strategy_version})",
                )
            ]
        return []

    def _record_processed(self, request: DecisionRequest) -> None:
        self._processed.add(
            (request.symbol, request.validated_state.as_of, request.validated_state.strategy_version)
        )

    # --- rollups -------------------------------------------------------------------

    @staticmethod
    def _rollup_validation_status(
        errors: tuple[DecisionValidationIssue, ...], warnings: tuple[DecisionValidationIssue, ...]
    ) -> ValidationStatus:
        if errors:
            return ValidationStatus.INVALID
        if warnings:
            return ValidationStatus.WARNING
        return ValidationStatus.VALID

    @staticmethod
    def _not_ready_reason(errors: tuple[DecisionValidationIssue, ...], upstream_invalid: bool) -> str:
        parts = []
        if errors:
            parts.append(f"{len(errors)} validation error(s)")
        if upstream_invalid:
            parts.append("upstream signal validation failed")
        return "not ready: " + "; ".join(parts)
