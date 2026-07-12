"""Validates a set of :class:`~btengine.scoring.models.ScoreComponent`
objects before they're assembled into a :class:`~btengine.scoring.models.StrategyScore`.

Checks exactly the five things this task's VALIDATION section names:
missing feature inputs, invalid scores, duplicate calculations, missing
modules, and version mismatch. "Duplicate calculations" is the one
check that needs state across calls (has this exact (symbol, as_of,
version) already been scored?) and so lives on
:class:`~btengine.scoring.engine.ScoringEngine` itself rather than here
— this validator only inspects one snapshot of components in isolation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from btengine.scoring.config import ScoringEngineConfig
from btengine.scoring.models import ScoreComponent, StrategyScoreValidationIssue


class StrategyScoreValidator:
    """Runs every check and returns the full list of issues found."""

    def __init__(self, config: ScoringEngineConfig | None = None) -> None:
        self._config = config or ScoringEngineConfig(engine_version="unversioned")

    def validate(
        self, components: Mapping[str, ScoreComponent | None]
    ) -> list[StrategyScoreValidationIssue]:
        issues: list[StrategyScoreValidationIssue] = []
        issues += self._check_missing_modules(components)
        issues += self._check_missing_feature_inputs(components)
        issues += self._check_invalid_scores(components)
        issues += self._check_version_consistency(components)
        return issues

    def _check_missing_modules(
        self, components: Mapping[str, ScoreComponent | None]
    ) -> list[StrategyScoreValidationIssue]:
        required = self._config.required_providers or ()
        return [
            StrategyScoreValidationIssue(
                "ERROR", f"required provider {name!r} is missing", name
            )
            for name in required
            if components.get(name) is None
        ]

    def _check_missing_feature_inputs(
        self, components: Mapping[str, ScoreComponent | None]
    ) -> list[StrategyScoreValidationIssue]:
        return [
            StrategyScoreValidationIssue(
                "WARNING",
                f"{name} input had zero confidence (no usable historical data upstream)",
                name,
            )
            for name, component in components.items()
            if component is not None and component.confidence == 0.0
        ]

    def _check_invalid_scores(
        self, components: Mapping[str, ScoreComponent | None]
    ) -> list[StrategyScoreValidationIssue]:
        issues: list[StrategyScoreValidationIssue] = []
        for name, component in components.items():
            if component is None or component.value is None:
                continue
            if math.isnan(component.value) or math.isinf(component.value):
                issues.append(
                    StrategyScoreValidationIssue(
                        "ERROR", f"{name} score {component.value} is NaN/infinite", name
                    )
                )
            elif not (self._config.score_min <= component.value <= self._config.score_max):
                issues.append(
                    StrategyScoreValidationIssue(
                        "ERROR",
                        f"{name} score {component.value} is outside "
                        f"[{self._config.score_min}, {self._config.score_max}]",
                        name,
                    )
                )
        return issues

    def _check_version_consistency(
        self, components: Mapping[str, ScoreComponent | None]
    ) -> list[StrategyScoreValidationIssue]:
        return [
            StrategyScoreValidationIssue(
                "WARNING",
                f"{name} provider_version {component.provider_version!r} does not match "
                f"engine_version {self._config.engine_version!r}",
                name,
            )
            for name, component in components.items()
            if component is not None and component.provider_version != self._config.engine_version
        ]
