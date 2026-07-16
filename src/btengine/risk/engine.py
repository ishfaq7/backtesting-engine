"""The Risk Management Framework's orchestrator.

Runs the pluggable input-validation checks and every registered
:class:`~btengine.risk.modules.base.RiskModule`, then rolls everything
up into one :class:`~btengine.risk.models.RiskAssessment` under strict
**fail-safe semantics**: ``risk_approved`` is only ever ``True`` when
validation found no errors, at least one module is registered, and
*every* registered module explicitly returned ``approved=True``. An
empty framework, an unimplemented module (``approved=None``), or any
validation error all resolve to ``risk_approved=False`` — an
unimplemented risk system must never fail open.

This engine never creates a trading signal, never sizes a position,
never sets leverage/stop/take-profit values — with the framework-only
modules shipped here, every numeric output field stays ``None``.
"""

from __future__ import annotations

from datetime import datetime

from btengine.decision.models import DecisionContext
from btengine.risk.checks.base import RiskValidationCheck
from btengine.risk.checks.builtin import default_checks
from btengine.risk.config import RiskEngineConfig
from btengine.risk.context import RiskRequest
from btengine.risk.models import (
    ExposureStatus,
    MarketDataSnapshot,
    PortfolioStateSnapshot,
    RiskAssessment,
    RiskModuleResult,
    RiskValidationIssue,
)
from btengine.risk.modules.base import RiskModule
from btengine.scoring.models import StrategyScore, ValidationStatus

# Which module's result feeds which RiskAssessment field, once real
# implementations exist. Unknown module names simply don't map to a field.
_FIELD_BY_MODULE = {
    "position_sizing": "position_size",
    "leverage_validation": "leverage_allowed",
    "max_risk_validation": "max_risk_allowed",
    "portfolio_risk": "portfolio_risk",
}


class RiskEngine:
    """Prepares a :class:`RiskAssessment` from a decision context and portfolio state."""

    def __init__(
        self,
        config: RiskEngineConfig,
        *,
        modules: list[RiskModule] | None = None,
        checks: list[RiskValidationCheck] | None = None,
    ) -> None:
        self._config = config
        self._modules = list(modules) if modules is not None else []
        self._checks = list(checks) if checks is not None else default_checks()

    def assess(
        self,
        symbol: str,
        reference_time: datetime,
        *,
        decision_context: DecisionContext,
        score: StrategyScore,
        portfolio: PortfolioStateSnapshot,
        market_data: MarketDataSnapshot | None = None,
    ) -> RiskAssessment:
        """Prepare a :class:`RiskAssessment` for ``symbol`` as of ``reference_time``."""
        symbol = symbol.upper()
        request = RiskRequest(
            symbol=symbol, reference_time=reference_time, decision_context=decision_context,
            score=score, portfolio=portfolio, market_data=market_data, config=self._config,
        )

        issues: list[RiskValidationIssue] = []
        for check in self._checks:
            issues += check.run(request)
        errors = tuple(issue for issue in issues if issue.severity == "ERROR")
        warnings = tuple(issue for issue in issues if issue.severity == "WARNING")

        module_results = tuple(self._run_modules(request)) if not errors else ()

        risk_approved = (
            not errors
            and bool(module_results)
            and all(result.approved is True for result in module_results)
        )

        values = self._collect_module_values(module_results)
        exposure_status = self._exposure_status(module_results)

        return RiskAssessment(
            symbol=symbol,
            as_of=decision_context.as_of,
            strategy_version=decision_context.strategy_version,
            timestamp=reference_time,
            risk_approved=risk_approved,
            position_size=values.get("position_size"),
            leverage_allowed=values.get("leverage_allowed"),
            max_risk_allowed=values.get("max_risk_allowed"),
            exposure_status=exposure_status,
            portfolio_risk=values.get("portfolio_risk"),
            validation_status=self._rollup_validation_status(errors, warnings),
            module_results=module_results,
            errors=errors,
            warnings=warnings,
            metadata={
                "registered_modules": [module.module_name for module in self._modules],
                "engine_version": self._config.engine_version,
                "active_profile": self._config.active_profile,
            },
        )

    # --- modules -----------------------------------------------------------

    def _run_modules(self, request: RiskRequest) -> list[RiskModuleResult]:
        results: list[RiskModuleResult] = []
        for module in self._modules:
            try:
                result = module.evaluate(request)
            except NotImplementedError:
                result = RiskModuleResult(
                    module_name=module.module_name, module_version=module.module_version,
                    approved=None, value=None, reason="risk rule not implemented",
                )
            results.append(result)
        return results

    @staticmethod
    def _collect_module_values(module_results: tuple[RiskModuleResult, ...]) -> dict[str, float]:
        values: dict[str, float] = {}
        for result in module_results:
            field = _FIELD_BY_MODULE.get(result.module_name)
            if field is not None and result.value is not None:
                values[field] = result.value
        return values

    @staticmethod
    def _exposure_status(module_results: tuple[RiskModuleResult, ...]) -> ExposureStatus:
        for result in module_results:
            if result.module_name == "exposure_management" and result.approved is not None:
                return ExposureStatus.WITHIN_LIMITS if result.approved else ExposureStatus.EXCEEDED
        return ExposureStatus.UNKNOWN

    @staticmethod
    def _rollup_validation_status(
        errors: tuple[RiskValidationIssue, ...], warnings: tuple[RiskValidationIssue, ...]
    ) -> ValidationStatus:
        if errors:
            return ValidationStatus.INVALID
        if warnings:
            return ValidationStatus.WARNING
        return ValidationStatus.VALID
