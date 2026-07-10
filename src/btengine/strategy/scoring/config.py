"""Scoring Model configuration — shape only, no scoring logic.

Explicitly out of scope per this framework's instructions: *how* factor
values are computed, *how* they combine into a single score, and *what*
the resulting number means are all left to a future, separate scoring
implementation. This module only fixes what a scoring configuration must
be able to express: multiple named factors, a weight per factor, one or
more configurable thresholds, an explicit version, and a placeholder for
a future AI-driven scoring mode — see the "SCORING MODEL" requirements in
this framework's originating request and ``docs/strategy_spec.md``
§Scoring.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScoringFactorConfig(BaseModel):
    """One named input to the score — a weighted reference to a rule
    category's output. Carries no computation itself."""

    model_config = ConfigDict(extra="forbid")

    name: str
    source_rule_set: str = ""  # TODO(owner): which rule category this factor reads (e.g. "funding_rate")
    weight: float | None = None  # TODO(owner): required
    enabled: bool = True


class ScoringModelConfig(BaseModel):
    """The full, versioned scoring configuration.

    ``version`` has no default: every scoring configuration must be
    explicitly versioned (see "Strategy Versioning" in
    ``docs/RESEARCH_PLATFORM_ARCHITECTURE.md`` for the companion strategy-
    level version registry this can be cross-referenced against).
    """

    model_config = ConfigDict(extra="forbid")

    version: str  # TODO(owner): required, e.g. "0.1.0"
    enabled: bool = False
    factors: list[ScoringFactorConfig] = Field(default_factory=list)
    entry_threshold: float | None = None  # TODO(owner): required
    exit_threshold: float | None = None  # TODO(owner): required
    ai_scoring_enabled: bool = False  # future AI scoring support placeholder
    ai_model_name: str | None = None  # TODO(owner): required if ai_scoring_enabled
    notes: str = ""

    @model_validator(mode="after")
    def _factor_names_must_be_unique(self) -> "ScoringModelConfig":
        names = [factor.name for factor in self.factors]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(f"duplicate scoring factor names: {sorted(duplicates)}")
        return self

    @model_validator(mode="after")
    def _ai_scoring_requires_a_model_name(self) -> "ScoringModelConfig":
        if self.ai_scoring_enabled and not self.ai_model_name:
            raise ValueError("ai_model_name is required when ai_scoring_enabled is True")
        return self
