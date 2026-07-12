"""Configuration for the Scoring Engine Framework.

Every weight and threshold here defaults to ``None`` — an explicit,
unset placeholder, exactly like every analysis module's own
``*AnalysisConfig`` before it. This is the most important config in the
whole project to keep unopinionated: it is, by the task's own framing,
"the core of the proprietary strategy," so nothing here may guess a
weight, a threshold, or a priority on the strategy owner's behalf.

``engine_version`` has no default (unlike every other field) — every
:class:`~btengine.scoring.engine.ScoringEngine` must be explicitly
versioned, the same requirement
:class:`btengine.strategy.scoring.config.ScoringModelConfig.version`
already places on the declarative strategy-spec layer this engine can
be driven from (see :func:`weights_from_scoring_model_config`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

from btengine.scoring.errors import ScoringConfigError
from btengine.strategy.scoring.config import ScoringModelConfig

_PROVIDER_NAMES = ("funding", "open_interest", "premium_discount", "liquidity")

# The strategy-spec layer's rule-category naming (btengine/strategy/rules/,
# config/strategy/rules/) doesn't exactly match this engine's provider
# names (e.g. "funding_rate" vs "funding") - see weights_from_scoring_model_config.
_SOURCE_RULE_SET_TO_PROVIDER_NAME = {
    "funding_rate": "funding",
    "open_interest": "open_interest",
    "premium_discount": "premium_discount",
    "liquidity": "liquidity",
}


class ConfidenceAggregationMethod(str, Enum):
    """How the ``confidence_level`` of each supplied analysis combines
    into :class:`~btengine.scoring.models.StrategyScore.confidence`.

    ``MIN`` (default) is the conservative "a chain is as strong as its
    weakest link" convention: overall confidence never exceeds the least
    confident contributing input. ``MEAN`` averages instead. Both are
    generic combination rules, not a trading judgment.
    """

    MIN = "MIN"
    MEAN = "MEAN"


@dataclass(frozen=True)
class ScoreWeights:
    """Per-provider weights. Every field defaults to ``None`` — a
    required-but-unset placeholder (see module docstring). A
    :class:`~btengine.scoring.aggregation.ScoreAggregator` must refuse to
    produce a ``total_score`` for any component whose weight is unset,
    rather than assuming equal weighting.
    """

    funding: float | None = None
    open_interest: float | None = None
    premium_discount: float | None = None
    liquidity: float | None = None

    def __post_init__(self) -> None:
        for name in _PROVIDER_NAMES:
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} weight must be >= 0, got {value}")

    def get(self, provider_name: str) -> float | None:
        return getattr(self, provider_name, None)


@dataclass(frozen=True)
class ScorePriorities:
    """Per-provider evaluation-order priority. Every field defaults to
    ``None`` — a placeholder for a future conflict-resolution rule the
    strategy owner has not supplied yet. This framework only offers
    :func:`order_providers_by_priority` as a deterministic ordering
    utility; it does not decide what a priority *does* beyond ordering
    (e.g. it does not let a higher-priority provider override a
    lower-priority one's value — that would be inventing a rule).
    """

    funding: int | None = None
    open_interest: int | None = None
    premium_discount: int | None = None
    liquidity: int | None = None

    def get(self, provider_name: str) -> int | None:
        return getattr(self, provider_name, None)


def order_providers_by_priority(priorities: ScorePriorities) -> list[str]:
    """Return the four provider names ordered by ascending priority.

    A provider with an unset (``None``) priority sorts after every
    explicitly-prioritized provider; ties (including "all unset") break
    alphabetically by provider name, so the result is always
    deterministic.
    """

    def sort_key(name: str) -> tuple[int, int, str]:
        priority = priorities.get(name)
        return (0, priority, name) if priority is not None else (1, 0, name)

    return sorted(_PROVIDER_NAMES, key=sort_key)


@dataclass(frozen=True)
class ScoringEngineConfig:
    """Tunable parameters for :class:`~btengine.scoring.engine.ScoringEngine`."""

    engine_version: str

    weights: ScoreWeights = field(default_factory=ScoreWeights)
    priorities: ScorePriorities = field(default_factory=ScorePriorities)

    # None = no provider is required; a missing one is simply reported as
    # such in StrategyScore.feature_status, not a validation ERROR.
    required_providers: tuple[str, ...] | None = None

    # The framework's own normalized score scale — a structural bound
    # (like confidence_level's established 0..1 convention throughout
    # this project), not a strategy threshold.
    score_min: float = 0.0
    score_max: float = 1.0

    confidence_aggregation: ConfidenceAggregationMethod = ConfidenceAggregationMethod.MIN

    def __post_init__(self) -> None:
        if not self.engine_version.strip():
            raise ValueError("engine_version must not be empty")
        if self.score_min >= self.score_max:
            raise ValueError(f"score_min ({self.score_min}) must be < score_max ({self.score_max})")
        if self.required_providers is not None:
            unknown = set(self.required_providers) - set(_PROVIDER_NAMES)
            if unknown:
                raise ValueError(
                    f"unknown provider name(s) in required_providers: {sorted(unknown)}"
                )


def weights_from_scoring_model_config(model_config: ScoringModelConfig) -> ScoreWeights:
    """Adapt a declarative, strategy-spec-level :class:`ScoringModelConfig`
    into this engine's :class:`ScoreWeights`.

    Only enabled factors whose ``source_rule_set`` matches one of the
    four known provider names (see
    ``_SOURCE_RULE_SET_TO_PROVIDER_NAME``) contribute a weight; anything
    else is ignored rather than guessed at. This is the integration seam
    between the Strategy Specification Framework's declarative
    ``config/strategy/scoring.yaml`` and this runtime engine — a strategy
    owner can fill in weights in one place (the spec) and drive this
    engine from it, or configure :class:`ScoreWeights` directly.
    """
    by_provider: dict[str, float | None] = {}
    for factor in model_config.factors:
        if not factor.enabled:
            continue
        provider_name = _SOURCE_RULE_SET_TO_PROVIDER_NAME.get(factor.source_rule_set)
        if provider_name is not None:
            by_provider[provider_name] = factor.weight
    return ScoreWeights(**by_provider)


def load_scoring_engine_config(path: Path | str) -> ScoringEngineConfig:
    """Load a :class:`ScoringEngineConfig` from a YAML file.

    Follows the same "missing value is a placeholder, not an error"
    convention as :func:`btengine.strategy.spec_loader.load_strategy_spec`
    — an absent optional key simply keeps that field's dataclass default
    (usually ``None``); schema validation (e.g. ``engine_version`` being
    required) is what surfaces genuinely missing information.
    """
    path = Path(path)
    try:
        raw = path.read_text()
    except OSError as exc:
        raise ScoringConfigError(f"Could not read scoring engine config {path}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ScoringConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ScoringConfigError(
            f"Expected a YAML mapping at the top level of {path}, got {type(data).__name__}"
        )

    engine_version = data.get("engine_version")
    if not engine_version:
        raise ScoringConfigError(f"{path}: engine_version is required")

    required_providers = data.get("required_providers")
    if required_providers is not None:
        required_providers = tuple(required_providers)

    try:
        return ScoringEngineConfig(
            engine_version=engine_version,
            weights=ScoreWeights(**(data.get("weights") or {})),
            priorities=ScorePriorities(**(data.get("priorities") or {})),
            required_providers=required_providers,
            score_min=data.get("score_min", 0.0),
            score_max=data.get("score_max", 1.0),
            confidence_aggregation=ConfidenceAggregationMethod(
                data.get("confidence_aggregation", "MIN")
            ),
        )
    except (ValueError, TypeError) as exc:
        raise ScoringConfigError(f"{path}: invalid scoring engine config: {exc}") from exc
