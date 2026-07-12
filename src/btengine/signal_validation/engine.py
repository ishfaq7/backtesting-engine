"""The Signal Validation Engine: the quality/integrity gate between the
Scoring Engine and the (not-yet-built) Decision Engine.

Runs a pluggable list of stateless :class:`~btengine.signal_validation.checks.base.ValidationCheck`
instances (dependency injection, defaulting to
:func:`~btengine.signal_validation.checks.builtin.default_checks`) plus
its own two stateful checks — duplicate-signal detection and historical
(monotonic-timestamp) consistency, both of which need memory across
calls that a stateless check cannot hold — and rolls everything up into
one :class:`~btengine.signal_validation.models.ValidatedStrategyState`.

This engine **never modifies** the :class:`~btengine.scoring.models.StrategyScore`
it's given; it only reads it and returns it unchanged, embedded in the
output, alongside a diagnosis.
"""

from __future__ import annotations

import math
from collections import deque
from datetime import datetime

from btengine.analysis.funding_rate.models import FundingAnalysis
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis
from btengine.scoring.models import FeatureStatus, StrategyScore
from btengine.signal_validation.checks.base import ValidationCheck
from btengine.signal_validation.checks.builtin import default_checks
from btengine.signal_validation.config import SignalValidationConfig
from btengine.signal_validation.context import ValidationContext
from btengine.signal_validation.models import (
    ConfidenceStatus,
    DataIntegrityStatus,
    FeatureCompleteness,
    ModuleHealthStatus,
    SignalValidationIssue,
    ValidatedStrategyState,
)

_FRESHNESS_CATEGORIES = {"freshness"}
_INCONSISTENCY_CATEGORIES = {"consistency", "structural", "sequencing"}


class SignalValidationEngine:
    """Validates a :class:`StrategyScore` and its four upstream analyses."""

    def __init__(
        self, config: SignalValidationConfig, *, checks: list[ValidationCheck] | None = None
    ) -> None:
        self._config = config
        self._checks = list(checks) if checks is not None else default_checks()
        self._seen_signals: set[tuple[str, datetime, str]] = set()
        self._history: dict[str, deque[datetime]] = {}

    def validate(
        self,
        symbol: str,
        reference_time: datetime,
        *,
        score: StrategyScore,
        funding: FundingAnalysis | None = None,
        open_interest: OpenInterestAnalysis | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        liquidity: LiquidityAnalysis | None = None,
    ) -> ValidatedStrategyState:
        """Validate ``score`` (and its supplied upstream analyses) for ``symbol``.

        ``reference_time`` is supplied by the caller (never read from the
        wall clock) so this engine behaves identically whether called
        live or replayed inside a backtest with a simulated clock.
        """
        symbol = symbol.upper()
        context = ValidationContext(
            symbol=symbol, reference_time=reference_time, score=score, funding=funding,
            open_interest=open_interest, premium_discount=premium_discount, liquidity=liquidity,
            config=self._config,
        )

        issues: list[SignalValidationIssue] = []
        for check in self._checks:
            issues += check.run(context)
        issues += self._check_duplicate_signal(context)
        issues += self._check_historical_consistency(context)
        self._record_history(context)

        errors = tuple(issue for issue in issues if issue.severity == "ERROR")
        warnings = tuple(issue for issue in issues if issue.severity == "WARNING")

        return ValidatedStrategyState(
            symbol=symbol,
            as_of=score.as_of,
            strategy_version=score.score_version,
            score=score,
            validation_passed=not errors,
            validation_errors=errors,
            validation_warnings=warnings,
            confidence_status=self._confidence_status(score.confidence),
            feature_completeness=self._feature_completeness(score.feature_status),
            module_health=self._module_health(context),
            data_integrity=self._data_integrity(errors, warnings),
        )

    # --- stateful checks -----------------------------------------------------

    def _check_duplicate_signal(self, context: ValidationContext) -> list[SignalValidationIssue]:
        key = (context.symbol, context.score.as_of, context.score.score_version)
        if key in self._seen_signals:
            return [
                SignalValidationIssue(
                    "WARNING", "duplicate",
                    f"duplicate signal for {context.symbol} at {context.score.as_of} "
                    f"(version {context.score.score_version})",
                )
            ]
        self._seen_signals.add(key)
        return []

    def _check_historical_consistency(self, context: ValidationContext) -> list[SignalValidationIssue]:
        history = self._history.get(context.symbol)
        if not history:
            return []
        last_seen = history[-1]
        if context.score.as_of <= last_seen:
            return [
                SignalValidationIssue(
                    "ERROR", "sequencing",
                    f"{context.symbol} score as_of {context.score.as_of} is not after the "
                    f"previously validated as_of {last_seen} (out-of-order replay)",
                )
            ]
        return []

    def _record_history(self, context: ValidationContext) -> None:
        history = self._history.setdefault(
            context.symbol, deque(maxlen=self._config.history_window)
        )
        if not history or context.score.as_of > history[-1]:
            history.append(context.score.as_of)

    # --- rollups ---------------------------------------------------------------

    def _confidence_status(self, confidence: float | None) -> ConfidenceStatus:
        if confidence is None:
            return ConfidenceStatus.UNKNOWN
        if math.isnan(confidence) or math.isinf(confidence) or not (0.0 <= confidence <= 1.0):
            return ConfidenceStatus.INVALID
        if self._config.min_confidence is not None and confidence < self._config.min_confidence:
            return ConfidenceStatus.LOW
        return ConfidenceStatus.VALID

    def _feature_completeness(self, feature_status: dict[str, FeatureStatus]) -> FeatureCompleteness:
        available = tuple(
            sorted(name for name, status in feature_status.items() if status is FeatureStatus.AVAILABLE)
        )
        missing = tuple(sorted(name for name in feature_status if name not in available))
        ratio = len(available) / len(feature_status) if feature_status else 0.0
        threshold = self._config.min_completeness_ratio
        is_sufficient = None if threshold is None else ratio >= threshold
        return FeatureCompleteness(
            available_providers=available, missing_providers=missing,
            completeness_ratio=ratio, is_sufficient=is_sufficient,
        )

    def _module_health(self, context: ValidationContext) -> dict[str, ModuleHealthStatus]:
        health: dict[str, ModuleHealthStatus] = {}
        max_staleness = self._config.max_staleness
        for name, status in context.score.feature_status.items():
            if status is FeatureStatus.MISSING:
                health[name] = ModuleHealthStatus.MISSING
            elif status is FeatureStatus.NOT_IMPLEMENTED:
                health[name] = ModuleHealthStatus.NOT_IMPLEMENTED
            elif status is FeatureStatus.INVALID:
                health[name] = ModuleHealthStatus.INVALID
            else:
                analysis = context.analyses.get(name)
                if (
                    analysis is not None
                    and max_staleness is not None
                    and context.reference_time - analysis.as_of > max_staleness
                ):
                    health[name] = ModuleHealthStatus.STALE
                else:
                    health[name] = ModuleHealthStatus.HEALTHY
        return health

    @staticmethod
    def _data_integrity(
        errors: tuple[SignalValidationIssue, ...], warnings: tuple[SignalValidationIssue, ...]
    ) -> DataIntegrityStatus:
        all_issues = errors + warnings
        if any(issue.category in _FRESHNESS_CATEGORIES for issue in all_issues):
            return DataIntegrityStatus.STALE
        if any(issue.category in _INCONSISTENCY_CATEGORIES for issue in errors):
            return DataIntegrityStatus.INCONSISTENT
        if errors:
            return DataIntegrityStatus.INVALID
        return DataIntegrityStatus.VALID
