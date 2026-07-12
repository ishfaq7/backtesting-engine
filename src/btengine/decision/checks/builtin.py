"""The five stateless, built-in decision-input validation checks.

"Duplicate processing" — the sixth named responsibility — needs memory
across calls (has this exact signal already been processed?) and so
lives directly on :class:`~btengine.decision.engine.DecisionEngine`
instead of here, the same split
:class:`~btengine.signal_validation.engine.SignalValidationEngine` uses
for its own stateful checks.
"""

from __future__ import annotations

import math

from btengine.decision.checks.base import DecisionValidationCheck
from btengine.decision.context import DecisionRequest
from btengine.decision.models import DecisionValidationIssue


class MissingInputsCheck(DecisionValidationCheck):
    """Flags any of the four analyses that was not supplied at all."""

    @property
    def check_name(self) -> str:
        return "missing_inputs"

    def run(self, request: DecisionRequest) -> list[DecisionValidationIssue]:
        return [
            DecisionValidationIssue(
                "WARNING", "completeness", f"{name} analysis was not provided", name
            )
            for name, analysis in request.analyses.items()
            if analysis is None
        ]


class InvalidScoreObjectCheck(DecisionValidationCheck):
    """Structural sanity of the upstream :class:`~btengine.scoring.models.StrategyScore`.

    Independent, defense-in-depth re-validation — the score has already
    passed through the Scoring Engine's own validator and the Signal
    Validation Engine, but this framework does not assume either
    upstream stage was error-free.
    """

    @property
    def check_name(self) -> str:
        return "invalid_score_object"

    def run(self, request: DecisionRequest) -> list[DecisionValidationIssue]:
        score = request.validated_state.score
        issues: list[DecisionValidationIssue] = []
        if not score.symbol:
            issues.append(
                DecisionValidationIssue("ERROR", "structural", "score has an empty symbol", "score")
            )
        if score.as_of.tzinfo is None:
            issues.append(
                DecisionValidationIssue(
                    "ERROR", "structural", "score has a naive (non-timezone-aware) timestamp", "score"
                )
            )
        if not score.score_version.strip():
            issues.append(
                DecisionValidationIssue("ERROR", "structural", "score has an empty score_version", "score")
            )
        confidence = score.confidence
        if confidence is not None and (
            math.isnan(confidence) or math.isinf(confidence) or not (0.0 <= confidence <= 1.0)
        ):
            issues.append(
                DecisionValidationIssue(
                    "ERROR", "structural", f"score has an invalid confidence {confidence}", "score"
                )
            )
        return issues


class InvalidAnalysisObjectsCheck(DecisionValidationCheck):
    """Structural sanity of every supplied analysis object.

    Mirrors :class:`btengine.signal_validation.checks.builtin.InvalidAnalyticalObjectsCheck`
    (re-checking the same invariants at this later stage is deliberate
    defense-in-depth, not a re-derivation of any analyzer's own logic).
    """

    @property
    def check_name(self) -> str:
        return "invalid_analysis_objects"

    def run(self, request: DecisionRequest) -> list[DecisionValidationIssue]:
        issues: list[DecisionValidationIssue] = []
        for name, analysis in request.analyses.items():
            if analysis is None:
                continue
            if not analysis.symbol:
                issues.append(
                    DecisionValidationIssue(
                        "ERROR", "structural", f"{name} analysis has an empty symbol", name
                    )
                )
            if analysis.as_of.tzinfo is None:
                issues.append(
                    DecisionValidationIssue(
                        "ERROR", "structural",
                        f"{name} analysis has a naive (non-timezone-aware) timestamp", name,
                    )
                )
            confidence = analysis.confidence_level
            if math.isnan(confidence) or math.isinf(confidence) or not (0.0 <= confidence <= 1.0):
                issues.append(
                    DecisionValidationIssue(
                        "ERROR", "structural",
                        f"{name} analysis has an invalid confidence_level {confidence}", name,
                    )
                )
        return issues


class StrategyVersionMismatchCheck(DecisionValidationCheck):
    """Flags a ``strategy_version`` that doesn't match the configured
    expectation, and any internal disagreement between
    ``ValidatedStrategyState.strategy_version`` and its own embedded
    score's ``score_version``.
    """

    @property
    def check_name(self) -> str:
        return "strategy_version_mismatch"

    def run(self, request: DecisionRequest) -> list[DecisionValidationIssue]:
        issues: list[DecisionValidationIssue] = []
        state = request.validated_state
        expected = request.config.expected_strategy_version
        if expected is not None and state.strategy_version != expected:
            issues.append(
                DecisionValidationIssue(
                    "WARNING", "version",
                    f"strategy_version {state.strategy_version!r} does not match "
                    f"expected {expected!r}",
                )
            )
        if state.strategy_version != state.score.score_version:
            issues.append(
                DecisionValidationIssue(
                    "WARNING", "version",
                    f"ValidatedStrategyState.strategy_version {state.strategy_version!r} disagrees "
                    f"with its embedded score_version {state.score.score_version!r}",
                )
            )
        return issues


class UnsupportedDecisionProvidersCheck(DecisionValidationCheck):
    """Flags any provider named in ``required_providers`` that isn't
    actually registered with the engine.
    """

    @property
    def check_name(self) -> str:
        return "unsupported_decision_providers"

    def run(self, request: DecisionRequest) -> list[DecisionValidationIssue]:
        required = request.config.required_providers or ()
        registered = set(request.provider_names)
        return [
            DecisionValidationIssue(
                "ERROR", "unsupported",
                f"required decision provider {name!r} is not registered with this engine", name,
            )
            for name in required
            if name not in registered
        ]


def default_checks() -> list[DecisionValidationCheck]:
    """The standard set of built-in checks, in a stable, deterministic order."""
    return [
        MissingInputsCheck(),
        InvalidScoreObjectCheck(),
        InvalidAnalysisObjectsCheck(),
        StrategyVersionMismatchCheck(),
        UnsupportedDecisionProvidersCheck(),
    ]
