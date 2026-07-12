"""The eight stateless, built-in validation checks.

Two of this task's ten named responsibilities — "Duplicate signals" and
"Historical consistency" — need state across calls (has this exact
signal been seen before? are timestamps arriving in order?) and so live
directly on :class:`~btengine.signal_validation.engine.SignalValidationEngine`
instead of here; every check in this module only ever looks at the one
:class:`~btengine.signal_validation.context.ValidationContext` it's
given.
"""

from __future__ import annotations

import math
from datetime import timedelta

from btengine.scoring.models import FeatureStatus
from btengine.signal_validation.checks.base import ValidationCheck
from btengine.signal_validation.context import ValidationContext
from btengine.signal_validation.models import SignalValidationIssue


class MissingFeatureInputsCheck(ValidationCheck):
    """Flags any of the four analyses that was not supplied at all."""

    @property
    def check_name(self) -> str:
        return "missing_feature_inputs"

    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        return [
            SignalValidationIssue(
                "WARNING", "completeness", f"{name} analysis was not provided", name
            )
            for name, analysis in context.analyses.items()
            if analysis is None
        ]


class InvalidAnalyticalObjectsCheck(ValidationCheck):
    """Structural sanity of every supplied analysis object.

    The four analysis dataclasses are plain (not pydantic-validated), so
    a hand-constructed or corrupted object could violate the invariants
    their own engines guarantee (a timezone-aware timestamp, a
    non-empty symbol, a ``confidence_level`` in ``[0, 1]``). This is
    independent, defense-in-depth re-validation, not a re-derivation of
    any analyzer's own logic.
    """

    @property
    def check_name(self) -> str:
        return "invalid_analytical_objects"

    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        issues: list[SignalValidationIssue] = []
        for name, analysis in context.analyses.items():
            if analysis is None:
                continue
            if not analysis.symbol:
                issues.append(
                    SignalValidationIssue(
                        "ERROR", "structural", f"{name} analysis has an empty symbol", name
                    )
                )
            if analysis.as_of.tzinfo is None:
                issues.append(
                    SignalValidationIssue(
                        "ERROR", "structural",
                        f"{name} analysis has a naive (non-timezone-aware) timestamp", name,
                    )
                )
            confidence = analysis.confidence_level
            if math.isnan(confidence) or math.isinf(confidence) or not (0.0 <= confidence <= 1.0):
                issues.append(
                    SignalValidationIssue(
                        "ERROR", "structural",
                        f"{name} analysis has an invalid confidence_level {confidence}", name,
                    )
                )
        return issues


class MissingScoreProvidersCheck(ValidationCheck):
    """Flags any score provider whose :class:`~btengine.scoring.models.FeatureStatus`
    isn't ``AVAILABLE`` — ``ERROR`` if it's in ``required_providers``, ``WARNING`` otherwise.
    """

    @property
    def check_name(self) -> str:
        return "missing_score_providers"

    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        required = context.config.required_providers or ()
        issues: list[SignalValidationIssue] = []
        for name, status in context.score.feature_status.items():
            if status is FeatureStatus.AVAILABLE:
                continue
            severity = "ERROR" if name in required else "WARNING"
            issues.append(
                SignalValidationIssue(
                    severity, "completeness", f"score provider {name!r} is {status.value}", name
                )
            )
        return issues


class ConflictingModuleOutputsCheck(ValidationCheck):
    """Flags structural, objective disagreement between modules.

    Scoped deliberately to *identity* consistency (does everything agree
    on which symbol this is, and roughly when) rather than comparing
    analytical field values against each other — deciding what counts as
    a "conflicting" funding trend vs. open interest trend would be
    inventing a strategy interpretation, which this framework must not do.
    """

    @property
    def check_name(self) -> str:
        return "conflicting_module_outputs"

    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        issues: list[SignalValidationIssue] = []
        present = {name: a for name, a in context.analyses.items() if a is not None}

        for name, analysis in present.items():
            if analysis.symbol != context.symbol:
                issues.append(
                    SignalValidationIssue(
                        "ERROR", "consistency",
                        f"{name} analysis symbol {analysis.symbol!r} does not match {context.symbol!r}",
                        name,
                    )
                )
        if context.score.symbol != context.symbol:
            issues.append(
                SignalValidationIssue(
                    "ERROR", "consistency",
                    f"score symbol {context.score.symbol!r} does not match {context.symbol!r}", "score",
                )
            )

        skew = context.config.max_timestamp_skew
        if skew is not None and present:
            timestamps = [analysis.as_of for analysis in present.values()]
            spread = max(timestamps) - min(timestamps)
            if spread > skew:
                issues.append(
                    SignalValidationIssue(
                        "WARNING", "consistency",
                        f"analysis timestamps span {spread}, exceeding max_timestamp_skew {skew}",
                    )
                )
        return issues


class InvalidConfidenceValuesCheck(ValidationCheck):
    """Flags a structurally invalid or (if configured) too-low ``StrategyScore.confidence``."""

    @property
    def check_name(self) -> str:
        return "invalid_confidence_values"

    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        confidence = context.score.confidence
        if confidence is None:
            return []
        if math.isnan(confidence) or math.isinf(confidence) or not (0.0 <= confidence <= 1.0):
            return [
                SignalValidationIssue(
                    "ERROR", "confidence", f"StrategyScore confidence {confidence} is invalid"
                )
            ]
        min_confidence = context.config.min_confidence
        if min_confidence is not None and confidence < min_confidence:
            return [
                SignalValidationIssue(
                    "WARNING", "confidence",
                    f"StrategyScore confidence {confidence} is below min_confidence {min_confidence}",
                )
            ]
        return []


class VersionMismatchCheck(ValidationCheck):
    """Flags a ``score_version`` that doesn't match the configured expectation,
    and any disagreement between the score components' own ``provider_version``s.
    """

    @property
    def check_name(self) -> str:
        return "version_mismatch"

    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        issues: list[SignalValidationIssue] = []
        expected = context.config.expected_score_version
        if expected is not None and context.score.score_version != expected:
            issues.append(
                SignalValidationIssue(
                    "WARNING", "version",
                    f"score_version {context.score.score_version!r} does not match "
                    f"expected {expected!r}",
                )
            )

        component_versions = {
            name: component.provider_version
            for name, component in (
                ("funding", context.score.funding_score),
                ("open_interest", context.score.oi_score),
                ("premium_discount", context.score.premium_discount_score),
                ("liquidity", context.score.liquidity_score),
            )
            if component is not None
        }
        if len(set(component_versions.values())) > 1:
            issues.append(
                SignalValidationIssue(
                    "WARNING", "version",
                    f"score components disagree on provider_version: {component_versions}",
                )
            )
        return issues


class DataFreshnessCheck(ValidationCheck):
    """Flags a timestamp from the future unconditionally, and a stale
    timestamp whenever ``max_staleness`` is configured.
    """

    @property
    def check_name(self) -> str:
        return "data_freshness"

    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        issues: list[SignalValidationIssue] = []
        max_staleness = context.config.max_staleness
        timestamped = {**context.analyses, "score": context.score}

        for name, obj in timestamped.items():
            if obj is None:
                continue
            provider_name = None if name == "score" else name
            age = context.reference_time - obj.as_of
            if age < timedelta(0):
                issues.append(
                    SignalValidationIssue(
                        "WARNING", "freshness",
                        f"{name} timestamp is in the future relative to reference_time (by {-age})",
                        provider_name,
                    )
                )
            elif max_staleness is not None and age > max_staleness:
                issues.append(
                    SignalValidationIssue(
                        "WARNING", "freshness",
                        f"{name} is stale: age {age} exceeds max_staleness {max_staleness}",
                        provider_name,
                    )
                )
        return issues


class StrategyCompletenessCheck(ValidationCheck):
    """Flags an aggregate feature-completeness ratio below the configured minimum.

    Distinct from :class:`MissingScoreProvidersCheck`, which flags
    individual missing/unavailable providers by name; this check only
    looks at the overall fraction available.
    """

    @property
    def check_name(self) -> str:
        return "strategy_completeness"

    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        threshold = context.config.min_completeness_ratio
        if threshold is None:
            return []
        feature_status = context.score.feature_status
        if not feature_status:
            return []
        available = sum(1 for status in feature_status.values() if status is FeatureStatus.AVAILABLE)
        ratio = available / len(feature_status)
        if ratio < threshold:
            return [
                SignalValidationIssue(
                    "WARNING", "completeness",
                    f"strategy completeness {ratio:.2f} is below min_completeness_ratio {threshold}",
                )
            ]
        return []


def default_checks() -> list[ValidationCheck]:
    """The standard set of built-in checks, in a stable, deterministic order."""
    return [
        MissingFeatureInputsCheck(),
        InvalidAnalyticalObjectsCheck(),
        MissingScoreProvidersCheck(),
        ConflictingModuleOutputsCheck(),
        InvalidConfidenceValuesCheck(),
        VersionMismatchCheck(),
        DataFreshnessCheck(),
        StrategyCompletenessCheck(),
    ]
